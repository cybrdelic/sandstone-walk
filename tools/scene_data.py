"""Load the shipped immutable geometry/bake buffers. No re-bake is involved."""
from __future__ import annotations
import hashlib,json,zlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def manifest(root:Path=ROOT)->dict:
    return json.loads((root/'web/scene.json').read_text())

def read_asset(entry:dict,dtype:str,components:int,root:Path=ROOT)->np.ndarray:
    path=(root/entry['url']).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Asset escapes repository')
    packed=path.read_bytes()
    if len(packed)!=entry['bytes'] or hashlib.sha256(packed).hexdigest()!=entry['sha256']:
        raise ValueError(f'Asset integrity failure: {entry["url"]}')
    raw=zlib.decompress(packed)
    if len(raw)!=entry['decodedBytes']:raise ValueError('Decoded byte count mismatch')
    array=np.frombuffer(raw,dtype=dtype)
    if array.size%components:raise ValueError('Invalid component count')
    return array.reshape(-1,components)

def indices(mesh:dict,root:Path=ROOT)->np.ndarray:
    if mesh['kind']!='grid':return read_asset(mesh['index'],'<u4',3,root)
    rows,cols=mesh['rows'],mesh['cols']
    a=(np.arange(rows-1,dtype='u4')[:,None]*cols+np.arange(cols-1,dtype='u4')[None,:]).ravel()
    idx=np.concatenate([np.stack([a,a+1,a+cols+1],axis=1),np.stack([a,a+cols+1,a+cols],axis=1)])
    if mesh['flip']:idx=idx[:,::-1].copy()
    return idx

def attributes(mesh:dict,root:Path=ROOT)->dict:
    return {'position':read_asset(mesh['position'],'<f4',3,root),
            'bakeNormal':read_asset(mesh['normal'],'<i2',3,root).astype('f4')/32767,
            'directRadiance':read_asset(mesh['direct'],'<f2',3,root).astype('f4'),
            'indirectRadiance':read_asset(mesh['indirect'],'<f2',3,root).astype('f4'),
            'surface':read_asset(mesh['surface'],'<u2',2,root).astype('f4')/65535}
