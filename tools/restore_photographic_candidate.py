"""Validate and restore the staged photographic candidate without committing it."""
from pathlib import Path
import argparse,hashlib,json,shutil,stat,subprocess,tempfile,zipfile
EXPECTED={'SOURCE':'ec936167d15f81d9aa60f5a468db22b36ec0f8178535a7eb55c5521c10accacc','DATA1':'5795b2bb48b6bfd5018e8213912574eb277c3a319258a0e81394d24e79edd827','DATA2':'be7ca86bca9a477737d3aa7e1bca69a4f67258cd22082d3d1c8d5ab042115994','DATA3':'b2889d3cc5ef8b49774dc6bcf2e016ec8852df380bc01c6daba2080a9387f265','DATA4':'3119a07b0e95596ef2fcd06165e70e5610eabdec517e991213eb149232d2d4c0'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('inputs',type=Path);args=ap.parse_args()
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    root=Path.cwd().resolve()
    with tempfile.TemporaryDirectory() as directory:
        stage=Path(directory);seen=set()
        for name,wanted in EXPECTED.items():
            path=args.inputs/(name+'.zip')
            if sha(path)!=wanted:raise ValueError('Archive checksum mismatch: '+name)
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    p=Path(entry.filename)
                    if p.is_absolute() or {'..','.git','.github'}&set(p.parts) or stat.S_ISLNK(entry.external_attr>>16) or entry.filename in seen:raise ValueError('Unsafe or duplicate archive path')
                    seen.add(entry.filename)
                archive.extractall(stage)
        source=json.loads((stage/'PHOTO_SOURCE_MANIFEST.json').read_text())
        data=json.loads((stage/'PHOTO_DATA_MANIFEST.json').read_text())
        for name,h in source['files'].items():
            if sha(stage/name)!=h:raise ValueError('Source checksum mismatch: '+name)
        for name,h in data.items():
            if sha(stage/name)!=h:raise ValueError('Data checksum mismatch: '+name)
        for name,h in source['base_files'].items():
            if name=='verification.json':
                actual=subprocess.check_output(['git','hash-object',name]).decode().strip()
                if actual!='87ae5de41cfef1a0f2f3896e001e7f4852407d27':raise ValueError('Baseline verification changed')
            elif (Path(name).exists() if h is None else sha(Path(name))!=h):raise ValueError('Baseline changed: '+name)
        subprocess.run(['git','diff','--exit-code',source['baseline_commit'],'HEAD','--',*source['files']],check=True)
        for name in set(source['files'])|set(data):
            p=root/name
            if not p.resolve().is_relative_to(root):raise ValueError('Destination escapes checkout')
            p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(stage/name,p)
        Path('photo-intake.json').write_text(json.dumps({'source':source,'data':data,'archives':EXPECTED,'transfer_run':35266889060},indent=2)+'\n')
    print('PASS: photographic candidate restored; no remote changes made')
if __name__=='__main__':main()
