# CYBR Canyon — native surface-bake recovery

This package preserves the original canyon and replaces the failed interactive lighting path. It is not an “AAA” visual-quality certification or a claim of a pixel-identical match to the original still.

## Start

Open `CYBR_Canyon_Recovery.html` in a modern WebGL2 browser. Three.js r180, geometry, baked lighting, shaders and sky data are embedded; no CDN or image service is required. The standalone file is about 124 MB because it retains all 8.1 million source triangles. Allow time to load and use a device with sufficient graphics memory. Lowering the pixel-resolution selector reduces shading work, not geometry complexity.

Drag to look; use WASD/arrows to move, Q/E vertically, and R to reset. The on-screen arrows support touch movement. “Walk through” follows a fixed path. Movement is a free-camera inspection controller, not a collision-qualified walking simulation. The lighting selector exposes direct-only, indirect-only, normal and sun-visibility views.

If a browser disallows local HTML execution, serve the extracted project normally with `python -m http.server 8000` and open it from localhost. Browser security settings should remain enabled.

## Preserved source

The complete native geometry rebuild produced **8,108,728 triangles and 4,072,674 vertices**. Its native mesh SHA-256 is:

```
50fbfa563abe246a9049279274a1cea710be5b38f423ccdc6ab6ef731d27156a
```

This is the recorded original canyon mesh hash. The viewer uses its original topology and the same float32 position conversion as the earlier exact-geometry port. There is no decimation, alternate formation recipe, proxy wall or projected photograph.

`source/cybr-geo/` retains the recovered source and native renderer. The surface-bake adapter is kept separately in `source/bake.cpp` and `source/transport_bake.cpp`. The original reference is supplied as `original_reference.png` for comparison only. It is never read by the bake or embedded in the viewer.

## What was actually executed

The recovered native renderer traced a 16-band spectral surface irradiance bake at **414,439 actual surface sites, 256 hemisphere samples per site and a maximum path depth of 10**. Separate finite-sun-disc visibility rays tested the full 8.1-million-triangle geometry, with up to 16 rays at each sun-facing vertex. The run recorded 37,452,960 solar-visibility rays, zero invalid samples and zero contribution clamps.

Sunlight that would escape directly from a receiving site is excluded from the indirect estimator; it is handled by the separate solar-visibility term. Reflections of sunlight through other surfaces still use the native integrator. The native materials, sampled spectral sky, sun orientation and historical display transform are retained. Material reflectance is multiplied by irradiance in the 16-band representation before RGB integration.

The browser interpolates that **surface-bound diffuse lighting**, rather than blending made-up probe colors. Direct diffuse and specular response are evaluated with the current view direction. There are no hemisphere fill lights, directional “bounce” lights or hero-camera lighting projections.

## Deliberate approximations and remaining visual differences

The indirect bake is finite-resolution, positively filtered and interpolated back onto the original vertices. Its low-frequency Oren–Nayar diffuse response is view-independent; view-dependent indirect glossy transport is not reproduced. Material parameters are evaluated at vertices rather than by the offline renderer at every pixel. These limitations can soften details or change local brightness near ledges and at close range.

Direct visibility uses a conservative one-ring minimum over coherent normals. This reduces isolated bright shadow leaks but slightly expands shadow edges by approximately a local vertex spacing. The raw visibility ray results remain separate and unchanged. This is a biased reconstruction step, not an additional physical effect.

Lighting, sun and geometry are static. This is not real-time path tracing or a dynamic DDGI system. The recovery still differs visibly from the original offline image; it should not be treated as an approved final visual match.

## Verification boundaries

The delivered surface and sky shaders compiled as **GLSL ES 3.00** on a standalone Mesa OpenGL ES 3.2 context. That renderer executed the exact delivered shader source and GPU-precision attribute values at the reference, forward and reverse cameras. All seven proof images submitted the full original topology and returned zero OpenGL errors. These images are **native shader renders, not browser screenshots** and not the original reference image.

JavaScript syntax, payload lengths, geometry hashes, full topology ordering, finite lighting attributes and shader/source identity were also checked. Chromium navigation in this environment returned `ERR_BLOCKED_BY_ADMINISTRATOR`; the policy was not disabled or bypassed. **End-to-end Three.js/browser startup, controls, performance and mobile behavior remain unverified here.** Native shader execution does not establish those browser claims.

See `verification.json` and `evidence/` for executed receipts, shader hashes, diagnostic images, spectral-data samples and the browser-attempt log. Historical R4 “verification” flags are not reused as proof.

## Rebuild from source

A Linux/WSL environment with Python, GCC C++17 and OpenMP is the supported build path. Install the Python packages in `source/requirements.txt`, then run:

```bash
python -m pip install -r source/requirements.txt
python source/rebuild.py --workspace ./work --out ./rebuilt --spp 256 --threads 4 --depth 10
```

The workspace needs several GB. The builder fails if the regenerated native mesh hash differs from the original. To reuse a locally completed raw bake explicitly, add `--skip-geometry --reuse-raw-bake`; this is not a silent fallback. Numerical results may vary across compilers and dependency versions. `evidence/environment.json` records this execution environment.

With Mesa/EGL available, add `--glsl-proof` for the standalone native GLES proof. This option does not launch or certify a browser. The newly added orchestration wrapper was syntax-checked; its constituent build, bake, resolve, packaging and proof stages were executed individually in this delivery, not rerun end-to-end through that wrapper.

The package includes all source, precomputed runtime lighting and proof images. Large temporary native mesh/bake work files are rebuilt rather than duplicated in the archive. A sampled subset of actual raw spectra is included for inspection. CYBR GEO-derived code retains GPL-2.0-only; the bundled Three.js code retains its MIT notice. Original bundled asset notices are preserved.
