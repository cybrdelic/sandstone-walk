"""Resolve LIGHT TRANSPORT, not per-vertex texture color.

Incident 16-band irradiance is projected onto three spectral anchor bases. Each
anchor response is an RGB vector, so the runtime reconstructs receiver color
from a 3x3 transfer matrix AFTER interpolating illumination. Signed basis RGB
values must not be clamped; only physical final radiance is clamped for display.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from scipy.ndimage import map_coordinates
from resolve_solid import filter_grid, filter_rocks, expand_rock_irradiance


def run(work: Path) -> dict:
    baked=work/'material_baked';out=work/'material_resolved';out.mkdir(exist_ok=True)
    layout=json.loads((work/'data/layout.json').read_text())
    gi=np.memmap(baked/'irradiance.raw.f32',dtype='<f4',mode='r',shape=(layout['sites'],16))
    vertices=np.memmap(baked/'vertex_bake.raw.f32',dtype='<f4',mode='r',shape=(layout['vertices'],24))
    basis=np.fromfile(baked/'anchor_basis.f32',dtype='<f4').reshape(16,3)
    matrix=np.fromfile(baked/'spectral_rgb_matrix.f32',dtype='<f4').reshape(16,3)
    assert np.max(np.abs(basis.sum(1)-1))<1e-6 and basis.min()>=0
    report={'schema':'sandstone-world-material-resolve/1','geometry_modified':False,
            'receiver_albedo_baked_into_attributes':False,'receiver_micro_normals_baked':False,
            'method':'16-band irradiance projected to a signed 3x3 spectral anchor response; same positive surface-local GI resolve as v0.3',
            'parts':[],'max_spectral_projection_absolute_error':0.0,'max_half_projection_relative_error':0.0}
    rng=np.random.default_rng(17092026)
    for e in layout['parts']:
        name=e['name'];nv=e['vertices'];start=e['siteOffset'];v=e['vertexOffset']
        p=np.load(work/f'data/{name}.pos.npy');n=np.load(work/f'data/{name}.norm.npy')
        f=np.load(work/f'data/{name}.idx.npy')
        irradiance=gi[start:start+e['sites']].copy()
        if e['kind']=='grid':
            nr,nc=e['rows'],e['cols'];rs,cs=np.array(e['sampleRows']),np.array(e['sampleCols'])
            light=irradiance.reshape(len(rs),len(cs),16)
            ns=n.reshape(nr,nc,3)[rs[:,None],cs[None,:]];ps=p.reshape(nr,nc,3)[rs[:,None],cs[None,:]]
            filtered=filter_grid(light,ns,ps)
            iy=np.interp(np.arange(nr),rs,np.arange(len(rs)));ix=np.interp(np.arange(nc),cs,np.arange(len(cs)))
            irradiance=np.empty((nv,16),dtype='f4')
            for y in range(0,nr,64):
                yy,xx=np.meshgrid(iy[y:y+64],ix,indexing='ij');coord=np.stack([yy.ravel(),xx.ravel()])
                z=np.stack([map_coordinates(filtered[:,:,k],coord,order=1,mode='nearest') for k in range(16)],1)
                irradiance[y*nc:y*nc+len(z)]=z
        else:
            if 'sampleIndices' in e:irradiance=expand_rock_irradiance(irradiance,n,p,e,work)
            irradiance=filter_rocks(irradiance,n,f,p)
        # [vertex, anchor, RGB]; no surface reflectance/roughness is in these columns.
        transfer=np.einsum('nk,kc,ko->nco',irradiance,basis,matrix,optimize=True)/np.pi
        if not np.isfinite(transfer).all() or np.max(np.abs(transfer))>=60000:raise ValueError('Invalid transport matrix')
        ids=np.arange(0,nv,max(1,nv//128));anchors=rng.uniform(.04,.80,(len(ids),3)).astype('f4')
        raw=((irradiance[ids]*(anchors@basis.T))@matrix)/np.pi
        projected=np.einsum('nco,nc->no',transfer[ids],anchors)
        half=np.einsum('nco,nc->no',transfer[ids].astype('f2').astype('f4'),anchors)
        error=float(np.max(np.abs(raw-projected)))
        quant=float(np.max(np.abs(raw-half)/(1+np.abs(raw))))
        if error>5e-5 or quant>1e-3:raise ValueError(('Spectral transport projection error',name,error,quant))
        report['max_spectral_projection_absolute_error']=max(report['max_spectral_projection_absolute_error'],error)
        report['max_half_projection_relative_error']=max(report['max_half_projection_relative_error'],quant)
        n=n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-20)
        normal=np.rint(np.clip(n,-1,1)*32767).astype('<i2')
        visibility=np.clip(vertices[v:v+nv,7],0,1).copy()
        # Retain the original conservative visibility resolve independently of albedo.
        conservative=visibility.copy()
        for aa,bb in [(0,1),(1,2),(2,0)]:
            ia,ib=f[:,aa],f[:,bb];same=np.sum(n[ia]*n[ib],axis=-1)>.86
            np.minimum.at(conservative,ia[same],visibility[ib[same]])
            np.minimum.at(conservative,ib[same],visibility[ia[same]])
        surface=np.stack([conservative,np.full(nv,e['material']/255)],axis=1)
        surface=np.rint(surface*65535).astype('<u2')
        np.save(out/f'{name}.normal.npy',normal);np.save(out/f'{name}.surface.npy',surface)
        for k,key in enumerate(['giR','giG','giB']):np.save(out/f'{name}.{key}.npy',transfer[:,k,:].astype('<f2'))
        report['parts'].append({'name':name,'vertices':nv,'material':e['material'],
            'normal_mean_dot_geometric':float(np.mean(np.sum(normal.astype('f4')/32767*n,axis=1))),
            'transfer_min':float(transfer.min()),'transfer_max':float(transfer.max()),
            'finite':True,'projection_absolute_error':error,'half_relative_error':quant})
        print('RESOLVED',name,nv,error,quant,flush=True)
    (out/'resolve.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);run(p.parse_args().work)
