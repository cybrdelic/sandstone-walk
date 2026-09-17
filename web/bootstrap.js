"use strict";
(async function () {
 try {
  async function read(path,json=false){const r=await fetch(path);if(!r.ok)throw new Error(path+': HTTP '+r.status);return json?r.json():r.text();}
  const [payload,sv,sf,kv,kf]=await Promise.all([read('web/scene.json',true),read('web/surface.vert.glsl'),read('web/surface.frag.glsl'),read('web/sky.vert.glsl'),read('web/sky.frag.glsl')]);
  Object.assign(window,{CYBR_BAKE:payload,SURFACE_VERTEX:sv,SURFACE_FRAGMENT:sf,SKY_VERTEX:kv,SKY_FRAGMENT:kf});
  const s=document.createElement('script');s.src='web/app.js';s.onerror=()=>{throw new Error('Could not load web/app.js');};document.body.appendChild(s);
 } catch(e) {
  document.getElementById('loading').hidden=true;const box=document.getElementById('error');box.hidden=false;box.textContent='Could not load Sandstone Walk. Serve the repository over HTTP, for example with python -m http.server 8000.\n'+e.message;console.error(e);
 }
})();
