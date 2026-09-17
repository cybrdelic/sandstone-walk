"""Execute the rebuilt scene in real Chromium; capture actual WebGL frames.
GPL-2.0-only. A software-GPU test is not a physical-phone benchmark.
"""
from pathlib import Path
import argparse,base64,functools,hashlib,http.server,io,json,math,os,threading,time,traceback
from PIL import Image,ImageStat
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HOOK=r'''(()=>{
const raf=requestAnimationFrame.bind(window);const s={paused:false,pending:null,arm:0,ready:0,png:null,error:null};window.__cap=s;
window.requestAnimationFrame=cb=>{if(cb.name!=='frame')return raf(cb);return setTimeout(()=>raf(t=>{if(s.paused){s.pending=cb;return;}cb(t);window.CYBR_RECOVERY?.renderer.getContext().finish();if(s.arm){try{s.png=document.querySelector('canvas').toDataURL('image/png')}catch(e){s.error=String(e)}s.ready=s.arm;s.arm=0;s.paused=true;}}),120)};
window.__resume=()=>{s.paused=false;if(s.pending){const cb=s.pending;s.pending=null;requestAnimationFrame(cb)}};
})();'''

def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--materials-baseline',action='store_true',help='Capture the old material before changing the application');ap.add_argument('--materials',action='store_true',help='Add surface material close-ups and mapping diagnostics');ap.add_argument('--standalone',action='store_true',help='Execute the offline document via set_content without URL navigation');ap.add_argument('--out',type=Path,default=ROOT/'evidence/browser');args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    expected=json.loads((ROOT/'verification.json').read_text())['scene']
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT));httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=httpd.serve_forever,daemon=True).start()
    report={'software_gpu_frame_sync':'Test-only gl.finish after actual frame plus 120ms pacing; scene, input and shaders unchanged. Not a frame-rate benchmark.','result':'FAIL','browser_runtime_verified':False,'errors':[],'checks':[],'captures':{},'source_mesh_sha256':expected['source_mesh_sha256']}
    start=time.monotonic()
    try:
      with sync_playwright() as p:
        backend=os.getenv('ANGLE_BACKEND','swiftshader')
        opts={'headless':True,'args':['--no-sandbox','--use-gl=angle','--use-angle='+backend,'--ignore-gpu-blocklist','--enable-unsafe-swiftshader','--disable-dev-shm-usage','--disable-gpu-sandbox']}
        if os.getenv('CHROMIUM_PATH'):opts['executable_path']=os.getenv('CHROMIUM_PATH')
        b=p.chromium.launch(**opts);context=b.new_context(viewport={'width':1440,'height':960},device_scale_factor=1,has_touch=True,is_mobile=True)
        page=context.new_page();page.set_default_timeout(120000);page.add_init_script(HOOK)
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
        if args.standalone:
            page.evaluate(HOOK)
            page.set_content((ROOT/'Sandstone_Walk_Solid.html').read_text(),wait_until='load',timeout=180000)
            report['entrypoint']='Actual offline HTML executed via Playwright set_content; no URL navigation or network fetch tested'
        else:
            page.goto(f'http://127.0.0.1:{httpd.server_port}/',wait_until='load',timeout=120000)
            report['entrypoint']='Split web application via localhost HTTP'
        page.wait_for_function('window.CYBR_RECOVERY && document.getElementById("loading").hidden',timeout=180000,polling=100)
        def check(name,ok):
            assert ok,name;report['checks'].append(name);print('PASS',name,flush=True)
        def snap():return page.evaluate('CYBR_RECOVERY.controls.snapshot()')
        def capture(name):
            ident=len(report['captures'])+1
            page.evaluate('(i)=>{__cap.arm=i;__resume()}',ident)
            page.wait_for_function('(i)=>__cap.ready===i',arg=ident,polling=100,timeout=120000)
            d=page.evaluate('({png:__cap.png,error:__cap.error,glError:CYBR_RECOVERY.renderer.getContext().getError(),triangles:CYBR_RECOVERY.renderer.info.render.triangles})')
            check(name+' GL error free',d['error'] is None and d['glError']==0)
            raw=base64.b64decode(d['png'].split(',',1)[1]);im=Image.open(io.BytesIO(raw));std=ImageStat.Stat(im.convert('L')).stddev[0]
            check(name+' nonblank frame',std>5)
            (args.out/(name+'.png')).write_bytes(raw)
            report['captures'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':list(im.size),'gl_error':d['glError'],'triangles_drawn':d['triangles'],'camera':snap(),'luminance_std':std}
            print('CAPTURED',name,flush=True)
            page.evaluate('__resume()')
        totals=page.evaluate('({triangles:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.index.count/3,0),vertices:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.attributes.position.count,0),programs:CYBR_RECOVERY.renderer.info.programs.length,hash:CYBR_RECOVERY.meta.source_mesh_sha256})')
        report['geometry']=totals
        report['active_shader_sha256']={name:hashlib.sha256((ROOT/'web'/name).read_bytes()).hexdigest() for name in ['surface.vert.glsl','surface.frag.glsl']}
        check('Every regenerated triangle and vertex loaded',totals['triangles']==expected['triangles'] and totals['vertices']==expected['vertex_count'])
        check('Correct fresh bake identity',totals['hash']==expected['source_mesh_sha256'])
        check('Surface and sky shader programs linked',totals['programs']==2)
        capture('hero')
        page.evaluate('CYBR_RECOVERY.setPose([.25,4.8,1.6],[1.2,16,2.6])');capture('forward')
        page.evaluate('CYBR_RECOVERY.setPose([.6,9,1.75],[-.3,-4,2.6])');capture('reverse')
        if args.materials or args.materials_baseline:
            meta=page.evaluate('CYBR_RECOVERY.meta')
            report['material_baseline']=args.materials_baseline
            if not args.materials_baseline:
                check('Correct world material schema',meta['material_schema']=='world-space-spectral-transfer/1')
                check('Fresh bake of the delivered material',meta['material_field_sha256']==hashlib.sha256((ROOT/'source/material_field.glsl').read_bytes()).hexdigest())
                check('Receiver color and bump not baked',not meta['receiver_albedo_baked'] and not meta['receiver_micro_normal_baked'])
                report['material_field_sha256']=meta['material_field_sha256']
            for name,eye,target in [
                ('left_close',[-.70,-2.8,1.9],[-2.65,-1.,2.10]),
                ('right_close',[.70,5.0,1.8],[3.15,6.8,2.15]),
                ('ground',[.1,-2,1.20],[.3,-.55,-.1]),
                ('talus',[-.75,-2.4,.95],[-2.,-1.0,.24])]:
                page.evaluate('p=>CYBR_RECOVERY.setPose(p[0],p[1])',[eye,target])
                for mode,label in ([(0,'beauty')] if args.materials_baseline else [(0,'beauty'),(5,'albedo'),(6,'world_checker')]):
                    page.evaluate('CYBR_RECOVERY.setMode('+str(mode)+')');capture(name+'_'+label)
            page.evaluate('CYBR_RECOVERY.setMode(0)')

        page.evaluate('CYBR_RECOVERY.setNavigationMode("orbit")');capture('orbit')
        check('Orbit is a different actual camera',dist(report['captures']['hero']['camera']['eye'],snap()['eye'])>10)
        check('No image projection',not page.evaluate('CYBR_RECOVERY.meta.image_projection'))
        page.evaluate('CYBR_RECOVERY.setReference()');check('Reference camera restored',dist(snap()['eye'],expected['camera'])<1e-8)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
        check('Mobile thumbstick is visible',page.locator('#joystick').is_visible())
        cdp=context.new_cdp_session(page)
        def touch(kind,points):
            cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'id':i,'x':x,'y':y,'radiusX':4,'radiusY':4,'force':1} for i,x,y in points]});page.wait_for_timeout(100)
            page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>resolve()))')
        bounds=page.locator('#joystick').bounding_box();x=bounds['x']+bounds['width']*.5;y=bounds['y']+bounds['height']*.5;before=snap()
        touch('touchStart',[(1,x,y)]);touch('touchMove',[(1,x,y-36)])
        page.wait_for_function('(v)=>CYBR_RECOVERY.camera.position.distanceTo(new THREE.Vector3(...v))>.01',arg=before['eye'],polling=100)
        q=snap()['quaternion'];touch('touchStart',[(1,x,y-36),(2,270,300)]);touch('touchMove',[(1,x,y-36),(2,320,277)])
        report['touch_snapshots']={'quaternion_before':q,'after':snap()}
        check('Walk and look operate simultaneously',snap()['stick'][1]<-.2 and dist(q,snap()['quaternion'])>.01)
        touch('touchEnd',[]);check('Touch release clears movement',snap()['stick']==[0,0] and snap()['pointers']==0)
        page.evaluate('CYBR_RECOVERY.setReference()');capture('mobile_walk')
        page.locator('#nav-orbit').tap();before=snap()
        touch('touchStart',[(1,100,320),(2,280,320)]);touch('touchMove',[(1,60,320),(2,320,320)])
        check('Orbit pinch zooms',snap()['radius']<before['radius']*.9)
        before=snap();touch('touchMove',[(1,80,350),(2,340,350)])
        check('Two-finger pan moves target',dist(before['target'],snap()['target'])>.1)
        touch('touchCancel',[]);check('Cancellation clears all gestures',snap()['pointers']==0)
        page.locator('#frame-canyon').tap();page.set_viewport_size({'width':1000,'height':650});page.locator('#frame-canyon').tap();capture('landscape_orbit')
        check('Controls shader runtime error free',not report['errors'])
        report.update(result='PASS',browser_runtime_verified=True,renderer=page.evaluate('CYBR_RECOVERY.renderer.getContext().getParameter(CYBR_RECOVERY.renderer.getContext().RENDERER)'),
                      browser_version=b.version,angle_backend=backend,physical_phone_benchmark=False)
        context.close();b.close()
    except Exception as e:
        report['exception']=str(e);report['traceback']=traceback.format_exc()
    finally:
        httpd.shutdown();report['seconds']=time.monotonic()-start
        (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
    if report['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
