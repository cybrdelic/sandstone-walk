# Photographic detail and native pixels — 0.5.0

This revision replaces the **receiving surface material**, not the canyon geometry.
All 5,029,800 source triangles, 2,526,592 vertices, vertex/index order, native sky
and v0.4 incident spectral-response arrays are retained. Native mesh fingerprint:
`7522cf1848ef94af2593e4a2d2a9df382df11c2e85e9ac4662a364a107656c79`.

## Actual material data

Two photographic Poly Haven sources are used: [Rock Face 03](https://polyhaven.com/a/rock_face_03)
and [Sandy Gravel](https://polyhaven.com/a/sandy_gravel). The original diffuse,
OpenGL normal, roughness, displacement and AO maps are 4096 × 4096. They are CC0;
see [Poly Haven's license](https://polyhaven.com/license) and the complete
[URL/size/SHA-256 receipt](../source/detail_sources.json). The canyon itself remains
an authored procedural landform, **not a photogrammetry scan**.

The runtime packs each material into two RGBA textures. Color RGB is sRGB diffuse,
with **linear roughness in alpha**. The second texture is entirely linear: normal
X/Y, normalized height, and AO. Normal/height/AO WebP data is lossless after explicit
8-bit packing; diffuse RGB uses quality-96 WebP. Height sources are quantized from
16 to 8 bits for delivery. A separate 2K derivative is explicitly lower resolution.
There is no AI texture synthesis, photograph projection from a camera, sharpening
pass, painted scene-lighting overlay, or image upscaler.

World-space triplanar projection uses 2.7-metre rock and 2.1-metre sediment periods.
The texture coordinates and handed tangent frames are shared by all registered
maps. Normal gradients are blended in world space rather than assigning tangent
normals to the wrong projection axis. Up to 16× anisotropic filtering and full
mip chains handle oblique/minified texture samples. These settings are reported
by the running viewer rather than inferred from a screenshot.

A bounded 12-layer parallax intersection plus bracket interpolation gives
camera-dependent relief. Four height-field shadow samples add local sun
occlusion. Relief amplitudes are **authored approximations**: 26 mm on rock and
16 mm on sediment, fading smoothly between 5 and 10 metres. These are material
intersections, **not changes to triangle silhouettes or collision geometry**.

## Lighting and its limits

The v0.4 16-band *macro* irradiance response is reused. Photographic albedo is
mean-matched toward that receiver palette, then multiplied by the existing
spectral-anchor response. Fine normals, AO and height shadows are evaluated at
runtime. This is **not a new full spectral bake of all scanned-material bounces**.
Diffuse bounce is low-frequency; off-screen reflection transport and full
view-dependent indirect gloss are still not represented.

Direct sun visibility now comes from the actual scene in a broad 4096² depth map
and a tighter 4096² map around the walking region. Receiver-plane depth correction
avoids the stripe acne of plain constant-bias PCF on sloped receivers. Filter width
uses blocker separation and an approximate finite solar disk, with bounded sample
counts. The near map updates in four-metre camera cells; its light-space bounds
snap to texels. No decorative bounce lights or hand-painted shadow functions are
added. Bias, finite map resolution and the small blocker search remain raster
approximations and can still be exposed by extreme close-ups.

## Raster resolution and stationary antialiasing

The default is **devicePixelRatio**, not one pixel per CSS pixel. A 390 × 844 CSS
viewport at DPR 3 therefore requests 1170 × 2532 actual render pixels (nine times
the former pixel count). Interactive resolution is capped at 8,388,608 pixels and
the GPU's maximum texture dimension; the HUD and report expose any cap. Explicit
1×/0.75× CSS-pixel settings remain available, as does a 1.5× native setting.

The scene is rendered into a half-float HDR target. Eight independent jittered
subpixel samples are averaged **before** the original native tone/color transform.
The first moving-camera sample is centred. After the camera settles, the same
view accumulates; a camera, projection or material change discards that history.
There is no motion reprojection, old-frame warping or ghost-history reuse.

A power-of-two storage exposure of 1/4 keeps the bright solar disk inside
half-float range. The presentation pass restores the factor before display.
Without it, the solar disk could overflow half-float and become NaN/black.
Exposure changes only re-present the current linear image. Once converged, the
viewer stops redrawing the expensive source scene; the displayed update rate
must not be mistaken for a full-scene rendering benchmark.

**Capture 4K PNG** performs a fresh 3840-pixel-long-edge render with eight actual
HDR samples, encodes the canvas, then restores interactive resolution and input.
The original aspect ratio is preserved: the default 3:2 view is **3840 × 2560**.
No 1200-pixel screenshot is enlarged to make this file.

## Memory and navigation

Geometry is deliberately not decimated. Four uncompressed 4K RGBA textures with
mips occupy about **341 MiB** of GPU memory, before scene buffers, two depth maps
and render targets. The 2K derivative uses about **85 MiB** for those maps. WebP
reduces delivery size, not GPU memory. Uploaded ImageBitmaps and compressed mesh
strings are released from CPU memory. The viewer reports context loss and requires
reload instead of pretending that a lost resource still exists.

Mobile thumbstick/look, height controls, orbit/pinch/pan, reference reset and
camera mode restoration are preserved. Navigation is still a free inspection
camera, not a collision or ground-following controller. High-DPI correctness and
emulated touch tests are not measurements of physical-phone frame rate.

## Reproduction

```bash
python -m pip install -r tools/requirements-test.txt
python tools/fetch_detail_sources.py
python tools/prepare_detail_textures.py
python tools/build_detail.py
python tools/verify_detail.py
python tools/make_standalone.py
python tools/make_standalone.py --texture-size 2048 --out dist/Sandstone_Walk_Compact.html
python tools/test_detail_browser.py
```

`tools/test_detail_browser.py --in-memory` uses the exact app, shaders, compressed
scene buffers and material images through an explicit in-memory loader when URL
navigation is unavailable. It is labelled separately from normal localhost HTTP
startup. Its screenshots are still actual Three.js/WebGL renders. Existing
native-field tests cover the preserved base field, **not the additional scans**.
