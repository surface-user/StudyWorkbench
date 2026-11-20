"""Compare frozen OpenTelemetry code and its shipped metadata with the official 1.45.2 wheel."""
import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

from PyInstaller.archive.readers import CArchiveReader

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
from check_frozen_sources import equivalent  # noqa: E402

WHEEL = '2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34'
DIST = 'opentelemetry_api-1.45.2.dist-info'
TARGET = 'opentelemetry.trace.propagation.tracecontext'


def verify(exe, wheel):
    if sys.version_info[:3] != (3, 13, 17):
        raise ValueError('Use the pinned release Python')
    raw = wheel.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WHEEL:
        raise ValueError('Unexpected upstream wheel digest')
    archive = CArchiveReader(str(exe))
    pyz_name, = [name for name, item in archive.toc.items() if item[-1] == 'z']
    pyz = archive.open_embedded_archive(pyz_name)
    modules = []
    metadata = []
    with ZipFile(io.BytesIO(raw)) as z:
        for name, (kind, *_) in pyz.toc.items():
            if name != 'opentelemetry' and not name.startswith('opentelemetry.'):
                continue
            if kind == 3:
                continue
            if kind not in (0, 1) or not re.fullmatch(r'\w+(?:\.\w+)*', name):
                raise ValueError('Unexpected embedded module')
            path = name.replace('.', '/') + ('/__init__.py' if kind == 1 else '.py')
            code = pyz.extract(name)
            expected = compile(z.read(path), code.co_filename, 'exec', dont_inherit=True)
            if not equivalent(code, expected):
                raise ValueError('Module differs from patched wheel: ' + name)
            modules.append(name)
        if TARGET not in modules:
            raise ValueError('Updated propagator missing')
        internal = exe.parent / '_internal'
        if {p.name for p in internal.glob('opentelemetry_api-*.dist-info')} != {DIST}:
            raise ValueError('Unexpected frozen metadata version')
        for name in ['METADATA', 'WHEEL', 'licenses/LICENSE', 'entry_points.txt']:
            path = DIST + '/' + name
            if (internal / path).read_bytes() != z.read(path):
                raise ValueError('Frozen metadata differs: ' + name)
            metadata.append(name)
    return dict(wheel_sha256=WHEEL, executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                matched_modules=len(modules), patched_propagator=TARGET, metadata=metadata)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.exe, args.wheel)))
