"""Self-authored fixtures exercise conservative boundaries and portable provenance."""
import hashlib
import io
import json
import re
from zipfile import ZipFile

import pytest
from study_workbench.documents import extract
from study_workbench.question_splitting import markdown, split_blocks
from test_draft_editing import edit
from test_imports import SCOPE, client, upload


def test_complex_markers_subquestions_decimals_and_duplicates():
    warnings = []
    text = ('一、选择题\n第十一题：主体\n（1）小问\n(2) 小问\n1.25 小数\n'
            '【12】下一题\n第十二题：重号但不是同一题\n第十三题：末题')
    drafts = split_blocks([dict(type='text', text=text)], warnings)
    assert [d['title'] for d in drafts] == ['第十一题：主体', '【12】下一题', '第十二题：重号但不是同一题', '第十三题：末题']
    assert all(value in markdown(drafts[0]) for value in ['（1）', '(2)', '1.25'])
    assert len(warnings) == 1 and '重复题号' in warnings[0]
    assert split_blocks([dict(type='text', text='第一一题：无效中文序号\n第百题：不支持\n【1】')]) == []


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_explicit_material_keeps_order_and_attachment_without_guessing_answers(newline):
    blocks = [dict(type='text', text=newline.join(['卷头', '阅读下列材料，回答第11至12题：', '共同条件'])),
              dict(type='image', attachment_id='diagram', alt='自编图'),
              dict(type='text', text='第十一题：首题\n(1) 小问'),
              dict(type='text', text='【12】次题\n13. 独立题')]
    warnings = []
    drafts = split_blocks(blocks, warnings)
    assert len(drafts) == 3 and warnings == []
    material = drafts[0]['shared_materials'][0]
    assert material == drafts[1]['shared_materials'][0]
    assert material['blocks'][1] == blocks[1]
    assert '共同条件' in markdown(drafts[0]) and '共同条件' in markdown(drafts[1])
    assert '共同条件' not in markdown(drafts[2])
    assert 'shared_materials' not in drafts[2]
    assert 'answer' not in drafts[0] and 'kind' not in drafts[0]
    assert split_blocks(blocks) == drafts  # Identities/order do not depend on random state.


@pytest.mark.parametrize('span,questions', [
    ('1-3', ['1. one', '3. three']), ('1-2', ['1. one', '1. duplicate', '2. two']),
    ('1-2', ['2. two', '1. one']), ('2-1', ['1. one']), ('0-1', ['1. one']),
    ('1-9999', ['1. one']), ('1-2', []),
])
def test_ambiguous_material_ranges_never_silently_attach(span, questions):
    warnings = []
    text = '\n'.join([f'Read the following passage and answer questions {span}:', 'source material', *questions])
    drafts = split_blocks([dict(type='text', text=text)], warnings)
    assert len(drafts) == len(questions)
    assert all('shared_materials' not in draft for draft in drafts)
    assert any('未自动关联' in warning for warning in warnings)


def test_two_groups_have_distinct_ids_and_no_cross_group_material():
    text = ('阅读下列材料，回答第1-1题：\n第一组材料\n1. 首题\n'
            '阅读下列材料，回答第1-1题：\n第二组材料\n1. 另一章首题')
    first, second = split_blocks([dict(type='text', text=text)])
    assert first['shared_materials'][0]['id'] != second['shared_materials'][0]['id']
    assert '第二组材料' not in markdown(first) and '第一组材料' not in markdown(second)


def test_question_and_material_budgets_are_unchanged():
    with pytest.raises(ValueError, match='超过200道'):
        split_blocks([dict(type='text', text='\n'.join(f'【{i}】题干' for i in range(201)))])
    with pytest.raises(ValueError, match='超过200组'):
        split_blocks([dict(type='text', text='\n'.join(['阅读下列材料，回答第1至2题：'] * 201))])


def grouped_sample(suffix):
    if suffix == 'docx':
        from docx import Document
        from test_markdown_questions import SAMPLES

        document = Document(io.BytesIO((SAMPLES / 'numbered-questions.docx').read_bytes()))
        first = document.paragraphs[0]
        first.insert_paragraph_before('阅读下列材料，回答第1至2题：')
        first.text = '自编共享材料：保留来源和图片，不提供标准答案。'
        output = io.BytesIO()
        document.save(output)
        return output.getvalue()
    # Two-page PDF with material continuing before the first question on page two.
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>']
    for stream in (6, 7):
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents {stream} 0 R >>'.encode())
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    for lines in [
        ['Read the following passage and answer questions 1-2:', 'Shared material starts here.'],
        ['Shared material continues here.', '1. First question.', '2. Second question.'],
    ]:
        content = ('BT /F1 12 Tf 30 740 Td ' + ' 0 -100 Td '.join(f'({line}) Tj' for line in lines) + ' ET').encode()
        objects.append(f'<< /Length {len(content)} >>\nstream\n'.encode() + content + b'\nendstream')
    data, offsets = bytearray(b'%PDF-1.4\n'), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{index} 0 obj\n'.encode() + value + b'\nendobj\n')
    start = len(data)
    data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode())
    return bytes(data)


@pytest.mark.parametrize('suffix', ['docx', 'pdf'])
def test_real_grouped_document_preview_confirmation_export_restart_and_source(tmp_path, suffix):
    raw = grouped_sample(suffix)
    with client(tmp_path) as c:
        job = upload(c, raw, f'自编共享材料.{suffix}').json()
        assert job['status'] == 'preview', job
        assert job['parser_version'].startswith('builtin-4-')
        drafts = job['preview']['question_drafts']
        assert len(drafts) == 2
        material = drafts[0]['shared_materials'][0]
        assert material == drafts[1]['shared_materials'][0]
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        if suffix == 'pdf':
            assert material['source_pages'] == [1, 2]
            assert drafts[0]['source_pages'] == drafts[1]['source_pages'] == [2]
            assert material['regions'][1]['box'][3] == drafts[0]['regions'][0]['box'][1]
            assert 'Shared material continues here.' in markdown(drafts[1])
            assert 'First question' not in markdown(drafts[1])
        else:
            assert material['source_pages'] == material['regions'] == []
            assert '自编共享材料' in markdown(drafts[1])
        renamed = edit(c, job, 'rename', title='显式修订候选标题').json()
        url = f"{SCOPE}/imports/{job['id']}/question-markdown"
        body = dict(expected_revision=job['draft_revision'], selected=[0, 1], confirm=True)
        assert c.post(url, json=body).status_code == 409
        body['expected_revision'] = renamed['draft_revision']
        saved = c.post(url, json=body)
        assert saved.status_code == 200, saved.text
        assert c.post(url, json=body).json() == saved.json()
        assert edit(c, renamed, 'rename', title='不可覆盖').status_code == 409
        with ZipFile(io.BytesIO(c.get(f'{SCOPE}/export').content)) as archive:
            for item in saved.json():
                md = archive.read(f"questions/{item['id']}/question.md").decode()
                provenance = json.loads(md.split('```json\n')[-1].split('\n```')[0])
                assert provenance['original_sha256'] == hashlib.sha256(raw).hexdigest()
                assert provenance['answer_status'] == 'not_inferred'
                assert provenance['shared_materials'][0]['regions'] == material['regions']
                for identifier in re.findall(r'assets/([a-f0-9]{32})\.png', md):
                    assert archive.read(f"questions/{item['id']}/assets/{identifier}.png").startswith(b'\x89PNG')
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
    with client(tmp_path) as c:
        assert c.post(url, json=body).json() == saved.json()


def test_combined_material_and_question_still_obey_content_budget():
    from pydantic import TypeAdapter, ValidationError
    from study_workbench.question_protocol import Content
    from study_workbench.question_splitting import all_blocks

    blocks = [dict(type='text', text='阅读下列材料，回答第1至1题：')]
    blocks += [dict(type='text', text='材料段落')] * 199
    blocks += [dict(type='text', text='1. 题干')]
    draft, = split_blocks(blocks)
    with pytest.raises(ValidationError):
        TypeAdapter(Content).validate_python(all_blocks(draft))


def test_pdf_worker_keeps_unknown_forms_in_source():
    preview = extract(grouped_sample('pdf'), '.pdf')
    assert len(preview['_assets']) == 6  # Two full pages, two material regions, two question regions.
    assert len([b for b in preview['blocks'] if b['type'] == 'image']) == 2
