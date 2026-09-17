"""Prepare/finalize the reviewed geometry correction in an existing repository.
The source archive never includes old assets or secret credentials. GPL-2.0-only.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HASH='7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79'
TRIANGLES=5029800
VERTICES=2526592

def prepare():
    old=ROOT/'source/legacy_v0_2';old.mkdir(exist_ok=True)
    current=json.loads((ROOT/'web/scene.json').read_text())
    if not (old/'scene.json').exists():
        if current['meta']['source_mesh_sha256']!='50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a':raise ValueError('Unexpected baseline scene')
        shutil.copyfile(ROOT/'web/scene.json',old/'scene.json')
        shutil.copyfile(ROOT/'README.md',old/'README.md')
        shutil.copyfile(ROOT/'index.html',old/'index.html')
        shutil.copyfile(ROOT/'web/app.js',old/'app.js')
        shutil.copyfile(ROOT/'tools/verify.py',old/'verify.py')
    # Keep legacy reconstruction meaningful after the active manifest changes.
    path=ROOT/'tools/make_standalone.py';text=path.read_text()
    oldline="def build_legacy(output:Path)->None:\n    data=json.loads((ROOT/'web/scene.json').read_text())"
    newline="def build_legacy(output:Path)->None:\n    data=json.loads((ROOT/'source/legacy_v0_2/scene.json').read_text())"
    if oldline in text:text=text.replace(oldline,newline,1);path.write_text(text)
    elif newline not in text:raise ValueError('Legacy builder has changed; reconcile instead of overwrite')
    # Retain every desktop/mobile regression; update only explicit scene totals.
    for name in ['browser_smoke.py','mobile_controls_smoke.py']:
        path=ROOT/'tools'/name;text=path.read_text()
        for oldn,newn in [('8108728',str(TRIANGLES)),('4072674',str(VERTICES))]:
            if oldn not in text and newn not in text:raise ValueError('Missing count check in '+name)
            text=text.replace(oldn,newn)
        path.write_text(text)
    (ROOT/'tools/verify.py').write_text('"""Active closed-landform validation; historical checks are in source/legacy_v0_2."""\nfrom verify_solid import main\nif __name__=="__main__":main()\n')
    package=ROOT/'package.json';p=json.loads(package.read_text());p['version']='0.3.0';package.write_text(json.dumps(p,indent=2)+'\n')
    path=ROOT/'tools/requirements-test.txt';text=path.read_text()
    for dependency in ['trimesh==4.11.1','scipy==1.17.0']:
        if dependency not in text:text+=dependency+'\n'
    path.write_text(text)
    workflow=ROOT/'.github/workflows/verify.yml';text=workflow.read_text()
    anchor='      - name: Preserve validation and browser evidence'
    if 'test_solid_browser.py' not in text:
        if text.count(anchor)!=1:raise ValueError('Verification workflow structure changed')
        text=text.replace(anchor,'      - name: Test regenerated geometry from multiple browser cameras\n        run: python tools/test_solid_browser.py --out build/solid_browser\n'+anchor,1)
        text=text.replace('            build/mobile/','            build/mobile/\n            build/solid_browser/')
        workflow.write_text(text)
    print('READY: legacy asset manifest preserved; regression assertions retained with revised counts')

def finalize():
    r=json.loads((ROOT/'verification.json').read_text());v=json.loads((ROOT/'evidence/solid_validation.json').read_text())
    b=json.loads((ROOT/'evidence/browser/report.json').read_text());m=json.loads((ROOT/'evidence/solid_media.json').read_text())
    assert r['scene']['source_mesh_sha256']==v['source_mesh_sha256']==b['source_mesh_sha256']==m['source_mesh_sha256']==HASH
    assert v['result']=='PASS' and b['result']=='PASS' and b['browser_runtime_verified']
    assert v['triangles']==TRIANGLES and v['vertices']==VERTICES
    # Historical source/scene assets are untouched even though active geometry changes.
    legacy=json.loads((ROOT/'source/legacy_v0_2/scene.json').read_text())
    for mesh in legacy['meshes']:
        for key in ['position','normal','direct','indirect','surface','index']:
            if key in mesh:
                e=mesh[key];assert hashlib.sha256((ROOT/e['url']).read_bytes()).hexdigest()==e['sha256'],e['url']
    e=legacy['sky']['data'];assert hashlib.sha256((ROOT/e['url']).read_bytes()).hexdigest()==e['sha256']
    r['browser_runtime_verified']=True;r['browser_verification']='evidence/browser/report.json'
    r['shipped_geometry_validation']='evidence/solid_validation.json';r['legacy_assets_preserved']=True
    (ROOT/'verification.json').write_text(json.dumps(r,indent=2)+'\n')
    # Old metadata is not silently relabeled as evidence for the new geometry.
    path=ROOT/'evidence/package_validation.json'
    if path.exists() and not (ROOT/'source/legacy_v0_2/package_validation.json').exists():shutil.copyfile(path,ROOT/'source/legacy_v0_2/package_validation.json')
    path.write_text(json.dumps({'schema':'sandstone-walk-geometry-expectations/2','source_mesh_sha256':HASH,'geometry':v['parts'],'triangles':TRIANGLES,'vertices':VERTICES},indent=2)+'\n')
    text=(ROOT/'docs/README_SOLID.template.md').read_text()
    asset_bytes=sum(e['bytes'] for x in json.loads((ROOT/'web/scene.json').read_text())['meshes'] for e in [x[k] for k in ['position','normal','direct','indirect','surface','index'] if k in x])
    replaces={'__TRIANGLES__':f'{TRIANGLES:,}','__VERTICES__':f'{VERTICES:,}','__SITES__':f"{r['scene']['sites']:,}",'__ROCKS__':str(v['closed_rock_components']),'__ASSET_MB__':f'{asset_bytes/1e6:.1f}','__MESH_HASH__':HASH}
    for key,value in replaces.items():text=text.replace(key,value)
    (ROOT/'README.md').write_text(text)
    (ROOT/'docs/RELEASE_NOTES.md').write_text('# Sandstone Walk 0.3.0 — Closed landform\n\nReplaces the thin wall/backdrop stage with a joined, closed terrain volume, irregular rims, exterior outcrops, a real canyon bend and rough joint-cut rocks. The changed scene is freshly baked through the native 16-band spectral pipeline. The active mesh contains '+f'{TRIANGLES:,} triangles and {VERTICES:,} vertices.\n\nMobile thumbstick, independent look, orbit/pinch/pan and settings remain; the automatic walk follows the new centerline. The previous scene and bake remain in release v0.2.0 and the preserved legacy manifest/assets.\n\nGenuine regenerated camera-loop GIF/MP4, native bake receipts, topology checks and browser/mobile evidence are included. This is authored geometry, not a scanned location, physical erosion simulation or a claimed AAA-quality certification. Lighting remains a static surface bake.\n')
    for name in ['ARCHITECTURE.md','REPRODUCING.md']:
        path=ROOT/'docs'/name
        if path.exists():
            text=path.read_text();notice='> Historical v0.1/v0.2 recovery notes. The active v0.3 closed-landform recipe, counts and rebuild commands are documented in [SOLID_GEOMETRY.md](SOLID_GEOMETRY.md) and the root README.\n\n'
            if not text.startswith('> Historical'):path.write_text(notice+text)
    print('FINALIZED: current receipts passed; original legacy assets unchanged')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','finalize']);a=ap.parse_args();globals()[a.stage]()
