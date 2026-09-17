"""Package exact geometry and executed spectral bake as a self-contained Three.js viewer."""
from pathlib import Path
import argparse,base64,zlib,json,hashlib
import numpy as np

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def packed(a):return base64.b64encode(zlib.compress(np.ascontiguousarray(a).tobytes(),8)).decode('ascii')
def build(work,out):
 source=Path(__file__).resolve().parent;out.mkdir(exist_ok=True,parents=True);D=work/'resolved_final';layout=json.loads((work/'data/layout.json').read_text());meta=json.loads((D/'bake_execution.json').read_text())
 meta.update({'source_mesh_sha256':sha(work/'native_scene/canyon/scene.meshbin'),'geometry_modified':False,'positions':'same float32 conversion as preserved renderer mesh; no decimation','camera':[-.42,-5.8,1.56],'target':[.15,9.8,3.12],'horizontalFov':68,'sun':[-.24,-.33,.913],'lighting':'native spectral surface irradiance and exact-geometry solar visibility','image_projection':False,'hand_authored_probes':False,'runtime_ambient_lights':0,'static_bake':True,'view_dependent_indirect_gloss':False,'browser_runtime_verified':False})
 meshes=[];checks=[]
 for ent in layout['parts']:
  name=ent['name'];p=np.load(work/f'data/{name}.pos.npy');idx=np.load(work/f'data/{name}.idx.npy')
  nn=np.load(D/f'{name}.normal.npy');dr=np.load(D/f'{name}.direct.npy');ir=np.load(D/f'{name}.indirect.npy');surf=np.load(D/f'{name}.surface.npy')
  if len(p)!=ent['vertices'] or idx.size!=ent['triangles']*3 or idx.max()>=len(p):raise RuntimeError('Invalid original geometry')
  for a in [p,nn,dr,ir,surf]:
   if not np.isfinite(a).all():raise RuntimeError('Nonfinite GPU attribute')
  m={k:ent[k] for k in ['name','vertices','triangles','kind']}
  if ent['kind']=='grid':
   m.update({k:ent[k] for k in ['rows','cols','flip']})
   r,c=ent['rows'],ent['cols'];a=(np.arange(r-1)[:,None]*c+np.arange(c-1)[None,:]).ravel();expected=np.concatenate([np.stack([a,a+1,a+c+1],1),np.stack([a,a+c+1,a+c],1)]).astype('<u4')
   if ent['flip']:expected=expected[:,::-1]
   if not np.array_equal(expected,idx):raise RuntimeError('Exact grid face ordering mismatch: '+name)
  else:m['index']=packed(idx.astype('<u4'))
  for key,arr in [('position',p),('normal',nn),('direct',dr),('indirect',ir),('surface',surf)]:m[key]=packed(arr)
  meshes.append(m);checks.append({'name':name,'vertices':len(p),'triangles':len(idx),'positions_sha256':hashlib.sha256(p.tobytes()).hexdigest(),'topology_sha256':hashlib.sha256(idx.tobytes()).hexdigest(),'gpu_attributes_finite':True})
  print('packed',name,flush=True)
 raw=(work/'native_sky.bin').read_bytes();w,h=np.frombuffer(raw,dtype='<u4',count=2);rgb=np.frombuffer(raw,dtype='<f4',offset=8).reshape(h,w,3);rgba=np.ones((h,w,4),'<f2');rgba[:,:,:3]=rgb
 payload={'meta':meta,'meshes':meshes,'sky':{'width':int(w),'height':int(h),'data':packed(rgba),'source':'evaluated native physicalSky, not an image reference'}}
 text=(source/'page.html').read_text();mapping={'THREE_BUNDLE':(source/'three.bundle.js').read_text(),'PAYLOAD':json.dumps(payload,separators=(',',':')),'SURFACE_VERTEX':json.dumps((source/'surface.vert.glsl').read_text()),'SURFACE_FRAGMENT':json.dumps((source/'surface.frag.glsl').read_text()),'SKY_VERTEX':json.dumps((source/'sky.vert.glsl').read_text()),'SKY_FRAGMENT':json.dumps((source/'sky.frag.glsl').read_text()),'APP':(source/'app.js').read_text()}
 for key,value in mapping.items():text=text.replace('__'+key+'__',value)
 target=out/'CYBR_Canyon_Recovery.html';target.write_text(text)
 report={'geometry':checks,'source_mesh_sha256':meta['source_mesh_sha256'],'native_bake':meta,'html_sha256':sha(target),'html_bytes':target.stat().st_size,'browser_runtime_verified':False}
 (out/'evidence/package_validation.json').parent.mkdir(exist_ok=True,parents=True);(out/'evidence/package_validation.json').write_text(json.dumps(report,indent=2));print(target,target.stat().st_size,flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--workspace',type=Path,required=True);a.add_argument('--out',type=Path,required=True);p=a.parse_args();build(p.workspace,p.out)
