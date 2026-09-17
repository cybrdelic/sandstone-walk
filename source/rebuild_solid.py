"""Rebuild and rebake the closed-landform revision. Old recovery source is preserved.
Usage: python source/rebuild_solid.py --work /path/to/work --out /path/to/project
"""
from pathlib import Path
import argparse,subprocess,sys,os,json,hashlib,shutil,time
S=Path(__file__).resolve().parent

def run(work,out,spp=256,depth=10,threads=4,skip_geometry=False):
    work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True);logs=work/'logs';logs.mkdir(exist_ok=True)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS=str(threads),CYBR_WORKSPACE=str(work),CYBR_DELIVERY_ROOT=str(out))
    cmds=[]
    def stage(name,args):
        argv=list(map(str,args));cmds.append({'name':name,'argv':argv});print('STAGE',name,flush=True)
        with (logs/(name+'.log')).open('w') as f:subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    if not skip_geometry:stage('geometry',[sys.executable,S/'solid_geometry.py','--work',work])
    geometry=json.loads((work/'geometry_report.json').read_text());mesh=work/'native_scene/canyon/scene.meshbin'
    h=hashlib.sha256()
    with mesh.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    if h.hexdigest()!=geometry['mesh_sha256']:raise ValueError('Geometry hash changed before bake')
    if not geometry['terrain']['watertight']:raise ValueError('Terrain is not closed')
    stage('prepare',[sys.executable,S/'prepare_solid.py','--work',work])
    layout=json.loads((work/'data/layout.json').read_text());cxx=shutil.which('g++')
    if not cxx:raise RuntimeError('g++ with OpenMP is required')
    flags=['-O3','-std=c++17','-fopenmp','-I'+str(S/'cybr-geo/native')]
    stage('compile',[cxx,*flags,'-DSOLID_TRIANGLE_COUNT='+str(layout['triangles']),S/'solid_bake.cpp','-o',work/'solid_bake'])
    def filehash(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        return h.hexdigest()
    inputs={'scene.meshbin':mesh,'sites.bin':work/'data/sites.bin','vertices.bin':work/'data/vertices.bin','solid_bake':work/'solid_bake','solid_bake.cpp':S/'solid_bake.cpp','transport_bake.cpp':S/'transport_bake.cpp'}
    fingerprint={name:{'path':str(path),'sha256':filehash(path),'bytes':path.stat().st_size} for name,path in inputs.items()}
    (work/'bake_inputs.json').write_text(json.dumps({'schema':'sandstone-walk-bake-inputs/1','capture_phase':'before_native_bake','files':fingerprint},indent=2)+'\n')
    stage('bake',[work/'solid_bake',mesh,work/'data/sites.bin',work/'data/vertices.bin',work/'baked_final',S/'cybr-geo/examples/desert_hot_springs/assets',spp,threads,depth])
    for name,path in inputs.items():
        if filehash(path)!=fingerprint[name]['sha256']:raise ValueError('Input changed during native bake: '+name)

    stage('compile_sky',[cxx,*flags,S/'sky.cpp','-o',work/'sky'])
    stage('sky',[work/'sky',work/'native_sky.bin'])
    stage('resolve',[sys.executable,S/'resolve_solid.py','--root',work,'--baked','baked_final','--out','resolved_final'])
    stage('package',[sys.executable,S/'package_solid.py','--work',work,'--out',out])
    (out/'evidence/commands.json').write_text(json.dumps(cmds,indent=2)+'\n')
    print('COMPLETE',out/'Sandstone_Walk_Solid.html',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--spp',type=int,default=256);ap.add_argument('--depth',type=int,default=10);ap.add_argument('--threads',type=int,default=4);ap.add_argument('--skip-geometry',action='store_true')
    a=ap.parse_args()
    if a.spp<8 or a.spp>4096 or a.depth<2 or a.threads<1:ap.error('Invalid bake budget')
    run(a.work,a.out,a.spp,a.depth,a.threads,a.skip_geometry)
