# Closed-landform geometry correction

## Scope

The v0.2 canyon was composed of interior surface sheets. This revision changes the source geometry itself and rebakes it. It does not project the original screenshot, add guessed radiance probes or apply a cosmetic image filter.

`source/solid_geometry.py` imports the existing CYBR GEO assembly builder and deterministic field primitives, then constructs one connected terrain. The charts traverse the west exterior/rim, west inner cliff, alluvial floor, east inner cliff and east exterior/rim. The perimeter and underside close the volume. Adjacent charts use identical boundary coordinates and geometric normals. The far view turns with the channel rather than terminating at a separate upright backdrop.

A canonical closed mesh is tested before chart separation. `tools/verify_solid.py` independently decodes the *delivered* buffers, exactly welds the duplicated chart boundaries and checks closure, winding, positive volume and connectedness again. Rocks are checked as separate closed components. No epsilon-based welding is used to hide gaps.

Rim and upland relief are distinct two-dimensional fields; rim notches are not swept across the whole plateau. Bedding units have irregular thickness/resistance and finite joint/spall cuts. Anisotropic, tilted joint-plane intersections produce the rockfall blocks. A bounded, resolved implicit relief field breaks the perfectly flat convex-hull appearance; Marching Cubes extracts actual watertight geometry. Footprint-dependent mesh resolution puts more vertices on the large nearby blocks.

## Native bake

`source/prepare_solid.py` emits real sample positions/normals and a complete vertex stream. Grid charts use explicit sampled rows/columns. Hero blocks retain full vertex sampling. Smaller rocks use deterministic samples chosen by spatial and normal separation, plus extra contact-region samples on the larger talus; interpolation is constrained to the same closed rock and preserves exact sample values before the original positive adjacency filter. The emitted site count is recorded, not inferred from the vertex count. `source/solid_bake.cpp` imports the retained native spectral transport implementation and requires the triangle count from the freshly validated layout at compile time. The wrapper checks the mesh hash before invoking it.

The bake evaluates 256 cosine-weighted hemisphere samples per location at 16 wavelength bands, up to 10 path bounces. Solar escape is excluded from the indirect estimator to avoid double counting. Separate finite-sun visibility uses all scene triangles and up to 16 solar rays per lit vertex. The existing positive normal/position-guided irradiance resolve is retained. Source and viewer GLSL remain byte-identical.

`source/package_solid.py` stores new, `solid-`-prefixed compressed assets. Old assets and their original manifest are preserved; legacy receipts are not rewritten as new evidence. Browser integrity totals change deliberately and still fail closed. Both web and standalone use the same buffers, material shaders and control implementation. The sole route change in the mobile controller reads the new centerline for the automatic walk.

## Limits

This is art-directed geometry, not a physically simulated geological history or surveyed sandstone site. The finite scene's underside/perimeter is a presentation boundary. Mesh closure, positive component volume and shared-seam checks are not exhaustive collision/intersection certification. Navigation remains free-camera. GI is a static surface bake; some sub-texel shading and narrow shadow transitions remain approximate.

## Closure and sampling fixes checked during this revision

The front and rear endcaps are constrained triangulations of the actual XZ boundary profiles. Only the outer terrain edges descend to the base; the underside is a separate constrained XY triangulation. Projecting every vertical wall vertex straight onto the bottom created overlapping/degenerate cap edges in an intermediate build. That build was rejected by exact-position-weld validation of the delivered float32 buffers, not published.

Every rock is also required to be a single connected closed body. Two sub-grid disconnected islands produced by the implicit roughness field were removed before the final geometry export. This is meshing cleanup, not a terrain scan or erosion simulation.

Sparse rock irradiance samples are selected by a deterministic position/normal farthest-point rule, independently inside each connected rock. Large-talus contact regions receive extra sites; hero blocks retain every-vertex irradiance sampling. Unsampled vertices interpolate only from the same rock. All vertices still receive full geometric normal/material evaluation and independent finite-sun visibility queries. `bake_inputs.json` fingerprints the exact mesh, sites, vertices and compiled baker before transport executes and verifies them afterward.
