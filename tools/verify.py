"""Verify shipped array integrity, topology, shaders, and publication references."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import numpy as np
from scene_data import ROOT,manifest,read_asset,indices,attributes

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    b=manifest();reference=json.loads((ROOT/'evidence/package_validation.json').read_text())
    expected={m['name']:m for m in reference['geometry']};rows=[];triangles=0;vertices=0
    assert b['meta']['source_mesh_sha256']=='50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a'
    for m in b['meshes']:
        a=attributes(m);idx=indices(m);ref=expected[m['name']]
        assert len(a['position'])==m['vertices']
        assert idx.shape==(m['triangles'],3) and idx.min()>=0 and idx.max()<m['vertices']
        for key,arr in a.items():
            assert len(arr)==m['vertices'] and np.isfinite(arr).all(),(m['name'],key)
        ph=hashlib.sha256(a['position'].tobytes()).hexdigest();ih=hashlib.sha256(idx.tobytes()).hexdigest()
        assert ph==ref['positions_sha256'],m['name']
        assert ih==ref['topology_sha256'],m['name']
        rows.append({'name':m['name'],'vertices':m['vertices'],'triangles':m['triangles'],'position_sha256':ph,'topology_sha256':ih,'attributes_finite':True})
        triangles+=m['triangles'];vertices+=m['vertices']
    assert triangles==8108728 and vertices==4072674
    sky=read_asset(b['sky']['data'],'<f2',4);assert np.isfinite(sky).all() and len(sky)==b['sky']['width']*b['sky']['height']
    sh={}
    for p in (ROOT/'web').glob('*.glsl'):
        assert p.read_bytes()==(ROOT/'source'/p.name).read_bytes();sh[p.name]=sha(p)
    app=(ROOT/'web/app.js').read_text()
    for removed in ['cybrRefTex','initProbeVolume','HemisphereLight','DirectionalLight','AmbientLight']:assert removed not in app,removed
    assert b['meta']['reference_image_used'] is False and b['meta']['hero_camera_used_by_bake'] is False
    report={'schema':'sandstone-walk-publication-validation/1','result':'PASS','triangles':triangles,'vertices':vertices,'parts':rows,'original_geometry_hashes_match':True,'all_assets_sha256_valid':True,'all_attributes_finite':True,'unchanged_shader_sha256':sh,'no_reference_projection':True,'no_hand_authored_light_probes':True}
    out=ROOT/'build';out.mkdir(exist_ok=True);(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='parts'},indent=2))
if __name__=='__main__':
    if manifest()['meta'].get('version')=='0.3.0':
        from verify_volume import main as volume_main
        volume_main()
    else:main()
