"""Spectral surface-irradiance resolve. Smoothing affects GI, never the geometry."""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from prepare_solid import feature_space

def filter_grid(gi,n,p):
 out=np.zeros_like(gi);weight=np.zeros(gi.shape[:2],np.float32)
 # A normalized, positive, normal- and position-guided kernel, in linear light.
 for y in range(-2,3):
  for x in range(-2,3):
   e=np.roll(gi,(y,x),(0,1));nn=np.roll(n,(y,x),(0,1));pp=np.roll(p,(y,x),(0,1))
   w=(np.maximum(0,np.sum(n*nn,-1))**12)*np.exp(-(x*x+y*y)/4.0)/(1+np.sum((p-pp)**2,-1)/.30**2)
   if y>0:w[:y]=0
   elif y<0:w[y:]=0
   if x>0:w[:,:x]=0
   elif x<0:w[:,x:]=0
   out+=e*w[...,None];weight+=w
 return out/np.maximum(weight[...,None],1e-20)

def filter_rocks(gi,n,f,p):
 # Face adjacency prevents filtering across separate rocks or through a wall.
 # Three Jacobi passes; all coefficients are nonnegative and normalized.
 a=np.r_[f[:,0],f[:,1],f[:,2]];b=np.r_[f[:,1],f[:,2],f[:,0]]
 w=np.maximum(0,np.sum(n[a]*n[b],-1))**16
 w/=1+np.sum((p[a]-p[b])**2,-1)/.12**2
 totals=np.bincount(a,weights=w,minlength=len(gi))+np.bincount(b,weights=w,minlength=len(gi))
 for _ in range(3):
  result=np.empty_like(gi)
  for k in range(16):
   total=np.bincount(a,weights=w*gi[b,k],minlength=len(gi))+np.bincount(b,weights=w*gi[a,k],minlength=len(gi))
   result[:,k]=.25*gi[:,k]+.75*total/np.maximum(totals,1e-20)
  gi=result
 return gi

def expand_rock_irradiance(e,n,p,entry,root):
 out=np.empty((len(p),16),dtype='f4');site_ids=np.load(root/'data'/entry['sampleIndices'])
 covered=np.zeros(len(p),dtype=bool)
 for group in entry['componentSamples']:
  start,count,sstart,ns=[group[k] for k in ['vertex_start','vertices','site_start','sites']]
  stop=start+count;ids=site_ids[sstart:sstart+ns]-start
  if ids.min()<0 or ids.max()>=count:raise ValueError('Cross-rock irradiance sample map')
  pp=p[start:stop].astype('f8');nn=n[start:stop].astype('f8');feature=feature_space(pp,nn)
  tree=cKDTree(feature[ids]);distance,near=tree.query(feature,k=min(8,ns))
  if near.ndim==1:near=near[:,None];distance=distance[:,None]
  angular=np.maximum(0,np.sum(nn[:,None,:]*nn[ids[near]],axis=-1))**16
  weights=angular/np.maximum(distance*distance,1e-10)
  total=weights.sum(1);bad=total<1e-20
  if bad.any():
   best=np.argmax(nn[bad]@nn[ids].T,axis=1)
   # A normal-nearest sample from this same rock, never a nearby rock or wall.
   out[start:stop][bad]=e[sstart+best]
  good=~bad
  out[start:stop][good]=np.sum(e[sstart+near[good]]*weights[good,:,None],axis=1)/total[good,None]
  # Exact sample vertices retain their native irradiance before adjacency filtering.
  out[start+ids]=e[sstart:sstart+ns];covered[start:stop]=True
 if not covered.all() or not np.isfinite(out).all():raise ValueError('Incomplete surface irradiance interpolation')
 return out


def run(root,baked,out):
 out.mkdir(exist_ok=True,parents=True)
 layout=json.loads((root/'data/layout.json').read_text());meta=json.loads((baked/'bake_execution.json').read_text())
 gi=np.memmap(baked/'irradiance.raw.f32',dtype='<f4',mode='r',shape=(layout['sites'],16))
 vm=np.memmap(baked/'vertex_bake.raw.f32',dtype='<f4',mode='r',shape=(layout['vertices'],24))
 matrix=np.fromfile(baked/'spectral_rgb_matrix.f32',dtype='<f4').reshape(16,3)
 reports=[]
 for entry in layout['parts']:
  name=entry['name'];nvertex=entry['vertices'];s=entry['siteOffset'];v=entry['vertexOffset'];e=gi[s:s+entry['sites']].copy();vb=vm[v:v+nvertex]
  p=np.load(root/f'data/{name}.pos.npy');n=np.load(root/f'data/{name}.norm.npy')
  indirect=np.empty((nvertex,3),'f4')
  if entry['kind']=='grid':
   nr,nc=entry['rows'],entry['cols'];rs,cs=np.array(entry['sampleRows']),np.array(entry['sampleCols']);e=e.reshape(len(rs),len(cs),16)
   normal=n.reshape(nr,nc,3)[rs[:,None],cs[None,:]];pts=p.reshape(nr,nc,3)[rs[:,None],cs[None,:]]
   ef=filter_grid(e,normal,pts);iy=np.interp(np.arange(nr),rs,np.arange(len(rs)));ix=np.interp(np.arange(nc),cs,np.arange(len(cs)))
   for y in range(0,nr,64):
    yy,xx=np.meshgrid(iy[y:y+64],ix,indexing='ij');coord=np.stack([yy.ravel(),xx.ravel()]);z=np.stack([map_coordinates(ef[:,:,k],coord,order=1,mode='nearest') for k in range(16)],1)
    off=y*nc;end=off+len(z);rho=vb[off:end,8:24];indirect[off:end]=((z*rho)@matrix)/np.pi
  else:
   f=np.load(root/f'data/{name}.idx.npy')
   if 'sampleIndices' in entry:e=expand_rock_irradiance(e,n,p,entry,root)
   ef=filter_rocks(e,n,f,p)
   for off in range(0,nvertex,131072):
    end=min(off+131072,nvertex);indirect[off:end]=((ef[off:end]*vb[off:end,8:24])@matrix)/np.pi
  # View-independent low-frequency Oren-Nayar diffuse; direct BSDF is evaluated per fragment.
  rough=vb[:,3];s2=(rough*.52)**2;A=1-s2/(2*(s2+.33));F0=((1.49-1)/(1.49+1))**2
  indirect*=((1-F0)*A)[:,None]
  if not np.isfinite(indirect).all() or np.max(indirect)>100:raise RuntimeError('Invalid resolved irradiance')
  # Store the GPU precision once; test renderer and Three.js use these same buffers.
  nn=np.rint(np.clip(vb[:,:3],-1,1)*32767).astype('<i2');direct=np.maximum(vb[:,4:7],0).astype('<f2');indirect=np.maximum(indirect,0).astype('<f2')
  vis=np.clip(vb[:,7],0,1).copy()
  # Conservative one-ring lightmap visibility reconstruction. This removes
  # isolated lit vertex leaks at shadow edges; raw ray results stay untouched.
  f=np.load(root/f'data/{name}.idx.npy')
  for _ in range(1):
   vv=vis.copy()
   for aa,bb in [(0,1),(1,2),(2,0)]:
    ia,ib=f[:,aa],f[:,bb]
    # Only propagate on coherent faces, not across geometric creases.
    same=np.sum(n[ia]*n[ib],-1)>.86
    np.minimum.at(vv,ia[same],vis[ib[same]])
    np.minimum.at(vv,ib[same],vis[ia[same]])
   vis=vv
  surface=np.stack([vis,np.clip(vb[:,3],0,1)],1);surface=np.rint(surface*65535).astype('<u2')
  for key,data in [('normal',nn),('direct',direct),('indirect',indirect),('surface',surface)]:
   np.save(out/f'{name}.{key}.npy',data)
  reports.append({'name':name,'vertices':nvertex,'indirect_min':float(indirect.min()),'indirect_max':float(indirect.max()),'indirect_mean_rgb':indirect.astype('f4').mean(0).tolist(),'finite':True})
  print(name,reports[-1],flush=True)
 (out/'resolve.json').write_text(json.dumps({'method':'positive normalized linear-light GI filtering followed by spectral reflectance product and 16-band integration','geometry_modified':False,'sparse_small_rock_interpolation':'8 spatial/normal nearest baked sites within the same closed rock, positive normalized weights; full samples at hero blocks; original adjacency filter retained','albedo_smoothed':False,'direct_color_smoothed':False,'direct_visibility_reconstruction':'one-ring conservative minimum across normals with dot > 0.86; finite shadow-edge erosion; raw ray results unchanged','parts':reports},indent=2))
 (out/'bake_execution.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/canyon_repair'));ap.add_argument('--baked',default='baked');ap.add_argument('--out',default='resolved');a=ap.parse_args();run(a.root,a.root/a.baked,a.root/a.out)
