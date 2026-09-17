# Rendering architecture

The geometry and lighting originate from the native surface-bake recovery, not the rejected single-camera projection or heuristic-probe variants.

## Offline

`source/cybr-geo/examples/three_scenes/rebuild_scenes.py` generates the seven mesh groups. `source/prepare.py` extracts exact vertex/index buffers and surface sampling sites. `source/bake.cpp` calls the retained native spectral transport code in `source/transport_bake.cpp`; it estimates indirect illumination in 16 wavelength bands and traces separate finite-sun visibility against the complete mesh. `source/resolve.py` filters and interpolates those samples onto the original vertices. `source/pack_app.py` packs the original single-file viewer.

Indirect light escaping directly to the sun from the receiving site is excluded from the indirect estimate because direct solar lighting has its own term. Reflected sunlight through other surfaces remains in the native indirect integrator. The pipeline combines spectral reflectance and irradiance before integrating RGB.

## Runtime

`web/scene.json` names all zlib-compressed binary arrays and their lengths/hashes. `web/bootstrap.js` fetches that manifest and the GLSL; `web/app.js` inflates the arrays and creates Three.js buffers. Float32 positions, 32-bit indices, normalized 16-bit normals/surface parameters and half-precision direct/indirect values preserve the recovery's delivered data. Grid index buffers are regenerated in the exact original face order.

The raw GLSL evaluates Oren–Nayar-style direct diffuse response and a rough dielectric GGX direct specular term with native solar radiance and baked visibility. Indirect surface radiance is interpolated. A half-float texture stores the native sky evaluation; it is not a photograph. White balance, exposure and the native hue-preserving display transform occur once in GLSL, with no additional Three.js tone-mapping pass.

## Why split the HTML?

The original 124,439,021-byte HTML embeds all compressed arrays as base64. The repository stores the same arrays as separate binary resources totaling 92,786,366 bytes, along with reviewable JavaScript and GLSL. No asset exceeds 7.3 MB. The web shader files are byte-identical to their native source copies. `tools/make_standalone.py` recreates and verifies the exact original HTML when an offline single-file delivery is needed.

## Scope

This is view-independent diffuse surface lighting plus a view-dependent direct shading term. It is not a multi-view radiance field, dynamic probe system, mesh simplification experiment, or a camera-dependent image projection. See the README for current visual and performance limitations.
