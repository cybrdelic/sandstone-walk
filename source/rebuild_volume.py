"""Rebuild the closed canyon, rebake real light transport, and package current UI."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
SOURCE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--project',type=Path,default=SOURCE.parent);p.add_argument('--spp',type=int,default=256);p.add_argument('--threads',type=int,default=4);p.add_argument('--skip-geometry',action='store_true');p.add_argument('--expected-mesh');p.add_argument('--render',action='store_true');p.add_argument('--film',action='store_true');a=p.parse_args()
 if a.spp<16 or a.threads<1:p.error('Positive sampling and thread budgets required')
 root=a.workspace.resolve();project=a.project.resolve();logs=root/'logs';logs.mkdir(parents=True,exist_ok=True)
 env={**os.environ,'CYBR_WORKSPACE':str(root),'CYBR_DELIVERY_ROOT':str(project),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':str(a.threads)}
 steps=[]
 def run(stage,cmd):
  start=time.monotonic();argv=list(map(str,cmd));print(stage,flush=True)
  with (logs/(stage+'.log')).open('w') as f:r=subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT,cwd=project)
  steps.append({'stage':stage,'command':argv,'returncode':r.returncode,'seconds':time.monotonic()-start})
  if r.returncode:raise RuntimeError(stage+' failed: '+str(logs/(stage+'.log')))
 if not a.skip_geometry:run('geometry',[sys.executable,SOURCE/'formation_volume.py','--out',root/'native_scene/canyon'])
 mesh=root/'native_scene/canyon/scene.meshbin';meshsha=sha(mesh)
 if a.expected_mesh and meshsha!=a.expected_mesh:raise RuntimeError('Regenerated geometry does not match reviewed source: '+meshsha)
 run('sites',[sys.executable,SOURCE/'prepare_volume.py','--root',root,'--stride',6])
 layout=json.loads((root/'data/layout.json').read_text());sourcehashes={str(q.relative_to(SOURCE)):sha(q) for q in [SOURCE/'bake.cpp',SOURCE/'transport_bake.cpp',SOURCE/'material_volume.h',SOURCE/'formation_volume.py',SOURCE/'support_surface.py',SOURCE/'prepare_volume.py',SOURCE/'resolve_volume.py',SOURCE/'pack_volume.py',SOURCE/'rebuild_volume.py']}
 flags=['g++','-O3','-std=c++17','-fopenmp','-I'+str(SOURCE/'cybr-geo/native')]
 run('compile_baker',flags+['-DCYBR_EXPECTED_TRIANGLE_COUNT='+str(layout['triangles']),'-DCYBR_FORMATION_MATERIALS="material_volume.h"',SOURCE/'bake.cpp','-o',root/'bake'])
 inputs={str(q.relative_to(root)):sha(q) for q in [mesh,root/'data/sites.bin',root/'data/vertices.bin']}
 run('spectral_bake',[root/'bake',mesh,root/'data/sites.bin',root/'data/vertices.bin',root/'baked_final',SOURCE/'cybr-geo/examples/desert_hot_springs/assets',a.spp,a.threads,10])
 for name,expected in inputs.items():
  if sha(root/name)!=expected:raise RuntimeError('Input mutated during bake: '+name)
 meta=json.loads((root/'baked_final/bake_execution.json').read_text())
 assert meta['invalid_samples']==0 and meta['clamped_contributions']==0 and meta['triangles']==layout['triangles']
 meta.update(source_mesh_sha256=meshsha,input_sha256=inputs,source_sha256=sourcehashes,baker_binary_sha256=sha(root/'bake'))
 (root/'baked_final/bake_execution.json').write_text(json.dumps(meta,indent=2)+'\n')
 run('compile_sky',flags+[SOURCE/'sky.cpp','-o',root/'sky']);run('native_sky',[root/'sky',root/'native_sky.bin'])
 run('resolve',[sys.executable,SOURCE/'resolve_volume.py','--root',root])
 run('pack',[sys.executable,SOURCE/'pack_volume.py','--root',root,'--project',project])
 if a.render:run('native_views',[sys.executable,project/'tools/render_volume.py','--gles','--resolved','resolved_final','--width',1200,'--height',800])
 if a.film:run('native_film',[sys.executable,project/'tools/render_volume.py','--gles','--resolved','resolved_final','--width',960,'--height',640,'--film','--output','build/formation_frames'])
 for name,expected in sourcehashes.items():
  if sha(SOURCE/name)!=expected:raise RuntimeError('Source changed during execution: '+name)
 evidence=project/'evidence/formation';evidence.mkdir(parents=True,exist_ok=True)
 (evidence/'rebuild_execution.json').write_text(json.dumps({'source_mesh_sha256':meshsha,'input_sha256':inputs,'source_sha256':sourcehashes,'steps':steps},indent=2)+'\n')
 for f in logs.glob('*.log'):shutil.copyfile(f,evidence/f.name)
 print('COMPLETE',meshsha,flush=True)

if __name__=='__main__':main()
