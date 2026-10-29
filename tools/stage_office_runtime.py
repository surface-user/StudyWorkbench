"""Copy a verified optional runtime into a new release component directory."""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench.imports import resource_path  # noqa: E402
from study_workbench.office_runtime import OfficeRuntime  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve(strict=True)
    runtime = OfficeRuntime(args.runtime.resolve(strict=True))
    assert not stage.is_relative_to(runtime.root), 'Stage cannot be inside runtime'
    destination = resource_path(stage, 'converters/libreoffice')
    assert not destination.exists(), 'Never replace an existing converter'
    runtime.verify(lambda: None)
    print('Source inventory verified; copying optional component', flush=True)
    destination.mkdir(parents=True)
    for relative in [*runtime.files, 'runtime-lock.json']:
        # Both roots and all relative names were checked; destination is exclusively new.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runtime.root / relative, target)
    copied = OfficeRuntime(destination)
    copied.verify(lambda: None)
    assert copied.fingerprint == runtime.fingerprint
    print(f'Optional LibreOffice {len(runtime.files)} files verified and staged')


if __name__ == '__main__':
    main()
