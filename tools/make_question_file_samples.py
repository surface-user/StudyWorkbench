"""Self-authored portable QuestionFile fixtures; never use a personal data directory."""
import argparse
import hashlib
import io
import sys
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench.content import DEMO, SUBJECTIVE  # noqa: E402
from study_workbench.question_files_format import QuestionFile, parse_file, serialize_file  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output
    root.mkdir()
    (root / 'assets').mkdir()
    image = Image.new('RGB', (160, 80), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 35, 60, 70), fill='#4976c4')
    draw.rectangle((90, 15, 135, 70), fill='#7ca4dd')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    png = buffer.getvalue()
    (root / 'assets/figure-sample.png').write_bytes(png)
    q = deepcopy(DEMO)
    q['id'] = 'sample-question-file'
    q['source'] = dict(kind='manual', title='自编有答案样例', verification='unverified')
    q['stem'].append(dict(type='image', attachment_id='figure-sample', alt='自编柱状示意图'))
    files = [('有答案.md', QuestionFile(title='有答案的题目文件', question=q, attachments={
        'figure-sample': dict(path='assets/figure-sample.png', sha256=hashlib.sha256(png).hexdigest(), mime='image/png')},
        sample_metadata={'origin': 'self-authored', 'unknown_field_preserved': True}))]
    q = deepcopy(SUBJECTIVE)
    q.update(id='sample-unanswered-file', answer=None, knowledge_points=[])
    q['source'] = dict(kind='manual', title='自编无答案样例', verification='unverified')
    files.append(('待批改.md', QuestionFile(title='无标准答案的题目文件', question=q)))
    for name, file in files:
        value = serialize_file(file)
        assert parse_file(value) == file
        (root / name).write_text(value, encoding='utf-8')
    print('Two portable self-authored QuestionFiles and one PNG created; roundtrip verified')


if __name__ == '__main__':
    main()
