"""Assemble or verify the fixed, offline Windows OCR developer component."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench import ocr_component  # noqa: E402
from study_workbench.backup_store import no_links  # noqa: E402


def prepare(root, sources):
    no_links(root.parent)
    if os.path.lexists(root):
        raise FileExistsError(root)
    with tempfile.TemporaryDirectory(dir=root.parent) as temp:
        candidate = Path(temp) / 'component'
        for name in ocr_component.FILES:
            data = ocr_component.checked_bytes(sources[name], name)
            target = candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        ocr_component.verify(candidate)
        candidate.rename(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stage = commands.add_parser('prepare')
    for key in ('engine', 'tessdata', 'engine-license', 'leptonica-license', 'compiler-license'):
        stage.add_argument('--' + key, type=Path, required=True)
    for command in (stage, commands.add_parser('verify')):
        command.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.absolute()
    if args.command == 'prepare':
        sources = {
            'bin/tesseract.exe': args.engine,
            'tessdata/eng.traineddata': args.tessdata / 'eng.traineddata',
            'tessdata/chi_sim.traineddata': args.tessdata / 'chi_sim.traineddata',
            'licenses/tesseract-LICENSE': args.engine_license,
            'licenses/tessdata-LICENSE': args.tessdata / 'LICENSE',
            'licenses/leptonica-license.txt': args.leptonica_license,
            'licenses/Visual-Studio-2022-Community-License-EN.docx': args.compiler_license,
        }
        prepare(root, {name: path.absolute() for name, path in sources.items()})
    ocr_component.verify(root)
    print(f'Verified {len(ocr_component.FILES)} files for the optional Windows OCR developer component.')


if __name__ == '__main__':
    main()
