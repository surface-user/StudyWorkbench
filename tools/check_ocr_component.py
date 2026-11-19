"""Run known printed lines and a blank PGM through the pinned Windows OCR executable."""

import argparse
import csv
import io
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from prepare_ocr_runtime import verify


def check(root):
    verify(root)
    fonts = Path(os.environ['SystemRoot']) / 'Fonts'
    cases = [('eng', 'arial.ttf', 'Study page 123'), ('chi_sim', 'msyh.ttc', '中文学习'), ('eng', 'arial.ttf', '')]
    with tempfile.TemporaryDirectory() as temp:
        for lang, font, expected in cases:
            image = Image.new('L', (390, 84), 255)
            ImageDraw.Draw(image).text((10, 3), expected, font=ImageFont.truetype(str(fonts / font), 48), fill=0)
            pgm = io.BytesIO()
            image.save(pgm, format='PPM')
            args = [str(root / 'bin/tesseract.exe'), 'stdin', 'stdout', '--tessdata-dir', str(root / 'tessdata'),
                    '-l', lang, '--oem', '1', '--psm', '6', '-c', 'tessedit_create_tsv=1']
            result = subprocess.run(args, input=pgm.getvalue(), capture_output=True, timeout=15, cwd=temp,
                                    env={'SystemRoot': os.environ['SystemRoot'], 'TEMP': temp, 'TMP': temp}, check=True)
            if result.stderr or len(result.stdout) > 8192:
                raise ValueError('Unexpected diagnostics or excessive output for the fixed OCR sample')
            rows = csv.DictReader(io.StringIO(result.stdout.decode('utf-8')), delimiter='\t', quoting=csv.QUOTE_NONE)
            words = [row for row in rows if row['level'] == '5']
            actual = (' ' if lang == 'eng' else '').join(row['text'] for row in words)
            if actual != expected:
                raise ValueError(f'Unexpected {lang} OCR transcript for the fixed sample')
            for row in words:
                x, y, width, height = (int(row[k]) for k in ('left', 'top', 'width', 'height'))
                if not (0 <= x < x + width <= 390 and 0 <= y < y + height <= 84 and 0 <= float(row['conf']) <= 100):
                    raise ValueError('OCR bounds or confidence outside the fixed image')
            print(f'{lang}: {len(words)} expected words/regions verified')
    verify(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    check(parser.parse_args().directory.absolute())
