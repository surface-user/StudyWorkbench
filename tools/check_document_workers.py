"""Verify real source/frozen offline workers on the repository's original samples."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from numbered_cell_sample import check_numbered_cell, numbered_cell_docx, numbered_range_docx

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--exe', type=Path)
args = parser.parse_args()
environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
               'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
if args.exe:
    command = [str(args.exe.resolve())]
    environment['PATH'] = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32')
    environment.pop('PYTHONPATH', None)
else:
    command = [sys.executable, '-m', 'study_workbench']
    environment['PYTHONPATH'] = str(root / 'backend')
for suffix in ('docx', 'pdf'):
    raw = (root / f'contracts/samples/original-study.{suffix}').read_bytes()
    response = subprocess.run([*command, '--parse-document', '.' + suffix], input=raw, capture_output=True,
                              timeout=45, env=environment, cwd=root)
    assert response.returncode == 0, f'{suffix}: worker exit {response.returncode}'
    result = json.loads(response.stdout)
    assert 'error' not in result, f'{suffix}: {result.get("error")}'
    assert result['kind'] == 'note' and result['warnings'] and result['_assets']
    assert any(b['type'] == 'image' for b in result['blocks'])
    if suffix == 'docx':
        assert any(b['type'] == 'latex' for b in result['blocks'])
        assert any('中文题干' in b.get('text', '') for b in result['blocks'])
    else:
        assert len([b for b in result['blocks'] if b['type'] == 'image']) == 2
        assert any(b.get('text') == '第 2 页' for b in result['blocks'])
    print(f'{suffix}: real offline worker, text/images/formula/page checks passed')
    raw = (root / f'contracts/samples/numbered-questions.{suffix}').read_bytes()
    response = subprocess.run([*command, '--parse-document', '.' + suffix], input=raw, capture_output=True,
                              timeout=45, env=environment, cwd=root)
    assert response.returncode == 0, f'{suffix}: numbered worker exit {response.returncode}'
    result = json.loads(response.stdout)
    assert 'error' not in result, f'{suffix}: numbered extraction failed'
    drafts = result['question_drafts']
    assert len(drafts) == 2 and all(d['blocks'] for d in drafts)
    assert any(b['type'] == 'image' for b in drafts[0]['blocks'])
    if suffix == 'pdf':
        assert drafts[0]['source_pages'] == [1, 2] and drafts[1]['source_pages'] == [2]
    else:
        assert any(b['type'] == 'latex' for b in drafts[0]['blocks'])
    print(f'{suffix}: two numbered question candidates, image/math and cross-page boundaries passed')

response = subprocess.run([*command, '--parse-document', '.docx'], input=numbered_cell_docx(), capture_output=True,
                          check=True, timeout=45, env=environment, cwd=root)
check_numbered_cell(json.loads(response.stdout))
print('docx: numbered rich table cell stays with its original question, including image and math')

response = subprocess.run([*command, '--parse-word-range', '2', '3'], input=numbered_range_docx(), capture_output=True,
                          check=True, timeout=25, env=environment, cwd=root)
preview = json.loads(response.stdout)
assert preview['available'] and preview['block_positions'] == [2, 3]
assert [item['title'] for item in preview['question_drafts']] == ['2. Second original question', '3. Third original question']
assert 'PREFIX-ONLY' not in str(preview)
print('docx: selected body positions keep original list numbers')

raw = (root / 'contracts/samples/numbered-questions.pdf').read_bytes()
response = subprocess.run([*command, '--parse-pdf-pages', '2', '2'], input=raw, capture_output=True,
                          check=True, timeout=25, env=environment, cwd=root)
chunk = json.loads(response.stdout)
assert (chunk['first_page'], chunk['last_page'], chunk['page_count']) == (2, 2, 2)
assert chunk['fragments'][0]['marker'] is None and any(part['marker'] for part in chunk['fragments'])
assert all(part['source_pages'] == [2] and not part['ambiguous'] for part in chunk['fragments'])
assert len(chunk['warnings']) == 1 and chunk['_assets']
print('pdf: absolute page range, continuation and question marker passed')

raw = (root / 'contracts/samples/two-column-order.pdf').read_bytes()
response = subprocess.run([*command, '--view-document', 'pdf-columns'], input=b'{"page":1}\n' + raw,
                          capture_output=True, check=True, timeout=20, env=environment, cwd=root)
columns = json.loads(response.stdout)
assert columns['available'] and columns['page'] == columns['page_count'] == 1
assert [c['text'] for c in columns['columns']] == ['Left first\nLeft second', 'Right first\nRight second']
print('pdf: explicit two-column reading order passed')
