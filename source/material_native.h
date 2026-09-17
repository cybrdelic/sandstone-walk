// SPDX-License-Identifier: GPL-2.0-only
#pragma once
// The common material field is valid GLSL plus this small C++ compatibility layer.
namespace sw {
using vec3=V;
using uint=uint32_t;
using std::floor;
inline float min(float a,float b){return std::min(a,b);}
inline float max(float a,float b){return std::max(a,b);}
inline float clamp(float p,float a,float b){return min(max(p,a),b);}
inline V normalize(V v){return unit(v);}
inline float length(V v){return len(v);}
inline V mix(V a,V b,float t){return a*(1.f-t)+b*t;}
inline V clamp(V p,V a,V b){return vmin(vmax(p,a),b);}
#include "material_field.glsl"
}
