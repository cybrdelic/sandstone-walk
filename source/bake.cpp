// GPL-2.0-only. Surface irradiance bake adapter for the recovered CYBR GEO tracer.
// No reference photographs or hero-camera images are read by this program.
#define main cybr_preserved_native_main
#include "transport_bake.cpp"
#undef main
#include <filesystem>

struct Site {V p,n;float material;};
static_assert(sizeof(Site)==28);
struct VertexBake {V n;float rough; V direct;float visibility; Spec reflectance;};
static_assert(sizeof(VertexBake)==96);
std::vector<Site> readSites(const std::string&path,const char* magic){
 std::ifstream f(path,std::ios::binary);char h[4];uint32_t n;
 f.read(h,4);f.read(reinterpret_cast<char*>(&n),4);
 if(!f||std::memcmp(h,magic,4)||n>12000000)throw std::runtime_error("Bad sample file");
 std::vector<Site>s(n);f.read(reinterpret_cast<char*>(s.data()),s.size()*sizeof(Site));
 if(!f)throw std::runtime_error("Truncated samples");
 for(const auto&a:s)for(float x:{a.p.x,a.p.y,a.p.z,a.n.x,a.n.y,a.n.z,a.material})if(!std::isfinite(x))throw std::runtime_error("Nonfinite sample");
 return s;
}
void loadExactMesh(const std::string&path){
 std::ifstream f(path,std::ios::binary);uint32_t n;f.read(reinterpret_cast<char*>(&n),4);
 if(!f||n!=8108728)throw std::runtime_error("Unexpected geometry count; refusing a substitute scene");
 tris.resize(n);
 for(uint32_t i=0;i<n;i++){
  float a[20];f.read(reinterpret_cast<char*>(a),80);if(!f)throw std::runtime_error("Truncated mesh");
  Tri&t=tris[i];t.p=V(a[0],a[1],a[2]);t.e1=V(a[3],a[4],a[5])-t.p;t.e2=V(a[6],a[7],a[8])-t.p;
  t.n0=V(a[9],a[10],a[11]);t.n1=V(a[12],a[13],a[14]);t.n2=V(a[15],a[16],a[17]);t.mat=int(a[18]);t.group=int(a[19]);
 }
 order.resize(n);std::iota(order.begin(),order.end(),0);nodes.reserve(n/2);build(0,n);buildWideR3();
 std::cerr<<"EXACT_BVH "<<n<<" triangles "<<nodes.size()<<" nodes "<<wideNodesR3.size()<<" wide\n";
}
float radicalInverse(uint32_t x){
 x=(x<<16)|(x>>16);x=((x&0x55555555u)<<1)|((x&0xaaaaaaaau)>>1);x=((x&0x33333333u)<<2)|((x&0xccccccccu)>>2);
 x=((x&0x0f0f0f0fu)<<4)|((x&0xf0f0f0f0u)>>4);x=((x&0x00ff00ffu)<<8)|((x&0xff00ff00u)>>8);
 return x*2.3283064365386963e-10f;
}
int main(int argc,char**argv){try{
 if(argc<7)throw std::runtime_error("Usage: bake mesh sites vertices outdir assetdir spp [threads] [depth]");
 const std::string output=argv[4],assets=argv[5];const int spp=std::stoi(argv[6]),threads=argc>7?std::stoi(argv[7]):4,depth=argc>8?std::stoi(argv[8]):8;
 if(spp<8||spp>4096||threads<1||depth<2)throw std::runtime_error("Invalid budgets");
 std::filesystem::create_directories(output);omp_set_num_threads(threads);
 sceneStyle=0;sceneSunScale=1.f;sceneSkyScale=.95f;SUN=unit(V(-.24f,-.33f,.913f));useClouds=false;useSteam=false;useWater=false;indirectClamp=0;
 configureScene();initSpectra();bakeSuppressPrimarySolar=true;
 photographicGrain.load(assets+"/gravel_periodic.pgm");granularRelief.load(assets+"/granular_relief.bin");
 auto start=std::chrono::steady_clock::now();loadExactMesh(argv[1]);
 const auto elapsed=[&](){return std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();};
 std::cerr<<"BVH_SECONDS "<<elapsed()<<"\n";
 auto sites=readSites(argv[2],"SIT1");std::vector<Spec>irr(sites.size());std::vector<float>variances(sites.size());std::atomic<uint64_t> invalid{0},rays{0};std::atomic<int>completed{0};
 // Estimate E = integral Li cos(theta) dOmega. Direct solar escape is excluded
 // here because solar visibility is evaluated independently below. Reflections
 // of the sun through other surfaces still go through native trace().
 #pragma omp parallel for schedule(dynamic,64)
 for(size_t i=0;i<sites.size();i++){
  const Site&s=sites[i];V n=unit(s.n);Frame frame(n);RNG rng(uint64_t(i)*0x9e3779b97f4a7c15ULL+20260917u);
  const float rotation=rng.uniform();Spec sum;double lum2=0;
  for(int j=0;j<spp;j++){
   float u=(j+.5f)/spp,phi=2*PI*std::fmod(radicalInverse(j)+rotation,1.f);float r=std::sqrt(u);
   V d=frame.world(V(r*std::cos(phi),r*std::sin(phi),std::sqrt(1-u)));
   Spec value=trace(Ray(s.p+n*(EPS*8),unit(d)),rng,depth,.002f);
   bool finite=true;for(float x:value.v)finite=finite&&std::isfinite(x)&&x>=0;
   if(!finite){invalid++;continue;}sum+=value;double lum=xyz(value).y;lum2+=lum*lum;
  }
  irr[i]=sum*(PI/spp);double l=xyz(sum).y/spp;variances[i]=float(PI*PI*std::max(0.,lum2/spp-l*l)/(spp-1));
  int done=++completed;if(done%20000==0){
   #pragma omp critical
   std::cerr<<"INDIRECT "<<done<<"/"<<sites.size()<<" "<<elapsed()<<" s\n";
  }
 }
 std::ofstream gi(output+"/irradiance.raw.f32",std::ios::binary);gi.write(reinterpret_cast<char*>(irr.data()),irr.size()*sizeof(Spec));gi.close();
 std::ofstream var(output+"/variance.raw.f32",std::ios::binary);var.write(reinterpret_cast<char*>(variances.data()),variances.size()*4);var.close();
 sites.clear();sites.shrink_to_fit();irr.clear();irr.shrink_to_fit();variances.clear();variances.shrink_to_fit();
 const double giSeconds=elapsed();std::cerr<<"INDIRECT_COMPLETE "<<giSeconds<<" s\n";
 auto vertices=readSites(argv[3],"VTX1");constexpr size_t batch=131072;std::vector<VertexBake>out(batch);std::ofstream vf(output+"/vertex_bake.raw.f32",std::ios::binary);
 const int sunSamples=16;Frame sf(SUN);std::array<V,sunSamples> sunDirs;
 for(int j=0;j<sunSamples;j++){float c=1-(j+.5f)/sunSamples*(1-SUN_COS),r=std::sqrt(std::max(0.f,1-c*c)),p=2*PI*radicalInverse(j);sunDirs[j]=unit(sf.world(V(r*std::cos(p),r*std::sin(p),c)));}
 for(size_t first=0;first<vertices.size();first+=batch){size_t count=std::min(batch,vertices.size()-first);
  #pragma omp parallel for schedule(static)
  for(size_t j=0;j<count;j++){
   size_t i=first+j;const Site&s=vertices[i];V geom=unit(s.n),n=geom;
   Surface m=shade(s.p,n,int(s.material),.008f);if(dot(n,geom)<.1f)n=geom;
   Spec base=rgbAnchors(m.color);VertexBake v;v.n=n;v.rough=m.rough;v.reflectance=base;v.direct=toRGB(base*solar)*(SUN_SOLID/PI);
   float visibility=0;RNG rng(i+394853);
   if(dot(n,SUN)>.002f&&dot(geom,SUN)>0){
    for(V d:sunDirs){rays++;if(dot(geom,d)>0&&!opaqueShadow(Ray(s.p+geom*(EPS*8),d),INF))visibility+=airTransmittance(Ray(s.p+geom*(EPS*8),d),INF,rng);}
   }
   v.visibility=visibility/sunSamples;out[j]=v;
  }
  vf.write(reinterpret_cast<char*>(out.data()),count*sizeof(VertexBake));
  std::cerr<<"DIRECT "<<first+count<<"/"<<vertices.size()<<" "<<elapsed()<<" s\n";
 }
 vf.close();V sun=toRGB(solar)*SUN_SOLID,wb=toRGB(blackbody(5900.f));
 std::ofstream meta(output+"/bake_execution.json");meta<<std::setprecision(10)<<"{\n\"integrator\":\"recovered CYBR GEO spectral trace, surface irradiance adapter\",\n\"spectral_bands\":16,\n\"wavelength_nm\":[380,780],\n\"triangles\":"<<tris.size()<<",\n\"sites\":"<<completed<<",\n\"hemisphere_samples_per_site\":"<<spp<<",\n\"maximum_path_depth\":"<<depth<<",\n\"sun_samples_per_lit_vertex\":"<<sunSamples<<",\n\"sun_visibility_rays\":"<<rays<<",\n\"vertex_count\":"<<vertices.size()<<",\n\"invalid_samples\":"<<invalid<<",\n\"clamped_contributions\":"<<clampedIndirectContributions<<",\n\"indirect_seconds_including_bvh\":"<<giSeconds<<",\n\"wall_seconds\":"<<elapsed()<<",\n\"solar_rgb\":["<<sun.x<<","<<sun.y<<","<<sun.z<<"],\n\"display_white_rgb\":["<<wb.x<<","<<wb.y<<","<<wb.z<<"],\n\"exposure\":2.5,\n\"reference_image_used\":false,\n\"hero_camera_used_by_bake\":false\n}\n";
 std::ofstream matrix(output+"/spectral_rgb_matrix.f32",std::ios::binary);for(int i=0;i<NBANDS;i++){Spec s;s.v[i]=1;V c=toRGB(s);matrix.write(reinterpret_cast<char*>(&c),sizeof(V));}
 return invalid?2:0;
 }catch(const std::exception&e){std::cerr<<"BAKE_FAILED "<<e.what()<<"\n";return 1;}}
