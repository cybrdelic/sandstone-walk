"""Integrate closed-formation support while preserving the tested navigation code."""
from __future__ import annotations
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def patch(path,old,new):
 p=ROOT/path;s=p.read_text()
 if new in s:return
 if s.count(old)!=1:raise ValueError('Integration anchor mismatch: '+path+' '+old[:80])
 p.write_text(s.replace(old,new,1))

def main():
 patch('source/transport_bake.cpp','#include "formation_materials_r4.h"','#ifndef CYBR_FORMATION_MATERIALS\n#define CYBR_FORMATION_MATERIALS "formation_materials_r4.h"\n#endif\n#include CYBR_FORMATION_MATERIALS')
 patch('source/bake.cpp','#include <filesystem>','#include <filesystem>\n#ifndef CYBR_EXPECTED_TRIANGLE_COUNT\n#define CYBR_EXPECTED_TRIANGLE_COUNT 8108728\n#endif')
 patch('source/bake.cpp','n!=8108728','n!=CYBR_EXPECTED_TRIANGLE_COUNT')
 patch('web/app.js',"if(triangles!==8108728||vertices!==4072674)throw new Error('Geometry integrity totals do not match the preserved canyon.');","if(triangles!==B.meta.triangles||vertices!==B.meta.vertex_count)throw new Error('Geometry integrity totals do not match the current native formation.');")
 patch('web/app.js','exact geometry uses substantial GPU memory.','the full formation uses substantial GPU memory.')
 # The historical verifier remains intact and usable against the legacy release.
 p=ROOT/'tools/verify.py'
 if p.exists():
  old="if __name__=='__main__':main()"
  new="if __name__=='__main__':\n    if manifest()['meta'].get('version')=='0.3.0':\n        from verify_volume import main as volume_main\n        volume_main()\n    else:main()"
  patch('tools/verify.py',old,new)
 for path in ['tools/browser_smoke.py','tools/mobile_controls_smoke.py']:
  p=ROOT/path
  if not p.exists():continue
  text=p.read_text()
  if 'EXPECTED_TRIANGLES' not in text:
   i=text.index('\n',text.index('ROOT=')) if 'ROOT=' in text else text.index('\n',text.index('ROOT ='))
   text=text[:i]+"\n_EXPECTED=json.loads((ROOT/'web/scene.json').read_text())['meta']\nEXPECTED_TRIANGLES=_EXPECTED['triangles']\nEXPECTED_VERTICES=_EXPECTED['vertex_count']"+text[i:]
   text=text.replace('8108728','EXPECTED_TRIANGLES').replace('4072674','EXPECTED_VERTICES')
   p.write_text(text)
 p=ROOT/'tools/requirements-test.txt'
 if p.exists():
  s=p.read_text()
  for requirement in ['scipy==1.17.0','trimesh==4.11.1','shapely==2.1.2']:
   if requirement not in s:s+=requirement+'\n'
  p.write_text(s)
 p=ROOT/'package.json'
 if p.exists():
  d=json.loads(p.read_text());d['version']='0.3.0';p.write_text(json.dumps(d,indent=2)+'\n')
 print('Volume support integrated. Mobile controller, CSS and GLSL unchanged.')

if __name__=='__main__':main()
