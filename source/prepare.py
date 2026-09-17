"""Prepare exact CYBR GEO surface samples; this does not compute lighting."""
from pathlib import Path
import json, struct, hashlib, os
import numpy as np
R=Path(os.environ['CYBR_WORKSPACE'])
A=R/'native_scene/canyon/assembly'
info=json.loads((A/'scene.json').read_text())
GRID={'Alluvial_sand_and_rockfall_support':(1350,650,False),'West_bedded_sandstone':(730,1700,False),'East_bedded_sandstone':(730,1700,True),'Far_bend_continuous_wall':(640,560,False)}
layout=[];nv=ns=0
(R/'data').mkdir(exist_ok=True)
with np.load(A/'meshes.npz',allow_pickle=False) as z, (R/'data/vertices.bin').open('wb') as vo, (R/'data/sites.bin').open('wb') as so:
 vo.write(b'VTX1'+struct.pack('<I',0));so.write(b'SIT1'+struct.pack('<I',0))
 for p in info['parts']:
  k=p['key'];name=p['name'];v=(z[k+'_vertices']*.001).astype('<f4');n=z[k+'_normals'].astype('<f4');f=z[k+'_faces'].astype('<u4');cnt=len(v)
  # Float32 conversion is the same as the preserved browser mesh.
  np.save(R/f'data/{name}.pos.npy',v);np.save(R/f'data/{name}.norm.npy',n);np.save(R/f'data/{name}.idx.npy',f)
  data=np.empty((cnt,7),'<f4');data[:,:3]=v;data[:,3:6]=n;data[:,6]=p['material'];vo.write(data.tobytes())
  ent={'name':name,'material':p['material'],'vertices':cnt,'triangles':len(f),'vertexOffset':nv,'siteOffset':ns}
  if name in GRID:
   rows,cols,flip=GRID[name]
   # Every sample is an actual source vertex, not an off-surface interpolation.
   ri=np.unique(np.rint(np.linspace(0,rows-1,(rows-1)//8+2)).astype(int));ci=np.unique(np.rint(np.linspace(0,cols-1,(cols-1)//8+2)).astype(int))
   ids=(ri[:,None]*cols+ci[None,:]).ravel();ent.update(kind='grid',rows=rows,cols=cols,flip=flip,sampleRows=ri.tolist(),sampleCols=ci.tolist())
  else:
   ids=np.arange(cnt);ent.update(kind='indexed')
  sites=data[ids];so.write(sites.tobytes());ent['sites']=len(sites);layout.append(ent);ns+=len(sites);nv+=cnt
  print(name,cnt,len(sites),flush=True)
 vo.seek(4);vo.write(struct.pack('<I',nv));so.seek(4);so.write(struct.pack('<I',ns))
(R/'data/layout.json').write_text(json.dumps({'parts':layout,'vertices':nv,'sites':ns,'triangles':sum(p['triangles'] for p in layout)},indent=2))
print('total',nv,ns,flush=True)
