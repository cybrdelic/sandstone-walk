"""Verify both self-contained delivery files in a real browser via localhost."""
from __future__ import annotations
import argparse,base64,functools,hashlib,http.server,io,json,os,threading,time,traceback
from pathlib import Path
from PIL import Image,ImageStat
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HOOK="""(()=>{const raf=requestAnimationFrame.bind(window);window.__next=null;window.requestAnimationFrame=cb=>{if(cb.name==='frame'){__next=cb;return 1}return raf(cb)};window.__step=()=>{__next(performance.now());CYBR_RECOVERY.renderer.getContext().finish();};})();"""
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=ROOT/'build/detail-standalone');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    report={'result':'FAIL','errors':[],'entrypoint':'Actual standalone HTML via localhost','deliveries':[],'physical_device_benchmark':False,
            'capture_method':'Actual canvas PNG immediately after draw in the same JavaScript task; no screenshot substitution'}
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start();start=time.monotonic()
    try:
      with sync_playwright() as p:
        for filename,size in [('Sandstone_Walk_Standalone.html',4096),('Sandstone_Walk_Compact.html',2048)]:
          path=ROOT/'dist'/filename;receipt=json.loads(path.with_suffix('.json').read_text())
          assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
          opts={'headless':os.getenv('SW_HEADLESS','1')!='0','args':['--no-sandbox','--use-gl=angle','--use-angle='+os.getenv('SW_ANGLE','swiftshader'),'--enable-unsafe-swiftshader','--disable-dev-shm-usage','--disable-gpu-watchdog','--ignore-gpu-blocklist']}
          if os.getenv('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
          browser=p.chromium.launch(**opts);page=browser.new_page(viewport={'width':960,'height':640},device_scale_factor=1)
          page.set_default_timeout(240000);page.add_init_script(HOOK);requests=[]
          page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:report['errors'].append(str(e)))
          page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
          prefix=f'http://127.0.0.1:{server.server_port}/'
          page.goto(prefix+'dist/'+filename,wait_until='load',timeout=240000)
          page.wait_for_function('window.CYBR_RECOVERY || !document.getElementById("error").hidden',polling=100)
          assert page.evaluate('!!window.CYBR_RECOVERY'),page.locator('#error').inner_text()
          page.evaluate('''()=>{window.__sourceDraws=[];const a=CYBR_RECOVERY,render=a.renderer.render.bind(a.renderer);a.renderer.render=(s,c)=>{render(s,c);if(s===a.scene&&!s.overrideMaterial)__sourceDraws.push(a.renderer.info.render.triangles)};a.quality.limit=2;a.quality.invalidate();}''')
          images=[]
          for i in range(2):
            if i:page.evaluate('CYBR_RECOVERY.setPose([.25,4.8,1.6],[1.2,16,2.6])')
            page.evaluate('__step()')
            # The app intentionally does not preserve the default framebuffer.
            # Draw and encode together; a separate task can observe a cleared canvas.
            raw=base64.b64decode(page.evaluate('''()=>{__step();return document.querySelector('canvas').toDataURL('image/png');}''').split(',',1)[1])
            file=a.out/f'{size}_{i}.png';file.write_bytes(raw)
            im=Image.open(io.BytesIO(raw)).convert('RGB');deviation=ImageStat.Stat(im.convert('L')).stddev[0]
            assert im.size==(960,640) and deviation>8,{'size':im.size,'luminance_stddev':deviation,'image':str(file)}
            images.append(hashlib.sha256(raw).hexdigest())
          state=page.evaluate('''()=>({maps:CYBR_RECOVERY.detail.resolution,uploaded:CYBR_RECOVERY.detail.textures.map(t=>t.userData.uploadedSize),
            triangles:CYBR_RECOVERY.geometry.reduce((n,g)=>n+g.index.count/3,0),vertices:CYBR_RECOVERY.geometry.reduce((n,g)=>n+g.attributes.position.count,0),
            observed:__sourceDraws,glError:CYBR_RECOVERY.renderer.getContext().getError(),dataNodes:!!document.getElementById('sw-scene-data')||!!document.getElementById('sw-detail-data'),
            controlMode:CYBR_RECOVERY.controls.mode})''')
          assert state['maps']==size and state['triangles']==5029800 and state['vertices']==2526592
          assert all(x==5029800 for x in state['observed']) and len(state['observed'])>=4
          assert state['glError']==0 and state['dataNodes'] is False and state['controlMode']=='walk'
          assert all(x==[size,size] for x in state['uploaded']) and images[0]!=images[1]
          external=[url for url in requests if not url.startswith(prefix)]
          assert not external,external
          asset_requests=[url for url in requests if url!=prefix+'dist/'+filename]
          assert not asset_requests,asset_requests
          assert not report['errors'],report['errors']
          report['deliveries'].append({'filename':filename,'sha256':receipt['sha256'],'bytes':path.stat().st_size,'state':state,'image_sha256':images,'external_requests':external,'asset_requests':asset_requests})
          browser.close();print('PASS: standalone',filename,size,flush=True)
      report['result']='PASS'
    except Exception as e:report['exception']=str(e);report['traceback']=traceback.format_exc()
    finally:
      server.shutdown();report['seconds']=time.monotonic()-start;(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if report['result']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
