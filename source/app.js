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
  async function inflate(s){return await new Response(new Blob([base64(s)]).stream().pipeThrough(new DecompressionStream('deflate'))).arrayBuffer();}
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
  if(triangles!==8108728||vertices!==4072674)throw new Error('Geometry integrity totals do not match the preserved canyon.');
  const skyData=new Uint16Array(await inflate(B.sky.data));
  if(skyData.length!==B.sky.width*B.sky.height*4)throw new Error('Invalid native sky data.');
  const skyTexture=new THREE.DataTexture(skyData,B.sky.width,B.sky.height,THREE.RGBAFormat,THREE.HalfFloatType);
  skyTexture.colorSpace=THREE.NoColorSpace;skyTexture.minFilter=THREE.LinearFilter;skyTexture.magFilter=THREE.LinearFilter;skyTexture.wrapS=THREE.RepeatWrapping;skyTexture.wrapT=THREE.ClampToEdgeWrapping;skyTexture.generateMipmaps=false;skyTexture.needsUpdate=true;
  const skyUniforms={uInvVP:{value:new THREE.Matrix4()},uEye:uniforms.uEye,uSun:uniforms.uSun,uSolar:uniforms.uSolar,uWhite:uniforms.uWhite,uExposure:uniforms.uExposure,uSky:{value:skyTexture}};
  const skyMat=new THREE.RawShaderMaterial({glslVersion:THREE.GLSL3,vertexShader:SKY_VERTEX,fragmentShader:SKY_FRAGMENT,uniforms:skyUniforms,depthTest:false,depthWrite:false,toneMapped:false});
  const skyGeom=new THREE.BufferGeometry();skyGeom.setAttribute('position',new THREE.Float32BufferAttribute([-1,-1,0,3,-1,0,-1,3,0],3));
  const skyScene=new THREE.Scene(),skyMesh=new THREE.Mesh(skyGeom,skyMat);skyMesh.frustumCulled=false;skyScene.add(skyMesh);
  const keys=new Set();let yaw=0,pitch=0,autoWalk=false,walkY=-5.8,dragging=false,lastX=0,lastY=0,renderScale=1;
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function center(y){let t=clamp((y-17)/13,0,1);return .4*Math.sin(y*.21)+1.35*Math.exp(-Math.pow((y-18)/6.8,2))-.9*Math.exp(-Math.pow((y-30)/4.8,2))+6.2*t*t*(3-2*t);}
  function look(){const c=Math.cos(pitch);camera.lookAt(camera.position.x+Math.sin(yaw)*c,camera.position.y+Math.cos(yaw)*c,camera.position.z+Math.sin(pitch));}
  function aim(target){const d=new THREE.Vector3(...target).sub(camera.position).normalize();yaw=Math.atan2(d.x,d.y);pitch=Math.asin(clamp(d.z,-1,1));look();}
  function reset(){autoWalk=false;keys.clear();$('walk').setAttribute('aria-pressed','false');camera.position.fromArray(B.meta.camera);aim(B.meta.target);walkY=-5.8;}
  function resize(){const w=Math.max(1,innerWidth),h=Math.max(1,innerHeight);renderer.setPixelRatio(renderScale);renderer.setSize(w,h,false);camera.aspect=w/h;camera.fov=2*Math.atan(Math.tan(B.meta.horizontalFov*Math.PI/360)/camera.aspect)*180/Math.PI;camera.updateProjectionMatrix();}
  canvas.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);autoWalk=false;$('walk').setAttribute('aria-pressed','false');});
  canvas.addEventListener('pointermove',e=>{if(!dragging)return;yaw+=(e.clientX-lastX)*.003;pitch=clamp(pitch-(e.clientY-lastY)*.003,-1.46,1.46);lastX=e.clientX;lastY=e.clientY;look();});
  const stopDrag=()=>{dragging=false;};canvas.addEventListener('pointerup',stopDrag);canvas.addEventListener('pointercancel',stopDrag);
  canvas.addEventListener('wheel',e=>{e.preventDefault();const d=new THREE.Vector3(Math.sin(yaw),Math.cos(yaw),0);camera.position.addScaledVector(d,-Math.sign(e.deltaY)*.3);look();},{passive:false});
  addEventListener('keydown',e=>{if(['INPUT','SELECT','BUTTON'].includes(document.activeElement?.tagName))return;if(['KeyW','KeyA','KeyS','KeyD','KeyQ','KeyE','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','ShiftLeft'].includes(e.code)){e.preventDefault();keys.add(e.code);}if(e.code==='KeyR')reset();});
  addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>{keys.clear();dragging=false;});
  for(const button of document.querySelectorAll('[data-move]')){
   button.addEventListener('pointerdown',e=>{e.preventDefault();button.setPointerCapture(e.pointerId);keys.add(button.dataset.move);});
   for(const type of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(type,()=>keys.delete(button.dataset.move));
  }
  $('reset').onclick=reset;
  $('walk').onclick=()=>{autoWalk=!autoWalk;walkY=clamp(camera.position.y,-5.8,27.8);$('walk').setAttribute('aria-pressed',String(autoWalk));};
  $('mode').onchange=e=>{uniforms.uMode.value=Number(e.target.value);};
  $('exposure').oninput=e=>{uniforms.uExposure.value=Number(e.target.value);$('ev').textContent=uniforms.uExposure.value.toFixed(2);};
  $('resolution').onchange=e=>{renderScale=Number(e.target.value);resize();};
  $('hide').onclick=()=>{$('hud').classList.toggle('compact');};
  addEventListener('resize',resize);reset();resize();
  camera.updateMatrixWorld(true);uniforms.uVP.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);skyUniforms.uInvVP.value.copy(uniforms.uVP.value).invert();
  renderer.compile(scene,camera);renderer.compile(skyScene,camera);
  if(failure)throw failure;
  loading.hidden=true;
  let last=performance.now(),frames=0,mark=last;
  function frame(now){
   if(failure)return;
   const dt=Math.min(.05,(now-last)/1000);last=now;
   if(keys.size){
    autoWalk=false;$('walk').setAttribute('aria-pressed','false');
    let f=(keys.has('KeyW')||keys.has('ArrowUp')?1:0)-(keys.has('KeyS')||keys.has('ArrowDown')?1:0);
    let r=(keys.has('KeyD')||keys.has('ArrowRight')?1:0)-(keys.has('KeyA')||keys.has('ArrowLeft')?1:0),z=(keys.has('KeyE')?1:0)-(keys.has('KeyQ')?1:0);
    const norm=Math.hypot(f,r,z)||1,speed=dt*(keys.has('ShiftLeft')?5:1.8)/norm;
    camera.position.x+=(Math.sin(yaw)*f+Math.cos(yaw)*r)*speed;camera.position.y+=(Math.cos(yaw)*f-Math.sin(yaw)*r)*speed;camera.position.z+=z*speed;look();
   }else if(autoWalk){walkY+=dt*.6;if(walkY>=28){walkY=28;autoWalk=false;$('walk').setAttribute('aria-pressed','false');}camera.position.set(center(walkY)-.15,walkY,1.56+.012*(walkY+5.8));aim([center(walkY+5),walkY+5,2.3+.012*(walkY+5.8)]);}
   camera.updateMatrixWorld(true);uniforms.uVP.value.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);skyUniforms.uInvVP.value.copy(uniforms.uVP.value).invert();
   renderer.clear();renderer.render(skyScene,camera);renderer.render(scene,camera);
   frames++;if(now-mark>1000){$('stats').textContent=`${Math.round(frames*1000/(now-mark))} fps · ${triangles.toLocaleString()} source triangles`;frames=0;mark=now;}
   requestAnimationFrame(frame);
  }
  // Read-only inspection hook plus explicit test controls; no screenshots supply lighting.
  window.CYBR_RECOVERY={renderer,scene,camera,material,meta:B.meta,setReference:reset,setMode:value=>{uniforms.uMode.value=Number(value);},setPose:(eye,target)=>{autoWalk=false;camera.position.fromArray(eye);aim(target);},geometry};
  requestAnimationFrame(frame);
 }catch(error){fail(error);}
})();
