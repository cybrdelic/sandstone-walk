"""Generate the browser shader from the same field included by native C++."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def build():
    source=ROOT/'source';web=ROOT/'web'
    field=(source/'material_field.glsl').read_text()
    template=(source/'surface_material.frag.glsl').read_text()
    if template.count('__MATERIAL_FIELD__')!=1:raise ValueError('Missing single shared-field anchor')
    (web/'surface.frag.glsl').write_text(template.replace('__MATERIAL_FIELD__',field))
    (web/'surface.vert.glsl').write_text((source/'surface_material.vert.glsl').read_text())
    # bootstrap.js historically contained stale duplicate shader/app strings.
    # Generate it from the actual files and record their identities every time.
    statements='\n'.join('const '+name+'='+json.dumps((web/file).read_text())+';' for name,file in [
      ('SURFACE_VERTEX','surface.vert.glsl'),('SURFACE_FRAGMENT','surface.frag.glsl'),('SKY_VERTEX','sky.vert.glsl'),('SKY_FRAGMENT','sky.frag.glsl')])
    text="(async()=>{try{const r=await fetch('web/scene.json');if(!r.ok)throw new Error('Scene metadata unavailable');window.CYBR_BAKE=await r.json();\n"+statements+'\n'+(web/'app.js').read_text()+"\n}catch(e){document.getElementById('error').hidden=false;document.getElementById('error').textContent=String(e);document.getElementById('loading').hidden=true;console.error(e)}})();\n"
    (web/'bootstrap.js').write_text(text)
    return hashlib.sha256(field.encode()).hexdigest()
if __name__=='__main__':print(build())
