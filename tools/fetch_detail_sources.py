"""Download the exact CC0 photographic inputs named by the committed receipt."""
from pathlib import Path
import hashlib,json,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def main():
    receipt=json.loads((ROOT/'source/detail_sources.json').read_text())
    for asset in receipt['assets'].values():
        for e in asset['maps'].values():
            path=(ROOT/e['path']).resolve()
            if not path.is_relative_to(ROOT/'detail_sources'):raise ValueError('Unsafe source path')
            if not e['url'].startswith(('https://dl.polyhaven.org/','https://dl.polyhaven.com/')):raise ValueError('Unexpected source host')
            if path.exists() and digest(path)==e['sha256']:continue
            path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.part')
            for attempt in range(3):
                try:
                    request=urllib.request.Request(e['url'],headers={'User-Agent':'SandstoneWalk/0.5 reproducible asset fetch'})
                    with urllib.request.urlopen(request,timeout=120) as response,temporary.open('wb') as output:
                        while data:=response.read(1<<20):output.write(data)
                    if temporary.stat().st_size!=e['bytes'] or digest(temporary)!=e['sha256']:raise ValueError('Source checksum mismatch')
                    temporary.replace(path);print(path.relative_to(ROOT),flush=True);break
                except Exception:
                    temporary.unlink(missing_ok=True)
                    if attempt==2:raise
                    time.sleep(2)
    (ROOT/'detail_sources/provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
