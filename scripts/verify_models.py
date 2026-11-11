"""Verify the trusted pickle/Vosk artifact before loading executable pickle files."""
import hashlib
import os
from pathlib import Path

def verify():
    root=Path(os.getenv('MODEL_ROOT','.'))
    manifest=Path(__file__).resolve().parents[1]/'model-assets.sha256'
    for line in manifest.read_text().splitlines():
        expected,relative=line.split('  ',1)
        digest=hashlib.sha256()
        with (root/relative).open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                digest.update(block)
        if digest.hexdigest()!=expected:
            raise RuntimeError('Model checksum mismatch: '+relative)

if __name__=='__main__':
    verify()
    print('Model assets verified')
