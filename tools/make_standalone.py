"""Reassemble the byte-identical original recovery HTML from the versioned assets."""
from __future__ import annotations
import argparse,base64,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(output:Path)->None:
    data=json.loads((ROOT/'web/scene.json').read_text())
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
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=ROOT/'dist/Sandstone_Walk_Standalone.html');args=ap.parse_args();build(args.out)
