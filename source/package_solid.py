"""Write actual baked buffers to split web assets and a no-CDN standalone.
Preserves the tested mobile controller. Geometry identity is deliberately revised.
GPL-2.0-only.
"""
from pathlib import Path
import argparse,base64,zlib,json,hashlib,shutil,re
import numpy as np
SOURCE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(work,out):
    web=out/'web';assets=web/'assets';assets.mkdir(parents=True,exist_ok=True)
    D=work/'resolved_final';layout=json.loads((work/'data/layout.json').read_text());meta=json.loads((D/'bake_execution.json').read_text())
    report=json.loads((work/'geometry_report.json').read_text())
    if report['mesh_sha256']!=sha(work/'native_scene/canyon/scene.meshbin'):raise ValueError('Scene changed after geometry validation')
    if meta['triangles']!=layout['triangles'] or meta['vertex_count']!=layout['vertices']:raise ValueError('Bake belongs to a different geometry')
    inputs=json.loads((work/'bake_inputs.json').read_text())
    for name,p in [('scene.meshbin',work/'native_scene/canyon/scene.meshbin'),('sites.bin',work/'data/sites.bin'),('vertices.bin',work/'data/vertices.bin')]:
        if sha(p)!=inputs['files'][name]['sha256']:raise ValueError('Input identity changed since native bake: '+name)
    if inputs['files']['scene.meshbin']['sha256']!=report['mesh_sha256']:raise ValueError('Bake input scene does not match exported geometry')

    meta.update({'schema':'sandstone-walk-solid/1','source_mesh_sha256':report['mesh_sha256'],'geometry_modified':True,
        'geometry_revision':'Closed connected landform with joint-cut rockfall','centerline':report['centerline'],
        'positions':'Regenerated source vertices converted to float32; no post-build decimation',
        'camera':[-.42,-5.8,1.56],'target':[.15,9.8,3.12],'horizontalFov':68,'sun':[-.24,-.33,.913],
        'lighting':'Fresh native 16-band spectral surface bake for this regenerated mesh',
        'image_projection':False,'hand_authored_probes':False,'runtime_ambient_lights':0,'static_bake':True,
        'view_dependent_indirect_gloss':False,'browser_runtime_verified':False,'terrain_watertight':True})
    def packed(arr,name):
        a=np.ascontiguousarray(arr);blob=zlib.compress(a.tobytes(),8);p=assets/('solid-'+name+'.deflate');p.write_bytes(blob)
        return {'url':str(p.relative_to(out)),'bytes':len(blob),'decodedBytes':a.nbytes,'sha256':hashlib.sha256(blob).hexdigest()}
    meshes=[];checks=[]
    for ent in layout['parts']:
        name=ent['name'];pos=np.load(work/f'data/{name}.pos.npy');idx=np.load(work/f'data/{name}.idx.npy')
        if idx.max()>=len(pos) or idx.size!=ent['triangles']*3:raise RuntimeError('Invalid geometry')
        m={k:ent[k] for k in ['name','vertices','triangles','kind']}
        if ent['kind']=='grid':
            m.update({k:ent[k] for k in ['rows','cols','flip']})
        else:m['index']=packed(idx.astype('<u4'),name+'.index')
        a=[('position',pos)]+[(k,np.load(D/f'{name}.{k}.npy')) for k in ['normal','direct','indirect','surface']]
        for k,array in a:
            if not np.isfinite(array).all():raise ValueError('Nonfinite '+name+' '+k)
            m[k]=packed(array,name+'.'+k)
        meshes.append(m)
        checks.append({'name':name,'vertices':len(pos),'triangles':len(idx),'position_sha256':hashlib.sha256(pos.tobytes()).hexdigest(),
                       'topology_sha256':hashlib.sha256(idx.tobytes()).hexdigest(),'finite':True})
    raw=(work/'native_sky.bin').read_bytes();w,h=np.frombuffer(raw,dtype='<u4',count=2);rgb=np.frombuffer(raw,dtype='<f4',offset=8).reshape(h,w,3)
    rgba=np.ones((h,w,4),'<f2');rgba[:,:,:3]=rgb
    payload={'meta':meta,'meshes':meshes,'sky':{'width':int(w),'height':int(h),'data':packed(rgba,'native-sky'),'source':'Native physicalSky evaluation'}}
    (web/'scene.json').write_text(json.dumps(payload,indent=2)+'\n')
    app=(web/'app.js').read_text()
    # Replace the old literal integrity totals, never bypass the check.
    old="if(triangles!==8108728||vertices!==4072674)throw new Error('Geometry integrity totals do not match the preserved canyon.');"
    new=f"if(triangles!=={layout['triangles']}||vertices!=={layout['vertices']})throw new Error('Geometry integrity totals do not match the regenerated closed canyon.');"
    if old in app:app=app.replace(old,new)
    elif new not in app:
        pattern=r"if\(triangles!==[0-9]+\|\|vertices!==[0-9]+\)throw new Error\('Geometry integrity totals do not match the regenerated closed canyon\.'\);"
        app,n=re.subn(pattern,lambda m:new,app)
        if n!=1:raise ValueError('Unrecognized app integrity check')
    (web/'app.js').write_text(app)
    # Both entry points run the same controller, shaders and render loop.
    consts={'SURFACE_VERTEX':'surface.vert.glsl','SURFACE_FRAGMENT':'surface.frag.glsl','SKY_VERTEX':'sky.vert.glsl','SKY_FRAGMENT':'sky.frag.glsl'}
    statements='\n'.join('const '+key+'='+json.dumps((web/name).read_text())+';' for key,name in consts.items())
    scaffold=(SOURCE/'solid_page.html').read_text().replace('Sandstone Walk — Baked Canyon','Sandstone Walk — Solid Canyon')
    scaffold=scaffold.replace('Recovered exact geometry · native spectral surface bake','Closed landform · fresh spectral surface bake')
    # Source shaders are preserved; a geometry-only inspection mode is optional in future.
    bootstrap="(async()=>{try{const r=await fetch('web/scene.json');if(!r.ok)throw new Error('Scene metadata unavailable');window.CYBR_BAKE=await r.json();\n"+statements+"\n"+app+"\n}catch(e){document.getElementById('error').hidden=false;document.getElementById('error').textContent=String(e);document.getElementById('loading').hidden=true;console.error(e)}})();\n"
    (web/'bootstrap.js').write_text(bootstrap)
    index=scaffold.replace('__SOLID_APPLICATION__','<script src="web/bootstrap.js"></script>')
    (out/'index.html').write_text(index)
    # Use separate deep copy because the web manifest must retain URLs and checksums.
    inline=json.loads(json.dumps(payload))
    for m in inline['meshes']:
        for k in ['position','normal','direct','indirect','surface','index']:
            if k in m:m[k]=base64.b64encode((out/m[k]['url']).read_bytes()).decode('ascii')
    inline['sky']['data']=base64.b64encode((out/inline['sky']['data']['url']).read_bytes()).decode('ascii')
    html=scaffold.replace('__SOLID_APPLICATION__','<script>const CYBR_BAKE='+json.dumps(inline,separators=(',',':'))+';\n'+statements+'\n'+app+'</script>')
    for path in ['web/vendor/three.bundle.js','web/controls.js']:
        html=html.replace('<script src="'+path+'"></script>','<script>'+(out/path).read_text()+'</script>')
    html=html.replace('<link rel="stylesheet" href="web/controls.css">','<style>'+(web/'controls.css').read_text()+'</style>')
    (out/'Sandstone_Walk_Solid.html').write_text(html)
    verification={'geometry':checks,'scene':meta,'terrain_topology':report['terrain'],
                  'controls_sha256':sha(web/'controls.js'),'standalone_sha256':sha(out/'Sandstone_Walk_Solid.html'),
                  'standalone_bytes':(out/'Sandstone_Walk_Solid.html').stat().st_size,
                  'browser_runtime_verified':False}
    (out/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    for name in ['geometry_report.json','charts.json','bake_inputs.json']:
        shutil.copyfile(work/name,out/'evidence'/name)
    for name in ['bake_execution.json','resolve.json']:
        shutil.copyfile(D/name,out/'evidence'/name)
    print('PACKAGED',layout['triangles'],layout['vertices'],len(html),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.work,a.out)
