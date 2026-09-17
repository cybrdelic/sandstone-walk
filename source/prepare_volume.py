"""Prepare source-vertex quadrature sites for the closed native geometry.

The full geometry is used for every visibility/path query. Sparse sampling is
only of the low-frequency irradiance field, not a decimation of the mesh.
"""
from __future__ import annotations
import argparse,json,struct
from pathlib import Path
import numpy as np

def run(root:Path,stride=6):
 a=root/'native_scene/canyon/assembly';out=root/'data';out.mkdir(parents=True,exist_ok=True)
 info=json.loads((a/'scene.json').read_text());design=json.loads((a.parent/'design.json').read_text())
 parts=[];nv=ns=0
 with np.load(a/'meshes.npz',allow_pickle=False) as z,(out/'vertices.bin').open('wb') as vo,(out/'sites.bin').open('wb') as so:
  vo.write(b'VTX1'+struct.pack('<I',0));so.write(b'SIT1'+struct.pack('<I',0))
  for p in info['parts']:
   k=p['key'];name=p['name'];v=(z[k+'_vertices']*.001).astype('<f4');n=z[k+'_normals'].astype('<f4');f=z[k+'_faces'].astype('<u4')
   for key,arr in [('pos',v),('norm',n),('idx',f)]:np.save(out/(name+'.'+key+'.npy'),arr)
   records=np.c_[v,n,np.full(len(v),p['material'],'f4')].astype('<f4');vo.write(records.tobytes())
   e={'name':name,'material':p['material'],'vertices':len(v),'triangles':len(f),'vertexOffset':nv,'siteOffset':ns,'kind':'indexed'}
   if name in design:
    d=design[name];r,c=d['rows'],d['cols'];rs=np.unique(np.r_[np.arange(0,r,stride),r-1]);cs=np.unique(np.r_[np.arange(0,c,stride),c-1])
    # Explicitly sample the crest and footing transition on both sides.
    if 'cliffColumns' in d:cs=np.unique(np.r_[cs,d['cliffColumns']-2,d['cliffColumns']-1,d['cliffColumns'],c-4,c-3,c-2,c-1])
    ids=np.r_[(rs[:,None]*c+cs[None,:]).ravel(),np.arange(r*c,len(v))].astype('i4')
    e.update(d);e.update(sampleRows=rs.tolist(),sampleCols=cs.tolist(),sampleGridSites=len(rs)*len(cs),extraVertices=len(v)-r*c)
   else:ids=np.arange(len(v))
   so.write(records[ids].tobytes());e['sites']=len(ids);parts.append(e);nv+=len(v);ns+=len(ids)
   print(name,'vertices',len(v),'sites',len(ids),flush=True)
  vo.seek(4);vo.write(struct.pack('<I',nv));so.seek(4);so.write(struct.pack('<I',ns))
 layout={'parts':parts,'vertices':nv,'sites':ns,'triangles':sum(p['triangles'] for p in parts),'irradiance_stride':stride,'geometry_decimated':False}
 (out/'layout.json').write_text(json.dumps(layout,indent=2)+'\n');print(json.dumps({k:v for k,v in layout.items() if k!='parts'}),flush=True)
 return layout

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--stride',type=int,default=6);a=p.parse_args();run(a.root,a.stride)
