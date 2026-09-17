precision highp float;
precision highp int;
uniform vec3 uEye;
uniform vec3 uSun;
uniform vec3 uSolar;
uniform vec3 uWhite;
uniform float uExposure;
uniform int uMode;
uniform mat3 uRGBToAnchors;
uniform mat3 uSolarResponse;
in vec3 vWorld;
in vec3 vNormal;
in vec3 vGiR;
in vec3 vGiG;
in vec3 vGiB;
in vec2 vSurface;
out vec4 outColor;
const float PI=3.141592653589793;
__MATERIAL_FIELD__
float fresnel(float c){
 const float eta=1.49;
 float st2=(1.0-c*c)/(eta*eta),ct=sqrt(max(0.0,1.0-st2));
 float rs=(c-eta*ct)/(c+eta*ct),rp=(eta*c-ct)/(eta*c+ct);
 return .5*(rs*rs+rp*rp);
}
float ggxD(float nh,float a){float a2=a*a;float d=nh*nh*(a2-1.0)+1.0;return a2/(PI*d*d);}
float smithG1(float c,float a){return c>0.0?2.0*c/(c+sqrt(a*a+(1.0-a*a)*c*c)):0.0;}
vec3 encodeNative(vec3 rgb){
 vec3 a=max(rgb/uWhite*uExposure,vec3(0.0));
 a=a*a/(a+vec3(.035));float peak=max(max(a.r,a.g),max(a.b,.0000001));
 a*=(1.0-exp(-peak))/peak;
 a=clamp(a,0.0,1.0);
 return mix(12.92*a,1.055*pow(a,vec3(1.0/2.4))-.055,step(vec3(.0031308),a));
}
float screenFootprint(vec3 dx,vec3 dy){
 float a=dot(dx,dx),b=dot(dx,dy),c=dot(dy,dy);
 return sqrt(max(.5*(a+c+sqrt(max(0.0,(a-c)*(a-c)+4.0*b*b))),1e-12));
}
vec3 encodeAlbedo(vec3 a){return mix(12.92*a,1.055*pow(max(a,0.0),vec3(1.0/2.4))-.055,step(vec3(.0031308),a));}
void main(){
 vec3 dx=dFdx(vWorld),dy=dFdy(vWorld);
 float footprint=screenFootprint(dx,dy);
 vec3 geometric=normalize(vNormal),V=normalize(uEye-vWorld),L=uSun;
 vec3 Ng=normalize(cross(dx,dy));
 if(dot(Ng,V)<0.0)Ng=-Ng;
 if(dot(geometric,Ng)<0.0)geometric=-geometric;
 if(dot(geometric,Ng)<.1||dot(geometric,V)<.01)geometric=Ng;
 int family=int(floor(vSurface.y*255.0+.5));
 SWMaterial material=swMaterial(vWorld,geometric,family,footprint);
 vec3 N=material.normal;
 if(dot(N,Ng)<.1||dot(N,V)<.01)N=geometric;
 float nv=max(dot(N,V),.0001),nl=max(dot(N,L),0.0);
 float rough=material.rough,visibility=clamp(vSurface.x,0.0,1.0);
 vec3 anchors=clamp(uRGBToAnchors*material.color,vec3(0.0),vec3(.985));
 vec3 H=normalize(V+L);float fr=fresnel(clamp(dot(V,H),0.0,1.0));
 float s2=pow(rough*.52,2.0),A=1.0-s2/(2.0*(s2+.33)),B=.45*s2/(s2+.09);
 float vi=sqrt(max(0.0,1.0-nv*nv)),li=sqrt(max(0.0,1.0-nl*nl));
 float cosPhi=vi*li>.00000001?max(0.0,(dot(V,L)-nv*nl)/(vi*li)):0.0;
 float oren=A+B*cosPhi*max(vi,li)*min(vi/max(nv,.00001),li/max(nl,.00001));
 float alpha=max(.018,rough*rough);
 vec3 direct=(uSolarResponse*anchors)*(1.0-fr)*oren*nl*visibility;
 if(nl>0.0)direct+=uSolar*(visibility*fr*ggxD(max(dot(N,H),0.0),alpha)*smithG1(nv,alpha)*smithG1(nl,alpha)/(4.0*nv));
 const float F0=(.49*.49)/(2.49*2.49);
 vec3 indirect=max((vGiR*anchors.x+vGiG*anchors.y+vGiB*anchors.z)*((1.0-F0)*A),0.0);
 vec3 radiance=direct+indirect;
 if(uMode==1)radiance=direct;
 else if(uMode==2)radiance=indirect;
 else if(uMode==3){outColor=vec4(N*.5+.5,1.0);return;}
 else if(uMode==4){outColor=vec4(vec3(visibility),1.0);return;}
 else if(uMode==5){outColor=vec4(encodeAlbedo(material.color),1.0);return;}
 else if(uMode==6){
  // 25-cm volumetric checker: no UVs or chart-dependent coordinates.
  vec3 q=vWorld*4.0,w=max(fwidth(q),vec3(.0001));
  vec3 integral=2.0*(abs(fract((q-.5*w)*.5)-.5)-abs(fract((q+.5*w)*.5)-.5))/w;
  float pattern=.5-.5*integral.x*integral.y*integral.z;
  outColor=vec4(mix(vec3(.15),vec3(.85),pattern),1.0);return;
 }
 else if(uMode==7){outColor=vec4(vec3(rough),1.0);return;}
 else if(uMode==8){outColor=vec4(geometric*.5+.5,1.0);return;}
 outColor=vec4(encodeNative(radiance),1.0);
}
