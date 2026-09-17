"""Package fresh closed geometry and its native bake into the current mobile viewer.

Only the scene manifest/buffers change. Native shader sources and the existing
mobile/orbit controller remain the same. No source image enters this pipeline.
"""
from __future__ import annotations
from pathlib import Path
import argparse,base64,hashlib,json,shutil,zlib
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(work:Path,project:Path):
 web=project/'web';asset=web/'assets';asset.mkdir(exist_ok=True);evidence=project/'evidence/formation';evidence.mkdir(parents=True,exist_ok=True)
 layout=json.loads((work/'data/layout.json').read_text());cfg=json.loads((work/'native_scene/canyon/camera.json').read_text());D=work/'resolved_final'
 meta=json.loads((D/'bake_execution.json').read_text());meshes=[];checks=[]
 def packed(arr,name):
  raw=np.ascontiguousarray(arr).tobytes();payload=zlib.compress(raw,8);p=asset/(name+'.deflate');p.write_bytes(payload)
  return {'url':p.relative_to(project).as_posix(),'bytes':len(payload),'decodedBytes':len(raw),'sha256':sha(p)}
 # Old surface bakes must never be silently reused with the new topology.
 assert meta['source_mesh_sha256']==sha(work/'native_scene/canyon/scene.meshbin')
 for e in layout['parts']:
  n=e['name'];p=np.load(work/f'data/{n}.pos.npy');idx=np.load(work/f'data/{n}.idx.npy')
  attrs={k:np.load(D/f'{n}.{k}.npy') for k in ['normal','direct','indirect','surface']}
  attrs.update(position=p,index=idx.astype('<u4'))
  assert len(p)==e['vertices'] and idx.size==e['triangles']*3
  assert idx.min()>=0 and idx.max()<len(p)
  m={'name':n,'kind':'indexed','vertices':len(p),'triangles':len(idx)}
  for k,a in attrs.items():
   assert np.isfinite(a).all(),n+' '+k
   m[k]=packed(a,n+'.'+k)
  meshes.append(m)
  checks.append({'name':n,'vertices':len(p),'triangles':len(idx),'positions_sha256':hashlib.sha256(p.tobytes()).hexdigest(),'topology_sha256':hashlib.sha256(idx.tobytes()).hexdigest(),'gpu_attributes_finite':True,'volume_body':e['kind']=='parametric'})
 raw=(work/'native_sky.bin').read_bytes();w,h=np.frombuffer(raw,'<u4',2);rgb=np.frombuffer(raw,'<f4',offset=8).reshape(h,w,3);rgba=np.ones((h,w,4),'<f2');rgba[:,:,:3]=rgb
 meta.update(version='0.3.0',geometry_modified=True,geometry_provenance='CYBR GEO closed parametric masses, authored erosion and supported fracture products',
  camera=cfg['camera'],target=cfg['target'],horizontalFov=cfg['fov'],sun=cfg['sun'],
  triangles=layout['triangles'],vertex_count=layout['vertices'],mesh_groups=len(meshes),
  previous_source_mesh_sha256='50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a',
  image_projection=False,hand_authored_probes=False,runtime_ambient_lights=0,static_bake=True,
  field_reused_from_old_geometry=False,measured_geometry=False,geological_simulation=False)
 scene={'meta':meta,'meshes':meshes,'sky':{'width':int(w),'height':int(h),'data':packed(rgba,'native-sky'),'source':'Native physicalSky evaluated in linear radiance'}}
 (web/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
 used={m[k]['url'].split('/')[-1] for m in meshes for k in ['position','normal','direct','indirect','surface','index']};used.add('native-sky.deflate')
 for p in asset.iterdir():
  if p.is_file() and p.name not in used:p.unlink()
 for src,dest in [('native_scene/canyon/geometry.json','native_geometry.json'),('native_scene/canyon/design.json','design.json'),('resolved_final/bake_execution.json','bake.json'),('resolved_final/resolve.json','resolve.json')]:shutil.copyfile(work/src,evidence/dest)
 (evidence/'buffers.json').write_text(json.dumps({'geometry':checks,'triangles':layout['triangles'],'vertices':layout['vertices'],'source_mesh_sha256':meta['source_mesh_sha256'],'bake_matches_geometry':True},indent=2)+'\n')
 print('PACKED',layout['triangles'],sum(p.stat().st_size for p in asset.iterdir()),flush=True)
 return scene

def standalone(project:Path,out:Path):
 data=json.loads((project/'web/scene.json').read_text())
 for m in data['meshes']:
  for k in ['position','normal','direct','indirect','surface','index']:
   e=m[k];p=project/e['url'];assert sha(p)==e['sha256'];m[k]=base64.b64encode(p.read_bytes()).decode('ascii')
 e=data['sky']['data'];assert sha(project/e['url'])==e['sha256'];data['sky']['data']=base64.b64encode((project/e['url']).read_bytes()).decode('ascii')
 html=(project/'index.html').read_text()
 html=html.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(project/'web/controls.css').read_text()+'</style>')
 for p in ['web/vendor/three.bundle.js','web/controls.js']:html=html.replace('<script src="'+p+'"></script>','<script>'+(project/p).read_text()+'</script>')
 script='const CYBR_BAKE='+json.dumps(data,separators=(',',':'))+';\n'
 for key,file in [('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')]:
  script+='const '+key+'='+json.dumps((project/'web'/file).read_text())+';\n'
 script+=(project/'web/app.js').read_text()
 html=html.replace('<script src="web/bootstrap.js"></script>','<script>'+script+'</script>')
 assert '<script src=' not in html and '<link rel="stylesheet"' not in html
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(html)
 record={'bytes':out.stat().st_size,'sha256':sha(out),'all_asset_hashes_verified':True,'mobile_controls_embedded':True,'closed_formation':True}
 out.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print('STANDALONE',record)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--project',type=Path,required=True);p.add_argument('--standalone',type=Path);a=p.parse_args();build(a.root,a.project)
 if a.standalone:standalone(a.project,a.standalone)
