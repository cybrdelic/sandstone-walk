"""Render a genuine two-shot camera film from the current shipped bake and GLSL.

Uses native Mesa GLES, not a browser and not image generation/frame interpolation.
The separate browser tests execute the actual Three.js renderer and controls.
GPL-2.0-only.
"""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,math,os,subprocess,sys,time,zlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageSequence
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'source'))
from egl_runtime import GL
from verify_solid import asset,indices

def matrix(eye,target,width,height,hfov=68):
    eye=np.array(eye,float);f=np.asarray(target)-eye;f/=np.linalg.norm(f)
    r=np.cross(f,[0,0,1]);r/=np.linalg.norm(r);u=np.cross(r,f)
    view=np.eye(4);view[0,:3]=r;view[1,:3]=u;view[2,:3]=-f;view[:3,3]=-view[:3,:3]@eye
    t=np.tan(np.deg2rad(hfov*.5));near=.02;far=500.
    projection=np.array([[1/t,0,0,0],[0,width/height/t,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]],float)
    return projection@view

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--width',type=int,default=1200);ap.add_argument('--height',type=int,default=800)
    ap.add_argument('--frames',type=int,default=144);ap.add_argument('--fps',type=int,default=24);a=ap.parse_args()
    if min(a.width,a.height,a.frames,a.fps)<1 or a.frames%2:ap.error('Positive dimensions/fps and even frame count required')
    scene=json.loads((ROOT/'web/scene.json').read_text());meta=scene['meta'];start=time.monotonic()
    frames=ROOT/'build/solid_frames';frames.mkdir(parents=True,exist_ok=True);media=ROOT/'media';media.mkdir(exist_ok=True)
    g=GL(a.width,a.height,gles=True);pfx='#version 300 es\n'
    program=g.program(pfx+(ROOT/'web/surface.vert.glsl').read_text(),pfx+(ROOT/'web/surface.frag.glsl').read_text())
    meshes=[];lo=np.full(3,np.inf);hi=-lo;triangles=0
    for m in scene['meshes']:
        pos=asset(ROOT,m['position'],'<f4',3);norm=asset(ROOT,m['normal'],'<i2',3).astype('f4')/32767
        dr=asset(ROOT,m['direct'],'<f2',3).astype('f4');ir=asset(ROOT,m['indirect'],'<f2',3).astype('f4');surface=asset(ROOT,m['surface'],'<u2',2).astype('f4')/65535
        idx=indices(m) if m['kind']=='grid' else asset(ROOT,m['index'],'<u4',3)
        meshes.append(g.upload(program,{'position':pos,'bakeNormal':norm,'directRadiance':dr,'indirectRadiance':ir,'surface':surface},idx))
        lo=np.minimum(lo,pos.min(0));hi=np.maximum(hi,pos.max(0));triangles+=len(idx)
    assert triangles==meta['triangles']
    skyprog=g.program(pfx+(ROOT/'web/sky.vert.glsl').read_text(),pfx+(ROOT/'web/sky.frag.glsl').read_text())
    skyobj=g.upload(skyprog,{'position':np.array([[-1,-1,0],[3,-1,0],[-1,3,0]],'f4')},np.array([0,1,2],'u4'))
    texdata=asset(ROOT,scene['sky']['data'],'<f2',4)
    gen=g.fn('glGenTextures',None,[C.c_int,C.POINTER(C.c_uint)]);bind=g.fn('glBindTexture',None,[C.c_uint,C.c_uint]);param=g.fn('glTexParameteri',None,[C.c_uint,C.c_uint,C.c_int]);image=g.fn('glTexImage2D',None,[C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]);active=g.fn('glActiveTexture',None,[C.c_uint])
    tex=C.c_uint();gen(1,C.byref(tex));active(0x84C0);bind(0x0DE1,tex.value)
    for key,value in [(0x2801,0x2601),(0x2800,0x2601),(0x2802,0x2901),(0x2803,0x812F)]:param(0x0DE1,key,value)
    image(0x0DE1,0,0x881A,scene['sky']['width'],scene['sky']['height'],0,0x1908,0x140B,C.c_void_p(texdata.ctypes.data));g.UseProgram(skyprog);g.uniform(skyprog,'uSky',0)
    sun=np.array(meta['sun']);sun/=np.linalg.norm(sun)
    for prog in [program,skyprog]:
        g.UseProgram(prog)
        for key,value in [('uSun',sun),('uSolar',meta['solar_rgb']),('uWhite',meta['display_white_rgb']),('uExposure',float(meta['exposure']))]:g.uniform(prog,key,value)
    def draw(name,eye,target,hfov=68,mode=0):
        g.ClearColor(0,0,0,1);g.Clear(0x4000|0x0100);g.Disable(0x0B44);g.Viewport(0,0,a.width,a.height)
        vp=matrix(eye,target,a.width,a.height,hfov);g.Disable(0x0B71);g.UseProgram(skyprog);g.uniform(skyprog,'uEye',eye);g.uniform(skyprog,'uInvVP',np.linalg.inv(vp));g.draw(skyobj)
        g.Enable(0x0B71);g.UseProgram(program);g.uniform(program,'uEye',eye);g.uniform(program,'uVP',vp);g.uniform(program,'uMode',mode)
        for obj in meshes:g.draw(obj)
        pixels=g.pixels();err=g.GetError()
        if err:raise RuntimeError(f'GLES error {err} in {name}')
        path=frames/name;Image.fromarray(pixels).convert('RGB').save(path)
        return {'file':name,'eye':list(map(float,eye)),'target':list(map(float,target)),'hfov':hfov,'rgba_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'gl_error':0}
    target=(lo+hi)*.5;radius=np.linalg.norm(hi-lo)*1.1
    records=[];half=a.frames//2
    for i in range(a.frames):
        if i<half:
            t=i/max(1,half-1);ease=t*t*(3-2*t);eye=[-.42+.28*ease,-5.8+6.5*ease,1.56+.07*ease];aim=[.15,9.8+5*ease,3.12-.45*ease];hfov=68
        else:
            t=(i-half)/max(1,half-1);angle=-.82+.48*t;pitch=.60+.07*np.sin(np.pi*t)
            eye=target+radius*np.array([np.sin(angle)*np.cos(pitch),np.cos(angle)*np.cos(pitch),np.sin(pitch)]);aim=target;hfov=float(np.rad2deg(2*np.arctan(np.tan(np.deg2rad(55*.5))*a.width/a.height)))
        records.append(draw(f'{i:04d}.png',eye,aim,hfov))
        if i%24==0:print('RENDERED',i,a.frames,flush=True)
    assert len({r['rgba_sha256'] for r in records})==a.frames,'Film must contain genuinely distinct rendered frames'
    import shutil
    shutil.copyfile(frames/'0000.png',media/'solid-hero.png');shutil.copyfile(frames/f'{half:04d}.png',media/'solid-orbit.png')
    video=media/'sandstone-walk-solid.mp4';gif=media/'sandstone-walk-solid.gif'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(a.fps),'-i',str(frames/'%04d.png'),'-frames:v',str(a.frames),'-c:v','libx264','-preset','slow','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(video),'-filter_complex','fps=12,scale=720:-2:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a','-loop','0',str(gif)],check=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate,duration','-of','json',str(video)]))['streams'][0]
    assert int(info['nb_read_frames'])==a.frames and info['width']==a.width and info['height']==a.height
    gif_image=Image.open(gif);gifhash=[hashlib.sha256(f.convert('RGB').tobytes()).hexdigest() for f in ImageSequence.Iterator(gif_image)]
    assert len(gifhash)==len(set(gifhash))
    report={'schema':'sandstone-walk-solid-media/1','source_mesh_sha256':meta['source_mesh_sha256'],'source':'Actual Mesa OpenGL ES execution of shipped GLSL, geometry and bake; not browser capture','image_generation':False,'frame_interpolation':False,'renderer':g.GetString(0x1F01).decode(),'GL_version':g.GetString(0x1F02).decode(),'triangles_submitted_per_frame':triangles,'frames':records,'seconds':time.monotonic()-start,'video':info,'gif_frames':len(gifhash),'gif_unique_frames':len(set(gifhash)),'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [video,gif,media/'solid-hero.png',media/'solid-orbit.png']}}
    (ROOT/'evidence/solid_media.json').write_text(json.dumps(report,indent=2)+'\n');print('MEDIA PASS',flush=True)
if __name__=='__main__':main()
