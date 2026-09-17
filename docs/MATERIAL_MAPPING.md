# Surface mapping correction (0.4)

## Diagnosis

There were no conventional terrain UVs to unwrap. The former viewer interpolated receiving color and perturbed micro-normals stored at mesh vertices. On long or coarsely spaced triangles this turns small-scale texture into elongated gradients. The old canyon patina additionally used strongly unequal axis scales (`p.y*1.15`, `p.z*.12`, `p.x*.10`), giving finite stains a streaked appearance. Higher texture filtering or extra polygons would not remove both defects.

## Replacement

`source/material_field.glsl` is a shared GLSL/C++ subset, included in the native bake through `material_native.h` and emitted into the actual browser shader by `tools/build_material_shaders.py`. All six stochastic bands use isotropic three-dimensional metre coordinates. The same field covers the walls, rims, ground and rocks; material families change reflectance and roughness, not coordinate units. This is a solid procedural texture, not triplanar projection or a newly unwrapped UV atlas.

Color has no dependence on the surface normal or viewing direction. A scalar-height analytic gradient is projected into the geometric tangent plane for micro-normal shading. Slopes are bounded to 0.22. The largest singular value of the world-position screen derivatives sets the footprint filter, so under-resolved octaves fade to their mean. This limits grazing-angle aliasing without changing feature locations.

The native transport is rebaked using the same field. The receiver is not premultiplied into the baked irradiance. Instead, each vertex stores three signed RGB response columns, one per spectral reflectance anchor, computed from the full 16-band incident irradiance. The shader applies the receiver's per-pixel anchors only after interpolating those response columns. Signed half-float values are retained; clamping a response column would corrupt the spectral conversion. The original native sky, display transform, sun direction and direct BRDF remain.

## Checks and diagnostics

`tools/test_material_field.py` compares 4,096 CPU/GPU material evaluations, including negative coordinates, lattice boundaries, varied normals and filter widths. It also renders the identical 18 m × 0.75 m patch using 2 versus 658 triangles and compares the pixels. The 47 × 7 fine grid is rendered at 188 × 126 so its cell boundaries coincide with pixel boundaries. This isolates material interpolation from fixed-point subpixel rasterization differences between differently tessellated primitives; world-position and footprint differences are measured separately, and the original color-error limits are unchanged. Normal-independent albedo and disappearance of unresolved bands are checked separately. `--backend egl` explicitly tests standalone GLES instead of a browser.

The actual scene has Albedo, 25 cm world checker, Roughness, Geometric normals, Micro normals and lighting-isolation modes in Settings. `tools/test_solid_browser.py --materials` captures close walls, floor and talus as beauty/albedo/checker, in addition to the retained walking, reverse, orbit and touch checks. Results are numerical/rendering checks, not automatic aesthetic certification.

Geometry bytes and index topology are required to match v0.3. `restore_material_geometry.py` reconstructs the exact native input from the existing browser positions/indices and the versioned geometric normals/sample maps in `source/material_geometry/`. It requires byte-identical native mesh, vertex-site and irradiance-site hashes. A clean-runner procedural regeneration produced a different native hash even with the same topology totals, so it was rejected rather than substituted. The original procedural recipe remains available, but material-only rebuilds now default to frozen input restoration. Mobile control source and CSS are unchanged. The original bake and native shader files remain for historical comparison. Current standalone packaging uses the new material and response attributes; --legacy retains the original recovery.

## Limits

Authored materials, not measured rock scans. Static baked diffuse GI; no live material/sun edits without a new bake. The world field is anchored to this static terrain: a future movable object should use a rigid object-local metric frame. Finite mesh geometry and irradiance/visibility sampling can still be visible in extreme close-ups. Material detail is fragment work and is more expensive near the surface than interpolated vertex color; no physical-phone frame-rate claim is made.
