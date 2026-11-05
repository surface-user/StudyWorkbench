import hashlib

import pytest
from test_document_files import add
from test_explorer import PREFIX, client


@pytest.mark.parametrize('suffix', ['.json', '.JSON', '.csv', '.log', '.vtt', '.srt'])
def test_utf8_formats_are_plain_readonly_preserve_bytes_and_use_resource_marks(tmp_path, suffix):
    content = '\ufeff{"正文":"<script>不执行</script>","url":"javascript:fixture"}\r\n中文原文\n'
    with client(tmp_path) as c:
        node, _, path = add(c, tmp_path, '自编文件' + suffix, content.encode())
        before = path.read_bytes()
        response = c.get(f'{PREFIX}/nodes/{node}/document')
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['type'] == 'text' and value['text'] == content
        assert value['source_format'] == suffix[1:].lower() and value['position_kind'] == 'resource'
        assert value['sha256'] == hashlib.sha256(before).hexdigest()
        assert c.post(f'{PREFIX}/nodes/{node}/working-copy', json={'expected_sha256': value['sha256']}).status_code == 422
        assert c.post(f'{PREFIX}/nodes/{node}/learning-anchor', json={'kind': 'resource'}).status_code == 200
        assert c.post(f'{PREFIX}/nodes/{node}/learning-anchor', json={
            'kind': 'text_line', 'line': 1, 'expected_sha256': value['sha256']}).status_code == 422
        assert c.patch(f'{PREFIX}/nodes/{node}', json={'name': '显示名.md', 'parent_id': None}).status_code == 200
        assert c.get(f'{PREFIX}/nodes/{node}/document').json()['type'] == 'text'
        assert path.read_bytes() == before


def test_invalid_utf8_and_budget_never_use_lossy_replacement_or_modify_original(tmp_path):
    with client(tmp_path) as c:
        for name, raw, status in [('坏编码.json', b'\xff\xfe', 422), ('过大.csv', b'x' * (1024 * 1024 + 1), 413)]:
            node, _, path = add(c, tmp_path, name, raw)
            assert c.get(f'{PREFIX}/nodes/{node}/document').status_code == status
            assert path.read_bytes() == raw
        node, _, _ = add(c, tmp_path, '未知.bin', b'valid utf-8 but unknown format')
        assert c.get(f'{PREFIX}/nodes/{node}/document').json()['type'] == 'unsupported'


@pytest.mark.parametrize('suffix', ['.txt', '.json', '.csv', '.log', '.vtt', '.srt', '.xlsx'])
def test_unified_import_preflight_recognizes_new_viewers_without_promising_large_files(tmp_path, suffix):
    from study_workbench.explorer import inspect_source
    source = tmp_path / ('自编' + suffix)
    source.write_bytes(b'PK\x03\x04fixture' if suffix == '.xlsx' else b'utf-8 fixture')
    value = inspect_source(str(source), tmp_path / 'separate-data')
    assert value['error'] is None and value['warning'] is None
    assert value['type'] != '普通文件'
    with source.open('ab') as handle:
        handle.truncate((16 if suffix == '.xlsx' else 1) * 1024 * 1024 + 1)
    value = inspect_source(str(source), tmp_path / 'separate-data')
    assert value['error'] is None and '超出查看预算' in value['warning']
