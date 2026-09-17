"""Exercise real Chromium startup, GPU rendering and controls; preserve failures honestly."""
from __future__ import annotations
import argparse,functools,http.server,json,os,threading,time,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'build/browser');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT))
    httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);threading.Thread(target=httpd.serve_forever,daemon=True).start()
    report={'browser_runtime_verified':False,'errors':[],'source':'actual Chromium / Three.js execution','started':time.time()}
    try:
        with sync_playwright() as p:
            options={'headless':True,'args':['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']}
            if os.getenv('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**options);page=browser.new_page(viewport={'width':1200,'height':800},device_scale_factor=1)
            page.on('pageerror',lambda e:report['errors'].append(str(e)))
            page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
            page.goto(f'http://127.0.0.1:{httpd.server_port}/',wait_until='load',timeout=90000)
            page.wait_for_function('window.CYBR_RECOVERY && document.getElementById("loading").hidden',timeout=120000)
            page.wait_for_timeout(1500)
            report['geometry']=page.evaluate('''() => ({triangles:CYBR_RECOVERY.geometry.reduce((s,g)=>s+g.index.count/3,0),vertices:CYBR_RECOVERY.geometry.reduce((s,g)=>s+g.attributes.position.count,0),programs:CYBR_RECOVERY.renderer.info.programs.length,drawnTriangles:CYBR_RECOVERY.renderer.info.render.triangles})''')
            assert report['geometry']['triangles']==8108728
            assert report['geometry']['vertices']==4072674
            page.locator('#hud').evaluate('(x)=>x.style.display="none"')
            page.screenshot(path=str(a.out/'hero.png'))
            page.evaluate('CYBR_RECOVERY.setPose([.25,4.8,1.60],[1.2,16,2.6])');page.wait_for_timeout(1500);page.screenshot(path=str(a.out/'forward.png'))
            page.evaluate('CYBR_RECOVERY.setReference()');page.wait_for_timeout(300)
            before=page.evaluate('CYBR_RECOVERY.camera.position.toArray()');page.locator('canvas').focus();page.keyboard.down('w');page.wait_for_timeout(1200);page.keyboard.up('w')
            after=page.evaluate('CYBR_RECOVERY.camera.position.toArray()');assert before!=after
            page.evaluate('CYBR_RECOVERY.setMode(2)');page.wait_for_timeout(500)
            assert page.evaluate('CYBR_RECOVERY.material.uniforms.uMode.value')==2
            page.evaluate('CYBR_RECOVERY.setMode(0);CYBR_RECOVERY.setReference()');page.wait_for_timeout(500)
            report['controls']={'keyboard_movement':True,'lighting_mode':True,'reference_reset':True,'pose_change':True}
            assert not report['errors'],report['errors']
            report['browser_runtime_verified']=True;report['result']='PASS';browser.close()
    except Exception as e:
        report['result']='FAIL';report['exception']=str(e);report['traceback']=traceback.format_exc()
    finally:
        httpd.shutdown();(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['browser_runtime_verified']:raise SystemExit(1)
if __name__=='__main__':main()
