"""Render actual moving-camera GLES frames from the shipped exact geometry and bake.

This is a native Mesa execution of the viewer shaders, NOT browser capture.
No image generation, image warping, frame interpolation, or reference-image projection.
"""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
from scene_data import ROOT,manifest,read_asset,indices,attributes
sys.path.insert(0,str(ROOT/'source'))
from egl_runtime import GL

def camera_matrix(eye,target,w,h):
    eye=np.asarray(eye,dtype=float);f=np.asarray(target,dtype=float)-eye;f/=np.linalg.norm(f)
    right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,f)
    view=np.eye(4);view[0,:3]=right;view[1,:3]=up;view[2,:3]=-f;view[:3,3]=-view[:3,:3]@eye
    tan=math.tan(math.radians(34));near=.02;far=180
    proj=np.array([[1/tan,0,0,0],[0,w/h/tan,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]])
    return proj@view

def pose(i,count):
    a=2*math.pi*i/count;s=(1-math.cos(a))/2
    eye=[-.42+.38*math.sin(a),-5.8+3.8*s,1.56+.045*math.sin(2*a)]
    target=[eye[0]+.57+.78*math.sin(a),eye[1]+15.6,eye[2]+1.56+.28*math.sin(a)]
    return eye,target

def run():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--width',type=int,default=1200);ap.add_argument('--height',type=int,default=800)
    ap.add_argument('--frames',type=int,default=144);ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--out',type=Path,default=ROOT/'build/frames')
    args=ap.parse_args()
    if min(args.width,args.height,args.frames,args.fps)<1:ap.error('All numeric parameters must be positive')
    args.out.mkdir(parents=True,exist_ok=True);start=time.monotonic();data=manifest()
    gl=GL(args.width,args.height,gles=True);prefix='#version 300 es\n'
    def program(stem):return gl.program(prefix+(ROOT/f'web/{stem}.vert.glsl').read_text(),prefix+(ROOT/f'web/{stem}.frag.glsl').read_text())
    surf=program('surface');sky=program('sky');meshes=[];total=0
    for m in data['meshes']:
        meshes.append(gl.upload(surf,attributes(m),indices(m)));total+=m['triangles'];print('UPLOADED',m['name'],flush=True)
    sky_mesh=gl.upload(sky,{'position':np.array([[-1,-1,0],[3,-1,0],[-1,3,0]],'f4')},np.array([0,1,2],'u4'))
    rgba=np.ascontiguousarray(read_asset(data['sky']['data'],'<f2',4));sw=data['sky']['width'];sh=data['sky']['height']
    gen=gl.fn('glGenTextures',None,[C.c_int,C.POINTER(C.c_uint)])
    bind=gl.fn('glBindTexture',None,[C.c_uint,C.c_uint]);param=gl.fn('glTexParameteri',None,[C.c_uint,C.c_uint,C.c_int])
    image=gl.fn('glTexImage2D',None,[C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p])
    tex=C.c_uint();gen(1,C.byref(tex));bind(0x0DE1,tex.value)
    for key,val in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x2901),(0x2803,0x812F)]:param(0x0DE1,key,val)
    image(0x0DE1,0,0x881A,sw,sh,0,0x1908,0x140B,C.c_void_p(rgba.ctypes.data))
    sun=np.asarray(data['meta']['sun'],float);sun/=np.linalg.norm(sun)
    for p in [surf,sky]:
        gl.UseProgram(p)
        for key,value in [('uSun',sun),('uSolar',data['meta']['solar_rgb']),('uWhite',data['meta']['display_white_rgb']),('uExposure',float(data['meta']['exposure']))]:gl.uniform(p,key,value)
    gl.UseProgram(sky);gl.uniform(sky,'uSky',0)
    gl.UseProgram(surf);gl.uniform(surf,'uMode',0)
    gl.Disable(0x0B44);gl.Viewport(0,0,args.width,args.height)
    receipts=[]
    for i in range(args.frames):
        eye,target=pose(i,args.frames);vp=camera_matrix(eye,target,args.width,args.height)
        gl.ClearColor(0,0,0,1);gl.Clear(0x4000|0x0100)
        gl.Disable(0x0B71);gl.UseProgram(sky);gl.uniform(sky,'uInvVP',np.linalg.inv(vp));gl.uniform(sky,'uEye',eye);gl.draw(sky_mesh)
        gl.Enable(0x0B71);gl.UseProgram(surf);gl.uniform(surf,'uVP',vp);gl.uniform(surf,'uEye',eye)
        for m in meshes:gl.draw(m)
        pixels=gl.pixels()[:,:,:3];error=gl.GetError()
        if error:raise RuntimeError(f'Frame {i}: GL error {hex(error)}')
        output=args.out/f'{i:04d}.png';Image.fromarray(pixels).save(output,compress_level=2)
        receipts.append({'index':i,'eye':eye,'target':target,'rgb_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'png_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'gl_error':error})
        if i%12==0:print('FRAME',i,'elapsed',round(time.monotonic()-start,2),flush=True)
    result={'schema':'sandstone-walk-preview/1','renderer':gl.GetString(0x1F01).decode(),'context':gl.GetString(0x1F02).decode(),
            'frame_count':args.frames,'unique_source_frames':len({r['rgb_sha256'] for r in receipts}),
            'width':args.width,'height':args.height,'fps':args.fps,'seconds':args.frames/args.fps,
            'triangles_per_frame':total,'gl_errors':0,'browser_capture':False,'image_generation':False,
            'frame_interpolation':False,'photograph_projection':False,'camera_loop':'smooth forward dolly with a small lateral orbit; every pose is freshly rendered',
            'shader_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'web').glob('*.glsl')},
            'wall_seconds':time.monotonic()-start,'frames':receipts}
    if result['unique_source_frames']!=args.frames:raise RuntimeError('The motion proof contains duplicate frames')
    (ROOT/'evidence/preview_render.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',result['wall_seconds'],flush=True)
if __name__=='__main__':run()
