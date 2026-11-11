"""Read-only native loading-domain evidence for an Office component or frozen backend."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from native_dependencies import inspect_dependencies
from prepare_java_runtime import no_links
from release_inventory import stage_files


def component_payload(root):
    if (root / 'build-inventory.json').exists():
        raise ValueError('Unexpected build inventory in Office component')
    files = stage_files(root)
    with files['runtime-lock.json'].open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Office inventory exceeds budget')
    manifest = json.loads(raw)
    if manifest.get('version') != '26.8.1' or manifest.get('java', {}).get('version') != '21.0.13+9':
        raise ValueError('Office/Java loading evidence must be renewed for this component version')
    expected = manifest['files']
    if set(files) != set(expected) | {'runtime-lock.json'}:
        raise ValueError('Office component inventory differs from actual files')
    for name, checksum in expected.items():
        with files[name].open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != checksum:
                raise ValueError('Office component hash changed: ' + name)
    return files, hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--office', type=Path)
    mode.add_argument('--backend', type=Path)
    args = parser.parse_args()
    directory = (args.office or args.backend).absolute()
    no_links(directory)
    directory = directory.resolve(strict=True)
    if args.office:
        files, fingerprint = component_payload(directory)
        payload = {'converters/libreoffice/' + name: path for name, path in files.items()}
    else:
        files = stage_files(directory)
        fingerprint = None
        payload = {'backend/' + name: path for name, path in files.items()}
    report = inspect_dependencies(payload, Path(os.environ['SystemRoot']) / 'System32')
    report.update(component_inventory_sha256=fingerprint, input_files=len(files))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
