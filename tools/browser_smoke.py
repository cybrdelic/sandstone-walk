"""Exercise Chromium/Three.js and capture its canvas after completed draw calls.

The test-only rAF wrapper pauses between captures so software GPU runners do not
starve compositor screenshots. It does not alter scene data, lighting or shaders.
"""
from __future__ import annotations
import argparse
import base64
import functools
import hashlib
import http.server
import io
import json
import os
import threading
import time
import traceback
from pathlib import Path

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_HOOK = r"""
(() => {
  const requestFrame = window.requestAnimationFrame.bind(window);
  const state = {paused:false, pending:null, armed:0, ready:0, png:null, error:null};
  window.__swCapture = state;
  window.requestAnimationFrame = callback => requestFrame(t => {
    if (state.paused) {state.pending=callback; return;}
    callback(t);
    if (state.armed) {
      try {state.png=document.querySelector('canvas').toDataURL('image/png');}
      catch(e) {state.error=String(e);}
      state.ready=state.armed;
      state.armed=0;
      state.paused=true;
    }
  });
  window.__swResume = () => {
    state.paused=false;
    if(state.pending) {
      const callback=state.pending;
      state.pending=null;
      window.requestAnimationFrame(callback);
    }
  };
  window.__swArmCapture = id => {
    state.png=null;
    state.error=null;
    state.armed=id;
    window.__swResume();
  };
})();
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'build/browser')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    report = {'browser_runtime_verified':False, 'errors':[],
              'source':'actual Chromium / Three.js WebGL2 execution',
              'capture_method':'canvas PNG immediately after actual draw; no native-render substitution',
              'started':time.time(), 'captures':{}}
    try:
        with sync_playwright() as p:
            options = {'headless':os.getenv('SW_HEADLESS','1')!='0', 'args':['--no-sandbox', '--use-gl=angle',
                '--use-angle='+os.getenv('SW_ANGLE','swiftshader'), '--enable-unsafe-swiftshader', '--disable-dev-shm-usage','--ignore-gpu-blocklist','--disable-gpu-watchdog']}
            if os.getenv('CHROMIUM_PATH'):
                options['executable_path'] = os.environ['CHROMIUM_PATH']
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width':1200, 'height':800}, device_scale_factor=1)
            page.set_default_timeout(180000)
            page.add_init_script(CAPTURE_HOOK)
            page.on('pageerror', lambda e:report['errors'].append(str(e)))
            page.on('console', lambda m:report['errors'].append(m.text) if m.type=='error' else None)
            page.goto(f'http://127.0.0.1:{httpd.server_port}/', wait_until='load', timeout=120000)
            page.wait_for_function('window.CYBR_RECOVERY && document.getElementById("loading").hidden',
                                   polling=100, timeout=180000)
            report['geometry'] = page.evaluate('''() => ({
              triangles:CYBR_RECOVERY.geometry.reduce((s,g)=>s+g.index.count/3,0),
              vertices:CYBR_RECOVERY.geometry.reduce((s,g)=>s+g.attributes.position.count,0),
              programs:CYBR_RECOVERY.renderer.info.programs.length})''')
            assert report['geometry']['triangles'] == 5029800
            assert report['geometry']['vertices'] == 2526592
            # Surface and sky compile at startup; HDR passes compile on first draw.
            assert report['geometry']['programs'] >= 2

            def capture(name, capture_id):
                page.evaluate('(id)=>window.__swArmCapture(id)', capture_id)
                page.wait_for_function('(id)=>window.__swCapture.ready===id', arg=capture_id,
                                       polling=100, timeout=180000)
                result = page.evaluate('''() => ({png:__swCapture.png,error:__swCapture.error,
                  glError:CYBR_RECOVERY.renderer.getContext().getError(),
                  drawnTriangles:CYBR_RECOVERY.quality.lastSceneTriangles})''')
                assert not result['error'], result['error']
                assert result['glError'] == 0, result
                assert result['drawnTriangles'] == 5029800, result['drawnTriangles']
                assert result['png'].startswith('data:image/png;base64,')
                raw = base64.b64decode(result['png'].split(',',1)[1], validate=True)
                image = Image.open(io.BytesIO(raw)).convert('RGB')
                assert image.size == (1200,800), image.size
                standard_deviation = ImageStat.Stat(image.convert('L')).stddev[0]
                assert standard_deviation > 8, 'Canvas is unexpectedly uniform or blank'
                (args.out/(name+'.png')).write_bytes(raw)
                report['captures'][name] = {'sha256':hashlib.sha256(raw).hexdigest(),
                    'bytes':len(raw), 'size':list(image.size), 'luminance_stddev':standard_deviation,
                    'gl_error':result['glError'], 'drawn_triangles':result['drawnTriangles']}

            capture('hero', 1)
            page.evaluate('CYBR_RECOVERY.setPose([.25,4.8,1.60],[1.2,16,2.6])')
            capture('forward', 2)
            assert report['captures']['hero']['sha256'] != report['captures']['forward']['sha256']
            page.evaluate('CYBR_RECOVERY.setReference();window.__swResume()')
            before = page.evaluate('CYBR_RECOVERY.camera.position.toArray()')
            page.locator('canvas').focus()
            page.keyboard.down('w')
            page.wait_for_function('(v)=>CYBR_RECOVERY.camera.position.distanceTo(new THREE.Vector3(...v))>0.001',
                                   arg=before, polling=100, timeout=60000)
            page.keyboard.up('w')
            after = page.evaluate('CYBR_RECOVERY.camera.position.toArray()')
            assert before != after
            page.evaluate('CYBR_RECOVERY.setMode(2)')
            capture('indirect', 3)
            assert page.evaluate('CYBR_RECOVERY.material.uniforms.uMode.value') == 2
            page.evaluate('CYBR_RECOVERY.setMode(0);CYBR_RECOVERY.setReference()')
            reset = page.evaluate('CYBR_RECOVERY.camera.position.toArray()')
            reference = page.evaluate('CYBR_RECOVERY.meta.camera')
            assert reset == reference
            report['controls'] = {'keyboard_movement':True, 'lighting_mode':True,
                                  'reference_reset':True, 'pose_change':True}
            report['keyboard_positions'] = {'before':before, 'after':after}
            assert not report['errors'], report['errors']
            report['browser_runtime_verified'] = True
            report['result'] = 'PASS'
            browser.close()
    except Exception as e:
        report['result'] = 'FAIL'
        report['exception'] = str(e)
        report['traceback'] = traceback.format_exc()
    finally:
        httpd.shutdown()
        report['wall_seconds'] = time.time()-report['started']
        (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['browser_runtime_verified']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
