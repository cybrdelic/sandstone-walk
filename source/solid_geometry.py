"""A closed canyon landform, not three camera-facing rock sheets.

GPL-2.0-only. Metres internally, CYBR GEO assembly export in millimetres.
This is deterministic art-directed geology, NOT a scanned site or an erosion
simulation. The original recovery generator remains untouched beside this file.

One indexed parametric terrain surface connects west outcrop, rim, interior
wall, alluvial channel, east wall and east rim. Its actual perimeter is closed
with sides and a bottom. The canonical terrain is checked as one watertight
manifold before splitting it into shared-boundary material/bake charts. These
charts do not change positions or topology. Near/far ends are low eroded slopes,
not a freestanding back-wall panel. Every fallen stone is an enclosed rough joint-cut volume.
"""
from __future__ import annotations
import argparse, gc, hashlib, json, math, struct, sys, time
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import trimesh
from skimage.measure import marching_cubes
from shapely import Polygon, constrained_delaunay_triangles

SOURCE=Path(__file__).resolve().parent
REPO=SOURCE/'cybr-geo'
sys.path[:0]=[str(REPO/'src'),str(REPO/'examples/three_scenes')]
from build_scenes import n3, fractal, smooth, unit, grid_faces, vertex_normals, Builder
from rebuild_scenes import canyon_center as legacy_center

def canyon_center(y):
    y=np.asarray(y)
    return legacy_center(y)+9.0*smooth(23.,43.,y)-3.6*smooth(45.,60.,y)

REMOVED_MICRO_ISLANDS=0
SEED=20260917
BASE_Z=-3.0
BED_LEVELS=np.array([-.8,-.20,.21,.88,1.43,2.46,2.81,3.75,4.40,5.74,6.06,
                     7.11,8.59,8.97,10.21,11.56,12.20,13.93,15.6,17.9,20.5,24.])
BED_RETREAT=np.array([.05,.16,-.07,.08,-.12,.02,.21,-.11,.12,-.02,.25,-.10,
                      .16,.02,-.08,.20,-.11,.05,.19,-.05,.08])


def field(x,y,z=0.,scale=1.,octaves=3):
    return fractal(np.asarray(x)*scale,np.asarray(y)*scale,np.asarray(z)*scale,octaves)


def write_json(path:Path,data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def extent(y):
    # The edges are irregular terrain toes, not vertical screen-sized panels.
    return 24.+2.2*n3(y*.086,3.4)+1.6*n3(y*.19,17.3)


def end_fade(y):
    return smooth(-26.,-11.5,y)*(1.-smooth(39.,60.,y))


def floor_height(x,y):
    x,y=np.broadcast_arrays(x,y)
    dx=x-canyon_center(y)
    talus=.30*smooth(1.7,3.0,np.abs(dx))*(1.+.36*n3(y*.38,dx*.5))
    thalweg=-.115*np.exp(-((dx+.32*np.sin(y*.19))/.76)**2)
    return -.12+.008*y+talus+thalweg+.026*field(x,y,scale=.68,octaves=3)


@dataclass(frozen=True)
class Scar:
    y:float
    z:float
    width:float
    height:float
    depth:float
    tilt:float


class Formation:
    def __init__(self,seed=SEED):
        self.seed=seed
        self.scars={};self.joints={}
        for side in [-1,1]:
            rng=np.random.default_rng(seed+side*81)
            js=np.cumsum(rng.uniform(1.8,4.4,27))-20
            self.joints[side]=[(float(y),float(rng.uniform(.0,6)),float(rng.uniform(4.,10.)),
                               float(rng.uniform(-.07,.07)),float(rng.uniform(.037,.085))) for y in js if y<57]
            scars=[]
            for _ in range(37):
                y=float(rng.uniform(-14,44));z=float(rng.uniform(.8,14.))
                # Fracture endpoints follow sedimentary bed boundaries.
                bi=int(np.clip(np.searchsorted(BED_LEVELS,z)-1,0,len(BED_RETREAT)-1))
                z=(BED_LEVELS[bi]+BED_LEVELS[bi+1])*.5
                scars.append(Scar(y,float(z),float(rng.uniform(.5,2.2)),
                                  float(min(rng.uniform(.34,.97),(BED_LEVELS[bi+1]-BED_LEVELS[bi])*.65)),
                                  float(rng.uniform(.06,.31)),float(rng.uniform(-.1,.1))))
            self.scars[side]=scars

    def rim(self,y,side):
        y=np.asarray(y)
        h=12.0+1.5*n3(y*.082+side*3,side*7)+.76*n3(y*.24,side*12)
        h+=4.0*np.exp(-((y-32.-side*2.)/8.)**2)
        # Discrete damaged rim notches, not a straight horizontal crop.
        for j,(cy,z0,zlen,tilt,width) in enumerate(self.joints[side]):
            h-=(.20+.15*(j%4))*np.exp(-((y-cy)/(.22+.12*(j%3)))**2)
        for cy,width,depth in self.tributaries(side):
            h-=depth*np.exp(-((y-cy)/width)**4)
        return floor_height(canyon_center(y)+side*3.,y)+.32+(h-.32)*end_fade(y)

    def tributaries(self,side):
        return [(-.4,1.4,2.0),(14.7,1.8,3.2),(29.2,1.45,2.4)] if side<0 else [(6.8,1.1,2.1),(23.2,2.0,3.1),(36.8,1.5,2.5)]

    def width(self,y,z,side):
        y,z=np.broadcast_arrays(y,z)
        bed=z+.030*y+.085*n3(y*.19+side*3,1.)
        w=2.47+.034*z+.32*field(y+side*11,z,scale=.19,octaves=3)
        # Broad alcoves and buttresses establish scale before any surface detail.
        for cy,cz,sy,sz,depth in [(2.2,2.7,2.9,2.1,.45),(10.9,6.4,3.4,3.8,.52),
                                  (20.0,4.0,3.8,3.7,.70),(31.,8.,4.0,5.4,.63)]:
            w+=depth*np.exp(-((y-cy-side*1.4)/sy)**2-((z-cz)/sz)**2)
        w-=.44*np.exp(-((y-13.3+side*.7)/2.4)**2)*smooth(.3,3.9,z)
        for i,(a,b) in enumerate(zip(BED_LEVELS[:-1],BED_LEVELS[1:])):
            local=bed+.020*field(y+i*3,z,scale=.65,octaves=2)
            mask=smooth(a-.052,a+.052,local)*(1-smooth(b-.058,b+.058,local))
            t=np.clip((local-a)/(b-a),0,1)
            persistence=.08+.92*smooth(-.20,.43,n3(y*.38+i*1.23,side*4.))
            recess=BED_RETREAT[i]*persistence
            # Sloping fracture faces; lips are finite patches, not continuous donuts.
            block=.026*(1-t)+.014*n3(y*.66,side*8+i*4)
            lip=.044*np.exp(-t/.11)*smooth(.05,.55,n3(y*.49+i,side*3))
            strength=.75 if i in [3,7,11,16] else .35
            w+=mask*(recess*strength+block*.7+lip*.6)
        for scar in self.scars[side]:
            dy=(y-scar.y)/scar.width
            dz=(bed-scar.z+dy*scar.tilt)/scar.height
            q=np.maximum(np.abs(dy)*.94,np.abs(dz))+.13*np.maximum(0,np.abs(dy)+np.abs(dz)-1)
            m=1-smooth(.79,1.02,q)
            w+=scar.depth*m*(.78+.14*dy+.08*dz)
        for j,(cy,z0,zlen,tilt,aperture) in enumerate(self.joints[side]):
            center=cy+tilt*z+.025*n3(z*.41,j*1.7)
            termination=smooth(z0,z0+.28,z)*(1-smooth(z0+zlen-.3,z0+zlen,z))
            w+=(.07+.035*(j%4))*np.exp(-((y-center)/aperture)**2)*termination
        # Band-limited granular relief: below-grid frequencies stay out of geometry.
        w+=.010*field(y+side*9,z,scale=3.0,octaves=2)
        w+=.16*np.exp(-((z-.50)/.32)**2)*np.exp(-((y-5-side)/3.1)**2)
        return w

    def contact(self,y,side):
        # Fixed point of the actual channel floor / wall contact.
        z=floor_height(canyon_center(y)+side*2.6,y)
        for _ in range(6):
            x=canyon_center(y)+side*self.width(y,z,side)
            z=floor_height(x,y)
        return x,z

    def chart(self,y,t,side):
        y,t=np.broadcast_arrays(y,t)
        # Avoid recomputing the full profile for 1D contacts at every column.
        yy=y[:,0] if y.ndim==2 else y
        _,zz0=self.contact(yy,side);hh=self.rim(yy,side)
        if y.ndim==2:zz0=zz0[:,None];hh=hh[:,None]
        z=zz0+(hh-zz0)*t
        w=self.width(y,z,side)
        w+=.34*smooth(.85,1.,t)**2
        # At the ends the landform opens into low, eroded channel banks.
        x=canyon_center(y)+side*w
        return np.stack([x,y,z],-1)


def constrained_cap(points,ids,axes,flip=False):
    """Triangulate a real cross-section without projecting overhangs onto a line."""
    ids=np.asarray(ids,dtype=np.int64);xy=np.asarray(points)[ids][:,axes]
    polygon=Polygon(xy)
    if not polygon.is_valid or polygon.area<=0:raise ValueError('Invalid terrain cap cross-section')
    lookup={tuple(p):int(i) for p,i in zip(xy,ids)}
    if len(lookup)!=len(ids):raise ValueError('Duplicate cap boundary vertex')
    result=constrained_delaunay_triangles(polygon);faces=[]
    for triangle in result.geoms:
        q=np.array(triangle.exterior.coords)[:3]
        try:f=[lookup[tuple(p)] for p in q]
        except KeyError:raise ValueError('Cap introduced an unregistered vertex')
        orient=(q[1,0]-q[0,0])*(q[2,1]-q[0,1])-(q[1,1]-q[0,1])*(q[2,0]-q[0,0])
        if orient<0:f=f[::-1]
        if flip:f=f[::-1]
        faces.append(f)
    return np.asarray(faces,dtype=np.int64)


def close_surface(top):
    """Real end sections and a triangulated underside, including overhangs.

    Projecting *every* top boundary vertex vertically to the bottom produces
    overlapping bottom edges below vertical cliffs. Instead only the exterior
    toes are extruded; the front and back are triangulated in their X/Z plane.
    """
    ny,nx,_=top.shape;v=top.reshape(-1,3);f=grid_faces(ny,nx)
    ids=np.arange(ny*nx).reshape(ny,nx);n=len(v)
    left=v[ids[:,0]].copy();right=v[ids[:,-1]].copy();left[:,2]=BASE_Z;right[:,2]=BASE_Z
    left_ids=np.arange(n,n+ny);right_ids=np.arange(n+ny,n+2*ny)
    allv=np.r_[v,left,right];parts=[]
    for top_ids,bottom_ids in [(ids[:,-1],right_ids),(ids[::-1,0],left_ids[::-1])]:
        parts.extend([np.stack([top_ids[:-1],bottom_ids[:-1],bottom_ids[1:]],1),
                      np.stack([top_ids[:-1],bottom_ids[1:],top_ids[1:]],1)])
    front=np.r_[ids[0,:],right_ids[0],left_ids[0]]
    back=np.r_[ids[-1,:],right_ids[-1],left_ids[-1]]
    parts.append(constrained_cap(allv,front,[0,2],False))
    parts.append(constrained_cap(allv,back,[0,2],True))
    bottom_ring=np.r_[left_ids,right_ids[::-1]]
    bottom=constrained_cap(allv,bottom_ring,[0,1],True)
    sides=np.concatenate(parts);allf=np.r_[f,sides,bottom]
    boundary=np.r_[ids[0,:],ids[1:,-1],ids[-1,-2::-1],ids[-2:0:-1,0]]
    return allv,allf,boundary,sides,bottom


def fracture_stone(rng,radius,rounded=False):
    """Polygonal joint planes eroded into a closed, rough implicit rock volume.

    The iso-surface is actual mesh geometry. Large stones are not flat low-poly
    hulls, nor an image-generated asset. Bounded surface relief softens/chips
    planes and edges without inflating each stone into a spherical cobble.
    """
    resolution=48 if radius>.45 else (30 if radius>.20 else (22 if radius>.06 else 16))
    lin=np.linspace(-1.5,1.5,resolution)
    X,Y,Z=np.meshgrid(lin,lin,lin,indexing='ij')
    normals=unit(np.r_[np.eye(3),-np.eye(3)]+rng.normal(0,.14,(6,3)))
    normals=np.r_[normals,unit(rng.normal(size=(6,3)))]
    distances=np.r_[rng.uniform(.78,1.08,6),rng.uniform(.75,1.2,6)]
    sdf=np.full(X.shape,-100.)
    # Log-sum-exp rounds joint intersections at a small physical radius.
    sharp=20. if not rounded else 12.
    for n,d in zip(normals,distances):
        plane=X*n[0]+Y*n[1]+Z*n[2]-d
        sdf=np.logaddexp(sdf*sharp,plane*sharp)/sharp
    # Bound occasional overlong joint wedges with six additional fracture planes.
    # The 1.30 limit plus bounded relief stays strictly inside the 1.50 mesh box.
    for plane in [X-1.30,-X-1.30,Y-1.30,-Y-1.30,Z-1.30,-Z-1.30]:
        sdf=np.logaddexp(sdf*sharp,plane*sharp)/sharp
    shift=rng.uniform(-20,20,3)
    sdf+=.045*field(X+shift[0],Y+shift[1],Z+shift[2],scale=2.5,octaves=3)
    sdf+=.013*field(X+shift[0]+5,Y+shift[1],Z+shift[2],scale=7.7,octaves=2)
    if rounded:sdf=.84*sdf+.16*(np.sqrt(X*X+Y*Y+Z*Z)-.94)
    # Closed at all volume boundaries. This is validated, not assumed.
    if min(sdf[0].min(),sdf[-1].min(),sdf[:,0].min(),sdf[:,-1].min(),sdf[:,:,0].min(),sdf[:,:,-1].min())<=0:
        raise ValueError('Rock escapes its meshing volume')
    delta=3./(resolution-1)
    points,faces,_,_=marching_cubes(sdf.astype('f4'),0.,spacing=(delta,delta,delta),allow_degenerate=False)
    points=points.astype('f8')-1.5;faces=faces.astype('i8')
    # The implicit chipping field can occasionally isolate a sub-grid speck.
    # A requested stone must be one connected solid, not disconnected debris.
    provisional=trimesh.Trimesh(points,faces,process=False)
    if provisional.body_count!=1:
        components=provisional.split(only_watertight=False)
        principal=max(components,key=lambda m:abs(m.volume))
        if not principal.is_watertight:raise ValueError('Main fracture body is open')
        global REMOVED_MICRO_ISLANDS
        REMOVED_MICRO_ISLANDS+=len(components)-1
        points=principal.vertices.copy();faces=principal.faces.copy()
    points*=np.array([radius,radius*rng.uniform(.60,1.06),radius*rng.uniform(.27,.61)])
    mesh=trimesh.Trimesh(points,faces,process=False)
    if mesh.volume<0:faces=faces[:,::-1].copy();mesh=trimesh.Trimesh(points,faces,process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume<=0:
        raise RuntimeError('Non-solid implicit fracture stone')
    yaw=rng.uniform(0,2*np.pi);pitch=rng.uniform(-.27,.27);roll=rng.uniform(-.22,.22)
    rot=trimesh.transformations.euler_matrix(roll,pitch,yaw)[:3,:3]
    return points@rot.T,faces


def terrain(seed=SEED,density=1.):
    form=Formation(seed)
    # A contiguous terrain with dense useful interior resolution and actual exterior.
    y=np.unique(np.r_[np.linspace(-26,-12,max(3,int(57*density))),
                      np.linspace(-12,40,max(3,int(1061*density))),
                      np.linspace(40,60,max(3,int(81*density)))])
    t=np.linspace(0,1,max(4,int(461*density)))
    west=form.chart(np.broadcast_to(y[:,None],(len(y),len(t))),np.broadcast_to(t[None,:],(len(y),len(t))),-1)
    east=form.chart(np.broadcast_to(y[:,None],(len(y),len(t))),np.broadcast_to(t[None,:],(len(y),len(t))),1)
    u=np.linspace(0,1,max(4,int(111*density)))
    rims=[]
    for side,wall in [(-1,west),(1,east)]:
        edge=wall[:,-1,:];X=edge[:,0,None]+side*(extent(y)-np.abs(edge[:,0]-canyon_center(y)))[:,None]*u[None,:]
        Y=np.broadcast_to(y[:,None],X.shape)
        # Exterior slopes descend continuously into the same terrain base.
        # Independent 2D upland relief. Do not extrude every rim notch across
        # the plateau: that was the source of the earlier stair-tread exterior.
        warped_x=X+1.6*n3(X*.10,Y*.13+side*7)
        warped_y=Y+2.1*n3(X*.13+side*11,Y*.11)
        hraw=11.7+2.3*field(warped_x+side*19,warped_y,scale=.115,octaves=3)
        hraw+=1.4*field(warped_x+side*12,warped_y,scale=.26,octaves=2)
        hraw+=3.3*np.exp(-((Y-32-side*3)/8.7)**2-((u[None,:]-.28)/.38)**2)
        # Tributary gullies reach the canyon rim and branch on the upland.
        for j,(cy,width,depth) in enumerate(form.tributaries(side)):
            center=cy+(3.0+2*j)*u[None,:]+1.0*np.sin(u[None,:]*4+j)
            center-=np.sin(j) # continuous mouth at the wall rim
            widen=width+1.1*u[None,:]
            hraw-=depth*np.exp(-((Y-center)/widen)**4)*(1-.55*u[None,:])
        H=floor_height(X,Y)+.32+(hraw-.32)*end_fade(Y)
        blend=smooth(0.,.14,u[None,:])
        H=edge[:,2,None]*(1-blend)+H*blend
        # The outer escarpment's contour varies independently of the inner rim.
        contour=.70+.075*n3(Y*.19,side*9)+.055*n3(Y*.37+side*5,3.)
        falling=smooth(contour,contour+.23,u[None,:])
        toe=floor_height(X,Y)-.12
        Z=H*(1-falling)+toe*falling
        Z-=.20*smooth(.12,.55,n3(X*.62,Y*.37))*np.sin(np.pi*u[None,:])
        P=np.stack([X,Y,Z],-1);P[:,0]=edge;rims.append(P)
    west_rim,east_rim=rims
    u=np.linspace(0,1,max(4,int(153*density)))
    X=west[:,0,0,None]*(1-u[None,:])+east[:,0,0,None]*u[None,:]
    Y=np.broadcast_to(y[:,None],X.shape);Z=floor_height(X,Y)
    Z+=.0035*field(X,Y,scale=8.3,octaves=2)*np.sin(np.pi*u[None,:])
    floor=np.stack([X,Y,Z],-1);floor[:,0]=west[:,0];floor[:,-1]=east[:,0]
    sections=[('West_outcrop_and_rim',west_rim[:,::-1,:],1),('West_jointed_wall',west[:,::-1,:],1),
              ('Connected_alluvial_channel',floor,0),('East_jointed_wall',east,1),('East_outcrop_and_rim',east_rim,1)]
    top=np.concatenate([s[1] if i==0 else s[1][:,1:,:] for i,s in enumerate(sections)],axis=1)
    charts=[];col=0
    for name,p,mat in sections:
        charts.append({'name':name,'rows':len(y),'cols':p.shape[1],'start_col':col,'material':mat,'flip':False})
        col+=p.shape[1]-1
    return form,top,charts


def build(work:Path,seed=SEED,density=1.):
    work.mkdir(parents=True,exist_ok=True);start=time.monotonic();form,top,charts=terrain(seed,density)
    print('TERRAIN',top.shape,flush=True)
    # Validate the same float32 geometry that will actually reach the GPU.
    top=top.astype('f4').astype('f8')
    v,f,boundary,sides,bottom=close_surface(top)
    canonical=trimesh.Trimesh(v,f,process=False)
    check={'vertices':len(v),'triangles':len(f),'watertight':bool(canonical.is_watertight),
           'winding_consistent':bool(canonical.is_winding_consistent),'signed_volume_m3':float(canonical.volume),
           'connected_components':0}
    # The topology is a disk + one closed perimeter + one bottom fan, hence one component.
    check['connected_components']=int(canonical.body_count)
    if not check['watertight'] or not check['winding_consistent'] or check['signed_volume_m3']<=0 or check['connected_components']!=1:
        raise RuntimeError(check)
    print('TOPOLOGY',check,flush=True)
    del canonical;gc.collect()
    # Gradients preserve shading-normal continuity between material/bake charts.
    n=unit(np.cross(np.gradient(top,axis=1),np.gradient(top,axis=0)))
    b=Builder('canyon',seed)
    minimum_area=float('inf');parts=[]
    for ent in charts:
        name=ent['name'];c=ent['start_col'];nc=ent['cols'];p=top[:,c:c+nc];nn=n[:,c:c+nc]
        ff=grid_faces(ent['rows'],nc)
        b.add(name,p.reshape(-1,3),ff,nn.reshape(-1,3),mat=ent['material'])
        ent.update(kind='grid',sample_stride=6 if 'wall' in name else 5)
        parts.append(ent)
    # Closed perimeter mesh reuses canonical surface boundary coordinates exactly.
    ids=np.unique(np.r_[sides.ravel(),bottom.ravel()]);idxmap=np.full(len(v),-1,dtype=np.int64);idxmap[ids]=np.arange(len(ids))
    ff=idxmap[np.r_[sides,bottom]];p=v[ids];nn=vertex_normals(p,ff)
    b.add('Closed_terrain_base',p,ff,nn,mat=16)
    parts.append({'name':'Closed_terrain_base','kind':'indexed','material':16})
    contacts=[];rng=np.random.default_rng(seed+472)
    # Talus is concentrated beneath fracture zones rather than evenly peppered.
    fans=[(-1,-1.,125),(1,5.,145),(-1,12.,120),(1,23.,120),(-1,31.,90),(1,35.,80)]
    stone_count=0;rejects=0
    contact_y=np.linspace(-17,45,3101)
    contacts_x={side:form.contact(contact_y,side)[0] for side in [-1,1]}
    for side,cy,count in fans:
        for j in range(count):
            y=float(rng.normal(cy,1.55));wx=float(np.interp(y,contact_y,contacts_x[side]))
            r=float(np.exp(rng.uniform(np.log(.028),np.log(.36))))
            offset=float(rng.exponential(.43))+r*.55
            x=wx-side*offset
            if abs(x-float(canyon_center(y)))<.9:rejects+=1;continue
            p,ff=fracture_stone(rng,r,False);p[:,:2]+=[x,y]
            h=floor_height(p[:,0],p[:,1]);support=float(np.max(h-p[:,2]));burial=float(max(np.ptp(p[:,2])*.17,.007))
            p[:,2]+=support-burial
            contacts.append({'name':f'talus_{stone_count}','penetration_m':float(np.max(h-p[:,2])),
                             'radius_m':r,'side':side,'source_y':cy})
            b.add('Joint_cut_talus',p,ff,mat=2);stone_count+=1
    # Sparse rounded gravel in the wash; some clear central passage remains.
    for j in range(440):
        y=float(rng.uniform(-11,38));dx=float(rng.uniform(-2.2,2.2))
        if abs(dx)<.80 and rng.random()<.90:continue
        x=float(canyon_center(y))+dx;r=float(rng.uniform(.013,.052))
        p,ff=fracture_stone(rng,r,True);p[:,:2]+=[x,y]
        h=floor_height(p[:,0],p[:,1]);p[:,2]+=float(np.max(h-p[:,2]))-float(np.ptp(p[:,2])*.28)
        b.add('Channel_lag_gravel',p,ff,mat=2);stone_count+=1
    # Specific larger joint-failure blocks, varied aspect and orientation.
    for side,y,rad in [(-1,-2.3,.65),(1,1.7,.57),(-1,6.2,.75),(1,12.6,.81),(-1,24.5,.62),(1,31.5,.92)]:
        wx,wz=form.contact(np.array([y]),side);x=float(wx[0])-side*(rad*.55+.1)
        p,ff=fracture_stone(rng,rad);p[:,:2]+=[x,y]
        h=floor_height(p[:,0],p[:,1]);p[:,2]+=float(np.max(h-p[:,2]))-float(np.ptp(p[:,2])*.13)
        b.add('Detached_joint_blocks',p,ff,mat=16);stone_count+=1
    for name,mat in [('Joint_cut_talus',2),('Channel_lag_gravel',2),('Detached_joint_blocks',16)]:
        parts.append({'name':name,'kind':'indexed','material':mat})
    cfg={'scene':'canyon','title':'Sandstone Passage — Closed landform and jointed rock',
         'camera':[-.42,-5.8,1.56],'target':[.15,9.8,3.12],'fov':68,'sun':[-.24,-.33,.913],
         'exposure':2.5,'white_balance':5900,'sun_scale':1.,'sky_scale':.95,'water_absorption':1.}
    out=work/'native_scene/canyon';b.finish(out,cfg,False)
    # Export topology/material metadata; the sampler reads it rather than hardcoded old grid sizes.
    write_json(work/'charts.json',{'charts':parts})
    report={'schema':'sandstone-walk-solid-geometry/1','seed':seed,'density':density,
            'source_file_sha256':sha(Path(__file__)),'terrain':check,'rock_count':stone_count,
            'discarded_disconnected_meshing_micro_islands':REMOVED_MICRO_ISLANDS,
            'rejected_center_channel_rocks':rejects,'talus_contacts':contacts,
            'minimum_talus_penetration_m':min(c['penetration_m'] for c in contacts),
            'seam_gap_m':0.0,'seam_method':'Same canonical terrain vertex coordinates/normals copied to adjacent charts',
            'rim_height_range_m':{str(side):[float(form.rim(np.linspace(-10,39,600),side).min()),float(form.rim(np.linspace(-10,39,600),side).max())] for side in [-1,1]},
            'camera':cfg['camera'],'target':cfg['target'],'centerline':[[float(y),float(canyon_center(y))] for y in np.linspace(-26,60,431)],'mesh_sha256':sha(out/'scene.meshbin'),
            'geometry_is_authored':True,'photogrammetry':False,'geophysical_simulation':False,
            'open_surface_wall_panels':0,'backdrop_wall_panel':False,'top_crops':False,
            'seconds':time.monotonic()-start}
    write_json(work/'geometry_report.json',report)
    print('BUILT',report['mesh_sha256'],report['seconds'],flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True)
    ap.add_argument('--density',type=float,default=1.);ap.add_argument('--seed',type=int,default=SEED)
    a=ap.parse_args()
    if not .15<=a.density<=2.:ap.error('density must be in [.15,2]')
    build(a.work,a.seed,a.density)
