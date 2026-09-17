"""Verify the publication manifest without executing any imported project code."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    data=json.loads((ROOT/'SHA256SUMS.json').read_text())
    for relative,expected in data.items():
        path=(ROOT/relative).resolve()
        if not path.is_relative_to(ROOT):raise SystemExit('Manifest path escapes repository')
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected:raise SystemExit(f'Checksum mismatch: {relative}')
    print(f'PASS: {len(data)} publication files are byte-identical to the local package.')
