// SPDX-License-Identifier: GPL-2.0-only
#include "spectral_geometry.h"
#include "material_native.h"
#include <fstream>
#include <stdexcept>
#include <array>
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("material_probe input.f32 output.f32");
 std::ifstream input(argv[1],std::ios::binary);std::ofstream output(argv[2],std::ios::binary);
 if(!input||!output)throw std::runtime_error("Probe files could not be opened");
 std::array<float,8> a;
 while(input.read(reinterpret_cast<char*>(a.data()),sizeof(a))){
  auto m=sw::swMaterial(V(a[0],a[1],a[2]),V(a[4],a[5],a[6]),int(a[7]),a[3]);
  float result[]={m.color.x,m.color.y,m.color.z,m.rough,m.normal.x,m.normal.y,m.normal.z,0.f};
  output.write(reinterpret_cast<char*>(result),sizeof(result));
 }
 if(!input.eof()||input.gcount()!=0)throw std::runtime_error("Truncated probe inputs");
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
