"""Pack original CC0 photographic material maps without resampling 4K masters.

Color RGB stays sRGB. Roughness is in alpha. The data texture contains normal X/Y,
height and ambient occlusion, all linear. Lossless data avoids lossy normal errors.
The 2K option is explicitly a lower-memory derivative, not a replacement master.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def linear(a):return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
def build(root:Path=ROOT):
    sources=root/'detail_sources';out=root/'web/detail';out.mkdir(exist_ok=True,parents=True)
    provenance=json.loads((sources/'provenance.json').read_text())
    manifest={'schema':'sandstone-walk-photographic-detail/1','license':'CC0-1.0',
              'geometry_changed':False,'camera_projection_used':False,'textures':{},
              'lighting':'Original 16-band macro irradiance response reused; scan albedo mean-matched. Fine normals, AO and parallax are runtime approximations, not a new full spectral transport bake.'}
    for asset,width,height_mm in [('rock_face_03',2.7,26.0),('sandy_gravel',2.1,16.0)]:
        maps=provenance['assets'][asset]['maps'];folder=sources/asset
        for role,record in maps.items():
            p=root/record['path'];assert p.exists() and sha(p)==record['sha256'],role
        color=Image.open(folder/'diff.jpg').convert('RGB')
        normals=Image.open(folder/'nor_gl.jpg').convert('RGB')
        rough=Image.open(folder/'rough.jpg').convert('L');ao=Image.open(folder/'ao.jpg').convert('L')
        height=Image.open(folder/'disp.png')
        assert all(x.size==(4096,4096) for x in [color,normals,rough,ao,height])
        # Compute mean in linear light, chunked to keep processing memory bounded.
        sums=np.zeros(3)
        for y in range(0,4096,128):
            a=np.asarray(color.crop((0,y,4096,y+128)),dtype=np.float64)/255
            sums+=linear(a).sum(axis=(0,1))
        mean=(sums/(4096*4096)).round(9).tolist()
        h=np.asarray(height,dtype=np.float32)
        if h.ndim==3:h=h[:,:,0]
        scale=65535 if float(h.max())>255 else 255
        height8=Image.fromarray(np.rint(np.clip(h/scale,0,1)*255).astype('uint8'),'L');del h
        cr=Image.merge('RGBA',(*color.split(),rough))
        nd=Image.merge('RGBA',(*normals.split()[:2],height8,ao))
        entry={'source':provenance['assets'][asset], 'width_metres':width,
               'parallax_height_metres':height_mm/1000,'linear_color_mean':mean,
               'normal_convention':'OpenGL +Y, surface-gradient triplanar; RG decoded to [-1,1], positive Z reconstructed',
               'formats':{'color_rough':'RGB sRGB diffuse; alpha linear roughness',
                          'normal_height_ao':'RG normal XY; B linear height; alpha linear AO'},'levels':{}}
        for size in [4096,2048]:
            packed={}
            for role,im in [('color_rough',cr),('normal_height_ao',nd)]:
                tex=im if size==4096 else im.resize((size,size),Image.Resampling.LANCZOS)
                path=out/f'{asset}_{role}_{size}.webp'
                # Albedo is high-quality lossy RGB with exact roughness alpha.
                # Encoded normals/height/occlusion are fully lossless 8-bit maps.
                tex.save(path,'WEBP',lossless=role=='normal_height_ao',quality=96,method=4,exact=True)
                packed[role]={'url':path.relative_to(root).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'width':size,'height':size}
            entry['levels'][str(size)]=packed
        manifest['textures'][asset]=entry
        print(asset,'mean',mean,'files',[(p.name,p.stat().st_size) for p in out.glob(asset+'*.webp')],flush=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':build()
