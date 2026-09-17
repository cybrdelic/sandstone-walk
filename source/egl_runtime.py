"""Small standalone EGL/OpenGL test renderer; not a browser or URL loader."""
import ctypes as C
from ctypes.util import find_library
import numpy as np

class GL:
 def __init__(self,width=960,height=640,gles=False):
  self.width,self.height=width,height
  self.gles=gles
  self.egl=C.CDLL(find_library('EGL'))
  def egl(name,rest,args):
   f=getattr(self.egl,name);f.restype=rest;f.argtypes=args;return f
  self._getproc=egl('eglGetProcAddress',C.c_void_p,[C.c_char_p])
  getdisplay=C.CFUNCTYPE(C.c_void_p,C.c_uint,C.c_void_p,C.POINTER(C.c_int))(self._getproc(b'eglGetPlatformDisplayEXT'))
  d=getdisplay(0x31DD,None,None)
  major,minor=C.c_int(),C.c_int()
  if not egl('eglInitialize',C.c_uint,[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int)])(d,C.byref(major),C.byref(minor)):raise RuntimeError('EGL initialization failed')
  if not egl('eglBindAPI',C.c_uint,[C.c_uint])(0x30A0 if gles else 0x30A2):raise RuntimeError('OpenGL API unavailable')
  attrs=(C.c_int*15)(0x3033,1,0x3040,0x40 if gles else 8,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3025,24,0x3038)
  cfg,n=C.c_void_p(),C.c_int()
  choose=egl('eglChooseConfig',C.c_uint,[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_void_p),C.c_int,C.POINTER(C.c_int)])
  if not choose(d,attrs,C.byref(cfg),1,C.byref(n)) or not n.value:raise RuntimeError('No EGL framebuffer config')
  ca=(C.c_int*3)(0x3098,3,0x3038) if gles else (C.c_int*7)(0x3098,3,0x30FB,3,0x30FD,1,0x3038)
  ctx=egl('eglCreateContext',C.c_void_p,[C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int)])(d,cfg,None,ca)
  sa=(C.c_int*5)(0x3057,width,0x3056,height,0x3038)
  surface=egl('eglCreatePbufferSurface',C.c_void_p,[C.c_void_p,C.c_void_p,C.POINTER(C.c_int)])(d,cfg,sa)
  if not ctx or not surface:raise RuntimeError('EGL context/surface allocation failed')
  if not egl('eglMakeCurrent',C.c_uint,[C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p])(d,surface,surface,ctx):raise RuntimeError('EGL make-current failed')
  self.d,self.ctx,self.surface=d,ctx,surface
  self.GetString=self.fn('glGetString',C.c_char_p,[C.c_uint]);print(self.GetString(0x1F02),self.GetString(0x1F01),flush=True)
  self.CreateShader=self.fn('glCreateShader',C.c_uint,[C.c_uint]);self.ShaderSource=self.fn('glShaderSource',None,[C.c_uint,C.c_int,C.POINTER(C.c_char_p),C.POINTER(C.c_int)])
  self.CompileShader=self.fn('glCompileShader',None,[C.c_uint]);self.GetShaderiv=self.fn('glGetShaderiv',None,[C.c_uint,C.c_uint,C.POINTER(C.c_int)])
  self.GetShaderInfoLog=self.fn('glGetShaderInfoLog',None,[C.c_uint,C.c_int,C.POINTER(C.c_int),C.c_void_p])
  self.CreateProgram=self.fn('glCreateProgram',C.c_uint,[]);self.AttachShader=self.fn('glAttachShader',None,[C.c_uint,C.c_uint]);self.LinkProgram=self.fn('glLinkProgram',None,[C.c_uint])
  self.GetProgramiv=self.fn('glGetProgramiv',None,[C.c_uint,C.c_uint,C.POINTER(C.c_int)]);self.GetProgramInfoLog=self.fn('glGetProgramInfoLog',None,[C.c_uint,C.c_int,C.POINTER(C.c_int),C.c_void_p]);self.UseProgram=self.fn('glUseProgram',None,[C.c_uint])
  self.GetUniformLocation=self.fn('glGetUniformLocation',C.c_int,[C.c_uint,C.c_char_p]);self.Uniform1f=self.fn('glUniform1f',None,[C.c_int,C.c_float]);self.Uniform1i=self.fn('glUniform1i',None,[C.c_int,C.c_int]);self.Uniform3fv=self.fn('glUniform3fv',None,[C.c_int,C.c_int,C.c_void_p]);self.UniformMatrix4fv=self.fn('glUniformMatrix4fv',None,[C.c_int,C.c_int,C.c_ubyte,C.c_void_p])
  self.GenVertexArrays=self.fn('glGenVertexArrays',None,[C.c_int,C.POINTER(C.c_uint)]);self.BindVertexArray=self.fn('glBindVertexArray',None,[C.c_uint]);self.GenBuffers=self.fn('glGenBuffers',None,[C.c_int,C.POINTER(C.c_uint)]);self.BindBuffer=self.fn('glBindBuffer',None,[C.c_uint,C.c_uint]);self.BufferData=self.fn('glBufferData',None,[C.c_uint,C.c_ssize_t,C.c_void_p,C.c_uint]);self.GetAttribLocation=self.fn('glGetAttribLocation',C.c_int,[C.c_uint,C.c_char_p]);self.EnableVertexAttribArray=self.fn('glEnableVertexAttribArray',None,[C.c_uint]);self.VertexAttribPointer=self.fn('glVertexAttribPointer',None,[C.c_uint,C.c_int,C.c_uint,C.c_ubyte,C.c_int,C.c_void_p]);self.DeleteBuffers=self.fn('glDeleteBuffers',None,[C.c_int,C.POINTER(C.c_uint)]);self.DeleteVertexArrays=self.fn('glDeleteVertexArrays',None,[C.c_int,C.POINTER(C.c_uint)])
  self.Viewport=self.fn('glViewport',None,[C.c_int,C.c_int,C.c_int,C.c_int]);self.ClearColor=self.fn('glClearColor',None,[C.c_float]*4);self.Clear=self.fn('glClear',None,[C.c_uint]);self.Enable=self.fn('glEnable',None,[C.c_uint]);self.Disable=self.fn('glDisable',None,[C.c_uint]);self.DrawElements=self.fn('glDrawElements',None,[C.c_uint,C.c_int,C.c_uint,C.c_void_p]);self.ReadPixels=self.fn('glReadPixels',None,[C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p]);self.Finish=self.fn('glFinish',None,[]);self.GetError=self.fn('glGetError',C.c_uint,[])
 def fn(self,n,result,args):
  addr=self._getproc(n.encode());
  if not addr:raise RuntimeError('No OpenGL entry '+n)
  return C.CFUNCTYPE(result,*args)(addr)
 def program(self,vert,frag):
  shaders=[]
  for kind,s in [(0x8B31,vert),(0x8B30,frag)]:
   sh=self.CreateShader(kind);buf=C.c_char_p(s.encode());self.ShaderSource(sh,1,C.byref(buf),None);self.CompileShader(sh);ok=C.c_int();self.GetShaderiv(sh,0x8B81,C.byref(ok))
   if not ok.value:
    log=C.create_string_buffer(40000);self.GetShaderInfoLog(sh,40000,None,log);raise RuntimeError(log.value.decode())
   shaders.append(sh)
  p=self.CreateProgram()
  for sh in shaders:self.AttachShader(p,sh)
  self.LinkProgram(p);ok=C.c_int();self.GetProgramiv(p,0x8B82,C.byref(ok))
  if not ok.value:
   log=C.create_string_buffer(40000);self.GetProgramInfoLog(p,40000,None,log);raise RuntimeError(log.value.decode())
  self.UseProgram(p);return p
 def uniform(self,p,key,x):
  loc=self.GetUniformLocation(p,key.encode())
  if loc<0:return
  if isinstance(x,int):self.Uniform1i(loc,x)
  elif isinstance(x,float):self.Uniform1f(loc,x)
  else:
   x=np.ascontiguousarray(x,dtype='f4');ptr=C.c_void_p(x.ctypes.data)
   if x.shape==(4,4):
    column_major=np.ascontiguousarray(x.T);self.UniformMatrix4fv(loc,1,0,C.c_void_p(column_major.ctypes.data))
   elif x.size==3:self.Uniform3fv(loc,1,ptr)
   else:raise ValueError(x.shape)
 def upload(self,p,attrs,indices):
  vao=C.c_uint();self.GenVertexArrays(1,C.byref(vao));self.BindVertexArray(vao);buffers=[]
  for name,data in attrs.items():
   loc=self.GetAttribLocation(p,name.encode())
   if loc<0:continue
   a=np.ascontiguousarray(data,dtype='f4');b=C.c_uint();self.GenBuffers(1,C.byref(b));buffers.append(b);self.BindBuffer(0x8892,b.value);self.BufferData(0x8892,a.nbytes,C.c_void_p(a.ctypes.data),0x88E4);self.EnableVertexAttribArray(loc);self.VertexAttribPointer(loc,a.shape[1],0x1406,0,0,None)
  f=np.ascontiguousarray(indices,dtype='u4');b=C.c_uint();self.GenBuffers(1,C.byref(b));buffers.append(b);self.BindBuffer(0x8893,b.value);self.BufferData(0x8893,f.nbytes,C.c_void_p(f.ctypes.data),0x88E4)
  return (vao,buffers,f.size)
 def draw(self,obj):
  self.BindVertexArray(obj[0].value);self.DrawElements(4,obj[2],0x1405,None)
 def pixels(self):
  self.Finish();a=np.empty((self.height,self.width,4),'u1');self.ReadPixels(0,0,self.width,self.height,0x1908,0x1401,C.c_void_p(a.ctypes.data));return a[::-1].copy()
 def delete(self,obj):
  for b in obj[1]:self.DeleteBuffers(1,C.byref(b))
  self.DeleteVertexArrays(1,C.byref(obj[0]))

if __name__=='__main__':
 g=GL(128,128);p=g.program('#version 330 core\nin vec3 position;void main(){gl_Position=vec4(position,1);}', '#version 330 core\nout vec4 color;void main(){color=vec4(1,.3,.1,1);}')
 g.Viewport(0,0,128,128);g.ClearColor(0,0,0,1);g.Clear(0x4000)
 mesh=g.upload(p,{'position':np.array([[-1,-1,0],[1,-1,0],[0,1,0]])},np.array([0,1,2]));g.draw(mesh)
 from PIL import Image
 Image.fromarray(g.pixels()).save('/mnt/data/canyon_repair/egl_test.png');print('GL error',g.GetError())
