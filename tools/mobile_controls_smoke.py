"""Real multi-touch / orbit regression test, using CDP touch input in Chromium.

Default: run the actual Three.js application and capture its WebGL output.
--controls-only: exercise the same DOM/controller/Three.js camera without WebGL;
this explicit local fallback does NOT count as scene-rendering verification.
"""
from __future__ import annotations
import argparse,base64,functools,http.server,json,math,os,re,signal,threading,time,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HOOK=r'''(() => {
 const raf=requestAnimationFrame.bind(window);
 const s={paused:false,pending:null,armed:false,ready:false,png:null};window.__capture=s;
 window.requestAnimationFrame=cb=>{if(cb.name!=='frame')return raf(cb);return raf(t=>{
   if(s.paused){s.pending=cb;return;}cb(t);
   if(s.armed){s.png=document.querySelector('canvas').toDataURL('image/png');s.armed=false;s.ready=true;s.paused=true;}
 });};
 window.__resume=()=>{s.paused=false;if(s.pending){const cb=s.pending;s.pending=null;requestAnimationFrame(cb);}};
})();'''

def distance(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--controls-only',action='store_true')
    ap.add_argument('--out',type=Path,default=ROOT/'build/mobile');args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    report={'schema':'sandstone-walk-navigation-test/1','result':'FAIL','checks':[], 'errors':[],
            'input':'Chromium CDP multi-touch, mouse and keyboard; emulated touch device, not physical phone',
            'controls_only':args.controls_only,'scene_rendering_verified':False,'captures':[]}
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    started=time.monotonic()
    def deadline(signum,frame):raise TimeoutError("Mobile regression exceeded ten minutes; no pass claimed")
    signal.signal(signal.SIGALRM,deadline);signal.alarm(600)
    try:
      with sync_playwright() as p:
        options=dict(headless=True,args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])
        if os.getenv('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
        browser=p.chromium.launch(**options)
        context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
        page=context.new_page();page.set_default_timeout(120000)
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
        if args.controls_only:
          text=(ROOT/'index.html').read_text();text=re.sub(r'<script\b[^>]*>.*?</script>','',text,flags=re.S)
          text=text.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(ROOT/'web/controls.css').read_text()+'</style>')
          page.set_content(text)
          page.add_script_tag(content=(ROOT/'web/vendor/three.bundle.js').read_text())
          page.add_script_tag(content=(ROOT/'web/controls.js').read_text())
          page.evaluate('''() => {
            const canvas=document.createElement('canvas');canvas.tabIndex=0;document.body.prepend(canvas);
            const camera=new THREE.PerspectiveCamera(60,390/844,.02,180);camera.up.set(0,0,1);
            const reference={camera:[-.42,-5.8,1.56],target:[.15,9.8,3.12]};
            const bounds=new THREE.Box3(new THREE.Vector3(-16,-10,-1),new THREE.Vector3(20,42,25));
            const controls=new SandstoneControls({canvas,camera,bounds,reference,onModeChange:mode=>{camera.fov=mode==='orbit'?55:75;camera.updateProjectionMatrix();}});
            window.CYBR_RECOVERY={camera,controls,meta:reference,setReference:()=>controls.setReference()};
            document.getElementById('loading').hidden=true;
            document.getElementById('stats').textContent='CONTROL TEST ONLY · NO SCENE RENDER';
            document.getElementById('hide').onclick=()=>{controls.clearInput();document.body.classList.toggle('settings-open');};
            let last=performance.now();function tick(t){controls.update((t-last)/1000);last=t;requestAnimationFrame(tick);}requestAnimationFrame(tick);
            addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();});
          }''')
        else:
          page.add_init_script(HOOK)
          page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='load',timeout=120000)
          page.wait_for_function('window.CYBR_RECOVERY?.controls && document.getElementById("loading").hidden',polling=100,timeout=180000)
          geometry=page.evaluate('({triangles:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.index.count/3,0),vertices:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.attributes.position.count,0)})')
          assert geometry=={'triangles':5029800,'vertices':2526592},geometry
          report['geometry']=geometry
        cdp=context.new_cdp_session(page)
        def snap():return page.evaluate('CYBR_RECOVERY.controls.snapshot()')
        def check(name,condition,detail=None):
          if not condition:raise AssertionError(f'{name}: {detail}')
          report['checks'].append(name);print('PASS:',name,flush=True)
        def box(selector):
          b=page.locator(selector).bounding_box();assert b,selector
          return b
        def center(selector):
          b=box(selector);return b['x']+b['width']/2,b['y']+b['height']/2
        def touch(kind,points):
          cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'id':i,'x':x,'y':y,'radiusX':5,'radiusY':5,'force':1} for i,x,y in points]})
          page.wait_for_timeout(80) # Allow Chromium to deliver coalesced pointer events.
          page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>resolve()))')
        def idle():
          s=snap();check('No stuck pointers or held movement',s['stick']==[0,0] and s['pointers']==0 and s['holds']==0 and s['keys']==0,s)
        def capture(name):
          if args.controls_only:
            page.screenshot(path=str(args.out/(name+'_controls_only.png')))
            return
          page.evaluate('()=>{__capture.ready=false;__capture.armed=true;__resume();}')
          page.wait_for_function('__capture.ready',polling=100,timeout=180000)
          data=page.evaluate('({png:__capture.png,error:CYBR_RECOVERY.renderer.getContext().getError(),triangles:CYBR_RECOVERY.renderer.info.render.triangles})')
          check(name+' real GL draw',data['error']==0 and data['triangles']>0,data)
          (args.out/(name+'_canvas.png')).write_bytes(base64.b64decode(data['png'].split(',',1)[1]))
          screen=cdp.send('Page.captureScreenshot',{'format':'png','fromSurface':True})
          (args.out/(name+'.png')).write_bytes(base64.b64decode(screen['data']))
          report['captures'].append({'name':name,'gl_error':data['error'],'drawn_triangles':data['triangles'],'viewport':page.viewport_size})
          page.evaluate('__resume()')
        check('Touch UI visible',page.locator('#joystick').is_visible())
        check('Walking mode is initial mode',snap()['mode']=='walk')
        check('Touch targets at least 44px',all(box(s)['height']>=44 and box(s)['width']>=44 for s in ['#nav-walk','#nav-orbit','#home','#boost','[data-hold="KeyE"]']))
        j=box('#joystick');n=box('#navigation');check('Joystick clear of mode dock',j['y']+j['height']<n['y'])
        await_camera=page.evaluate('CYBR_RECOVERY.camera.position.toArray()')
        x,y=center('#joystick');touch('touchStart',[(1,x,y)]);touch('touchMove',[(1,x,y-38)])
        page.wait_for_function('(eye)=>CYBR_RECOVERY.camera.position.distanceTo(new THREE.Vector3(...eye))>.01',arg=await_camera,polling=50)
        check('Analog thumbstick walks forward',snap()['eye'][1]>await_camera[1])
        before=snap();touch('touchStart',[(1,x,y-38),(2,260,300)]);touch('touchMove',[(1,x,y-38),(2,310,275)])
        after=snap();check('Simultaneous thumbstick and drag-to-look',after['stick'][1]<-.5 and distance(before['quaternion'],after['quaternion'])>.02,after)
        touch('touchEnd',[]);idle();before=snap();page.wait_for_timeout(300)
        check('Release stops movement without drift',distance(before['eye'],snap()['eye'])<1e-7)
        x,y=center('[data-hold="KeyE"]');before=snap();touch('touchStart',[(1,x,y)])
        page.wait_for_function('(z)=>CYBR_RECOVERY.camera.position.z>z+.01',arg=before['eye'][2],polling=50)
        touch('touchCancel',[]);idle();check('Hold-to-rise and cancellation',snap()['eye'][2]>before['eye'][2])
        # Cancel an active stick, then force a focus loss while it is held.
        x,y=center('#joystick');touch('touchStart',[(1,x,y-30)]);touch('touchCancel',[]);idle()
        touch('touchStart',[(1,x,y-30)]);page.evaluate('window.dispatchEvent(new Event("blur"))');touch('touchEnd',[]);idle()
        check('Blur stops automatic tour',not snap()['tour'])
        page.locator('#home').tap();before=snap();capture('mobile_walk')
        page.locator('#nav-orbit').tap();s=snap();check('Orbit switches to overview',s['mode']=='orbit' and distance(s['eye'],before['eye'])>10)
        check('Walk controls hidden in orbit',not page.locator('#joystick').is_visible())
        fit=page.evaluate('''() => {const c=CYBR_RECOVERY.controls, b=c.bounds;
          c.camera.updateMatrixWorld(true);let maximum=0;
          for(const x of [b.min.x,b.max.x])for(const y of [b.min.y,b.max.y])for(const z of [b.min.z,b.max.z]){
            const p=new THREE.Vector3(x,y,z).project(c.camera);maximum=Math.max(maximum,Math.abs(p.x),Math.abs(p.y));
          }return maximum;}''')
        check('Overview fits actual bounds',fit<=1.001,fit)
        before=snap();touch('touchStart',[(1,150,310)]);touch('touchMove',[(1,220,350)]);touch('touchEnd',[])
        after=snap();check('One-finger orbit preserves radius',abs(after['radius']-before['radius'])<1e-7 and distance(before['eye'],after['eye'])>1)
        before=snap();touch('touchStart',[(1,110,320),(2,270,320)]);touch('touchMove',[(1,75,320),(2,305,320)])
        after=snap();check('Pinch out zooms in',after['radius']<before['radius']*.8,after)
        before=snap();touch('touchMove',[(1,95,355),(2,325,355)]);after=snap()
        check('Two-finger pan moves target',distance(before['target'],after['target'])>1,after)
        # Chromium supports keeping one point alive: verifies a two-to-one transition.
        touch('touchEnd',[(1,95,355)]);before=snap();touch('touchMove',[(1,96,356)]);after=snap()
        check('Two-to-one gesture transition is bounded',distance(before['eye'],after['eye'])<after['radius']*.10,after)
        touch('touchEnd',[]);idle()
        orbit=snap();page.locator('#nav-walk').tap();check('Walk pose restored',distance(snap()['eye'],[-.42,-5.8,1.56])<1e-8)
        page.locator('#nav-orbit').tap();check('Orbit pose restored',distance(snap()['eye'],orbit['eye'])<1e-7)
        page.locator('#frame-canyon').tap();capture('mobile_orbit')
        # Mouse and trackpad path shares the same explicit orbit state.
        page.mouse.move(190,300);before=snap();page.mouse.wheel(0,-180);page.wait_for_timeout(100);check('Mouse wheel zoom',snap()['radius']<before['radius'])
        before=snap();page.mouse.down(button='right');page.mouse.move(225,330);page.mouse.up(button='right')
        check('Right-drag pans',distance(before['target'],snap()['target'])>0.1)
        page.evaluate('CYBR_RECOVERY.controls.zoom(.0000001)');page.evaluate('CYBR_RECOVERY.controls.zoom(.0000001)')
        check('Zoom remains bounded and finite',all(math.isfinite(x) for x in snap()['eye']) and snap()['radius']>=snap()['near'])
        page.locator('#frame-canyon').tap();page.set_viewport_size({'width':844,'height':390});idle()
        page.locator('#frame-canyon').tap();capture('landscape_orbit')
        check('Landscape dock on screen',box('#navigation')['y']+box('#navigation')['height']<=390)
        page.locator('#home').tap();check('Reference exits orbit',snap()['mode']=='walk' and distance(snap()['eye'],[-.42,-5.8,1.56])<1e-8)
        page.locator('canvas').focus();before=snap();page.keyboard.down('w')
        page.wait_for_function('(eye)=>CYBR_RECOVERY.camera.position.distanceTo(new THREE.Vector3(...eye))>.005',arg=before['eye'],polling=50)
        page.keyboard.up('w');idle();page.keyboard.press('o');check('Keyboard orbit shortcut',snap()['mode']=='orbit')
        page.keyboard.press('r');check('Keyboard reference shortcut',snap()['mode']=='walk')
        page.locator('#hide').tap();check('Mobile settings drawer opens',page.locator('.panel').is_visible())
        page.locator('#hide').tap();check('Mobile settings drawer closes',not page.locator('.panel').is_visible());idle()
        check('No browser or shader errors',not report['errors'],report['errors'])
        report['scene_rendering_verified']=not args.controls_only;report['result']='PASS'
        context.close();browser.close()
    except Exception as e:
      report['exception']=str(e);report['traceback']=traceback.format_exc()
    finally:
      signal.alarm(0);server.shutdown();report['seconds']=time.monotonic()-started
      (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if report['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
