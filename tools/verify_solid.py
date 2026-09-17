"""Validate the shipped closed-landform revision, not merely its generator.

Decodes all delivered attributes, stitches only exact shared terrain vertices,
and checks the resulting terrain and each disconnected rock component. No
visual-quality or geophysical-simulation verdict is implied by these gates.
GPL-2.0-only.
"""
from __future__ import annotations
import argparse,hashlib,json,sys,zlib
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
OLD_HASH='50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a'
EXPECTED_PARTS=['West_outcrop_and_rim','West_jointed_wall','Connected_alluvial_channel','East_jointed_wall','East_outcrop_and_rim','Closed_terrain_base','Joint_cut_talus','Channel_lag_gravel','Detached_joint_blocks']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def asset(root,entry,dtype,components):
    path=(root/entry['url']).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Unsafe asset path')
    packed=path.read_bytes()
    if len(packed)!=entry['bytes'] or sha(packed)!=entry['sha256']:raise ValueError('Packed asset integrity failure '+str(path))
    raw=zlib.decompress(packed)
    if len(raw)!=entry['decodedBytes']:raise ValueError('Decoded asset length mismatch')
    a=np.frombuffer(raw,dtype=dtype).reshape(-1,components)
    if not np.isfinite(a).all():raise ValueError('Nonfinite attribute '+str(path))
    return a

def indices(m):
    r,c=m['rows'],m['cols'];a=np.arange((r-1)*c,dtype='<u4').reshape(r-1,c)[:,:-1].ravel()
    f=np.r_[np.stack([a,a+1,a+c+1],1),np.stack([a,a+c+1,a+c],1)]
    return f[:,::-1].copy() if m['flip'] else f

def component_volumes(mesh):
    labels=trimesh.graph.connected_component_labels(mesh.face_adjacency,node_count=len(mesh.faces))
    tri=mesh.triangles
    # Translation reduces cancellation for tiny stones far along the canyon.
    center=mesh.vertices.mean(0);tri=tri-center
    signed=np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2]))/6
    return np.bincount(labels,weights=signed)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=ROOT);args=ap.parse_args();root=args.root.resolve()
    scene=json.loads((root/'web/scene.json').read_text());receipt=json.loads((root/'verification.json').read_text());meta=scene['meta']
    shape=json.loads((root/'evidence/geometry_report.json').read_text());expect={x['name']:x for x in receipt['geometry']}
    assert [p['name'] for p in scene['meshes']]==EXPECTED_PARTS
    assert meta['source_mesh_sha256']==shape['mesh_sha256']==receipt['scene']['source_mesh_sha256']!=OLD_HASH
    assert meta['geometry_modified'] is True and shape['terrain']['watertight']
    assert meta['reference_image_used'] is False and meta['hero_camera_used_by_bake'] is False
    assert not meta['image_projection'] and not meta['hand_authored_probes']
    assert meta['invalid_samples']==0 and meta['clamped_contributions']==0
    assert meta['spectral_bands']==16 and meta['hemisphere_samples_per_site']==256 and meta['maximum_path_depth']==10
    assert meta['material_schema']=='world-space-spectral-transfer/1' and meta['receiver_albedo_baked'] is False
    assert sha((root/'source/material_field.glsl').read_bytes())==meta['material_field_sha256']
    rows=[];terrain_v=[];terrain_f=[];nv=0;tris=0;vertices=0;stone_components=0;grid_edges=[]
    for i,m in enumerate(scene['meshes']):
        name=m['name'];pos=asset(root,m['position'],'<f4',3)
        idx=indices(m) if m['kind']=='grid' else asset(root,m['index'],'<u4',3)
        assert len(pos)==m['vertices'] and idx.shape==(m['triangles'],3) and idx.min()>=0 and idx.max()<len(pos),name
        check=expect[name];assert sha(pos.tobytes())==check.get('position_sha256',check.get('positions_sha256')),name
        assert sha(idx.tobytes())==check['topology_sha256'],name
        for key,dtype,nc in [('normal','<i2',3),('giR','<f2',3),('giG','<f2',3),('giB','<f2',3),('surface','<u2',2)]:
            value=asset(root,m[key],dtype,nc);assert len(value)==len(pos),(name,key)
            if key in ['giR','giG','giB']:assert np.max(np.abs(value))<60000,(name,key) # Signed spectral basis: do not clamp components.
            if key=='surface':assert np.all(value[:,1]==m['material']*257),(name,'constant material family')
            if key=='normal':assert np.max(np.abs(np.linalg.norm(value.astype('f8')/32767,axis=1)-1))<.002,name
        item={'name':name,'vertices':len(pos),'triangles':len(idx),'positions_sha256':sha(pos.tobytes()),'topology_sha256':sha(idx.tobytes()),'all_attributes_finite':True}
        if i<6:
            terrain_v.append(pos);terrain_f.append(idx.astype('i8')+nv);nv+=len(pos)
            if m['kind']=='grid':grid_edges.append(pos.reshape(m['rows'],m['cols'],3))
        else:
            rock=trimesh.Trimesh(pos,idx,process=False)
            assert rock.is_watertight and rock.is_winding_consistent,name
            volumes=component_volumes(rock);assert len(volumes)>0 and volumes.min()>0,(name,volumes.min())
            stone_components+=len(volumes);item.update(closed_components=len(volumes),minimum_component_volume_m3=float(volumes.min()))
        rows.append(item);tris+=len(idx);vertices+=len(pos)
        print('PASS',name,flush=True)
    for a,b in zip(grid_edges[:-1],grid_edges[1:]):assert np.array_equal(a[:,-1],b[:,0]),'Terrain chart seam moved'
    terrain=trimesh.Trimesh(np.concatenate(terrain_v),np.concatenate(terrain_f),process=False)
    # Welding only bit-identical decoded positions, not an approximate repair.
    unique,inverse=np.unique(terrain.vertices,axis=0,return_inverse=True)
    terrain=trimesh.Trimesh(unique,inverse[terrain.faces],process=False)
    assert terrain.is_watertight and terrain.is_winding_consistent and terrain.body_count==1
    assert terrain.volume>0 and abs(terrain.volume-shape['terrain']['signed_volume_m3'])<.1
    assert len(terrain.faces)==shape['terrain']['triangles']
    assert np.min(terrain.area_faces)>0
    assert stone_components==shape['rock_count'],(stone_components,shape['rock_count'])
    assert tris==meta['triangles'] and vertices==meta['vertex_count']
    sky=asset(root,scene['sky']['data'],'<f2',4);assert len(sky)==scene['sky']['width']*scene['sky']['height']
    shaders={}
    for f in sorted((root/'web').glob('*.glsl')):
        if f.name=='surface.frag.glsl':
            expected_shader=(root/'source/surface_material.frag.glsl').read_text().replace('__MATERIAL_FIELD__',(root/'source/material_field.glsl').read_text())
            assert f.read_text()==expected_shader,f.name
        elif f.name=='surface.vert.glsl':assert f.read_bytes()==(root/'source/surface_material.vert.glsl').read_bytes(),f.name
        else:assert f.read_bytes()==(root/'source'/f.name).read_bytes(),f.name
        shaders[f.name]=sha(f.read_bytes())
    app=(root/'web/app.js').read_text()
    for term in ['cybrRefTex','initProbeVolume','HemisphereLight','DirectionalLight','AmbientLight']:assert term not in app,term
    assert 'new SandstoneControls' in app
    output={'schema':'sandstone-walk-solid-validation/1','result':'PASS','triangles':tris,'vertices':vertices,
        'parts':rows,'source_mesh_sha256':meta['source_mesh_sha256'],'geometry_origin':'closed-landform-v0.3','geometry_changed_in_material_fix':False,
        'all_assets_sha256_valid':True,'all_attributes_finite':True,'active_shader_sha256':shaders,
        'terrain':{'watertight':True,'winding_consistent':True,'components':1,'vertices_after_exact_seam_weld':len(terrain.vertices),
                   'triangles':len(terrain.faces),'volume_m3':float(terrain.volume),'minimum_face_area_m2':float(terrain.area_faces.min()),'open_boundary_edges':0,'chart_seam_gap_m':0},
        'closed_rock_components':stone_components,'no_reference_projection':True,'no_hand_authored_light_probes':True,
        'limits':'Checks establish indexed topology, orientation, positive volumes and buffer integrity; not measured geology or exhaustive intersection certification.'}
    directory=root/'evidence';directory.mkdir(exist_ok=True);(directory/'solid_validation.json').write_text(json.dumps(output,indent=2)+'\n')
    build=root/'build';build.mkdir(exist_ok=True);(build/'validation.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='parts'},indent=2))
if __name__=='__main__':main()
