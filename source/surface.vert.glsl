precision highp float;
uniform mat4 uVP;
in vec3 position;
in vec3 bakeNormal;
in vec3 directRadiance;
in vec3 indirectRadiance;
in vec2 surface;
out vec3 vWorld;
out vec3 vNormal;
out vec3 vDirect;
out vec3 vIndirect;
out vec2 vSurface;
void main(){
 vWorld=position;vNormal=bakeNormal;vDirect=directRadiance;vIndirect=indirectRadiance;vSurface=surface;
 gl_Position=uVP*vec4(position,1.0);
}
