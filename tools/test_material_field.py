"""CPU/GLSL parity and tessellation-independence tests.

Executes the actual shared material functions in C++ and WebGL2. No scene images
are used as a material input. Numeric pass thresholds are not a beauty verdict.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,subprocess,time
from pathlib import Path
import numpy as np
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--backend',choices=['webgl','egl'],default='webgl');ap.add_argument('--out',type=Path,default=ROOT/'build/material-field');args=ap.parse_args();args.out.mkdir(exist_ok=True,parents=True)
    started=time.monotonic();rng=np.random.default_rng(271828)
    rotation=np.array([[0,.8,.6],[-.8,.36,-.48],[-.6,-.48,.64]])
    assert np.max(np.abs(rotation@rotation.T-np.eye(3)))<1e-12
    assert abs(np.linalg.det(rotation)-1)<1e-12
    n=4096;data=np.zeros((n,8),dtype='<f4');data[:,:3]=rng.uniform(-24,61,(n,3))
    data[:,3]=rng.choice([0,.0003,.001,.004,.02,.2,10],n)
    normals=rng.normal(size=(n,3));normals/=np.linalg.norm(normals,axis=1,keepdims=True)
    data[:,4:7]=normals;data[:,7]=rng.choice([0,1,2],n)
    # Include integer noise-lattice boundaries and reflected/negative coordinates.
    data[:128,:3]=np.round(data[:128,:3]);data[128:256,:3]*=-1
    data[3072:3328]=data[:256];data[3072:3328,4:7]=normals[3072:3328]
    inp=args.out/'inputs.f32';cpu_path=args.out/'cpu.f32';data.tofile(inp)
    exe=args.out/'material_probe'
    subprocess.run(['g++','-O3','-std=c++17','-fopenmp','-I'+str(ROOT/'source/cybr-geo/native'),str(ROOT/'source/material_probe.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(inp),str(cpu_path)],check=True)
    cpu=np.fromfile(cpu_path,dtype='<f4').reshape(n,8)
    assert np.isfinite(cpu).all() and cpu[:,:3].min()>.008 and cpu[:,:3].max()<.82
    assert np.max(np.abs(np.linalg.norm(cpu[:,4:7],axis=1)-1))<1e-5
    normal_dot=np.sum(cpu[:,4:7]*data[:,4:7],axis=1)
    assert normal_dot.min()>=1/np.sqrt(1+.22**2)-1e-5
    color_orientation_error=float(np.abs(cpu[:256,:4]-cpu[3072:3328,:4]).max())
    assert color_orientation_error==0,('Color must not follow the normal/view',color_orientation_error)
    unresolved_variances=[]
    for family in [0,1,2]:
        group=cpu[(data[:,3]==10)&(data[:,7]==family),:4]
        unresolved_variances.append(float(np.max(np.ptp(group,axis=0))))
    assert max(unresolved_variances)<1e-6,unresolved_variances
    code=(ROOT/'source/material_field.glsl').read_text()
    report={'schema':'sandstone-material-field-test/1','result':'FAIL','errors':[],
            'material_field_sha256':hashlib.sha256(code.encode()).hexdigest(),'cpu_glsl_samples':n,'albedo_normal_independence_max_error':color_orientation_error,
            'unresolved_footprint_10m_color_ranges':unresolved_variances}
    if args.backend=='egl':
        from material_gles import evaluate
        output=evaluate(code,data)
        report['backend']='standalone GLES; not a browser'
    else:
        with sync_playwright() as p:
            options={'headless':True,'args':['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']}
            if os.getenv('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**options);page=browser.new_page()
            page.on('pageerror',lambda e:report['errors'].append(str(e)))
            page.set_content('<canvas width="64" height="64"></canvas>')
            output=page.evaluate(r'''({code,data})=>{
              const canvas=document.querySelector('canvas'),g=canvas.getContext('webgl2',{antialias:false});
              if(!g || !g.getExtension('EXT_color_buffer_float'))throw Error('Float WebGL2 output unavailable');
              function shader(type,text){let s=g.createShader(type);g.shaderSource(s,text);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s;}
              function program(v,f){let p=g.createProgram();g.attachShader(p,shader(g.VERTEX_SHADER,v));g.attachShader(p,shader(g.FRAGMENT_SHADER,f));g.linkProgram(p);if(!g.getProgramParameter(p,g.LINK_STATUS))throw Error(g.getProgramInfoLog(p));return p;}
              function texture(w,h,arr){let t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texImage2D(g.TEXTURE_2D,0,g.RGBA32F,w,h,0,g.RGBA,g.FLOAT,arr);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.NEAREST);return t;}
              function target(w,h){let f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);let a=texture(w,h,null),b=texture(w,h,null);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,a,0);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT1,g.TEXTURE_2D,b,0);g.drawBuffers([g.COLOR_ATTACHMENT0,g.COLOR_ATTACHMENT1]);if(g.checkFramebufferStatus(g.FRAMEBUFFER)!==g.FRAMEBUFFER_COMPLETE)throw Error('Incomplete FBO');return f;}
              const bin=Uint8Array.from(atob(data),c=>c.charCodeAt(0));const values=new Float32Array(bin.buffer),pos=new Float32Array(4096*4),norm=new Float32Array(4096*4);
              for(let i=0;i<4096;i++){pos.set(values.subarray(i*8,i*8+4),i*4);norm.set(values.subarray(i*8+4,i*8+8),i*4);}
              let tp=texture(64,64,pos),tn=texture(64,64,norm);const f=target(64,64);g.viewport(0,0,64,64);
              const prog=program('#version 300 es\nvoid main(){vec2 q=gl_VertexID==0?vec2(-1,-1):gl_VertexID==1?vec2(3,-1):vec2(-1,3);gl_Position=vec4(q,0,1);}',
                '#version 300 es\nprecision highp float;precision highp int;uniform highp sampler2D p;uniform highp sampler2D n;layout(location=0)out vec4 color;layout(location=1)out vec4 normal;\n'+code+'\nvoid main(){ivec2 at=ivec2(gl_FragCoord.xy);vec4 a=texelFetch(p,at,0),b=texelFetch(n,at,0);SWMaterial m=swMaterial(a.xyz,b.xyz,int(b.w),a.w);color=vec4(m.color,m.rough);normal=vec4(m.normal,0.0);}')
              g.useProgram(prog);g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,tp);g.uniform1i(g.getUniformLocation(prog,'p'),0);g.activeTexture(g.TEXTURE1);g.bindTexture(g.TEXTURE_2D,tn);g.uniform1i(g.getUniformLocation(prog,'n'),1);
              g.drawArrays(g.TRIANGLES,0,3);g.finish();let a=new Float32Array(4096*4),b=new Float32Array(4096*4);g.readBuffer(g.COLOR_ATTACHMENT0);g.readPixels(0,0,64,64,g.RGBA,g.FLOAT,a);g.readBuffer(g.COLOR_ATTACHMENT1);g.readPixels(0,0,64,64,g.RGBA,g.FLOAT,b);
              const parity={color:Array.from(a),normal:Array.from(b)};
              // The 47 x 7 fine grid aligns with pixel boundaries at 188 x 126.
              // This isolates material/topology dependence from fixed-point rasterizer
              // subpixel rounding of differently positioned vertex boundaries.
              let ft=target(188,126);g.viewport(0,0,188,126);
              let patch=program('#version 300 es\nprecision highp float;in vec2 xy;out vec3 P;void main(){P=vec3(-2.17,1.81+xy.x*18.0,1.34+xy.y*.75);gl_Position=vec4(xy*2.0-1.0,0,1);}',
                '#version 300 es\nprecision highp float;precision highp int;in vec3 P;layout(location=0)out vec4 color;layout(location=1)out vec4 normal;\n'+code+'\nvoid main(){vec3 x=dFdx(P),y=dFdy(P);float a=dot(x,x),b=dot(x,y),c=dot(y,y);float footprint=sqrt(.5*(a+c+sqrt((a-c)*(a-c)+4.0*b*b)));SWMaterial m=swMaterial(P,vec3(1,0,0),1,footprint);color=vec4(m.color,m.rough);normal=vec4(P,footprint);}')
              g.useProgram(patch);let buffer=g.createBuffer(),location=g.getAttribLocation(patch,'xy');g.bindBuffer(g.ARRAY_BUFFER,buffer);g.enableVertexAttribArray(location);g.vertexAttribPointer(location,2,g.FLOAT,false,0,0);
              function draw(nx,ny){let v=[];for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){let x=i/nx,y=j/ny,X=(i+1)/nx,Y=(j+1)/ny;v.push(x,y,X,y,X,Y,x,y,X,Y,x,Y);}g.bufferData(g.ARRAY_BUFFER,new Float32Array(v),g.STATIC_DRAW);g.drawArrays(g.TRIANGLES,0,v.length/2);g.finish();let out=new Float32Array(188*126*4);g.readBuffer(g.COLOR_ATTACHMENT0);g.readPixels(0,0,188,126,g.RGBA,g.FLOAT,out);let domain=new Float32Array(out.length);g.readBuffer(g.COLOR_ATTACHMENT1);g.readPixels(0,0,188,126,g.RGBA,g.FLOAT,domain);return {color:out,domain};}
              let coarse=draw(1,1),fine=draw(47,7),max=0,sum=0;
              let positionError=0,footprintError=0;for(let i=0;i<coarse.color.length;i++){let d=Math.abs(coarse.color[i]-fine.color[i]);max=Math.max(max,d);sum+=d;let e=Math.abs(coarse.domain[i]-fine.domain[i]);if(i%4===3)footprintError=Math.max(footprintError,e);else positionError=Math.max(positionError,e);}
              return {parity,topology:{maximum:max,mean:sum/coarse.color.length,position_max_error:positionError,footprint_max_error:footprintError},error:g.getError(),renderer:g.getParameter(g.RENDERER)};
            }''',{'code':code,'data':base64.b64encode(data.tobytes()).decode()})
    gpu=np.concatenate([np.array(output['parity']['color']).reshape(n,4),np.array(output['parity']['normal']).reshape(n,4)],axis=1)
    assert np.isfinite(gpu).all() and output['error']==0
    diff=np.abs(cpu-gpu);color_error=float(diff[:,:4].max());normal_error=float(diff[:,4:7].max())
    assert color_error<.0005,('Color CPU/GLSL mismatch',color_error)
    assert normal_error<.002,('Normal CPU/GLSL mismatch',normal_error)
    assert output['topology']['position_max_error']<.0001 and output['topology']['footprint_max_error']<.0001,output['topology']
    assert output['topology']['maximum']<.0005 and output['topology']['mean']<.00005,output['topology']
    report.update(result='PASS',cpu_glsl_max_color_error=color_error,cpu_glsl_max_normal_error=normal_error,
        minimum_normal_dot_geometric=float(normal_dot.min()),tessellation_test={'coarse_triangles':2,'fine_triangles':658,
        'physical_patch_m':[18,.75],'viewport':[188,126],'fine_grid':[47,7],
        'rasterization_protocol':'Grid boundaries aligned to pixel boundaries to isolate material sampling from subpixel rasterization rounding',**output['topology']},gl_error=output['error'],renderer=output['renderer'],
        coordinates='Isotropic 3D world positions; no UVs or chart-dependent scales',backend=args.backend)
    assert not report['errors']
    report['seconds']=time.monotonic()-started
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as error:
        import sys,traceback
        out=Path(sys.argv[sys.argv.index('--out')+1]) if '--out' in sys.argv else ROOT/'build/material-field'
        out.mkdir(parents=True,exist_ok=True)
        (out/'report.json').write_text(json.dumps({'result':'FAIL','error':str(error),'traceback':traceback.format_exc()},indent=2)+'\n')
        raise
