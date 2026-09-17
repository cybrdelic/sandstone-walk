"""Bind the photographic receiver and render-quality metadata to the base bake.

Does not regenerate or relabel the old spectral transport as a new scan bake.
Run prepare_detail_textures.py once before this step.
"""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build():
    sys.path.insert(0,str(ROOT/'tools'))
    from build_material_shaders import build as base_build
    base_build()
    p=ROOT/'web/detail/manifest.json';manifest=json.loads(p.read_text())
    manifest['shader_sha256']=sha(ROOT/'web/detail/material.glsl')
    manifest['rendering']={'default_maps':4096,'compact_maps':2048,'normal_height_ao_encoding':'lossless 8-bit WebP',
       'albedo_encoding':'quality-96 WebP; exact roughness alpha','default_pixels':'devicePixelRatio, capped at 8,388,608 interactive pixels',
       'stationary_aa_samples':8,'linear_hdr':True,'shadow_maps':{'broad':4096,'near':4096},
       'actual_displacement_geometry':False,'parallax_depth':'authored 26 mm rock / 16 mm sediment, faded between 5 and 10 metres',
       'native_spectral_bake_changed':False,'fine_scale_indirect':'AO approximation; source macro irradiance retained',
       'source_geometry_unchanged':True}
    p.write_text(json.dumps(manifest,indent=2)+'\n')
    p=ROOT/'web/scene.json';scene=json.loads(p.read_text())
    assert scene['meta']['source_mesh_sha256']=='7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79'
    scene['meta']['detail_rendering']={'revision':'0.5.0','manifest':'web/detail/manifest.json',
         'manifest_sha256':sha(ROOT/'web/detail/manifest.json'),'native_bake_retained':True,
         'source_mesh_changed':False,'runtime_receiver':'Photographic triplanar albedo, normal, roughness, parallax and AO',
         'direct_visibility':'Two geometry depth maps with receiver-plane bias and filtered finite-sun approximation',
         'indirect_limitation':'Existing v0.4 macro spectral response; no claim of a fresh scanned-material GI bake'}
    p.write_text(json.dumps(scene,indent=2)+'\n')
    print('Bound detail shader and metadata; native geometry / GI arrays unchanged.')
if __name__=='__main__':build()
