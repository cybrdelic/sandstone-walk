"""Check every loose fragment against the actual decoded floor triangles."""
from pathlib import Path
import hashlib,json,zlib,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
from support_surface import SupportSurface

def positions(m):
    e=m['position'];raw=(ROOT/e['url']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==e['sha256']
    return np.frombuffer(zlib.decompress(raw),'<f4').reshape(-1,3).astype('f8')

def check_support(b,design):
    by_name={m['name']:m for m in b['meshes']}
    d=design['Closed_alluvial_terrain']
    floor=SupportSurface(positions(by_name['Closed_alluvial_terrain']),d['rows'],d['cols'])
    group_names={r['group'] for r in design['deposits']}
    all_positions={name:positions(by_name[name]) for name in group_names}
    offsets={name:0 for name in group_names};records=[]
    for i,r in enumerate(design['deposits']):
        name=r['group'];start=offsets[name];end=start+r['vertices'];v=all_positions[name][start:end];offsets[name]=end
        assert len(v)==r['vertices']
        gap=v[:,2]-floor.height(v[:,:2])
        records.append({'piece':i,'group':name,'min_gap_m':float(gap.min()),'max_gap_m':float(gap.max())})
    assert all(offsets[name]==len(all_positions[name]) for name in group_names)
    floating=[x for x in records if x['min_gap_m']>1e-6]
    buried=[x for x in records if x['max_gap_m']<0]
    assert not floating,('Unsupported fragments',floating)
    assert not buried,('Completely buried fragments',buried)
    return {'method':'Vertical barycentric projection at every fragment vertex onto actual serialized floor triangles',
            'pieces':len(records),'floating_pieces':len(floating),'fully_buried_pieces':len(buried),
            'contact_tolerance_m':1e-6,'maximum_minimum_gap_m':max(x['min_gap_m'] for x in records),
            'records':records,'limits':'Geometric contact screen, not rigid-body stability or a complete solid-intersection proof.'}

if __name__=='__main__':
    b=json.loads((ROOT/'web/scene.json').read_text());design=json.loads((ROOT/'evidence/formation/design.json').read_text())
    r=check_support(b,design);r['source_mesh_sha256']=b['meta']['source_mesh_sha256']
    (ROOT/'evidence/formation/support_surface.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
