"""Reproduce the canyon mesh, native spectral bake, and self-contained viewer.

Run with a C++17 compiler with OpenMP (tested here with GCC on Linux).
The full working data needs several GB. Browser execution is a separate test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
EXPECTED_MESH = '50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a'

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--spp', type=int, default=256)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--depth', type=int, default=10)
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--skip-geometry', action='store_true', help='Reuse an existing hash-verified mesh and assembly.')
    parser.add_argument('--reuse-raw-bake', action='store_true', help='Explicitly reuse existing bake files, after checking their settings.')
    parser.add_argument('--glsl-proof', action='store_true', help='Run optional standalone EGL/GLES proof, not a browser test.')
    args = parser.parse_args()
    if not 8 <= args.spp <= 4096 or args.threads < 1 or args.depth < 2:
        parser.error('Invalid sample, thread, or depth budget.')
    compiler = shutil.which(args.cxx)
    if compiler is None:
        parser.error('A C++17 compiler with OpenMP is required: ' + args.cxx)
    work = args.workspace.resolve()
    out = args.out.resolve()
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    logs = work / 'logs'
    logs.mkdir(exist_ok=True)
    env = dict(os.environ, CYBR_WORKSPACE=str(work), CYBR_DELIVERY_ROOT=str(out))
    repo = SOURCE / 'cybr-geo'
    env['PYTHONPATH'] = str(repo / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    commands = []

    def run(label: str, command: list[str | Path]) -> None:
        argv = list(map(str, command))
        commands.append({'stage': label, 'command': argv})
        print(label, flush=True)
        with (logs / (label + '.log')).open('w') as handle:
            result = subprocess.run(argv, cwd=work, env=env, stdout=handle, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'{label} failed with exit code {result.returncode}. Read {logs / (label + ".log")}')

    if not args.skip_geometry:
        run('geometry', [sys.executable, repo / 'examples/three_scenes/rebuild_scenes.py', '--scene', 'canyon', '--out', work / 'native_scene', '--no-glb'])
    mesh = work / 'native_scene/canyon/scene.meshbin'
    if not mesh.is_file() or sha256(mesh) != EXPECTED_MESH:
        raise RuntimeError('The original mesh hash does not match; refusing a replacement formation.')
    run('surface_sites', [sys.executable, SOURCE / 'prepare.py'])
    baked = work / 'baked_final'
    flags = ['-O3', '-std=c++17', '-fopenmp', '-I' + str(repo / 'native')]
    if not args.reuse_raw_bake:
        run('compile_baker', [compiler, *flags, SOURCE / 'bake.cpp', '-o', work / 'bake'])
        run('native_surface_bake', [work / 'bake', mesh, work / 'data/sites.bin', work / 'data/vertices.bin', baked, repo / 'examples/desert_hot_springs/assets', str(args.spp), str(args.threads), str(args.depth)])
    else:
        receipt = json.loads((baked / 'bake_execution.json').read_text())
        if receipt['hemisphere_samples_per_site'] != args.spp or receipt['maximum_path_depth'] != args.depth or receipt['triangles'] != 8108728:
            raise RuntimeError('The requested reuse does not match the stored bake settings.')
        expected = {'irradiance.raw.f32': 414439 * 16 * 4, 'variance.raw.f32': 414439 * 4, 'vertex_bake.raw.f32': 4072674 * 24 * 4, 'spectral_rgb_matrix.f32': 16 * 3 * 4}
        for name, size in expected.items():
            if (baked / name).stat().st_size != size:
                raise RuntimeError('Incomplete raw bake: ' + name)
    run('native_sky_compile', [compiler, *flags, SOURCE / 'sky.cpp', '-o', work / 'sky'])
    run('native_sky', [work / 'sky', work / 'native_sky.bin'])
    run('resolve', [sys.executable, SOURCE / 'resolve.py', '--root', work, '--baked', 'baked_final', '--out', 'resolved_final'])
    if out / 'source' != SOURCE:
        shutil.copytree(SOURCE, out / 'source', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    run('package', [sys.executable, SOURCE / 'pack_app.py', '--workspace', work, '--out', out])
    if args.glsl_proof:
        run('gles_proof', [sys.executable, SOURCE / 'render_egl.py', '--gles', '--resolved', 'resolved_final', '--width', '1536', '--height', '1024'])
    (out / 'rebuild_commands.json').write_text(json.dumps(commands, indent=2))
    print(out / 'CYBR_Canyon_Recovery.html', flush=True)

if __name__ == '__main__':
    main()
