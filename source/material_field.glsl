// SPDX-License-Identifier: GPL-2.0-only
// Shared GLSL / C++ material field. P is in metres, N is a GEOMETRIC normal.
// All stochastic coordinates are isotropic 3D. No UVs, chart indices, normal-
// dependent projection or camera-space coordinates enter color/height.
// Footprint controls bandwidth only; it never changes the feature locations.
struct SWNoise { float value; vec3 gradient; };
struct SWMaterial { vec3 color; vec3 normal; float rough; };
uint swHash(int x, int y, int z) {
    uint h = uint(x)*0x8da6b343u ^ uint(y)*0xd8163841u ^ uint(z)*0xcb1ab31fu ^ 0x9e3779b9u;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15; h *= 0x846ca68bu; h ^= h >> 16;
    return h;
}
float swSaturate(float x) { return min(1.0,max(0.0,x)); }
float swSmooth(float a,float b,float x) { float t=swSaturate((x-a)/(b-a)); return t*t*(3.0-2.0*t); }
SWNoise swNoise(vec3 p) {
    int ix=int(floor(p.x)), iy=int(floor(p.y)), iz=int(floor(p.z));
    vec3 f=p-vec3(float(ix),float(iy),float(iz));
    vec3 t=f*f*f*(f*(f*6.0-vec3(15.0))+vec3(10.0));
    vec3 dt=30.0*f*f*(f-vec3(1.0))*(f-vec3(1.0));
    SWNoise n; n.value=0.0; n.gradient=vec3(0.0);
    for(int a=0;a<2;a++) for(int b=0;b<2;b++) for(int c=0;c<2;c++) {
        float v=float(swHash(ix+a,iy+b,iz+c)>>8)*(1.0/8388608.0)-1.0;
        float x=a==1?t.x:1.0-t.x, y=b==1?t.y:1.0-t.y, z=c==1?t.z:1.0-t.z;
        float dx=a==1?dt.x:-dt.x, dy=b==1?dt.y:-dt.y, dz=c==1?dt.z:-dt.z;
        n.value+=v*x*y*z;
        n.gradient+=v*vec3(dx*y*z,x*dy*z,x*y*dz);
    }
    return n;
}
// Fade unresolved octaves to their analytic zero mean. The conservative largest
// singular screen footprint is provided by the fragment shader. The path tracer
// supplies its native ray footprint. Derivatives are never evaluated in branches.
SWNoise swBand(vec3 p, float frequency, float footprint, vec3 offset) {
    float weight=1.0-swSmooth(0.20,0.65,frequency*footprint);
    SWNoise n; n.value=0.0; n.gradient=vec3(0.0);
    if(weight>0.00001) {
        // A fixed orthonormal rotation avoids aligning the value-noise lattice
        // with horizontal/vertical rock faces. It changes no metric scale.
        vec3 q=vec3(.8*p.y+.6*p.z,-.8*p.x+.36*p.y-.48*p.z,-.6*p.x-.48*p.y+.64*p.z);
        n=swNoise(q*frequency+offset);
        vec3 gradient=n.gradient;
        n.gradient=vec3(-.8*gradient.y-.6*gradient.z,
            .8*gradient.x+.36*gradient.y-.48*gradient.z,
            .6*gradient.x-.48*gradient.y+.64*gradient.z);
        n.value*=weight; n.gradient*=weight*frequency;
    }
    return n;
}
SWMaterial swMaterial(vec3 p,vec3 geometric,int family,float footprint) {
    vec3 n=normalize(geometric);
    SWNoise broad=swBand(p,.37,footprint,vec3(13.1,-8.4,2.3));
    SWNoise mottled=swBand(p,1.65,footprint,vec3(-17.2,3.8,29.1));
    SWNoise broken=swBand(p,5.8,footprint,vec3(4.9,27.7,-11.8));
    SWNoise pore=swBand(p,23.0,footprint,vec3(-5.7,-14.2,35.6));
    SWNoise grain=swBand(p,92.0,footprint,vec3(31.2,-3.1,7.6));
    SWNoise fine=swBand(p,368.0,footprint,vec3(-12.7,51.2,16.5));
    float macro=.65*broad.value+.25*mottled.value+.10*broken.value;
    float oxidation=swSmooth(-.04,.28,.55*broad.value+.35*mottled.value+.22*broken.value);
    float abrasion=swSmooth(-.04,.42,broken.value*.7+pore.value*.22);
    SWMaterial m;
    if(family==0 || family==4) {
        // Alluvial sediment: the same metre scale on level and inclined ground.
        m.color=mix(vec3(.282,.200,.132),vec3(.417,.314,.216),.56+.30*macro);
        m.color*=1.0+.10*broken.value+.12*pore.value+.20*grain.value+.10*fine.value;
        m.rough=.92+.025*broken.value;
    } else {
        m.color=mix(vec3(.245,.134,.063),vec3(.475,.305,.167),.61+.45*macro);
        float varnish=oxidation*(1.0-.70*abrasion);
        // Mottled, finite patches; no p.z*.12 vertical smearing or per-wall axes.
        m.color=mix(m.color,vec3(.108,.073,.045),.58*varnish);
        m.color*=1.0+.16*broken.value+.12*pore.value+.21*grain.value+.07*fine.value;
        if(family==2 || family==14) m.color=mix(m.color,vec3(.362,.243,.143),.20);
        m.rough=.84-.075*varnish+.020*pore.value;
    }
    vec3 slope=broken.gradient*.0035+pore.gradient*.0025+grain.gradient*.00085+fine.gradient*.00012;
    if(family==0 || family==4) slope*=1.12;
    // True scalar-height gradient projected into the tangent plane. This avoids
    // tangent handedness/projection seams and cannot rotate with the camera.
    slope=slope-n*dot(n,slope);
    float magnitude=length(slope);
    slope*=min(1.0,.22/max(magnitude,.000001));
    m.normal=normalize(n-slope);
    m.color=clamp(m.color,vec3(.008),vec3(.82));
    m.rough=clamp(m.rough,.65,.98);
    return m;
}
