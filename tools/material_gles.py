"""Execute material parity targets with Mesa GLES, distinct from browser testing."""
from __future__ import annotations
import ctypes as C
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source'))
from egl_runtime import GL

def evaluate(code: str, data: np.ndarray) -> dict:
    g=GL(188,126,gles=True)
    genTex=g.fn('glGenTextures',None,[C.c_int,C.POINTER(C.c_uint)])
    bindTex=g.fn('glBindTexture',None,[C.c_uint,C.c_uint])
    texImage=g.fn('glTexImage2D',None,[C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_void_p])
    param=g.fn('glTexParameteri',None,[C.c_uint,C.c_uint,C.c_int])
    active=g.fn('glActiveTexture',None,[C.c_uint])
    genFB=g.fn('glGenFramebuffers',None,[C.c_int,C.POINTER(C.c_uint)])
    bindFB=g.fn('glBindFramebuffer',None,[C.c_uint,C.c_uint])
    attach=g.fn('glFramebufferTexture2D',None,[C.c_uint,C.c_uint,C.c_uint,C.c_uint,C.c_int])
    drawBuffers=g.fn('glDrawBuffers',None,[C.c_int,C.POINTER(C.c_uint)])
    checkFB=g.fn('glCheckFramebufferStatus',C.c_uint,[C.c_uint])
    readBuffer=g.fn('glReadBuffer',None,[C.c_uint])
    drawArrays=g.fn('glDrawArrays',None,[C.c_uint,C.c_int,C.c_int])
    keep=[]
    def texture(w,h,a=None):
        t=C.c_uint();genTex(1,C.byref(t));bindTex(0x0DE1,t.value)
        raw=None if a is None else np.ascontiguousarray(a,dtype='<f4')
        texImage(0x0DE1,0,0x8814,w,h,0,0x1908,0x1406,None if raw is None else C.c_void_p(raw.ctypes.data))
        param(0x0DE1,0x2801,0x2600);param(0x0DE1,0x2800,0x2600)
        keep.append(t);return t.value
    def target(w,h):
        f=C.c_uint();genFB(1,C.byref(f));bindFB(0x8D40,f.value);keep.append(f)
        for i in range(2):attach(0x8D40,0x8CE0+i,0x0DE1,texture(w,h),0)
        drawBuffers(2,(C.c_uint*2)(0x8CE0,0x8CE1))
        if checkFB(0x8D40)!=0x8CD5:raise RuntimeError('Float MRT framebuffer incomplete')
        g.Viewport(0,0,w,h)
    def read(w,h,i=0):
        a=np.empty((w*h,4),dtype='<f4');g.Finish();readBuffer(0x8CE0+i)
        g.ReadPixels(0,0,w,h,0x1908,0x1406,C.c_void_p(a.ctypes.data));return a
    tp=texture(64,64,data[:,:4]);tn=texture(64,64,data[:,4:8]);target(64,64)
    v='#version 300 es\nvoid main(){vec2 q=gl_VertexID==0?vec2(-1,-1):gl_VertexID==1?vec2(3,-1):vec2(-1,3);gl_Position=vec4(q,0,1);}'
    f='#version 300 es\nprecision highp float;precision highp int;uniform highp sampler2D p;uniform highp sampler2D n;layout(location=0)out vec4 color;layout(location=1)out vec4 normal;\n'+code+'\nvoid main(){ivec2 at=ivec2(gl_FragCoord.xy);vec4 a=texelFetch(p,at,0),b=texelFetch(n,at,0);SWMaterial m=swMaterial(a.xyz,b.xyz,int(b.w),a.w);color=vec4(m.color,m.rough);normal=vec4(m.normal,0.0);}'
    prog=g.program(v,f);active(0x84C0);bindTex(0x0DE1,tp);g.uniform(prog,'p',0);active(0x84C1);bindTex(0x0DE1,tn);g.uniform(prog,'n',1)
    drawArrays(4,0,3);a=read(64,64,0);b=read(64,64,1)
    target(188,126)
    patch=g.program('#version 300 es\nprecision highp float;in vec2 xy;out vec3 P;void main(){P=vec3(-2.17,1.81+xy.x*18.0,1.34+xy.y*.75);gl_Position=vec4(xy*2.0-1.0,0,1);}',
      '#version 300 es\nprecision highp float;precision highp int;in vec3 P;layout(location=0)out vec4 color;layout(location=1)out vec4 normal;\n'+code+'\nvoid main(){vec3 x=dFdx(P),y=dFdy(P);float a=dot(x,x),b=dot(x,y),c=dot(y,y);float footprint=sqrt(.5*(a+c+sqrt((a-c)*(a-c)+4.0*b*b)));SWMaterial m=swMaterial(P,vec3(1,0,0),1,footprint);color=vec4(m.color,m.rough);normal=vec4(P,footprint);}')
    def draw(nx,ny):
        v=[]
        for j in range(ny):
            for i in range(nx):
                x,y,X,Y=i/nx,j/ny,(i+1)/nx,(j+1)/ny
                v.extend([(x,y),(X,y),(X,Y),(x,y),(X,Y),(x,Y)])
        obj=g.upload(patch,{'xy':np.array(v,dtype='<f4')},np.arange(len(v),dtype='<u4'));g.draw(obj)
        out=read(188,126);domain=read(188,126,1);g.delete(obj);return out,domain
    coarse,cd=draw(1,1);fine,fd=draw(47,7);difference=np.abs(coarse-fine);domain_difference=np.abs(cd-fd)
    return {'parity':{'color':a.reshape(-1).tolist(),'normal':b.reshape(-1).tolist()},
      'topology':{'maximum':float(difference.max()),'mean':float(difference.mean()),'position_max_error':float(domain_difference[:,:3].max()),'footprint_max_error':float(domain_difference[:,3].max())},
      'error':g.GetError(),'renderer':g.GetString(0x1F01).decode(),'backend':'Standalone OpenGL ES; not browser execution'}
