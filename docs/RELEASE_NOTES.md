# Sandstone Walk 0.4.0 — World-space materials

Fix elongated per-vertex color/bump interpolation and anisotropic weathering coordinates. Replace them with a shared, per-fragment metre-scaled 3D material field, analytic micro-normal gradients and footprint filtering. The native 16-band surface bake is recomputed with that same material; receiver reflectance is applied after interpolating signed spectral-anchor light response.

All v0.3 positions and triangle indices, mobile controls and orbit navigation are preserved. New albedo, 25 cm world-checker, roughness and geometric-normal diagnostics are included. CPU/GLSL material and tessellation-parity tests supplement the existing mesh, desktop, mobile and multi-view checks.

This is authored procedural sandstone, not scanned rock or an AAA certification. The lighting remains a static diffuse bake. Previous releases and the legacy recovery remain available.
