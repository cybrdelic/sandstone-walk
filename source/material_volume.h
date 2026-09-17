// SPDX-License-Identifier: GPL-2.0-only
// Authored sandstone reflectance for the closed formation. Not measured mineral spectra.
// Keep the old material implementation as an explicit non-canyon fallback.
#pragma once
#define shade cybrLegacyFormationShade
#include "formation_materials_r4.h"
#undef shade
Surface shade(V p,V& n,int id,float footprint){
 if(sceneStyle!=0)return cybrLegacyFormationShade(p,n,id,footprint);
 Surface m;m.kind=id;m.ior=1.49f;const V geometric=n;
 const float macro=noise(V(p.x*.25f,p.y*.19f,p.z*.21f));
 const float grain=noise(p*57.f)/(1.f+sqr(footprint*57.f));
 if(id==0||id==4){
  float bank=noise(V(p.x*.56f,p.y*.32f,2.1f));
  m.color=mixc(V(.29f,.204f,.130f),V(.425f,.320f,.220f),clamp(.62f+.21f*bank));
  m.color*=1.f+.045f*grain+.035f*noise(p*12.f);
  m.rough=.95f;
  m.color*=1.f+.18f*(projectedGrain(p,n,footprint,.63f)-1.f);
  n=unit(n-projectedRelief(p,n,footprint,.18f));
 }else{
  float bed=p.z+.022f*p.y;
  float lith=noise(V(p.y*.21f,bed*1.1f,p.x*.14f));
  m.color=mixc(V(.285f,.153f,.070f),V(.445f,.289f,.148f),clamp(.56f+.30f*lith+.13f*macro));
  // Subtle bedding colour. Geometry, not a high-contrast texture, carries the ledges.
  float lamina=std::sin(bed*71.f+.9f*noise(V(p.y*.9f,bed*.71f,0)));
  m.color*=1.f+.019f*lamina/(1.f+sqr(footprint*71.f))+.035f*grain;
  // Sparse broad weathering, avoiding the earlier high-frequency camouflage mask.
  float streak=smooth(.05f,.62f,noise(V(p.y*.39f,p.z*.035f,p.x*.22f))+.21f*noise(V(p.y*1.8f,p.z*.12f,3.8f)));
  streak*=smooth(1.5f,7.f,p.z)*(1-smooth(.25f,.68f,n.z));
  float spall=smooth(.1f,.55f,noise(p*.8f));streak*=1-.65f*spall;
  m.color=mixc(m.color,V(.16f,.118f,.077f),streak*.34f);
  float dust=smooth(.38f,.90f,n.z)*(.56f+.14f*noise(p*1.6f));
  m.color=mixc(m.color,V(.42f,.300f,.186f),dust*.48f);
  if(id==2){m.color=mixc(m.color,V(.36f,.234f,.126f),.22f);streak*=.2f;}
  m.rough=.88f-.055f*streak;
  m.color*=1.f+.125f*(projectedGrain(p,n,footprint,.63f)-1.f);
  n=unit(n-noiseSlope(p,n,52.f,.047f,footprint));
  n=unit(n-projectedRelief(p,n,footprint,.09f));
 }
 if(dot(n,geometric)<.8f)n=unit(n+geometric);
 m.color=vmin(vmax(m.color,V(.01f)),V(.75f));return m;
}
