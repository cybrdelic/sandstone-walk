"""Exercise photographic materials, native pixels, stationary AA and 4K export.

Default entrypoint is the actual split application over localhost HTTP.
--in-memory is an explicit local transport alternative, not an HTTP startup test.
Frame stepping records genuine Three.js draws; it does not replace their pixels.
"""
from __future__ import annotations
import argparse,base64,functools,hashlib,http.server,io,json,math,os,re,threading,time,traceback
from pathlib import Path
import numpy as np
from PIL import Image,ImageStat
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
POSES={
 'hero':([-.42,-5.8,1.56],[.15,9.8,3.12]),
 'right_close':([.70,5.,1.8],[3.15,6.8,2.15]),
 'left_close':([-.70,-2.8,1.9],[-2.65,-1.,2.10]),
 'ground':([.1,-2,1.2],[.3,-.55,-.1]),
 'talus':([-.75,-2.4,.95],[-2,-1,.24]),
 'forward':([.25,4.8,1.6],[1.2,16,2.6])}
HOOK=r'''(() => {
 const raf=requestAnimationFrame.bind(window);window.__next=null;
 window.requestAnimationFrame=cb=>{if(cb.name==='frame'){window.__next=cb;return 1;}return raf(cb)};
 window.__step=()=>{if(!__next)throw new Error('No live app frame');__next(performance.now());CYBR_RECOVERY.renderer.getContext().finish();};
 window.__snap=()=>{__step();return document.querySelector('canvas').toDataURL('image/png');};
})();'''

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def b64(p):return base64.b64encode(p.read_bytes()).decode()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--in-memory',action='store_true');ap.add_argument('--standalone',type=Path)
 ap.add_argument('--baseline',action='store_true');ap.add_argument('--skip-4k',action='store_true')
 ap.add_argument('--size',type=int,default=1200);ap.add_argument('--textures',type=int,choices=[2048,4096],default=4096)
 ap.add_argument('--out',type=Path,default=ROOT/'build/detail-browser');ap.add_argument('--film',action='store_true')
 args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
 report={'result':'FAIL','errors':[],'captures':{},'checks':[],
  'entrypoint':'Explicit in-memory file transport' if args.in_memory else 'localhost HTTP',
  'browser_rendering':True,'physical_device_benchmark':False,'image_generation':False,
  'source_mesh_sha256':'7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79'}
 handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT))
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
 threading.Thread(target=server.serve_forever,daemon=True).start();start=time.monotonic()
 try:
  with sync_playwright() as pw:
   opts={'headless':os.getenv('SW_HEADLESS','1')!='0','args':['--no-sandbox','--use-gl=angle','--use-angle='+os.getenv('SW_ANGLE','swiftshader'),
     '--enable-unsafe-swiftshader','--disable-dev-shm-usage','--ignore-gpu-blocklist','--disable-gpu-watchdog']}
   if os.getenv('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
   browser=pw.chromium.launch(**opts);context=browser.new_context(viewport={'width':args.size,'height':round(args.size*2/3)},device_scale_factor=1)
   page=context.new_page();page.set_default_timeout(600000)
   page.on('pageerror',lambda e:report['errors'].append(str(e)))
   page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
   if args.in_memory and not args.standalone:
    html=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',(ROOT/'index.html').read_text())
    html=html.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(ROOT/'web/controls.css').read_text()+'</style>')
    page.set_content(html);page.evaluate(HOOK)
    paths=['web/vendor/three.bundle.js','web/controls.js']+([] if args.baseline else ['web/detail/runtime.js','web/detail/quality.js'])
    for path in paths:page.add_script_tag(content=(ROOT/path).read_text())
    data=json.loads((ROOT/'web/scene.json').read_text());page.evaluate('x=>window.CYBR_BAKE=x',data)
    for i,m in enumerate(data['meshes']):
     for k,e in m.items():
      if isinstance(e,dict) and e.get('url','').startswith('web/assets/'):
       assert sha(ROOT/e['url'])==e['sha256']
       page.evaluate('([i,k,v])=>{CYBR_BAKE.meshes[i][k]=v}',[i,k,b64(ROOT/e['url'])])
    page.evaluate('s=>CYBR_BAKE.sky.data=s',b64(ROOT/data['sky']['data']['url']))
    for name,file in [('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')]:
     page.evaluate('([k,v])=>window[k]=v',[name,(ROOT/'web'/file).read_text()])
    if not args.baseline:
     manifest=json.loads((ROOT/'web/detail/manifest.json').read_text())
     page.evaluate('x=>window.SW_DETAIL_ASSETS=x',{'manifest':manifest,'resolution':args.textures,'shader':(ROOT/'web/detail/material.glsl').read_text(),'images':{}})
     for asset in manifest['textures'].values():
      for e in asset['levels'][str(args.textures)].values():page.evaluate('([k,v])=>SW_DETAIL_ASSETS.images[k]=v',[e['url'],b64(ROOT/e['url'])])
    app=ROOT/'tests/fixtures/v0_4_app.js' if args.baseline else ROOT/'web/app.js'
    page.add_script_tag(content=app.read_text())
   else:
    page.add_init_script(HOOK)
    if args.standalone and args.in_memory:
     # The hook is installed in the current document before writing the HTML.
     page.evaluate(HOOK);page.set_content(args.standalone.read_text(),wait_until='load',timeout=600000)
     report['entrypoint']='Complete offline HTML via set_content; not URL startup'
    else:
     route='/' if args.standalone is None else '/'+args.standalone.resolve().relative_to(ROOT).as_posix()
     page.goto(f'http://127.0.0.1:{server.server_port}'+route,wait_until='load',timeout=600000)
   page.wait_for_function('window.CYBR_RECOVERY || !document.getElementById("error").hidden',polling=100)
   if not page.evaluate('!!window.CYBR_RECOVERY'):raise RuntimeError(page.locator('#error').inner_text())
   def check(name,ok):
    if not ok:raise AssertionError(name)
    report['checks'].append(name);print('PASS',name,flush=True)
   # Observe actual source-scene draws independently of the app's public counter.
   page.evaluate('''() => {window.__observed=[];const app=CYBR_RECOVERY,draw=app.renderer.render.bind(app.renderer);
    app.renderer.render=(s,c)=>{draw(s,c);if(s===app.scene && !s.overrideMaterial)__observed.push(app.renderer.info.render.triangles);};}''')
   totals=page.evaluate('({triangles:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.index.count/3,0),vertices:CYBR_RECOVERY.geometry.reduce((a,g)=>a+g.attributes.position.count,0)})')
   check('All original triangles and vertices retained',totals=={'triangles':5029800,'vertices':2526592});report['geometry']=totals
   report['renderer']=page.evaluate('''()=>{const g=CYBR_RECOVERY.renderer.getContext(),e=g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)}''')
   def capture(name,samples=8):
    if args.baseline:samples=1
    if not args.baseline:page.evaluate('(n)=>CYBR_RECOVERY.quality.limit=n',samples)
    for _ in range(samples-1):page.evaluate('__step()')
    raw=base64.b64decode(page.evaluate('__snap()').split(',',1)[1])
    im=Image.open(io.BytesIO(raw)).convert('RGB');check(name+' nonblank',ImageStat.Stat(im.convert('L')).stddev[0]>5)
    state=page.evaluate('({glError:CYBR_RECOVERY.renderer.getContext().getError(),pose:CYBR_RECOVERY.controls.snapshot(),quality:CYBR_RECOVERY.quality?.report(),actualDraw:__observed.at(-1)})')
    check(name+' graphics error-free',state['glError']==0 and not report['errors'])
    if name!='sun_disk':check(name+' actual full-scene draw',state['actualDraw']==5029800)
    (args.out/(name+'.png')).write_bytes(raw)
    report['captures'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':list(im.size),**state}
    print('CAPTURE',name,im.size,flush=True);return im
   for name,pose in POSES.items():
    page.evaluate('p=>CYBR_RECOVERY.setPose(...p)',pose);capture(name)
   if not args.baseline:
    report['detail']=page.evaluate('CYBR_RECOVERY.detail.report()')
    check('Requested photographic map dimensions uploaded',report['detail']['resolution']==args.textures)
    check('Mipmapped maps and anisotropic filtering',page.evaluate('CYBR_RECOVERY.detail.textures.every(t=>t.generateMipmaps && t.minFilter===THREE.LinearMipmapLinearFilter && t.anisotropy>=1 && t.userData.uploadedSize[0]===CYBR_RECOVERY.detail.resolution)'))
    check('Four material maps registered to physical metre scales',page.evaluate('CYBR_RECOVERY.detail.textures.length===4 && CYBR_RECOVERY.detail.uniforms.uRockScale.value===2.7 && CYBR_RECOVERY.detail.uniforms.uSandScale.value===2.1'))
    page.evaluate('CYBR_RECOVERY.setReference();CYBR_RECOVERY.quality.limit=8;CYBR_RECOVERY.quality.invalidate()');page.evaluate('__step()')
    q=page.evaluate('CYBR_RECOVERY.quality.report()');check('Changed camera starts at one fresh sample',q['samples']==1)
    first=page.evaluate('__snap()');capture('hero_settled')
    q=page.evaluate('CYBR_RECOVERY.quality.report()');draws=q['sceneDraws'];check('Static camera converges to 8 HDR samples',q['samples']==8)
    page.evaluate('__step()');check('Converged camera reuses its own stable image',page.evaluate('CYBR_RECOVERY.quality.draws')==draws)
    page.evaluate('CYBR_RECOVERY.camera.position.x+=.04');page.evaluate('__step()');check('Camera change clears history without reprojection',page.evaluate('CYBR_RECOVERY.quality.samples')==1)
    page.evaluate('CYBR_RECOVERY.detail.setEnabled(false)');page.evaluate('__step()');check('Material changes clear history',page.evaluate('CYBR_RECOVERY.quality.samples')==1)
    page.evaluate('CYBR_RECOVERY.detail.setEnabled(true);CYBR_RECOVERY.setReference()')
    page.evaluate('CYBR_RECOVERY.setNavigationMode("orbit")');capture('orbit')
    page.evaluate('CYBR_RECOVERY.setReference()')
    for mode in [3,4,5,6,7,8]:
     page.evaluate('(m)=>CYBR_RECOVERY.setMode(m)',mode);capture('diagnostic_'+str(mode),samples=1)
    page.evaluate('CYBR_RECOVERY.setMode(0)')
    # Small bright solar disc is within the half-float storage range only because
    # a fixed linear exposure precedes storage and is inverted in presentation.
    page.evaluate('''()=>{const e=new THREE.Vector3(0,-38,28),t=e.clone().addScaledVector(CYBR_RECOVERY.material.uniforms.uSun.value,50);CYBR_RECOVERY.setPose(e.toArray(),t.toArray());}''')
    sun=capture('sun_disk');a=np.asarray(sun);cy,cx=a.shape[0]//2,a.shape[1]//2
    check('HDR solar disc remains bright, not NaN/black',float(a[cy-1:cy+2,cx-1:cx+2].mean())>235)
    page.evaluate('CYBR_RECOVERY.setReference()')
    # Independently emulate a 3x screen; the rasterizer must actually allocate 9x pixels.
    cdp=context.new_cdp_session(page)
    cdp.send('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':3,'mobile':True})
    page.wait_for_function('innerWidth===390 && innerHeight===844',polling=100)
    page.evaluate('CYBR_RECOVERY.quality.setResolution("native")')
    phone=capture('native_dpr3')
    check('DPR3 is 1170 by 2532 actual pixels',phone.size==(1170,2532))
    check('Native rendering is nine times the old CSS-pixel count',phone.width*phone.height==9*390*844)
    cdp.send('Emulation.setDeviceMetricsOverride',{'width':args.size,'height':round(args.size*2/3),'deviceScaleFactor':1,'mobile':False})
    page.wait_for_function('(w)=>innerWidth===w',arg=args.size,polling=100)
    page.evaluate('CYBR_RECOVERY.quality.setResolution("native");CYBR_RECOVERY.setReference()')
    if not args.skip_4k:
     result=page.evaluate('''async()=>{const result=await CYBR_RECOVERY.quality.capture4K({download:false,samples:8});const png=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(result.blob)});return {png,report:result.report,restored:CYBR_RECOVERY.quality.report(),error:CYBR_RECOVERY.renderer.getContext().getError(),inert:document.body.inert};}''')
     raw=base64.b64decode(result.pop('png').split(',',1)[1]);im=Image.open(io.BytesIO(raw))
     check('Fresh 3840x2560 export with eight actual samples',im.size==(3840,2560) and result['report']['samples']==8 and not result['report']['upscaled'])
     check('4K capture restores interactive dimensions and input',result['restored']['drawingBuffer']==[args.size,round(args.size*2/3)] and result['error']==0 and not result['inert'])
     (args.out/'hero_4k.png').write_bytes(raw);report['export4k']={'sha256':hashlib.sha256(raw).hexdigest(),**result}
    if args.film:
     film=args.out/'film';film.mkdir(exist_ok=True);frames=[]
     cdp.send('Emulation.setDeviceMetricsOverride',{'width':720,'height':480,'deviceScaleFactor':1,'mobile':False})
     page.wait_for_function('innerWidth===720',polling=100);page.evaluate('CYBR_RECOVERY.quality.setResolution("native");CYBR_RECOVERY.quality.limit=2')
     for i in range(48):
      angle=i/48*2*math.pi;eye=[-.42+.18*math.sin(angle),-5.3+.42*math.cos(angle),1.62+.035*math.sin(2*angle)]
      page.evaluate('p=>CYBR_RECOVERY.setPose(p,[.15,10,3.12])',eye);page.evaluate('__step()');raw=base64.b64decode(page.evaluate('__snap()').split(',',1)[1])
      (film/f'{i:04d}.png').write_bytes(raw);frames.append({'frame':i,'eye':eye,'sha256':hashlib.sha256(raw).hexdigest(),'actual_source_draw':page.evaluate('__observed.at(-1)')})
     check('Film consists of 48 distinct geometry-rendered frames',len({f['sha256'] for f in frames})==48 and all(f['actual_source_draw']==5029800 for f in frames))
     report['film']={'fps':12,'size':[720,480],'frames':frames,'interpolation':False,'per_frame_aa_samples':2}
   report['actual_fragment_sha256']=hashlib.sha256(page.evaluate('CYBR_RECOVERY.material.fragmentShader').encode()).hexdigest()
   report['draw_calls_observed']=page.evaluate('__observed.length')
   check('No browser or shader errors',not report['errors']);report['result']='PASS'
   browser.close()
 except Exception as e:
  report['exception']=str(e);report['traceback']=traceback.format_exc();print(report['traceback'],flush=True)
 finally:
  server.shutdown();report['seconds']=time.monotonic()-start
  (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  print('RESULT',report['result'],round(report['seconds'],2),flush=True)
 if report['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
