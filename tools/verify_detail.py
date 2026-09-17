"""Check source and texture integrity independently from visual acceptance."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from PIL import Image,features
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    original=json.loads((ROOT/'tests/fixtures/v0_4_scene.json').read_text())
    current=json.loads((ROOT/'web/scene.json').read_text())
    assert current['meshes']==original['meshes'],'A mesh descriptor / position / index / irradiance asset changed'
    assert current['sky']==original['sky'],'Native sky changed'
    entries=[]
    for m in current['meshes']:
        for key in ['position','normal','giR','giG','giB','surface','index']:
            if key in m:
                e=m[key];assert sha(ROOT/e['url'])==e['sha256'];entries.append(e['sha256'])
    assert sum(m['triangles'] for m in current['meshes'])==5029800
    assert sum(m['vertices'] for m in current['meshes'])==2526592
    manifest=json.loads((ROOT/'web/detail/manifest.json').read_text())
    assert manifest['shader_sha256']==sha(ROOT/'web/detail/material.glsl')
    dimensions=[]
    for name,asset in manifest['textures'].items():
        assert asset['width_metres']>0
        for size,maps in asset['levels'].items():
            assert set(maps)=={'color_rough','normal_height_ao'}
            for role,e in maps.items():
                p=ROOT/e['url'];assert sha(p)==e['sha256'];assert p.stat().st_size==e['bytes']
                with Image.open(p) as im:
                    assert im.size==(int(size),int(size)) and im.mode=='RGBA'
                    sample=np.asarray(im.resize((256,256)))
                    assert sample[:,:,:3].std()>8,'Untextured / blank material'
                    dimensions.append({'asset':name,'role':role,'dimensions':list(im.size),'sha256':e['sha256']})
    # The sun disk exceeds unscaled half-float range. Fixed power-of-two storage
    # exposure keeps it finite while the presentation pass restores its energy.
    solar=max(current['meta']['solar_rgb'])/.000067928
    assert solar*.25 < 65504 and solar>65504
    report={'result':'PASS','source_mesh_sha256':current['meta']['source_mesh_sha256'],
      'positions_indices_normals_macro_GI_and_sky_unchanged':True,'triangles':5029800,'vertices':2526592,
      'verified_mesh_attributes':len(entries),'maps':dimensions,'manifest_sha256':sha(ROOT/'web/detail/manifest.json'),
      'shader_sha256':sha(ROOT/'web/detail/material.glsl'),'storage_exposure':.25,
      'sun_disk_max_unscaled':solar,'sun_disk_max_scaled':solar*.25,
      'fresh_spectral_bake':False,'visual_acceptance':'Not established by integrity checks'}
    out=ROOT/'build/detail';out.mkdir(parents=True,exist_ok=True)
    (out/'integrity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
