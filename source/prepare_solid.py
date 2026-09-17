"""Prepare actual regenerated vertices and surface irradiance sample locations.
No images, view camera, or hand-colored probes are used. GPL-2.0-only.
"""
from pathlib import Path
import argparse,json,struct,hashlib
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from solid_geometry import floor_height

def feature_space(p,n):
    center=(p.min(0)+p.max(0))*.5
    scale=max(float(np.linalg.norm(p.max(0)-p.min(0))),1e-5)
    return np.c_[(p-center)/scale*2.0,n*.85].astype('f8')


def sparse_rock_sites(p,n,f):
    # Distinct rocks never share vertices, samples, or interpolation weights.
    edges=np.r_[f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]
    graph=coo_matrix((np.ones(len(edges),dtype='u1'),(edges[:,0],edges[:,1])),shape=(len(p),len(p))).tocsr()
    count,labels=connected_components(graph,directed=False)
    ordered=np.argsort(labels,kind='stable');sizes=np.bincount(labels);offsets=np.r_[0,np.cumsum(sizes)]
    samples=[];groups=[];site_offset=0
    for label in range(count):
        ids=ordered[offsets[label]:offsets[label+1]]
        if not np.all(np.diff(ids)==1):raise ValueError('Rock vertices must be contiguous for the stored interpolation map')
        v0=int(ids[0]);pp=p[ids].astype('f8');nn=n[ids].astype('f8');feature=feature_space(pp,nn)
        budget=min(len(ids),max(48,int(np.sqrt(len(ids))*3)))
        d=np.full(len(ids),np.inf);selected=[];next_id=int(np.argmax(pp[:,0]))
        for _ in range(budget):
            selected.append(next_id);q=feature-feature[next_id];d=np.minimum(d,np.einsum('ij,ij->i',q,q));next_id=int(np.argmax(d))
        # Preserve extra samples along visible contact regions of the larger talus.
        if np.max(np.ptp(pp,axis=0))>.18:
            clearance=pp[:,2]-floor_height(pp[:,0],pp[:,1])
            selected.extend(np.flatnonzero(np.abs(clearance)<.010).tolist())
        selected=np.unique(selected).astype('i8');samples.extend((selected+v0).tolist())
        groups.append({'vertex_start':v0,'vertices':len(ids),'site_start':site_offset,'sites':len(selected)})
        site_offset+=len(selected)
    return np.array(samples,dtype='i8'),groups


def run(work:Path):
    directory=work/'data';directory.mkdir(exist_ok=True)
    assembly=work/'native_scene/canyon/assembly'
    info=json.loads((assembly/'scene.json').read_text())
    charts={p['name']:p for p in json.loads((work/'charts.json').read_text())['charts']}
    layout=[];nv=ns=0
    with np.load(assembly/'meshes.npz',allow_pickle=False) as z,(directory/'vertices.bin').open('wb') as vo,(directory/'sites.bin').open('wb') as so:
        vo.write(b'VTX1'+struct.pack('<I',0));so.write(b'SIT1'+struct.pack('<I',0))
        for p in info['parts']:
            name=p['name'];key=p['key'];v=(z[key+'_vertices']*.001).astype('<f4');n=z[key+'_normals'].astype('<f4');f=z[key+'_faces'].astype('<u4')
            if not np.isfinite(v).all() or not np.isfinite(n).all():raise ValueError('Nonfinite geometry')
            if f.min()<0 or f.max()>=len(v):raise ValueError('Invalid topology')
            np.save(directory/(name+'.pos.npy'),v);np.save(directory/(name+'.norm.npy'),n);np.save(directory/(name+'.idx.npy'),f)
            data=np.c_[v,n,np.full(len(v),p['material'])].astype('<f4');vo.write(data.tobytes())
            ent={'name':name,'material':p['material'],'vertices':len(v),'triangles':len(f),'vertexOffset':nv,'siteOffset':ns}
            c=charts[name]
            if c['kind']=='grid':
                rows,cols,stride=c['rows'],c['cols'],c['sample_stride']
                if rows*cols!=len(v):raise ValueError('Chart grid mismatch')
                ri=np.unique(np.r_[np.arange(0,rows,stride),rows-1]);ci=np.unique(np.r_[np.arange(0,cols,stride),cols-1])
                ids=(ri[:,None]*cols+ci[None,:]).ravel()
                ent.update(kind='grid',rows=rows,cols=cols,flip=c['flip'],sampleRows=ri.tolist(),sampleCols=ci.tolist())
            else:
                ent.update(kind='indexed')
                if name in ['Joint_cut_talus','Channel_lag_gravel']:
                    ids,groups=sparse_rock_sites(v,n,f)
                    np.save(directory/(name+'.siteids.npy'),ids)
                    ent.update(sampleIndices=name+'.siteids.npy',componentSamples=groups,
                               sampling='Deterministic spatial/normal farthest samples within each closed rock; dense large-talus contact band')
                else:ids=np.arange(len(v))

            so.write(data[ids].tobytes());ent['sites']=len(ids);layout.append(ent);nv+=len(v);ns+=len(ids)
            print(name,len(v),len(f),len(ids),flush=True)
        vo.seek(4);vo.write(struct.pack('<I',nv));so.seek(4);so.write(struct.pack('<I',ns))
    meta={'parts':layout,'vertices':nv,'sites':ns,'triangles':sum(p['triangles'] for p in layout)}
    (directory/'layout.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('TOTAL',nv,ns,meta['triangles'],flush=True)
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
