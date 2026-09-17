"""Build the current offline viewer; --legacy preserves the original recovery HTML."""
from __future__ import annotations
import argparse,base64,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build_legacy(output:Path)->None:
    data=json.loads((ROOT/'source/legacy_v0_2/scene.json').read_text())
    def packed(entry):
        raw=(ROOT/entry['url']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Asset checksum mismatch')
        return base64.b64encode(raw).decode('ascii')
    for m in data['meshes']:
        for key in ['position','normal','direct','indirect','surface','index']:
            if key in m:m[key]=packed(m[key])
    data['sky']['data']=packed(data['sky']['data'])
    src=ROOT/'source';text=(src/'page.html').read_text()
    values={'THREE_BUNDLE':(src/'three.bundle.js').read_text(),'PAYLOAD':json.dumps(data,separators=(',',':')),'APP':(src/'app.js').read_text()}
    for key,path in [('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')]:values[key]=json.dumps((src/path).read_text())
    for key,value in values.items():text=text.replace('__'+key+'__',value)
    expected=json.loads((ROOT/'evidence/publication_layout.json').read_text())['source_html_sha256']
    raw=text.encode();actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected:raise ValueError(f'Standalone preservation failure: {actual} != {expected}')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw)
    print(f'{output}: {len(raw)} bytes; SHA-256 {actual}; original recovery byte identity PASS')

def build(output:Path)->None:
    data=json.loads((ROOT/'web/scene.json').read_text())
    def packed(entry):
        path=(ROOT/entry['url']).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Unsafe asset path')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Asset checksum mismatch')
        return base64.b64encode(raw).decode('ascii')
    for mesh in data['meshes']:
        for key in ['position','normal','giR','giG','giB','surface','index']:
            if key in mesh:mesh[key]=packed(mesh[key])
    data['sky']['data']=packed(data['sky']['data'])
    text=(ROOT/'index.html').read_text()
    text=text.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(ROOT/'web/controls.css').read_text()+'</style>')
    for path in ['web/vendor/three.bundle.js','web/controls.js']:
        text=text.replace('<script src="'+path+'"></script>','<script>'+(ROOT/path).read_text()+'</script>')
    script='const CYBR_BAKE='+json.dumps(data,separators=(',',':'))+';\n'
    for key,path in [('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')]:
        script+='const '+key+'='+json.dumps((ROOT/'web'/path).read_text())+';\n'
    script+=(ROOT/'web/app.js').read_text()
    text=text.replace('<script src="web/bootstrap.js"></script>','<script>'+script+'</script>')
    if '<script src=' in text or '<link rel="stylesheet"' in text:raise ValueError('Offline resources not embedded')
    raw=text.encode();output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw)
    report={'schema':'sandstone-walk-standalone/2','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'current_web_app_embedded':True,'mobile_and_orbit_controls_embedded':True,'all_asset_hashes_verified':True,
            'legacy_html_identity_expected':False}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=ROOT/'dist/Sandstone_Walk_Standalone.html');ap.add_argument('--legacy',action='store_true',help='Build the unmodified 0.1 recovery instead');args=ap.parse_args();(build_legacy if args.legacy else build)(args.out)
