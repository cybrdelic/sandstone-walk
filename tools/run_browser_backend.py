"""Run unchanged browser assertions through a selected real Chromium backend.

The default tests use SwiftShader. This wrapper is for an Xvfb/Mesa GL run;
it does not replace any image, shader, application code or input assertion.
"""
import argparse,json,runpy,sys
from pathlib import Path
from playwright.sync_api import BrowserType

def main():
    ap=argparse.ArgumentParser();ap.add_argument('suite',choices=['desktop','mobile','photographic']);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parent
    scripts={'desktop':'browser_smoke.py','mobile':'mobile_controls_smoke.py','photographic':'test_photographic_browser.py'}
    original=BrowserType.launch
    def launch(self,*pos,**kw):
        flags=[v for v in kw.get('args',[]) if not v.startswith('--use-angle=')]
        flags+=['--use-angle=gl','--ignore-gpu-blocklist','--disable-gpu-sandbox']
        kw['args']=flags;kw['headless']=False
        return original(self,*pos,**kw)
    BrowserType.launch=launch
    sys.path.insert(0,str(root));sys.argv=[str(root/scripts[args.suite]),'--out',str(args.out)]
    try:runpy.run_path(str(root/scripts[args.suite]),run_name='__main__')
    finally:
        BrowserType.launch=original
        p=args.out/'report.json'
        if p.exists():
            report=json.loads(p.read_text());report['browser_launch_backend']='Chromium ANGLE OpenGL under Xvfb/Mesa; software renderer, not a physical phone'
            report['backend_override_only']=True;p.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
