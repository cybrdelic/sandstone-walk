precision highp float;
uniform vec3 uEye;
uniform vec3 uSun;
uniform vec3 uSolar;
uniform vec3 uWhite;
uniform float uExposure;
uniform int uMode;
in vec3 vWorld;
in vec3 vNormal;
in vec3 vDirect;
in vec3 vIndirect;
in vec2 vSurface;
out vec4 outColor;
const float PI=3.141592653589793;
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
void main(){
 vec3 N=normalize(vNormal),V=normalize(uEye-vWorld),L=uSun;
 // Match the native tracer's shading-normal hemisphere safeguards.
 vec3 Ng=normalize(cross(dFdx(vWorld),dFdy(vWorld)));
 if(dot(Ng,V)<0.0)Ng=-Ng;
 if(dot(N,Ng)<0.0)N=-N;
 if(dot(N,Ng)<.1||dot(N,V)<.01)N=Ng;
 float nv=max(dot(N,V),.0001),nl=max(dot(N,L),0.0);
 float rough=clamp(vSurface.y,.1,1.0),visibility=clamp(vSurface.x,0.0,1.0);
 vec3 H=normalize(V+L);float fr=fresnel(clamp(dot(V,H),0.0,1.0));
 float s2=pow(rough*.52,2.0),A=1.0-s2/(2.0*(s2+.33)),B=.45*s2/(s2+.09);
 float vi=sqrt(max(0.0,1.0-nv*nv)),li=sqrt(max(0.0,1.0-nl*nl));
 float cosPhi=vi*li>.00000001?max(0.0,(dot(V,L)-nv*nl)/(vi*li)):0.0;
 float oren=A+B*cosPhi*max(vi,li)*min(vi/max(nv,.00001),li/max(nl,.00001));
 float alpha=max(.018,rough*rough);
 vec3 direct=vDirect*(1.0-fr)*oren*nl*visibility;
 if(nl>0.0)direct+=uSolar*(visibility*fr*ggxD(max(dot(N,H),0.0),alpha)*smithG1(nv,alpha)*smithG1(nl,alpha)/(4.0*nv));
 vec3 indirect=max(vIndirect,0.0);
 vec3 radiance=direct+indirect;
 if(uMode==1)radiance=direct;
 else if(uMode==2)radiance=indirect;
 else if(uMode==3){outColor=vec4(N*.5+.5,1.0);return;}
 else if(uMode==4){outColor=vec4(vec3(visibility),1.0);return;}
 outColor=vec4(encodeNative(radiance),1.0);
}
