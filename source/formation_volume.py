"""Sandstone Walk 0.3: closed, eroded canyon masses rather than camera-facing skins.

The existing CYBR GEO Part/Assembly serialization and native triangle writer are
retained. This is authored procedural geology, not a scan or erosion simulation.
All distances here are metres. The two rock masses and terrain apron are closed
oriented volumes; loose fragments are independently closed and bedded into the
actual floor. No reference pixels, displacement images or camera projection.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import trimesh
import shapely

ROOT=Path(__file__).resolve().parent
REPO=ROOT/'cybr-geo'
sys.path[:0]=[str(REPO/'src'),str(REPO/'examples/three_scenes')]
from build_scenes import Builder, grid_faces, vertex_normals, unit, smooth, n3, fractal
from rebuild_scenes import fracture_block
from support_surface import SupportSurface

# These are formation-scale lithologic units, not a stack of identical sinusoids.
BEDS=np.array([-.9,-.12,.39,1.10,1.82,2.93,3.37,4.52,5.83,6.34,7.86,8.61,10.34,12.11,14.24,16.63,19.8,23.5])
RECESS=np.array([.08,.015,-.015,.085,-.050,.035,.12,-.045,.025,.14,-.035,.075,-.04,.04,-.015,.07,.01])
SCARS=[(-1,-.2,2.7,1.2,.72),(1,3.3,3.9,1.5,.80),(-1,10.8,5.0,1.6,.75),
       (1,18.4,3.8,1.8,.58),(-1,23.8,6.7,1.8,.60),(1,30.3,4.2,1.9,.78)]

def field(x,y,z=0.,scale=1.,octaves=3):
    return fractal(np.asarray(x)*scale,np.asarray(y)*scale,np.asarray(z)*scale,octaves)

def center(y):
    y=np.asarray(y)
    # Keep the original entrance axis and first bend; continue rather than wall it off.
    return (.40*np.sin(y*.21)+1.35*np.exp(-((y-18)/6.8)**2)-.9*np.exp(-((y-30)/4.8)**2)
            +6.2*smooth(17,30,y)-3.9*smooth(42,56,y))

def floor(x,y):
    x,y=np.broadcast_arrays(x,y);offset=x-center(y)
    talus=.30*smooth(1.65,3.5,np.abs(offset))*(.92+.18*n3(y*.54,x*.35))
    wash=-.055*np.exp(-((offset+.35*np.sin(y*.37))/.68)**2)
    return (-.14+.010*y+talus+wash+.021*field(x,y,scale=.48,octaves=3)
            +.0045*field(x,y,scale=5.8,octaves=2))

def width(y,z,side):
    y,z=np.broadcast_arrays(y,z)
    b=z+.022*y+.065*field(y*.25+side*6,z*.12,octaves=2)
    w=2.48+.021*z+.24*field(y+side*17,z,scale=.25,octaves=3)
    # Broad differential retreat; spatially finite alcoves and surviving buttresses.
    w+=.085*field(y*.95+side*8,z*.63,octaves=3)
    for yy,zz,wy,wz,d in [(0.,2.5,3.0,2.6,.34),(9.6,7.2,3.0,3.4,.42),(18.8,4.1,3.4,2.9,.37),(32.,8.2,4.0,4.8,.46)]:
        w+=d*np.exp(-((y-yy-side*.6)/wy)**2-((z-zz)/wz)**2)
    w-=.34*np.exp(-((y-12.6+side*.7)/2.7)**2)*smooth(.6,4.,z)
    for i,(a,c) in enumerate(zip(BEDS[:-1],BEDS[1:])):
        bb=b+.032*field(y*1.05+i*1.3,z*.42,octaves=2)
        blend=.035+.028*(i%3)
        mask=smooth(a-blend,a+blend,bb)*(1-smooth(c-blend,c+blend,bb))
        t=np.clip((bb-a)/(c-a),0,1)
        # Resistant lips persist locally, not uniformly along both canyon walls.
        resistance=smooth(-.28,.34,n3(y*.34+1.81*i,side*2.7))
        erosion=RECESS[i]+.034*(1-t)+.061*resistance*np.exp(-t/.14)
        erosion+=.032*field(y*1.7+i,bb*1.0+side,octaves=2)
        w+=mask*erosion
    for j,yy in enumerate([-19.1,-13.8,-8.8,-3.6,1.3,5.7,10.6,15.9,21.2,26.8,32.1,38.4,45.2,52.4]):
        joint=yy+side*.74+.024*z+.13*field(z*.18,j*.81,octaves=2)
        aperture=.058+.018*(j%4)
        active=smooth(.12,.72,n3(z*.23+j*2.8,side*3.3)+.48)
        w+=(.16+.055*(j%3))*np.exp(-((y-joint)/aperture)**2)*active
    for ss,yy,zz,ry,depth in SCARS:
        if ss!=side:continue
        # A bounded planar-ish spall removes material behind a coherent curved edge.
        q=((y-yy)/ry)**2+((z-zz)/(ry*.86))**2
        w+=depth*(1-smooth(.45,1.15,q))*(.82+.18*np.clip((z-zz)/ry,-1,1))
    # Fracture-scale spall texture: centimetres in the mesh, not giant normal-map waves.
    pocket=smooth(.14,.52,field(y*2.1+side*13,z*3.2,octaves=3))
    w+=.028*pocket+.018*np.abs(field(y*1.5+side*7,z*2.4,octaves=2))
    w+=.0060*field(y+side*3,z,scale=6.5,octaves=2)
    return w

def closed_faces(rows,cols):
    a=(np.arange(rows-1)[:,None]*cols+np.arange(cols)[None,:]).ravel()
    b=(a//cols)*cols+(a%cols+1)%cols;c=a+cols;d=(b+cols)
    return np.concatenate([np.stack([a,b,d],1),np.stack([a,d,c],1)]).astype('i4')

def orient(v,f):
    signed=np.einsum('ij,ij->i',v[f[:,0]],np.cross(v[f[:,1]],v[f[:,2]])).sum()/6
    return f if signed>0 else f[:,::-1].copy()

def mass(side,quality=1):
    # Dense near the walkable corridor; no global 8M-vertex resolution bluff.
    y=np.unique(np.r_[np.linspace(-24,-13,61),np.linspace(-13,39,round(1080*quality)),np.linspace(39,59,131)])
    Hgate=smooth(-23,-10,y)*(1-smooth(38,59,y))
    c=center(y)
    w0=width(y,0,side)
    bottom=floor(c+side*w0,y)-.27-.9*(1-Hgate)
    H=Hgate*(13.5+1.5*field(y*.10+side*3,.8,octaves=3)
              +1.2*field(y*.24+side*7,1.9,octaves=2))+.035
    H-=Hgate*(.24*smooth(.10,.40,field(y*1.3+side*7,2.7,octaves=2))+.08*field(y*4.2+side*5,1.2,octaves=2))
    # A physically connected, uneven rim instead of a straight thirteen-metre cut.
    nz=round(480*quality)
    t=np.linspace(0,1,nz)
    zz=bottom[:,None]+H[:,None]*t[None,:]
    yy=np.broadcast_to(y[:,None],zz.shape)
    xx=c[:,None]+side*(width(yy,zz,side)+(.46+.32*field(y*.18+side,2.7,octaves=2))[:,None]*smooth(.83,1.,t)[None,:])
    # Near the buried ends, remove sharp lips so the cap is star-shaped and underground.
    ww=side*(xx-c[:,None]);ww=w0[:,None]+(ww-w0[:,None])*Hgate[:,None]
    # The caprock shoulder stays outside every upper-cliff recess. This prevents
    # the sloping top from crossing an overhanging lip at the crest seam.
    shoulder=int(.91*(nz-1));start_radius=ww[:,shoulder].copy()
    crest_radius=ww[:,shoulder:].max(axis=1)+.15*Hgate
    blend=smooth(0.,1.,np.linspace(0,1,nz-shoulder))
    ww[:,shoulder:]=start_radius[:,None]+(crest_radius-start_radius)[:,None]*blend[None,:]
    xx=c[:,None]+side*ww
    cliff=np.stack([xx,yy,zz],-1)
    rimx=xx[:,-1];rimz=zz[:,-1]
    # A crest, broad weathered shoulder, gullied back slope, and exterior toe.
    no=round(205*quality);u=np.linspace(0,1,no+1)[1:]
    reach=2.4+Hgate**.40*(12.8+1.5*field(y*.12+side*4,3.9,octaves=2))
    ox=rimx[:,None]+side*reach[:,None]*u[None,:]
    oy=np.broadcast_to(y[:,None],ox.shape)
    toe=floor(ox,oy)-.13-.9*(1-Hgate[:,None])
    # A broad caprock bench, broken exterior escarpment, and talus foot -- not a smooth hill.
    shape=(1-.15*smooth(.0,.29,u)-.63*smooth(.31,.72,u)-.22*smooth(.72,1.,u))
    oz=toe+(rimz[:,None]-toe)*shape[None,:]
    # Large drainage channels widen downslope and cut into the plateau margin.
    for j,gy in enumerate([-17.,-10.8,-4.,3.4,10.0,16.7,24.1,31.8,39.4,47.8,54.7]):
        gy+=side*.83
        channel=gy+side*(ox-rimx[:,None])*(.11+.045*(j%3))+.30*field(ox*.30+side*7,j*.8,octaves=2)
        dist=np.abs(oy-channel);spread=.28+1.95*u[None,:]
        profile=np.exp(-(dist/spread)**1.4)
        incise=(2.6+.5*(j%3))*np.sin(np.pi*u)[None,:]**.65*profile*Hgate[:,None]
        oz-=incise
    # Weathered bedding breaks on the exterior slope; each unit remains a coherent ledge.
    bed_outer=oz+.022*oy
    for j,level in enumerate(BEDS[2:-2]):
        local=.022*field(oy*.68+j,ox*.41,octaves=2)
        band=np.exp(-((bed_outer-level)/(.085+.025*(j%3)))**2)
        oz-=.15*band*Hgate[:,None]*np.sin(np.pi*u)[None,:]
    relief=field(ox*.94+side*13,oy*.69,octaves=3)
    oz+=Hgate[:,None]*(.21*relief-.13*smooth(.18,.48,relief))*np.sin(np.pi*u)[None,:]
    oz+=.055*field(ox*3.3,oy*2.9,octaves=2)*np.sin(np.pi*u)[None,:]*Hgate[:,None]
    # Keep the end caps buried even where incised gullies approach the toe.
    oz=np.maximum(oz,floor(ox,oy)-.21-.9*(1-Hgate[:,None]))
    flank=np.stack([ox,oy,oz],-1)
    # Underground return path closes the cross-section; no exposed backface geometry.
    xb=ox[:,-1];base=-4.6+.006*y
    returnpath=np.stack([np.stack([xb,y,base],-1),
                         np.stack([(xb+xx[:,0])*.5,y,base],-1),
                         np.stack([xx[:,0],y,base],-1)],axis=1)
    ring=np.concatenate([cliff,flank,returnpath],axis=1)
    rows,cols,_=ring.shape;v=ring.reshape(-1,3)
    # Buried caps use the same perimeter indices, never intersecting duplicate skins.
    cc=np.array([[(ring[k,:,0].min()+ring[k,:,0].max())*.5,y[k],base[k]+.3] for k in [0,-1]])
    n=len(v);caps=[]
    for arow,mid in [(0,n),(rows-1,n+1)]:
        a=arow*cols+np.arange(cols);b=arow*cols+(np.arange(cols)+1)%cols
        caps.append(np.stack([np.full(cols,mid),b,a],1) if arow==0 else np.stack([np.full(cols,mid),a,b],1))
    v=np.concatenate([v,cc]);f=np.concatenate([closed_faces(rows,cols),*caps]);f=orient(v,f)
    sections=ring[:,:,[0,2]]
    for sampled in [sections,(sections[:-1]+sections[1:])*.5]:
        valid=shapely.is_valid(shapely.polygons(sampled))
        if not valid.all():raise ValueError('Self-crossing rock cross-section: '+str(np.where(~valid)[0][:5]))
    name='West_closed_sandstone_mass' if side<0 else 'East_closed_sandstone_mass' 
    return name,v,f,{'rows':rows,'cols':cols,'baseVertices':rows*cols,'cyclicColumns':True,'kind':'parametric','cliffColumns':nz,'extraVertices':2,'valid_cross_sections':rows*2-1}

def apron(quality=1):
    x=np.unique(np.r_[np.linspace(-34,-7,60),np.linspace(-7,14,round(440*quality)),np.linspace(14,39,60)])
    y=np.unique(np.r_[np.linspace(-31,-14,58),np.linspace(-14,40,round(720*quality)),np.linspace(40,66,84)])
    xx,yy=np.meshgrid(x,y)
    yn=(yy-17.5)/48.5
    weight=smooth(10.,30.,np.abs(xx-2.5))
    taper=1-.56*np.abs(yn)**3.4
    xx=2.5+(xx-2.5)*taper
    xx+=weight*(1.3*field(yy*.15,4.6,octaves=2))
    # Bring the edge toward the subsurface so the finite terrain block is unobtrusive.
    edge=np.maximum(np.abs((np.broadcast_to(x[None,:],xx.shape)-2.5)/36.5),np.abs((yy-17.5)/48.5))
    zz=floor(xx,yy)-2.6*smooth(.81,1.,edge)
    # No repeated ripples drawn everywhere; sparse stream-bar relief is geometry-bound.
    zz+=.0065*field(xx,yy,scale=9.,octaves=2)*(1-smooth(6,10,np.abs(xx-center(yy))))
    assert np.all(np.diff(xx,axis=1)>0), 'Folded apron parameterization'
    grid=np.stack([xx,yy,zz],-1);rows,cols,_=grid.shape;v=grid.reshape(-1,3)
    perimeter=np.r_[np.arange(cols),np.arange(1,rows)*cols+cols-1,
                     (rows-1)*cols+np.arange(cols-2,-1,-1),np.arange(rows-2,0,-1)*cols]
    nv=len(v);skirt=v[perimeter].copy();skirt[:,2]=-6.3
    sidx=nv+np.arange(len(perimeter));a=perimeter;b=np.roll(perimeter,-1);c=sidx;d=np.roll(sidx,-1)
    f=np.concatenate([grid_faces(rows,cols),np.stack([a,c,d],1),np.stack([a,d,b],1),
                      np.stack([np.full(len(perimeter),nv+len(perimeter)),d,c],1)])
    v=np.concatenate([v,skirt,np.array([[2.5,17.5,-6.3]])]);f=orient(v,f.astype('i4'))
    return 'Closed_alluvial_terrain',v,f,{'rows':rows,'cols':cols,'baseVertices':rows*cols,'cyclicColumns':False,'kind':'parametric','extraVertices':len(v)-rows*cols}

class Deposits:
    def __init__(self,b,support):
        self.support=support
        self.b=b;self.hash={};self.records=[];self.rejected=0
        self.yy=np.linspace(-26,65,2400)
        self.ww={side:width(self.yy,.20,side) for side in [-1,1]}
    def foot(self,y,side):return float(np.interp(y,self.yy,self.ww[side]))
    def add(self,x,y,r,label,family='slab',sub=2,burial=.14):
        if abs(x-center(y))>self.foot(y,1 if x>center(y) else -1)-.08:
            self.rejected+=1;return False
        cell=(int(np.floor(x/.5)),int(np.floor(y/.5)));checkradius=int(np.ceil((r+1.2)/.5))
        for a in range(cell[0]-checkradius,cell[0]+checkradius+1):
            for c in range(cell[1]-checkradius,cell[1]+checkradius+1):
                for px,py,pr in self.hash.get((a,c),[]):
                    if np.hypot(px-x,py-y)<.83*(r+pr):self.rejected+=1;return False
        rng=self.b.rng;scale=(r,r*rng.uniform(.58,1.0),r*rng.uniform(.22,.50))
        v,f=fracture_block(int(rng.integers(1,2**30)),scale,family,sub)
        # Settle the full footprint onto the actual floor, then bury slightly.
        support=self.support.height(np.c_[x+v[:,0],y+v[:,1]]);height=float(np.ptp(v[:,2]))
        vertical=float(np.max(support-v[:,2]))-burial*height
        v+=np.array([x,y,vertical]);gap=v[:,2]-self.support.height(v[:,:2])
        self.b.add(label,v,f,mat=2)
        self.hash.setdefault(cell,[]).append((x,y,r))
        self.records.append({'group':label,'x':float(x),'y':float(y),'scale_m':list(map(float,scale)),
            'minimum_vertex_floor_gap_m':float(gap.min()),'maximum_vertex_floor_gap_m':float(gap.max()),
            'burial_fraction':float(burial),'vertices':len(v),'triangles':len(f)})
        return True

def validate_solid(name,v,f):
    mesh=trimesh.Trimesh(v,f,process=False)
    # Full topology/volume check on the serialized float32 mesh, not just a nominal shape.
    area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)*.5
    edges=np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1)
    edge_codes=(edges[:,0].astype('u8')<<32)|edges[:,1].astype('u8')
    _,count=np.unique(edge_codes,return_counts=True)
    r={'name':name,'vertices':len(v),'triangles':len(f),'boundary_edges':int(np.sum(count==1)),
       'nonmanifold_edges':int(np.sum(count!=2)),'degenerate_triangles':int(np.sum(area<1e-12)),
       'minimum_triangle_area_m2':float(area.min()),'watertight':bool(mesh.is_watertight),
       'winding_consistent':bool(mesh.is_winding_consistent),'volume_m3':float(mesh.volume)}
    assert r['watertight'] and r['winding_consistent'] and r['volume_m3']>0 and not r['degenerate_triangles'],r
    return r

def build(out:Path,seed=20260917,quality=1.):
    b=Builder('canyon',seed);design={};solid_reports=[];start=time.monotonic()
    for call,mat in [(lambda:apron(quality),0),(lambda:mass(-1,quality),1),(lambda:mass(1,quality),1)]:
        name,v,f,hints=call();v=v.astype('f4').astype('f8')
        report=validate_solid(name,v,f);solid_reports.append(report)
        print('SOLID',round(time.monotonic()-start,2),json.dumps(report),flush=True)
        b.add(name,v,f,mat=mat);design[name]=hints
        if mat==0:support=SupportSurface(v,hints['rows'],hints['cols'])
    deposits=Deposits(b,support)
    for x,y,r in [(-1.77,-2.3,.58),(2.02,1.8,.48),(-1.85,5.5,.64),(2.10,10.1,.59),(-1.75,20.5,.67)]:
        deposits.add(float(x+center(y)),y,r,'Jointed_talus_blocks',sub=3,burial=.19)
    rng=b.rng
    for side,yy,_,ry,_ in SCARS:
        for i in range(185):
            y=float(rng.normal(yy,ry*.80));edge=float(center(y)+side*deposits.foot(y,side));r=float(np.exp(rng.uniform(np.log(.028),np.log(.23))))
            x=edge-side*(r*.6+rng.exponential(.45))
            if abs(x-center(y))<1.15:continue
            deposits.add(x,y,r,'Bedded_rockfall_fragments',sub=1 if r<.065 else 2,burial=float(rng.uniform(.12,.28)))
    for i in range(2900):
        y=float(rng.uniform(-13,49));x=float(center(y)+rng.uniform(-2.6,2.6));r=float(np.exp(rng.uniform(np.log(.016),np.log(.072))))
        if rng.uniform()>.045+.67*smooth(.65,2.6,abs(x-center(y))):continue
        deposits.add(x,y,r,'Wash_gravel',family='rounded',sub=1,burial=.28)
    cfg={'scene':'canyon','title':'Sandstone Passage — Closed Landforms',
         'camera':[-.42,-5.8,1.56],'target':[.15,9.8,3.12],'fov':68,
         'sun':[-.24,-.33,.913],'exposure':2.5,'white_balance':5900,'sun_scale':1.,'sky_scale':.95}
    report=b.finish(out,cfg,False)
    design.update(schema='sandstone-walk-closed-formation/1',version='0.3.0',seed=seed,quality=quality,
      solid_checks=solid_reports,deposit_count=len(deposits.records),rejected_deposit_candidates=deposits.rejected,
      deposits=deposits.records,far_backdrop_removed=True,outer_mass_geometry=True,geological_simulation=False,
      minimum_floor_gap_m=min(r['minimum_vertex_floor_gap_m'] for r in deposits.records),build_seconds=time.monotonic()-start)
    (out/'design.json').write_text(json.dumps(design,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--quality',type=float,default=1.);p.add_argument('--seed',type=int,default=20260917);a=p.parse_args()
    if not .25<=a.quality<=2.:p.error('quality must be in [.25,2]')
    build(a.out,a.seed,a.quality)
