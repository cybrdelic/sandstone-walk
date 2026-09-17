"""Render the actual delivered buffers and shaders in standalone OpenGL ES.

This renderer is NOT browser execution. Its evidence explicitly names the entry
point, shader hashes and packed-asset hashes. Browser tests are separate.
"""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,sys,time,zlib
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
from egl_runtime import GL
from verify_solid import indices

def matrix(eye,target,width,height):
    e=np.array(eye,float);f=np.array(target,float)-e;f/=np.linalg.norm(f);right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,f)
    view=np.eye(4);view[0,:3]=right;view[1,:3]=up;view[2,:3]=-f;view[:3,3]=-view[:3,:3]@e
    t=np.tan(np.deg2rad(34));near=.02;far=600
    projection=np.array([[1/t,0,0,0],[0,width/height/t,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]])
    return projection@view

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--baseline',action='store_true');ap.add_argument('--width',type=int,default=1440);ap.add_argument('--height',type=int,default=960);ap.add_argument('--out',type=Path);a=ap.parse_args()
    out=a.out or ROOT/'evidence/materials'/('before_native' if a.baseline else 'after_native');out.mkdir(exist_ok=True,parents=True)
    scene=json.loads((ROOT/('evidence/materials/baseline_scene.json' if a.baseline else 'web/scene.json')).read_text());meta=scene['meta']
    shaderpath=ROOT/('source' if a.baseline else 'web')
    def read(e,dtype,n):
        raw=(ROOT/e['url']).read_bytes();assert hashlib.sha256(raw).hexdigest()==e['sha256'];return np.frombuffer(zlib.decompress(raw),dtype=dtype).reshape(-1,n)
    g=GL(a.width,a.height,gles=True);start=time.monotonic()
    vs=(shaderpath/'surface.vert.glsl').read_text();fs=(shaderpath/'surface.frag.glsl').read_text()
    p=g.program('#version 300 es\n'+vs,'#version 300 es\n'+fs);meshes=[];total=0
    for m in scene['meshes']:
        attrs={'position':read(m['position'],'<f4',3),'bakeNormal':read(m['normal'],'<i2',3).astype('f4')/32767,'surface':read(m['surface'],'<u2',2).astype('f4')/65535}
        if a.baseline:attrs.update(directRadiance=read(m['direct'],'<f2',3),indirectRadiance=read(m['indirect'],'<f2',3))
        else:
            for key in ['giR','giG','giB']:attrs[key]=read(m[key],'<f2',3)
        idx=indices(m) if m['kind']=='grid' else read(m['index'],'<u4',3)
        meshes.append(g.upload(p,attrs,idx));total+=len(idx);print('UPLOAD',m['name'],flush=True)
    if total!=5029800:raise ValueError('Mesh count mismatch')
    sky=g.program('#version 300 es\n'+(ROOT/'web/sky.vert.glsl').read_text(),'#version 300 es\n'+(ROOT/'web/sky.frag.glsl').read_text())
    skyobj=g.upload(sky,{'position':np.array([[-1,-1,0],[3,-1,0],[-1,3,0]],'f4')},np.array([0,1,2],'u4'))
    gen=g.fn('glGenTextures',None,[C.c_int,C.POINTER(C.c_uint)]);bind=g.fn('glBindTexture',None,[C.c_uint,C.c_uint]);param=g.fn('glTexParameteri',None,[C.c_uint,C.c_uint,C.c_int]);image=g.fn('glTexImage2D',None,[C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]);active=g.fn('glActiveTexture',None,[C.c_uint])
    rgba=read(scene['sky']['data'],'<f2',4);tex=C.c_uint();gen(1,C.byref(tex));active(0x84C0);bind(0x0DE1,tex.value)
    for k,v in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x2901),(0x2803,0x812F)]:param(0x0DE1,k,v)
    image(0x0DE1,0,0x881A,scene['sky']['width'],scene['sky']['height'],0,0x1908,0x140B,C.c_void_p(rgba.ctypes.data));g.UseProgram(sky);g.uniform(sky,'uSky',0)
    sun=np.array(meta['sun']);sun/=np.linalg.norm(sun)
    for program in [p,sky]:
        g.UseProgram(program)
        for name,value in [('uSun',sun),('uSolar',meta['solar_rgb']),('uWhite',meta['display_white_rgb']),('uExposure',float(meta['exposure']))]:g.uniform(program,name,value)
    if not a.baseline:
        mat3=g.fn('glUniformMatrix3fv',None,[C.c_int,C.c_int,C.c_ubyte,C.c_void_p]);g.UseProgram(p)
        for name,value in [('uRGBToAnchors',np.array(meta['rgb_to_anchors'])),('uSolarResponse',np.array(meta['solar_anchor_response']).T)]:
            arr=np.ascontiguousarray(value.T,dtype='f4');mat3(g.GetUniformLocation(p,name.encode()),1,0,C.c_void_p(arr.ctypes.data))
    poses=[('hero',[-.42,-5.8,1.56],[.15,9.8,3.12]),('forward',[.25,4.8,1.6],[1.2,16,2.6]),
        ('left_close',[-.70,-2.8,1.9],[-2.65,-1.,2.10]),('right_close',[.70,5.0,1.8],[3.15,6.8,2.15]),
        ('ground',[.1,-2,1.20],[.3,-.55,-.1]),('talus',[-.75,-2.4,.95],[-2.,-1.0,.24]),
        ('orbit',[70,-86,68],[5,16,4])]
    results=[];g.Viewport(0,0,a.width,a.height);g.Disable(0x0B44)
    for name,eye,target in poses:
        modes=[(0,'beauty')]
        if name in ['left_close','right_close','ground'] and not a.baseline:modes.extend([(5,'albedo'),(6,'mapping')])
        for mode,label in modes:
            g.ClearColor(0,0,0,1);g.Clear(0x4000|0x0100);vp=matrix(eye,target,a.width,a.height)
            g.Disable(0x0B71);g.UseProgram(sky);g.uniform(sky,'uInvVP',np.linalg.inv(vp));g.uniform(sky,'uEye',eye);g.draw(skyobj)
            g.Enable(0x0B71);g.UseProgram(p);g.uniform(p,'uVP',vp);g.uniform(p,'uEye',eye);g.uniform(p,'uMode',mode)
            for mesh in meshes:g.draw(mesh)
            pixels=g.pixels();error=g.GetError()
            if error:raise RuntimeError('GLES error '+hex(error))
            path=out/(name+'_'+label+'.png');Image.fromarray(pixels).convert('RGB').save(path)
            results.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'eye':eye,'target':target,'mode':mode,'triangles':total,'gl_error':error})
            print('RENDER',path,flush=True)
    report={'result':'PASS','entrypoint':'Standalone OpenGL ES; NOT a browser capture','baseline':a.baseline,
        'shader_sha256':{'vertex':hashlib.sha256(vs.encode()).hexdigest(),'fragment':hashlib.sha256(fs.encode()).hexdigest()},
        'source_mesh_sha256':meta['source_mesh_sha256'],'size':[a.width,a.height],
        'renderer':g.GetString(0x1F01).decode(),'version':g.GetString(0x1F02).decode(),'seconds':time.monotonic()-start,'captures':results}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
