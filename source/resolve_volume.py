"""Resolve actual 16-band path-traced irradiance onto the unchanged new mesh."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates
from resolve import filter_grid,filter_rocks

def run(root:Path):
 baked=root/'baked_final';out=root/'resolved_final';out.mkdir(exist_ok=True)
 layout=json.loads((root/'data/layout.json').read_text());meta=json.loads((baked/'bake_execution.json').read_text())
 gi=np.memmap(baked/'irradiance.raw.f32','<f4','r',shape=(layout['sites'],16))
 vm=np.memmap(baked/'vertex_bake.raw.f32','<f4','r',shape=(layout['vertices'],24))
 matrix=np.fromfile(baked/'spectral_rgb_matrix.f32','<f4').reshape(16,3);reports=[]
 for e in layout['parts']:
  name=e['name'];cnt=e['vertices'];v=e['vertexOffset'];s=e['siteOffset'];vb=vm[v:v+cnt];irr=gi[s:s+e['sites']].copy()
  p=np.load(root/f'data/{name}.pos.npy');n=np.load(root/f'data/{name}.norm.npy');f=np.load(root/f'data/{name}.idx.npy')
  indirect=np.empty((cnt,3),'f4')
  if e['kind']=='parametric':
   r,c=e['rows'],e['cols'];rs=np.array(e['sampleRows']);cs=np.array(e['sampleCols']);ng=e['sampleGridSites']
   sh=irr[:ng].reshape(len(rs),len(cs),16);sp=p[:r*c].reshape(r,c,3)[rs[:,None],cs[None,:]];sn=n[:r*c].reshape(r,c,3)[rs[:,None],cs[None,:]]
   filtered=filter_grid(sh,sn,sp)
   iy=np.interp(np.arange(r),rs,np.arange(len(rs)));ix=np.interp(np.arange(c),cs,np.arange(len(cs)))
   for y in range(0,r,64):
    yy,xx=np.meshgrid(iy[y:y+64],ix,indexing='ij');coords=np.array([yy.ravel(),xx.ravel()]);values=np.stack([map_coordinates(filtered[:,:,i],coords,order=1,mode='nearest') for i in range(16)],1)
    offset=y*c;end=offset+len(values);indirect[offset:end]=(values*vb[offset:end,8:24])@matrix/np.pi
   if cnt>r*c:indirect[r*c:]=(irr[ng:]*vb[r*c:,8:24])@matrix/np.pi
  else:
   filtered=filter_rocks(irr,n,f,p)
   indirect=(filtered*vb[:,8:24])@matrix/np.pi
  rough=vb[:,3];s2=(rough*.52)**2;A=1-s2/(2*(s2+.33));F0=((1.49-1)/(1.49+1))**2
  indirect*=((1-F0)*A)[:,None]
  if not np.isfinite(indirect).all():raise ValueError('Nonfinite indirect transport')
  visibility=np.clip(vb[:,7],0,1).copy()
  # Keep finite-sun samples without the legacy one-ring minimum that thickened shadows.
  normal=np.rint(np.clip(vb[:,:3],-1,1)*32767).astype('<i2')
  direct=np.maximum(vb[:,4:7],0).astype('<f2');indirect=np.maximum(indirect,0).astype('<f2')
  surface=np.rint(np.stack([visibility,np.clip(rough,0,1)],1)*65535).astype('<u2')
  for key,a in [('normal',normal),('direct',direct),('indirect',indirect),('surface',surface)]:np.save(out/f'{name}.{key}.npy',a)
  reports.append({'name':name,'vertices':cnt,'finite':True,'indirect_mean_rgb':indirect.astype('f4').mean(0).tolist(),'indirect_max':float(indirect.max()),'minimum_visibility':float(visibility.min()),'maximum_visibility':float(visibility.max())})
  print(reports[-1],flush=True)
 current=hashlib.sha256((root/'native_scene/canyon/scene.meshbin').read_bytes()).hexdigest()
 if meta.get('source_mesh_sha256')!=current:raise RuntimeError('Raw bake not bound to this mesh; run rebuild_volume.py')
 meta['source_mesh_sha256']=current
 (out/'bake_execution.json').write_text(json.dumps(meta,indent=2)+'\n')
 (out/'resolve.json').write_text(json.dumps({'method':'positive geometry-guided filtering and parametric interpolation of baked spectral irradiance','geometry_changed_by_resolve':False,'direct_visibility_filtered':False,'parts':reports},indent=2)+'\n')
 return reports
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();run(a.root)
