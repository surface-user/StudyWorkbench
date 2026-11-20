"""Compose intact pinned Office/Java components with explicit application-local CRT copies."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from prepare_java_runtime import LOCK_NAME, no_links, verify_runtime  # noqa: E402
from study_workbench.office_runtime import (  # noqa: E402
    APP_LOCAL_CRT,
    APP_LOCAL_PYTHON,
    JAVA,
    JAVA_LOCK_SHA256,
    OFFICE_LOCK_SHA256,
    PYTHON_CORE,
    PYTHON_LAUNCHERS,
    OfficeRuntime,
)


def render_manifest(original_raw, files, total_bytes, *, python_launchers=False):
    manifest = json.loads(original_raw)
    manifest.update(java=JAVA, files=dict(sorted(files.items())), bytes=total_bytes)
    if python_launchers:
        manifest['python_launchers'] = PYTHON_LAUNCHERS
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def compose(office, java, destination, *, python_launchers=False):
    office, java, destination = office.absolute(), java.absolute(), destination.absolute()
    no_links(office)
    no_links(destination.parent)
    no_links(java)
    office, java = office.resolve(strict=True), java.resolve(strict=True)
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(office) or destination.is_relative_to(java):
        raise ValueError('Destination cannot modify a source component')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Never replace an existing runtime')
    original = OfficeRuntime(office)
    if original.java_home is not None or original.fingerprint != OFFICE_LOCK_SHA256:
        raise ValueError('Use the original pinned Office component')
    original.verify(lambda: None)
    if python_launchers and any(name not in original.files for name in APP_LOCAL_PYTHON.values()):
        raise ValueError('Original Office component lacks fixed Python launcher sources')
    raw_office = (office / 'runtime-lock.json').read_bytes()
    if hashlib.sha256(raw_office).hexdigest() != OFFICE_LOCK_SHA256:
        raise ValueError('Office component inventory changed')
    no_links(java / LOCK_NAME)
    with (java / LOCK_NAME).open('rb') as stream:
        raw_java = stream.read(4 * 1024 * 1024 + 1)
    if hashlib.sha256(raw_java).hexdigest() != JAVA_LOCK_SHA256:
        raise ValueError('Use the original pinned Java component inventory')
    java_manifest = json.loads(raw_java)
    verify_runtime(java, java_manifest['files'])
    destination.mkdir()
    files = dict(original.files)
    for name, checksum in original.files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(office / name, target)
    shutil.copyfile(office / 'runtime-lock.json', destination / 'office-runtime-lock.json')
    files['office-runtime-lock.json'] = OFFICE_LOCK_SHA256
    for name, checksum in {**java_manifest['files'], LOCK_NAME: JAVA_LOCK_SHA256}.items():
        target = destination / 'java' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(java / name, target)
        files['java/' + name] = checksum
    for name in APP_LOCAL_CRT:
        target = destination / 'program' / name
        if target.exists():
            raise ValueError('Refuse to overwrite an original Office CRT')
        shutil.copyfile(office / 'System64' / name, target)
        files['program/' + name] = original.files['System64/' + name]
    if python_launchers:
        for name, origin in APP_LOCAL_PYTHON.items():
            relative = PYTHON_CORE + 'bin/' + name
            target = destination / relative
            if target.exists():
                raise ValueError('Refuse to overwrite an original Python bin image')
            shutil.copyfile(office / origin, target)
            files[relative] = original.files[origin]
    original.verify(lambda: None)
    verify_runtime(java, java_manifest['files'])
    if ((office / 'runtime-lock.json').read_bytes() != raw_office
            or (java / LOCK_NAME).read_bytes() != raw_java):
        raise ValueError('Source component inventory changed during composition')
    lock = destination / 'runtime-lock.json'
    with lock.open('xb') as output:
        output.write(render_manifest(raw_office, files, sum((destination / name).stat().st_size for name in files),
                                     python_launchers=python_launchers))
    prepared = OfficeRuntime(destination)
    prepared.verify(lambda: None)
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--office', type=Path, required=True)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--python-launchers', action='store_true', help='Add exact application-local Python DLL copies')
    args = parser.parse_args()
    prepared = compose(args.office, args.java, args.destination, python_launchers=args.python_launchers)
    print(f'Composed {len(prepared.files)} files; fingerprint {prepared.fingerprint}')


if __name__ == '__main__':
    main()
