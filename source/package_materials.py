"""Package new light-transfer attributes while preserving all geometry bytes."""
from __future__ import annotations
import argparse,hashlib,json,shutil,zlib
from pathlib import Path
import numpy as np
from rebuild_materials import EXPECTED_MESH,sha

def package(work:Path,root:Path):
    web=root/'web';scene=json.loads((web/'scene.json').read_text())
    previous=json.loads((root/'verification.json').read_text())
    geometry=json.loads((work/'geometry_report.json').read_text())
    if geometry['mesh_sha256']!=EXPECTED_MESH or scene['meta']['source_mesh_sha256']!=EXPECTED_MESH:raise ValueError('Geometry mismatch')
    layout=json.loads((work/'data/layout.json').read_text())
    baking=json.loads((work/'material_baked/bake_execution.json').read_text())
    receipt=json.loads((work/'material_inputs.json').read_text())
    if receipt['files']['material_field.glsl']['sha256']!=sha(root/'source/material_field.glsl'):raise ValueError('Material source changed since baking')
    if not(baking['invalid_samples']==0 and baking['clamped_contributions']==0 and baking['hemisphere_samples_per_site']==256):raise ValueError('Unqualified bake')
    mdir=root/'evidence/materials';mdir.mkdir(exist_ok=True,parents=True)
    if not (mdir/'baseline_scene.json').exists():
        shutil.copyfile(web/'scene.json',mdir/'baseline_scene.json')
        shutil.copyfile(root/'verification.json',mdir/'baseline_verification.json')
    def encode(array,name):
        a=np.ascontiguousarray(array);raw=a.tobytes();compressed=zlib.compress(raw,8)
        p=web/'assets'/('material-'+name+'.deflate');p.write_bytes(compressed)
        return {'url':str(p.relative_to(root)),'bytes':len(compressed),'decodedBytes':len(raw),'sha256':sha(p)}
    geometry_checks=[]
    for mesh,entry in zip(scene['meshes'],layout['parts']):
        name=mesh['name'];assert name==entry['name']
        pp=np.load(work/f'data/{name}.pos.npy').astype('<f4')
        old=zlib.decompress((root/mesh['position']['url']).read_bytes())
        if old!=pp.tobytes():raise ValueError('Position bytes changed '+name)
        ff=np.load(work/f'data/{name}.idx.npy').astype('<u4')
        check=next(r for r in previous['geometry'] if r['name']==name)
        if hashlib.sha256(ff.tobytes()).hexdigest()!=check['topology_sha256']:raise ValueError('Topology changed')
        geometry_checks.append({'name':name,'positions_identical':True,'indices_identical':True})
        mesh.pop('direct',None);mesh.pop('indirect',None);mesh['material']=entry['material']
        for key in ['giR','giG','giB','normal','surface']:
            a=np.load(work/f'material_resolved/{name}.{key}.npy')
            if not np.isfinite(a).all():raise ValueError('Invalid asset')
            mesh[key]=encode(a,name+'.'+key)
    shared=sha(root/'source/material_field.glsl')
    scene['meta'].update(baking)
    scene['meta'].update({'material_schema':'world-space-spectral-transfer/1','material_revision':'Per-fragment isotropic 3D rock and sediment',
        'receiver_albedo_baked':False,'receiver_micro_normal_baked':False,'geometry_modified_in_material_revision':False,
        'material_field_sha256':shared,'rgb_to_anchors':np.fromfile(work/'material_baked/rgb_to_anchors.f32',dtype='<f4').reshape(3,3).tolist(),
        'solar_anchor_response':np.fromfile(work/'material_baked/solar_anchor_response.f32',dtype='<f4').reshape(3,3).tolist(),
        'lighting':'Fresh 16-band native bake with the shared material; signed anchor response per vertex, receiving material per fragment',
        'browser_runtime_verified':False,'shader_source':'source/material_field.glsl shared by C++ and GLSL',
        'specular_indirect':'Not represented; retained diffuse incident irradiance approximation'})
    (web/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
    previous['scene']=scene['meta'];previous['browser_runtime_verified']=False
    previous['material_revision']='world-space-spectral-transfer/1'
    previous.pop('standalone_sha256',None);previous.pop('standalone_bytes',None)
    (root/'verification.json').write_text(json.dumps(previous,indent=2)+'\n')
    for src,name in [(work/'material_inputs.json','bake_inputs.json'),(work/'material_execution.json','execution.json'),
                     (work/'material_baked/bake_execution.json','bake_execution.json'),(work/'material_resolved/resolve.json','resolve.json')]:shutil.copyfile(src,mdir/name)
    if (work/'geometry_restoration.json').exists():shutil.copyfile(work/'geometry_restoration.json',mdir/'geometry_restoration.json')
    (mdir/'geometry_preservation.json').write_text(json.dumps({'result':'PASS','source_mesh_sha256':EXPECTED_MESH,
        'triangles':5029800,'vertices':2526592,'parts':geometry_checks,'controls_sha256':sha(web/'controls.js'),
        'controls_css_sha256':sha(web/'controls.css'),'material_field_sha256':shared},indent=2)+'\n')
    print('PACKAGED MATERIAL TRANSFER',shared,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();package(a.work,a.root)
