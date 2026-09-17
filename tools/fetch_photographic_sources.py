"""Fetch source images from Poly Haven, retaining URLs and content hashes.

No generated imagery, sharpening or upscaling. Outputs are unmodified source
bytes, alongside official API metadata. Packing is a separate reproducible step.
"""
from __future__ import annotations
import hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/photographic_sources'
ASSETS={'rock_face':2.4,'sandy_gravel':2.1}
HEADERS={'User-Agent':'SandstoneWalk/0.5 (CC0 material research; https://github.com/cybrdelic/sandstone-walk)'}

def get(url):
    error=None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=90) as r:
                return r.read()
        except Exception as e:
            error=e;time.sleep(attempt+1)
    raise RuntimeError(f'Could not fetch {url}: {error}')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'schema':'sandstone-walk-photographic-intake/1','license':'CC0-1.0',
      'license_source':'https://polyhaven.com/license','assets':{}}
    for asset,tile in ASSETS.items():
        folder=OUT/asset;folder.mkdir(exist_ok=True)
        raw=get('https://api.polyhaven.com/files/'+asset)
        (folder/'files.json').write_bytes(raw);files=json.loads(raw)
        info=get('https://api.polyhaven.com/info/'+asset);(folder/'info.json').write_bytes(info)
        entry={'source_page':'https://polyhaven.com/a/'+asset,'metres_per_tile':tile,'files':{},'metadata':json.loads(info)}
        for kind in ['diff','nor_gl','rough','ao','disp']:
            variants=files.get(kind,{}).get('4k',{})
            if not variants:raise RuntimeError(f'No 4K {kind} map: {asset}; available: {list(files)}')
            ext='png' if 'png' in variants else 'jpg'
            record=variants[ext];url=record['url'];data=get(url)
            path=folder/(kind+'.'+ext);path.write_bytes(data)
            entry['files'][kind]={'url':url,'filename':path.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'api_record':record}
            print(asset,kind,len(data),flush=True)
        report['assets'][asset]=entry
    (OUT/'intake.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Completed CC0 source intake',flush=True)

if __name__=='__main__':main()
