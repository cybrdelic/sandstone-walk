# Sandstone Walk 0.1.1

Verified publication of the native surface-bake recovery as a ready-to-serve Three.js project. This packaging update includes passing Chromium canvas captures and controls tests; geometry, baked lighting, viewer shaders, GIF and MP4 are unchanged.

- Exact 8,108,728-triangle canyon and preserved lighting buffers.
- Reviewable browser code, shaders, native geometry/bake source and asset provenance.
- Six-second genuinely rendered camera loop in GIF and higher-quality MP4 formats.
- SHA-256-checked split web assets and byte-identical offline HTML reconstruction.
- Geometry, bake, native shader and browser-test evidence kept separately.

Download `Sandstone_Walk_Standalone.html` for the single-file viewer, or `Sandstone_Walk_Project.zip` for the source, precomputed assets and media. Serve the project ZIP with `python -m http.server 8000`.

Lighting is static. No real-time spectral path tracing, dynamic GI, collision controller or mobile performance qualification is claimed. Native preview frames are not browser recordings.
