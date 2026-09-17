"""Independently verify shipped closed geometry, native bake identity and shaders."""
from __future__ import annotations
import hashlib,json,zlib,sys
from pathlib import Path
import numpy as np
import trimesh,shapely
ROOT=Path(__file__).resolve().parents[1]

def raw(e,dtype,n):
 p=ROOT/e['url'];b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==e['sha256']
 assert len(b)==e['bytes'];d=zlib.decompress(b);assert len(d)==e['decodedBytes']
 return np.frombuffer(d,dtype).reshape(-1,n)

def main():
 b=json.loads((ROOT/'web/scene.json').read_text());ref=json.loads((ROOT/'evidence/formation/buffers.json').read_text());design=json.loads((ROOT/'evidence/formation/design.json').read_text());bake=json.loads((ROOT/'evidence/formation/bake.json').read_text());expected={p['name']:p for p in ref['geometry']};rows=[];nv=nt=0
 assert b['meta']['source_mesh_sha256']==ref['source_mesh_sha256']==bake['source_mesh_sha256']
 assert b['meta']['field_reused_from_old_geometry'] is False
 assert bake['invalid_samples']==0 and bake['clamped_contributions']==0
 assert bake['sites']>0 and bake['hemisphere_samples_per_site']>=256 and bake['spectral_bands']==16
 for m in b['meshes']:
  v=raw(m['position'],'<f4',3);f=raw(m['index'],'<u4',3)
  assert f.min()>=0 and f.max()<len(v) and len(v)==m['vertices'] and len(f)==m['triangles']
  assert hashlib.sha256(v.tobytes()).hexdigest()==expected[m['name']]['positions_sha256']
  assert hashlib.sha256(f.tobytes()).hexdigest()==expected[m['name']]['topology_sha256']
  for key,dtype,n in [('normal','<i2',3),('direct','<f2',3),('indirect','<f2',3),('surface','<u2',2)]:
   a=raw(m[key],dtype,n);assert len(a)==len(v) and np.isfinite(a).all()
   if key=='normal':assert np.linalg.norm(a.astype('f4')/32767,axis=1).min()>.98
  mesh=trimesh.Trimesh(v.astype('f8'),f,process=False)
  assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,m['name']
  area=mesh.area_faces;assert area.min()>1e-12
  r={'name':m['name'],'triangles':len(f),'vertices':len(v),'watertight':True,'winding_consistent':True,'volume_m3':float(mesh.volume),'degenerate_triangles':0}
  d=design.get(m['name'])
  if d:
   R,C=d['rows'],d['cols'];g=v[:R*C].reshape(R,C,3)
   if d['cyclicColumns']:
    sections=g[:,:,[0,2]]
    for sample in [sections,(sections[:-1]+sections[1:])*.5]:assert shapely.is_valid(shapely.polygons(sample)).all()
    r['valid_cross_sections']=2*R-1
   else:assert np.all(np.diff(g[:,:,0],axis=1)>0);r['folded_apron_cells']=0
  rows.append(r);nv+=len(v);nt+=len(f)
 assert nv==b['meta']['vertex_count']==ref['vertices']==bake['vertex_count']
 assert nt==b['meta']['triangles']==ref['triangles']==bake['triangles']
 assert all(x['minimum_vertex_floor_gap_m']<0 and x['maximum_vertex_floor_gap_m']>0 for x in design['deposits'])
 sky=raw(b['sky']['data'],'<f2',4);assert np.isfinite(sky).all()
 for p in (ROOT/'web').glob('*.glsl'):assert p.read_bytes()==(ROOT/'source'/p.name).read_bytes()
 app=(ROOT/'web/app.js').read_text()
 for x in ['cybrRefTex','initProbeVolume','HemisphereLight','DirectionalLight']:assert x not in app
 report={'schema':'sandstone-walk-closed-geometry-validation/1','result':'PASS','triangles':nt,'vertices':nv,'parts':rows,'source_mesh_sha256':ref['source_mesh_sha256'],'native_bake_matches_new_geometry':True,'all_assets_sha256_valid':True,'all_loose_rocks_intersect_actual_floor':True,'closed_mass_and_apron_topology':True,'projection_or_hand_authored_lighting':False,'limits':'Cross-section self-crossing checks sample source rows and row midpoints. Bedrock/terrain overlap below ground is intentional. This is not a geophysical simulation or an exhaustive 3D solid-intersection certification.'}
 out=ROOT/'build';out.mkdir(exist_ok=True);(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
 if '--evidence' in sys.argv:(ROOT/'evidence/formation/validation.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
