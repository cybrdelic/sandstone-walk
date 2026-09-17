(async()=>{try{const r=await fetch('web/scene.json');if(!r.ok)throw new Error('Scene metadata unavailable');window.CYBR_BAKE=await r.json();
const SURFACE_VERTEX="precision highp float;\nuniform mat4 uVP;\nin vec3 position;\nin vec3 bakeNormal;\nin vec3 directRadiance;\nin vec3 indirectRadiance;\nin vec2 surface;\nout vec3 vWorld;\nout vec3 vNormal;\nout vec3 vDirect;\nout vec3 vIndirect;\nout vec2 vSurface;\nvoid main(){\n vWorld=position;vNormal=bakeNormal;vDirect=directRadiance;vIndirect=indirectRadiance;vSurface=surface;\n gl_Position=uVP*vec4(position,1.0);\n}\n";
const SURFACE_FRAGMENT="precision highp float;\nuniform vec3 uEye;\nuniform vec3 uSun;\nuniform vec3 uSolar;\nuniform vec3 uWhite;\nuniform float uExposure;\nuniform int uMode;\nin vec3 vWorld;\nin vec3 vNormal;\nin vec3 vDirect;\nin vec3 vIndirect;\nin vec2 vSurface;\nout vec4 outColor;\nconst float PI=3.141592653589793;\nfloat fresnel(float c){\n const float eta=1.49;\n float st2=(1.0-c*c)/(eta*eta),ct=sqrt(max(0.0,1.0-st2));\n float rs=(c-eta*ct)/(c+eta*ct),rp=(eta*c-ct)/(eta*c+ct);\n return .5*(rs*rs+rp*rp);\n}\nfloat ggxD(float nh,float a){float a2=a*a;float d=nh*nh*(a2-1.0)+1.0;return a2/(PI*d*d);}\nfloat smithG1(float c,float a){return c>0.0?2.0*c/(c+sqrt(a*a+(1.0-a*a)*c*c)):0.0;}\nvec3 encodeNative(vec3 rgb){\n vec3 a=max(rgb/uWhite*uExposure,vec3(0.0));\n a=a*a/(a+vec3(.035));float peak=max(max(a.r,a.g),max(a.b,.0000001));\n a*=(1.0-exp(-peak))/peak;\n a=clamp(a,0.0,1.0);\n return mix(12.92*a,1.055*pow(a,vec3(1.0/2.4))-.055,step(vec3(.0031308),a));\n}\nvoid main(){\n vec3 N=normalize(vNormal),V=normalize(uEye-vWorld),L=uSun;\n // Match the native tracer's shading-normal hemisphere safeguards.\n vec3 Ng=normalize(cross(dFdx(vWorld),dFdy(vWorld)));\n if(dot(Ng,V)<0.0)Ng=-Ng;\n if(dot(N,Ng)<0.0)N=-N;\n if(dot(N,Ng)<.1||dot(N,V)<.01)N=Ng;\n float nv=max(dot(N,V),.0001),nl=max(dot(N,L),0.0);\n float rough=clamp(vSurface.y,.1,1.0),visibility=clamp(vSurface.x,0.0,1.0);\n vec3 H=normalize(V+L);float fr=fresnel(clamp(dot(V,H),0.0,1.0));\n float s2=pow(rough*.52,2.0),A=1.0-s2/(2.0*(s2+.33)),B=.45*s2/(s2+.09);\n float vi=sqrt(max(0.0,1.0-nv*nv)),li=sqrt(max(0.0,1.0-nl*nl));\n float cosPhi=vi*li>.00000001?max(0.0,(dot(V,L)-nv*nl)/(vi*li)):0.0;\n float oren=A+B*cosPhi*max(vi,li)*min(vi/max(nv,.00001),li/max(nl,.00001));\n float alpha=max(.018,rough*rough);\n vec3 direct=vDirect*(1.0-fr)*oren*nl*visibility;\n if(nl>0.0)direct+=uSolar*(visibility*fr*ggxD(max(dot(N,H),0.0),alpha)*smithG1(nv,alpha)*smithG1(nl,alpha)/(4.0*nv));\n vec3 indirect=max(vIndirect,0.0);\n vec3 radiance=direct+indirect;\n if(uMode==1)radiance=direct;\n else if(uMode==2)radiance=indirect;\n else if(uMode==3){outColor=vec4(N*.5+.5,1.0);return;}\n else if(uMode==4){outColor=vec4(vec3(visibility),1.0);return;}\n outColor=vec4(encodeNative(radiance),1.0);\n}\n";
const SKY_VERTEX="precision highp float;\nin vec3 position;\nuniform mat4 uInvVP;\nuniform vec3 uEye;\nout vec3 vDirection;\nvoid main(){\n vec4 q=uInvVP*vec4(position.xy,1.0,1.0);\n vDirection=q.xyz/q.w-uEye;\n gl_Position=vec4(position.xy,1.0,1.0);\n}\n";
const SKY_FRAGMENT="precision highp float;\nuniform sampler2D uSky;\nuniform vec3 uWhite;\nuniform vec3 uSun;\nuniform vec3 uSolar;\nuniform float uExposure;\nin vec3 vDirection;\nout vec4 outColor;\nvec3 encodeNative(vec3 rgb){\n vec3 a=max(rgb/uWhite*uExposure,vec3(0.0));a=a*a/(a+vec3(.035));float p=max(max(a.r,a.g),max(a.b,.0000001));a*=(1.0-exp(-p))/p;\n a=clamp(a,0.0,1.0);return mix(12.92*a,1.055*pow(a,vec3(1.0/2.4))-.055,step(vec3(.0031308),a));\n}\nvoid main(){\n vec3 d=normalize(vDirection);vec2 uv=vec2(fract(atan(d.y,d.x)/6.28318530718+1.0),acos(clamp(d.z,-1.0,1.0))/3.14159265359);\n vec3 c=texture(uSky,uv).rgb;\n if(dot(d,uSun)>=.999989189)c+=uSolar/.000067928;\n outColor=vec4(encodeNative(c),1.0);\n}\n";
'use strict';
(async function main(){
 const $=id=>document.getElementById(id);
 const status=$('status'),errorBox=$('error'),loading=$('loading');
 let failure=null;
 function fail(error){
  failure=error instanceof Error?error:new Error(String(error));
  loading.hidden=true;errorBox.hidden=false;errorBox.textContent='The viewer could not start.\n'+failure.message;
  console.error(failure);
 }
 try{
  if(THREE.REVISION!=='180')throw new Error('This scene is pinned to Three.js r180.');
  if(typeof DecompressionStream!=='function')throw new Error('This viewer needs a browser with DecompressionStream support.');
  const B=CYBR_BAKE;
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(50,1,.02,180);camera.up.set(0,0,1);
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,stencil:false,powerPreference:'high-performance',preserveDrawingBuffer:false});
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.NoToneMapping;renderer.autoClear=false;
  renderer.setPixelRatio(1);document.body.prepend(renderer.domElement);
  const canvas=renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','Interactive three-dimensional canyon');
  renderer.debug.checkShaderErrors=true;
  renderer.debug.onShaderError=(gl,program,vertex,fragment)=>{
   fail(new Error('Shader compilation/linking failed:\n'+gl.getProgramInfoLog(program)+'\n'+gl.getShaderInfoLog(vertex)+'\n'+gl.getShaderInfoLog(fragment)));
  };
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();fail(new Error('The graphics context was lost. Reload the viewer; exact geometry uses substantial GPU memory.'));});
  const sun=new THREE.Vector3(...B.meta.sun).normalize();
  const uniforms={uVP:{value:new THREE.Matrix4()},uEye:{value:camera.position},uSun:{value:sun},uSolar:{value:new THREE.Vector3(...B.meta.solar_rgb)},uWhite:{value:new THREE.Vector3(...B.meta.display_white_rgb)},uExposure:{value:B.meta.exposure},uMode:{value:0}};
  const material=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:SURFACE_VERTEX,fragmentShader:SURFACE_FRAGMENT,uniforms,side:THREE.DoubleSide,toneMapped:false});
  function base64(s){const raw=atob(s),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return bytes;}
  async function inflate(asset){
   if(typeof asset==='string')return await new Response(new Blob([base64(asset)]).stream().pipeThrough(new DecompressionStream('deflate'))).arrayBuffer();
   if(!asset||typeof asset.url!=='string')throw new Error('Invalid asset entry.');
   const response=await fetch(asset.url);
   if(!response.ok)throw new Error('Asset fetch failed: '+asset.url+' ('+response.status+')');
   const packed=await response.arrayBuffer();
   if(packed.byteLength!==asset.bytes)throw new Error('Truncated asset: '+asset.url);
   if(globalThis.crypto?.subtle){
    const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',packed));
    const hash=Array.from(digest,v=>v.toString(16).padStart(2,'0')).join('');
    if(hash!==asset.sha256)throw new Error('Asset hash mismatch: '+asset.url);
   }
   const decoded=await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('deflate'))).arrayBuffer();
   if(decoded.byteLength!==asset.decodedBytes)throw new Error('Decoded asset size mismatch: '+asset.url);
   return decoded;
  }
  async function attr(text,kind,items,expected){
   const bytes=await inflate(text);const Type=kind==='f32'?Float32Array:kind==='i16'?Int16Array:Uint16Array;
   const data=new Type(bytes);if(data.length!==items*expected)throw new Error('A packed mesh attribute has the wrong length.');
   if(kind==='f32')return new THREE.BufferAttribute(data,items);
   if(kind==='f16')return new THREE.Float16BufferAttribute(data,items);
   return new THREE.BufferAttribute(data,items,true);
  }
  function exactGridIndex(rows,cols,flip){
   const cells=(rows-1)*(cols-1),a=new Uint32Array(cells*6);let q=0;
   // This preserves the original source's face ordering as well as topology.
   for(let y=0;y<rows-1;y++)for(let x=0;x<cols-1;x++){
    const i=y*cols+x;
    if(flip){a[q++]=i+cols+1;a[q++]=i+1;a[q++]=i;}
    else{a[q++]=i;a[q++]=i+1;a[q++]=i+cols+1;}
   }
   for(let y=0;y<rows-1;y++)for(let x=0;x<cols-1;x++){
    const i=y*cols+x;
    if(flip){a[q++]=i+cols;a[q++]=i+cols+1;a[q++]=i;}
    else{a[q++]=i;a[q++]=i+cols+1;a[q++]=i+cols;}
   }
   return a;
  }
  let triangles=0,vertices=0;
  const geometry=[];
  for(let i=0;i<B.meshes.length;i++){
   const d=B.meshes[i];status.textContent=`Loading ${i+1}/${B.meshes.length}: ${d.name}`;
   await new Promise(resolve=>setTimeout(resolve,0));
   const g=new THREE.BufferGeometry();
   g.setAttribute('position',await attr(d.position,'f32',3,d.vertices));
   g.setAttribute('bakeNormal',await attr(d.normal,'i16',3,d.vertices));
   g.setAttribute('directRadiance',await attr(d.direct,'f16',3,d.vertices));
   g.setAttribute('indirectRadiance',await attr(d.indirect,'f16',3,d.vertices));
   g.setAttribute('surface',await attr(d.surface,'u16',2,d.vertices));
   const indices=d.kind==='grid'?exactGridIndex(d.rows,d.cols,d.flip):new Uint32Array(await inflate(d.index));
   if(indices.length!==d.triangles*3)throw new Error('Source topology count mismatch: '+d.name);
   g.setIndex(new THREE.BufferAttribute(indices,1));g.computeBoundingSphere();
   const mesh=new THREE.Mesh(g,material);mesh.name=d.name;scene.add(mesh);geometry.push(g);triangles+=d.triangles;vertices+=d.vertices;
  }
  if(triangles!==5029800||vertices!==2526592)throw new Error('Geometry integrity totals do not match the regenerated closed canyon.');
  const skyData=new Uint16Array(await inflate(B.sky.data));
  if(skyData.length!==B.sky.width*B.sky.height*4)throw new Error('Invalid native sky data.');
  const skyTexture=new THREE.DataTexture(skyData,B.sky.width,B.sky.height,THREE.RGBAFormat,THREE.HalfFloatType);
  skyTexture.colorSpace=THREE.NoColorSpace;skyTexture.minFilter=THREE.LinearFilter;skyTexture.magFilter=THREE.LinearFilter;skyTexture.wrapS=THREE.RepeatWrapping;skyTexture.wrapT=THREE.ClampToEdgeWrapping;skyTexture.generateMipmaps=false;skyTexture.needsUpdate=true;
  const skyUniforms={uInvVP:{value:new THREE.Matrix4()},uEye:uniforms.uEye,uSun:uniforms.uSun,uSolar:uniforms.uSolar,uWhite:uniforms.uWhite,uExposure:uniforms.uExposure,uSky:{value:skyTexture}};
  const skyMat=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:SKY_VERTEX,fragmentShader:SKY_FRAGMENT,uniforms:skyUniforms,depthTest:false,depthWrite:false,toneMapped:false});
  const skyGeom=new THREE.BufferGeometry();skyGeom.setAttribute('position',new THREE.Float32BufferAttribute([-1,-1,0,3,-1,0,-1,3,0],3));
  const skyScene=new THREE.Scene(),skyMesh=new THREE.Mesh(skyGeom,skyMat);skyMesh.frustumCulled=false;skyScene.add(skyMesh);
  let renderScale=1,controls=null;
  function resize(){
   const w=Math.max(1,innerWidth),h=Math.max(1,innerHeight);
   renderer.setPixelRatio(renderScale);renderer.setSize(w,h,false);camera.aspect=w/h;
   const nativeFov=2*Math.atan(Math.tan(B.meta.horizontalFov*Math.PI/360)/camera.aspect)*180/Math.PI;
   camera.fov=controls?.mode==='orbit'?55:Math.min(75,nativeFov);camera.updateProjectionMatrix();
  }
  const bounds=new THREE.Box3().setFromObject(scene);
  controls=new SandstoneControls({camera,canvas,bounds,reference:B.meta,onModeChange:()=>resize()});
  $('mode').onchange=e=>{uniforms.uMode.value=Number(e.target.value);};
  $('exposure').oninput=e=>{uniforms.uExposure.value=Number(e.target.value);$('ev').textContent=uniforms.uExposure.value.toFixed(2);};
  $('resolution').onchange=e=>{renderScale=Number(e.target.value);resize();};
  $('hide').textContent=controls.touch?'Settings':'Interface';
  $('hide').setAttribute('aria-expanded','false');
  $('hide').onclick=()=>{
   controls.clearInput();
   if(controls.touch){const open=document.body.classList.toggle('settings-open');if(open)controls.stopTour();$('hide').setAttribute('aria-expanded',String(open));}
   else $('hud').classList.toggle('compact');
  };
  addEventListener('resize',resize);resize();
  camera.updateMatrixWorld(true);uniforms.uVP.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);skyUniforms.uInvVP.value.copy(uniforms.uVP.value).invert();
  renderer.compile(scene,camera);renderer.compile(skyScene,camera);
  if(failure)throw failure;
  loading.hidden=true;
  let last=performance.now(),frames=0,mark=last;
  function frame(now){
   if(failure)return;
   const dt=Math.min(.05,(now-last)/1000);last=now;
   controls.update(dt);
   camera.updateMatrixWorld(true);uniforms.uVP.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);skyUniforms.uInvVP.value.copy(uniforms.uVP.value).invert();
   renderer.clear();renderer.render(skyScene,camera);renderer.render(scene,camera);
   frames++;if(now-mark>1000){$('stats').textContent=`${Math.round(frames*1000/(now-mark))} fps · ${triangles.toLocaleString()} source triangles`;frames=0;mark=now;}
   requestAnimationFrame(frame);
  }
  // Read-only inspection hook plus explicit test controls; no screenshots supply lighting.
  window.CYBR_RECOVERY={renderer,scene,camera,material,meta:B.meta,controls,setReference:()=>controls.setReference(),setMode:value=>{uniforms.uMode.value=Number(value);$('mode').value=String(value);},setPose:(eye,target)=>controls.setPose(eye,target),setNavigationMode:mode=>controls.setNavigationMode(mode),geometry};
  requestAnimationFrame(frame);
 }catch(error){fail(error);}
})();

}catch(e){document.getElementById('error').hidden=false;document.getElementById('error').textContent=String(e);document.getElementById('loading').hidden=true;console.error(e)}})();
