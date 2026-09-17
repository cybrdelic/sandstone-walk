"""One-time, fail-closed migration from the published 0.1.1 viewer.

Preserves source/, every binary asset and every shader. The ordinary edited web
files are committed after the migration and tests; users need not run this tool.
"""
from __future__ import annotations
import hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def replace(text, old, new):
    if text.count(old)!=1: raise ValueError('Expected exactly one integration anchor: '+old[:100])
    return text.replace(old,new,1)

def main():
    app_path=ROOT/'web/app.js'; app=app_path.read_text()
    if 'new SandstoneControls(' in app:
        print('Navigation migration already applied.'); return
    expected={'web/app.js':'42f49ae25bb75f8657860f051e6881a87839d9f3',
              'index.html':'58c6729598c15c5e4854caa7e66b852f482cd26d',
              'tools/make_standalone.py':'7af128921f64b9200735edb8896a6c3b716a0456'}
    for name,sha in expected.items():
        raw=(ROOT/name).read_bytes(); actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual!=sha: raise ValueError('Base changed; reconcile rather than overwrite '+name)
    start=app.index('  const keys=new Set();')
    end=app.index('  camera.updateMatrixWorld(true);uniforms.uVP',start)
    app=app[:start]+'''  let renderScale=1,controls=null;
  function resize(){
   const w=Math.max(1,innerWidth),h=Math.max(1,innerHeight);
   renderer.setPixelRatio(renderScale);renderer.setSize(w,h,false);camera.aspect=w/h;
   const nativeFov=2*Math.atan(Math.tan(B.meta.horizontalFov*Math.PI/360)/camera.aspect)*180/Math.PI;
   camera.fov=controls?.mode==='orbit'?55:Math.min(75,nativeFov);camera.updateProjectionMatrix();
  }
  const bounds=new THREE.Box3().setFromObject(scene);
  controls=new SandstoneControls({camera,canvas,bounds,reference:B.meta,onModeChange:()=>resize()});
  $('mode').onchange=e=>{uniforms.uMode.value=Number(e.target.value);};
  $('exposure').oninput=e=>{uniforms.uExposure.value=Number(e.target.value);$('ev').textContent=uniforms.uExposure.value.toFixed(2);};
  $('resolution').onchange=e=>{renderScale=Number(e.target.value);resize();};
  $('hide').textContent=controls.touch?'Settings':'Interface';
  $('hide').setAttribute('aria-expanded','false');
  $('hide').onclick=()=>{
   controls.clearInput();
   if(controls.touch){const open=document.body.classList.toggle('settings-open');if(open)controls.stopTour();$('hide').setAttribute('aria-expanded',String(open));}
   else $('hud').classList.toggle('compact');
  };
  addEventListener('resize',resize);resize();
''' + app[end:]
    start=app.index('   if(keys.size){');end=app.index('   camera.updateMatrixWorld(true);',start)
    app=app[:start]+'   controls.update(dt);\n'+app[end:]
    old='window.CYBR_RECOVERY={renderer,scene,camera,material,meta:B.meta,setReference:reset,setMode:value=>{uniforms.uMode.value=Number(value);},setPose:(eye,target)=>{autoWalk=false;camera.position.fromArray(eye);aim(target);},geometry};'
    new='window.CYBR_RECOVERY={renderer,scene,camera,material,meta:B.meta,controls,setReference:()=>controls.setReference(),setMode:value=>{uniforms.uMode.value=Number(value);$(\'mode\').value=String(value);},setPose:(eye,target)=>controls.setPose(eye,target),setNavigationMode:mode=>controls.setNavigationMode(mode),geometry};'
    app=replace(app,old,new);app_path.write_text(app)
    index=ROOT/'index.html';text=index.read_text()
    text=replace(text,'</style>','</style>\n<link rel="stylesheet" href="web/controls.css">')
    markup='''<nav id="navigation" aria-label="Camera navigation">
<button id="nav-walk" aria-pressed="true">Walk</button><button id="nav-orbit" aria-pressed="false">Orbit</button>
<button id="home" title="Return to the reference walking camera">Reference</button><button id="frame-canyon" hidden title="Frame the complete canyon">Fit canyon</button></nav>
<div id="gesture-help" role="status" aria-live="polite">Left thumb: move · drag scene: look</div>
<div id="touch-walk"><div id="joystick" tabindex="0" role="group" aria-label="Movement thumbstick. Drag to walk, or use WASD and arrow keys."><div id="joystick-knob"></div><span id="joystick-label">MOVE</span></div>
<div id="height-controls"><button data-hold="KeyQ" aria-label="Move down">−</button><button data-hold="KeyE" aria-label="Move up">+</button><button id="boost" aria-pressed="false">Move faster</button></div></div>
<div id="orbit-touch"><button id="zoom-in" aria-label="Zoom in">+</button><button id="zoom-out" aria-label="Zoom out">−</button></div>
'''
    text=replace(text,'<script src="web/vendor/three.bundle.js"></script>',markup+'<script src="web/vendor/three.bundle.js"></script>\n<script src="web/controls.js"></script>')
    index.write_text(text)
    # Keep the byte-identical recovery builder available explicitly, not as the default.
    builder=ROOT/'tools/make_standalone.py';legacy=builder.read_text()
    legacy=replace(legacy,'def build(output:Path)->None:','def build_legacy(output:Path)->None:')
    legacy=replace(legacy,'"""Reassemble the byte-identical original recovery HTML from the versioned assets."""','"""Build the current offline viewer; --legacy preserves the original recovery HTML."""')
    current='''
def build(output:Path)->None:
    data=json.loads((ROOT/'web/scene.json').read_text())
    def packed(entry):
        path=(ROOT/entry['url']).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Unsafe asset path')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Asset checksum mismatch')
        return base64.b64encode(raw).decode('ascii')
    for mesh in data['meshes']:
        for key in ['position','normal','direct','indirect','surface','index']:
            if key in mesh:mesh[key]=packed(mesh[key])
    data['sky']['data']=packed(data['sky']['data'])
    text=(ROOT/'index.html').read_text()
    text=text.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(ROOT/'web/controls.css').read_text()+'</style>')
    for path in ['web/vendor/three.bundle.js','web/controls.js']:
        text=text.replace('<script src="'+path+'"></script>','<script>'+(ROOT/path).read_text()+'</script>')
    script='const CYBR_BAKE='+json.dumps(data,separators=(',',':'))+';\\n'
    for key,path in [('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')]:
        script+='const '+key+'='+json.dumps((ROOT/'web'/path).read_text())+';\\n'
    script+=(ROOT/'web/app.js').read_text()
    text=text.replace('<script src="web/bootstrap.js"></script>','<script>'+script+'</script>')
    if '<script src=' in text or '<link rel="stylesheet"' in text:raise ValueError('Offline resources not embedded')
    raw=text.encode();output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw)
    report={'schema':'sandstone-walk-standalone/2','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'current_web_app_embedded':True,'mobile_and_orbit_controls_embedded':True,'all_asset_hashes_verified':True,
            'legacy_html_identity_expected':False}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\\n')
    print(json.dumps(report,indent=2))
'''
    legacy=replace(legacy,"if __name__=='__main__':",current+"\nif __name__=='__main__':")
    legacy=replace(legacy,"args=ap.parse_args();build(args.out)","ap.add_argument('--legacy',action='store_true',help='Build the unmodified 0.1 recovery instead');args=ap.parse_args();(build_legacy if args.legacy else build)(args.out)")
    builder.write_text(legacy)
    readme=ROOT/'README.md';text=readme.read_text()
    a=text.index('### Controls');b=text.index('\n## Lighting and geometry',a)
    text=text[:a]+'''### Mobile and orbit controls

Use **Walk** for the canyon interior and **Orbit** to inspect the entire formation. Switching back to Walk restores your previous walking position and direction. **Reference** returns to the authored camera; **Fit canyon** reframes the complete mesh in orbit mode.

| Action | Touch | Mouse / keyboard |
| --- | --- | --- |
| Walk and strafe | Left thumbstick (analog speed and dead zone) | WASD / arrows |
| Look while walking | Drag the scene with the other finger | Left drag |
| Change height | Hold − / + on the right | Q / E |
| Faster movement | Move faster toggle | Either Shift key |
| Orbit the scene | One-finger drag | Left drag |
| Orbit zoom | Pinch; + / − buttons | Wheel |
| Orbit pan | Two-finger drag | Right/middle drag, Shift-drag, or WASD |
| Switch navigation | Walk / Orbit buttons | O |
| Reframe orbit | Fit canyon | F |
| Reference camera | Reference | R |
| Automatic route | Settings → Walk through | Walk through |

The thumbstick and look gestures work **simultaneously**. Releasing, cancelling or losing pointer capture, switching modes, resizing, hiding the page or losing focus clears held movement. Orbit gestures remain continuous when a finger is added or lifted. Settings use a compact mobile drawer; controls respect safe-area insets and support portrait and landscape. The portrait walking field of view is capped at 75° vertically instead of stretching the original horizontal field into a fisheye-like view. The original reference camera projection at desktop aspect ratios is retained.

Movement remains **free-camera inspection, not a collision/ground-following character controller**. Geometry and lighting are unchanged. The resolution selector changes pixel shading cost, not mesh density. All 8.1M triangles still load: improved touch controls do not imply lower GPU-memory requirements or a mobile frame-rate guarantee.
''' + text[b:]
    text=replace(text,'This writes `dist/Sandstone_Walk_Standalone.html` and verifies that it is byte-identical to the preserved recovery delivery. It is approximately 124.4 MB. The split web version avoids placing that oversized HTML in Git and loads the same geometry, bake and shaders.',
      'This writes `dist/Sandstone_Walk_Standalone.html` with the **current web UI, mobile controller and orbit mode**, plus a SHA-256 receipt. It checks every asset hash before embedding the unchanged bake and geometry. The approximately 124 MB file has no runtime CDN dependency. `python tools/make_standalone.py --legacy --out dist/Legacy_Recovery.html` remains available to reconstruct the original recovery byte-for-byte; it intentionally does not include the new controls.')
    text=text.replace('node --check web/bootstrap.js','node --check web/bootstrap.js\nnode --check web/controls.js')
    text=text.replace('python tools/browser_smoke.py\n','python tools/browser_smoke.py\npython tools/mobile_controls_smoke.py\n')
    readme.write_text(text)
    package=ROOT/'package.json';data=json.loads(package.read_text());data['version']='0.2.0';package.write_text(json.dumps(data,indent=2)+'\n')
    notes=ROOT/'docs/RELEASE_NOTES.md';notes.write_text('''# Sandstone Walk 0.2.0

Mobile controls and orbit navigation. Analog thumbstick + simultaneous drag-to-look, height controls, speed toggle, two-finger orbit pan, pinch zoom, bounds-based framing, separate remembered camera poses and safe-area-aware portrait/landscape UI.

Geometry, spectral bake, shaders and existing preview media are unchanged. The current standalone builder now packages the current web UI instead of the archived original. The original recovery remains reproducible with --legacy. Free camera; no collision controller. All 8.1M triangles are still loaded; hardware memory and performance requirements are unchanged.
''')
    workflow=ROOT/'.github/workflows/verify.yml';text=workflow.read_text()
    if 'python tools/mobile_controls_smoke.py' not in text:
        text=replace(text,'node --check web/bootstrap.js','node --check web/bootstrap.js\n          node --check web/controls.js')
        text=replace(text,'      - name: Preserve validation and browser evidence',
          '      - name: Test mobile multi-touch and orbit controls\n        run: python tools/mobile_controls_smoke.py\n      - name: Preserve validation and browser evidence')
        text=text.replace('            build/browser/','            build/browser/\n            build/mobile/')
        workflow.write_text(text)
    print('Navigation integrated. Source geometry, shaders and bake files untouched.')

if __name__=='__main__':main()
