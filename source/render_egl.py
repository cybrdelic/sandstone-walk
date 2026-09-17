"""Execute the delivered GLSL with the exact delivered vertex attributes in Mesa."""
from pathlib import Path
import argparse,json,time,os,hashlib
import ctypes as C
import numpy as np
from PIL import Image
from egl_runtime import GL
R=Path(os.environ['CYBR_WORKSPACE']);O=Path(os.environ['CYBR_DELIVERY_ROOT'])

def camera_matrix(eye,target,w,h):
 e=np.array(eye,float);f=np.array(target,float)-e;f/=np.linalg.norm(f);right=np.cross(f,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,f)
 view=np.eye(4);view[0,:3]=right;view[1,:3]=up;view[2,:3]=-f;view[:3,3]=-view[:3,:3]@e
 tan=np.tan(np.deg2rad(68/2));near=.02;far=180
 proj=np.array([[1/tan,0,0,0],[0,w/h/tan,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]],float)
 return proj@view

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--gles',action='store_true');ap.add_argument('--resolved',default='resolved');ap.add_argument('--width',type=int,default=1200);ap.add_argument('--height',type=int,default=800);a=ap.parse_args();D=R/a.resolved
 vs=(O/'source/surface.vert.glsl').read_text();fs=(O/'source/surface.frag.glsl').read_text()
 g=GL(a.width,a.height,gles=a.gles);prefix='#version 300 es\n' if a.gles else '#version 330 core\n';prog=g.program(prefix+vs,prefix+fs)
 meta=json.loads((D/'bake_execution.json').read_text());layout=json.loads((R/'data/layout.json').read_text());meshes=[];total=0;start=time.monotonic()
 for p in layout['parts']:
  n=p['name'];pos=np.load(R/f'data/{n}.pos.npy');nn=np.load(D/f'{n}.normal.npy').astype('f4')/32767;direct=np.load(D/f'{n}.direct.npy').astype('f4');ind=np.load(D/f'{n}.indirect.npy').astype('f4');surf=np.load(D/f'{n}.surface.npy').astype('f4')/65535;idx=np.load(R/f'data/{n}.idx.npy')
  obj=g.upload(prog,{'position':pos,'bakeNormal':nn,'directRadiance':direct,'indirectRadiance':ind,'surface':surf},idx)
  meshes.append(obj);total+=idx.size//3;print('uploaded',n,flush=True)
 g.Enable(0x0B71);g.Disable(0x0B44);g.Viewport(0,0,a.width,a.height)
 skyprog=g.program(prefix+(O/'source/sky.vert.glsl').read_text(),prefix+(O/'source/sky.frag.glsl').read_text())
 skyobj=g.upload(skyprog,{'position':np.array([[-1,-1,0],[3,-1,0],[-1,3,0]],'f4')},np.array([0,1,2],'u4'))
 raw=(R/'native_sky.bin').read_bytes();sw,sh=np.frombuffer(raw,dtype='<u4',count=2);rgb=np.frombuffer(raw,dtype='<f4',offset=8).reshape(sh,sw,3)
 rgba=np.ones((sh,sw,4),'<f2');rgba[:,:,:3]=rgb
 gen=g.fn('glGenTextures',None,[C.c_int,C.POINTER(C.c_uint)]);bind=g.fn('glBindTexture',None,[C.c_uint,C.c_uint]);param=g.fn('glTexParameteri',None,[C.c_uint,C.c_uint,C.c_int]);image=g.fn('glTexImage2D',None,[C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]);active=g.fn('glActiveTexture',None,[C.c_uint])
 tex=C.c_uint();gen(1,C.byref(tex));active(0x84C0);bind(0x0DE1,tex.value);param(0x0DE1,0x2801,0x2601);param(0x0DE1,0x2800,0x2601);param(0x0DE1,0x2802,0x2901);param(0x0DE1,0x2803,0x812F);image(0x0DE1,0,0x881A,int(sw),int(sh),0,0x1908,0x140B,C.c_void_p(rgba.ctypes.data));g.uniform(skyprog,'uSky',0)

 sun=np.array([-.24,-.33,.913],float);sun/=np.linalg.norm(sun)
 for program in [prog,skyprog]:
  g.UseProgram(program)
  for k,x in [('uSun',sun),('uSolar',meta['solar_rgb']),('uWhite',meta['display_white_rgb']),('uExposure',2.5)]:g.uniform(program,k,x)
 poses=[('hero',[-.42,-5.8,1.56],[.15,9.8,3.12]),('forward',[.25,4.8,1.60],[1.2,16,2.6]),('reverse',[.6,9.0,1.75],[-.3,-4,2.6])]
 results=[]
 for name,eye,target in poses:
  for mode,label in [(0,'beauty')]+([(1,'direct'),(2,'indirect'),(3,'normals'),(4,'visibility')] if name=='hero' else []):
   g.ClearColor(0,0,0,1);g.Clear(0x4000|0x0100);vp=camera_matrix(eye,target,a.width,a.height)
   g.Disable(0x0B71);g.UseProgram(skyprog);g.uniform(skyprog,'uInvVP',np.linalg.inv(vp));g.uniform(skyprog,'uEye',eye);g.draw(skyobj)
   g.Enable(0x0B71);g.UseProgram(prog);g.uniform(prog,'uVP',vp);g.uniform(prog,'uEye',eye);g.uniform(prog,'uMode',mode)
   for obj in meshes:g.draw(obj)
   im=g.pixels();err=g.GetError()
   if err:raise RuntimeError(f'OpenGL error {hex(err)}')
   path=O/f'evidence/{name}_{label}.png';Image.fromarray(im).convert('RGB').save(path)
   results.append({'path':str(path.relative_to(O)),'camera':eye,'target':target,'mode':mode,'gl_error':err,'triangles_submitted':total,'rgb_mean':im[:,:,:3].mean((0,1)).tolist()});print('rendered',path,flush=True)
 (O/'evidence/native_glsl_execution.json').write_text(json.dumps({'renderer':g.GetString(0x1F01).decode(),'version':g.GetString(0x1F02).decode(),'same_shader_source_as_threejs':True,'glsl_version':'300 es' if a.gles else '330 core','shader_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (O/'source').glob('*.glsl')},'browser_execution':False,'width':a.width,'height':a.height,'seconds':time.monotonic()-start,'results':results},indent=2))
if __name__=='__main__':main()
