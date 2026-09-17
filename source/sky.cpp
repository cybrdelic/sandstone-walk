#define main cybr_preserved_main
#include "transport_bake.cpp"
#undef main
int main(int argc,char**argv){if(argc!=2)return 1;sceneStyle=0;sceneSunScale=1;sceneSkyScale=.95f;SUN=unit(V(-.24f,-.33f,.913f));useClouds=false;useSteam=false;configureScene();initSpectra();
 std::ofstream f(argv[1],std::ios::binary);uint32_t w=256,h=128;f.write(reinterpret_cast<char*>(&w),4);f.write(reinterpret_cast<char*>(&h),4);
 for(uint32_t y=0;y<h;y++)for(uint32_t x=0;x<w;x++){float t=(y+.5f)*PI/h,p=(x+.5f)*2*PI/w;V d(std::sin(t)*std::cos(p),std::sin(t)*std::sin(p),std::cos(t));V c=toRGB(physicalSky(d));f.write(reinterpret_cast<char*>(&c),sizeof(c));}
}
