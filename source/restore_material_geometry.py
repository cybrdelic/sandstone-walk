"""Restore the unchanged native scene from versioned geometric inputs.

Materials must not trigger procedural remeshing. Browser positions/indices are
reused verbatim; frozen full-precision GEOMETRIC normals and sampling indices
restore the native input streams, whose original SHA-256 values must match.
"""
from __future__ import annotations
import argparse,hashlib,io,json,struct,zlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
EXPECTED_MESH='7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79'

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def restore(work:Path):
    work=work.resolve();data=work/'data';data.mkdir(parents=True,exist_ok=True)
    frozen=ROOT/'source/material_geometry';manifest=json.loads((frozen/'manifest.json').read_text())
    if manifest['mesh_sha256']!=EXPECTED_MESH:raise ValueError('Unexpected frozen scene identity')
    def read_frozen(name):
        path=(frozen/name).resolve()
        if not path.is_relative_to(frozen.resolve()):raise ValueError('Invalid frozen path')
        entry=manifest['files'][name]
        if digest(path)!=entry['sha256']:raise ValueError('Frozen file checksum mismatch: '+name)
        raw=path.read_bytes()
        if name.endswith('.deflate'):
            raw=zlib.decompress(raw)
            if len(raw)!=entry['decoded_bytes'] or hashlib.sha256(raw).hexdigest()!=entry['decoded_sha256']:
                raise ValueError('Decoded frozen file checksum mismatch: '+name)
        return raw
    def read_asset(entry):
        path=(ROOT/entry['url']).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Invalid geometry asset path')
        if digest(path)!=entry['sha256']:raise ValueError('Geometry asset checksum mismatch')
        raw=zlib.decompress(path.read_bytes())
        if len(raw)!=entry['decodedBytes']:raise ValueError('Geometry asset length mismatch')
        return raw
    layout=json.loads(read_frozen('layout.json'));report=json.loads(read_frozen('geometry_report.json'))
    scene=json.loads((ROOT/'web/scene.json').read_text())
    if scene['meta']['source_mesh_sha256']!=EXPECTED_MESH:raise ValueError('Scene no longer matches the material-only baseline')
    if layout['triangles']!=5029800 or layout['vertices']!=2526592:raise ValueError('Unexpected pinned geometry counts')
    if len(layout['parts'])!=len(scene['meshes']):raise ValueError('Geometry part count mismatch')
    output=work/'native_scene/canyon/scene.meshbin';output.parent.mkdir(parents=True,exist_ok=True)
    part_checks=[]
    with output.open('wb') as native,(data/'sites.bin').open('wb') as sites,(data/'vertices.bin').open('wb') as vertices:
        native.write(struct.pack('<I',layout['triangles']))
        sites.write(b'SIT1'+struct.pack('<I',layout['sites']))
        vertices.write(b'VTX1'+struct.pack('<I',layout['vertices']))
        for group,(mesh,entry) in enumerate(zip(scene['meshes'],layout['parts'])):
            name=entry['name'];nv=entry['vertices']
            if mesh['name']!=name or mesh['vertices']!=nv:raise ValueError('Geometry ordering mismatch')
            pos=np.frombuffer(read_asset(mesh['position']),dtype='<f4').reshape(nv,3)
            normals=np.load(io.BytesIO(read_frozen(name+'.norm.npy.deflate')),allow_pickle=False)
            if normals.shape!=pos.shape or not np.isfinite(normals).all():raise ValueError('Invalid geometric normals')
            if np.max(np.abs(np.linalg.norm(normals,axis=1)-1))>1e-4:raise ValueError('Geometric normals are not normalized')
            if mesh['kind']=='grid':
                rows,cols=mesh['rows'],mesh['cols'];a=np.arange((rows-1)*cols,dtype=np.uint32).reshape(rows-1,cols)[:,:-1].ravel()
                faces=np.concatenate([np.stack([a,a+1,a+cols+1],1),np.stack([a,a+cols+1,a+cols],1)])
                if mesh['flip']:faces=faces[:,::-1]
            else:faces=np.frombuffer(read_asset(mesh['index']),dtype='<u4').reshape(-1,3)
            faces=np.ascontiguousarray(faces,dtype='<u4')
            if len(faces)!=entry['triangles'] or faces.max()>=nv:raise ValueError('Topology mismatch')
            np.save(data/(name+'.pos.npy'),pos);np.save(data/(name+'.norm.npy'),normals);np.save(data/(name+'.idx.npy'),faces)
            raw=np.c_[pos,normals,np.full(nv,entry['material'])].astype('<f4');vertices.write(raw.tobytes())
            if entry['kind']=='grid':
                ids=(np.array(entry['sampleRows'])[:,None]*entry['cols']+np.array(entry['sampleCols'])[None,:]).ravel()
            elif 'sampleIndices' in entry:
                site_raw=read_frozen(entry['sampleIndices']+'.deflate');(data/entry['sampleIndices']).write_bytes(site_raw)
                ids=np.load(io.BytesIO(site_raw),allow_pickle=False)
            else:ids=np.arange(nv)
            if len(ids)!=entry['sites'] or ids.min()<0 or ids.max()>=nv:raise ValueError('Irradiance sample map mismatch')
            sites.write(raw[ids].tobytes())
            for offset in range(0,len(faces),30000):
                ff=faces[offset:offset+30000];out=np.empty((len(ff),20),dtype='<f4')
                out[:,:9]=pos[ff].reshape(-1,9);out[:,9:18]=normals[ff].reshape(-1,9)
                out[:,18]=entry['material'];out[:,19]=group;native.write(out.tobytes())
            part_checks.append({'name':name,'positions_from_existing_assets':True,'triangles':len(faces),
                                'position_sha256':hashlib.sha256(pos.tobytes()).hexdigest(),
                                'topology_sha256':hashlib.sha256(faces.tobytes()).hexdigest()})
    for path,expected in [(output,manifest['mesh_sha256']),(data/'vertices.bin',manifest['vertices_sha256']),(data/'sites.bin',manifest['sites_sha256'])]:
        if digest(path)!=expected:raise ValueError('Restoration is not byte-identical: '+str(path))
    (data/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    (work/'geometry_report.json').write_text(json.dumps(report,indent=2)+'\n')
    proof={'schema':'sandstone-material-geometry-restoration/1','result':'PASS','source_mesh_sha256':EXPECTED_MESH,
           'mode':'Frozen native input restoration, not a new procedural build',
           'native_mesh_bytes_identical':True,'sample_sites_bytes_identical':True,'vertex_sites_bytes_identical':True,
           'frozen_manifest_sha256':digest(frozen/'manifest.json'),'parts':part_checks}
    (work/'geometry_restoration.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,indent=2),flush=True)
    return proof

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);a=p.parse_args();restore(a.work)
