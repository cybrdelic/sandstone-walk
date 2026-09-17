# Why the previous R4 delivery was rejected

The prior app retained the reference-image projection instead of providing a camera-independent native lighting bake. Its `initProbeVolume()` assigned irradiance colors using hand-authored formulas, without reading any native probe render output. Six longitudinal rows produced twelve side entries plus three elevated entries; the 18-element array then filled three remaining slots by repeating the final entry.

Its custom physical-material shader referenced `specularStrength`, which was absent from the expanded physical shader. It also fed the physical shader's view-space `geometryNormal` into a function whose positions and probe directions were in world coordinates. Thus the code contained both a shader correctness defect and a coordinate-space mismatch.

The old `verification.json` contained only four declarations: version, probe count, retained hero cache and retained geometry pipeline. It was not a render-test report.

The recovery does not retain that shader injection, the projected photograph, or those authored probe values. It retains the original geometry and executes a separate native spectral surface bake. Its limited native shader verification is explicitly distinguished from the unavailable browser run.
