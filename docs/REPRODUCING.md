# Reproduction

## Use the shipped bake

The committed `web/assets` data are sufficient for the browser, the GLES previews and standalone reassembly. Neither network asset downloads nor a new spectral bake is required. Run `python tools/verify.py` first. The original native mesh/bake work files are not duplicated in Git; they are generated from the retained source when requested.

## Native source

Install `source/requirements.txt`, GCC with C++17/OpenMP, and enough temporary disk space, then run `source/rebuild.py` as documented in the root README. Its `--workspace` directory receives the mesh, raw spectra, resolved bake and build outputs. `--out` receives the standalone delivery. The original source recipe, seed, assets and expected mesh hash are retained. Do not replace the recipe with the older `build_scenes.py` entry point: the active recovery uses `rebuild_scenes.py`.

The source wrapper was historically syntax-checked while its constituent stages were executed individually. This publication verifies the shipped output arrays and native shader rendering, not a new full spectral re-bake on a different compiler. `evidence/environment.json` records the environment of the original bake.

## Preview

The preview renderer reads the compressed committed buffers directly, decodes their GPU precision exactly, compiles `web/*.glsl` as GLSL ES 3.00, and submits the full triangle set on each frame through a standalone EGL context. Mesa software rendering is supported. The looping camera is defined in `tools/render_preview.py`; it makes a small lateral circuit while moving into and out of the passage. All frames are freshly drawn, not reversed images or optical-flow interpolation.

The README GIF is a 12 fps subset of the 24 fps master. Lanczos downsampling and palette quantization are encoding operations, not added scene detail. The MP4 is the higher-quality motion preview. Exact output hashes may differ with Mesa/FFmpeg versions even when all scene data match.

## Browser test

`tools/browser_smoke.py` starts a local HTTP server and launches Chromium with software WebGL flags on headless runners. It reports failures verbatim. It does not change administrator policies or disable them. The separate native EGL proof does not prove browser startup, controls or device performance. CI uses its own ordinary runner environment for browser execution.
