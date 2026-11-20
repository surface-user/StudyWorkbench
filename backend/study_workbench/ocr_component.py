"""Exact bytes accepted by the offline OCR worker and the component preparation tool."""
import hashlib
import stat
from pathlib import Path

from .backup_store import no_links

APACHE = (11358, 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30')
FILES = {
    'bin/tesseract.exe': (2473472, 'd825d9d9e94ab996f735e7eba9d199c009481ca9895ad16b1e1b6acfdeb343c0'),
    'tessdata/chi_sim.traineddata': (2469156, 'a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730'),
    'tessdata/eng.traineddata': (4113088, '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2'),
    'licenses/tesseract-LICENSE': APACHE,
    'licenses/tessdata-LICENSE': APACHE,
    'licenses/leptonica-license.txt': (1521, '87829abb5bbb00b55a107365da89e9a33f86c4250169e5a1e5588505be7d5806'),
    'licenses/Visual-Studio-2022-Community-License-EN.docx':
        (62859, '41a207b10c8ab91d0d2f10a854715f73dca54509581692d2fe179aa3ffcb8540'),
}


def checked_bytes(path, name):
    no_links(path)
    info = path.lstat()
    size, digest = FILES[name]
    if not stat.S_ISREG(info.st_mode) or info.st_size != size:
        raise ValueError(f'OCR component size or type differs: {name}')
    with path.open('rb') as stream:
        data = stream.read(size + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'OCR component bytes differ: {name}')
    return data


def verify(root):
    no_links(root)
    directories = {Path(name).parts[0] for name in FILES}
    if {p.name for p in root.iterdir()} != directories:
        raise ValueError('Unexpected OCR component layout')
    for directory in directories:
        parent = root / directory
        no_links(parent)
        expected = {Path(name).name for name in FILES if Path(name).parts[0] == directory}
        if {p.name for p in parent.iterdir()} != expected:
            raise ValueError(f'Unexpected OCR component files: {directory}')
    for name in FILES:
        checked_bytes(root / name, name)
