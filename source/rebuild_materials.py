"""Restore the pinned v0.3 mesh, bake the shared material, resolve transport.

python source/rebuild_materials.py --work build/material --skip-geometry
Use --skip-geometry only when work already contains the pinned geometry report.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
S=Path(__file__).resolve().parent
EXPECTED_MESH='7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for x in iter(lambda:f.read(1<<20),b''):h.update(x)
    return h.hexdigest()

def run(work:Path,spp=256,depth=10,threads=4,skip_geometry=False,procedural_geometry=False):
    work=work.resolve();work.mkdir(exist_ok=True,parents=True);logs=work/'logs';logs.mkdir(exist_ok=True)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS=str(threads));commands=[];start=time.monotonic()
    def stage(name,args):
        args=list(map(str,args));print('STAGE',name,flush=True);t=time.monotonic()
        with (logs/(name+'.log')).open('w') as f:subprocess.run(args,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        commands.append({'stage':name,'command':args,'seconds':time.monotonic()-t})
    if not skip_geometry:
        if procedural_geometry:stage('geometry',[sys.executable,S/'solid_geometry.py','--work',work])
        else:stage('restore_geometry',[sys.executable,S/'restore_material_geometry.py','--work',work])
    mesh=work/'native_scene/canyon/scene.meshbin'
    if sha(mesh)!=EXPECTED_MESH:raise ValueError('Source geometry changed: material-only revision refuses replacement mesh')
    if procedural_geometry or (skip_geometry and not (work/'data/layout.json').exists()):
        stage('prepare',[sys.executable,S/'prepare_solid.py','--work',work])
    layout=json.loads((work/'data/layout.json').read_text())
    if layout['triangles']!=5029800 or layout['vertices']!=2526592:raise ValueError('Unexpected mesh counts')
    flags=['-O3','-std=c++17','-fopenmp','-I'+str(S/'cybr-geo/native'),'-DSOLID_TRIANGLE_COUNT=5029800']
    stage('compile_material_bake',['g++',*flags,S/'material_bake.cpp','-o',work/'material_bake'])
    inputs={'scene.meshbin':mesh,'sites.bin':work/'data/sites.bin','vertices.bin':work/'data/vertices.bin',
            'material_bake':work/'material_bake'}
    for name in ['material_field.glsl','material_native.h','material_bake.cpp','transport_bake.cpp']:
        inputs[name]=S/name
    # Include every native header, not just the driver, in invalidation evidence.
    for p in (S/'cybr-geo/native').glob('*.h'):inputs['native/'+p.name]=p
    fingerprints={name:{'sha256':sha(path),'bytes':path.stat().st_size} for name,path in inputs.items()}
    (work/'material_inputs.json').write_text(json.dumps({'schema':'sandstone-material-bake-inputs/1',
        'capture_phase':'before_native_bake','files':fingerprints},indent=2)+'\n')
    stage('material_bake',[work/'material_bake',mesh,work/'data/sites.bin',work/'data/vertices.bin',work/'material_baked',
        S/'cybr-geo/examples/desert_hot_springs/assets',spp,threads,depth])
    for name,path in inputs.items():
        if sha(path)!=fingerprints[name]['sha256']:raise ValueError('Input changed while baking '+name)
    stage('resolve_materials',[sys.executable,S/'resolve_materials.py','--work',work])
    report={'schema':'sandstone-material-execution/1','result':'PASS','commands':commands,
            'wall_seconds':time.monotonic()-start,'source_mesh_sha256':EXPECTED_MESH,'all_input_hashes_unchanged':True}
    (work/'material_execution.json').write_text(json.dumps(report,indent=2)+'\n');print('COMPLETE',json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--spp',type=int,default=256);p.add_argument('--depth',type=int,default=10);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--skip-geometry',action='store_true')
    p.add_argument('--procedural-geometry',action='store_true',help='Regenerate procedurally and require the original native hash; default restores pinned geometry bytes')
    a=p.parse_args()
    if not(8<=a.spp<=4096 and 2<=a.depth<=32 and 1<=a.threads<=256):p.error('Invalid render budgets')
    run(a.work,a.spp,a.depth,a.threads,a.skip_geometry,a.procedural_geometry)
