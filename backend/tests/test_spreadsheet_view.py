import io
import struct
import zipfile
import zlib

import pytest
from study_workbench import spreadsheet_view as view


def workbook(parts=None):
    main, rel, package = view.MAIN, view.DOC_REL, view.PKG_REL
    entries = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>',
        '_rels/.rels': f'<Relationships xmlns="{package}"><Relationship Id="book" Type="{rel}officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{main}" xmlns:r="{rel[:-1]}"><sheets><sheet name="中文表" sheetId="1" r:id="one"/><sheet name="第二表" sheetId="2" r:id="two" state="hidden"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{package}"><Relationship Id="one" Type="{rel}worksheet" Target="worksheets/one.xml"/><Relationship Id="two" Type="{rel}worksheet" Target="/xl/worksheets/two.xml"/><Relationship Id="strings" Type="{rel}sharedStrings" Target="sharedStrings.xml"/></Relationships>',
        'xl/sharedStrings.xml': f'<sst xmlns="{main}"><si><r><t>中文</t></r><r><t>富文本</t></r></si></sst>',
        'xl/worksheets/one.xml': f'<worksheet xmlns="{main}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><f>1+1</f><v>2</v></c><c r="C1"><f>1+1</f></c><c r="D1" t="str"><f>IF(1,"","")</f><v/></c><c r="E1" t="b"><v>1</v></c><c r="F1" t="e"><v>#REF!</v></c><c r="G1"><v>45200</v></c><c r="H1" t="inlineStr"><is><t>&lt;script&gt;字面&lt;/script&gt;</t></is></c></row></sheetData></worksheet>',
        'xl/worksheets/two.xml': f'<worksheet xmlns="{main}"><sheetData><row r="1048576"><c r="XFD1048576"><v>42</v></c></row></sheetData></worksheet>',
    }
    entries.update(parts or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    return output.getvalue()


def sheet(body):
    return f'<worksheet xmlns="{view.MAIN}"><sheetData><row r="1">{body}</row></sheetData></worksheet>'


def test_multiple_sheets_exact_addresses_cached_values_and_no_formula_execution():
    raw = workbook()
    result = view.read_workbook(raw)
    assert result['cell_count'] == 9 and result['position_kind'] == 'resource'
    first, second = result['sheets']
    assert first['name'] == '中文表' and second['state'] == 'hidden'
    assert [cell['value'] for cell in first['cells']] == ['中文富文本', '2', '公式无缓存值', '', 'TRUE', '#REF!', '45200', '<script>字面</script>']
    assert first['cells'][1]['formula'] and not first['cells'][1]['cache_missing']
    assert first['cells'][2]['cache_missing'] and not first['cells'][3]['cache_missing']
    assert second['cells'][0]['address'] == 'XFD1048576'
    assert workbook() == raw


@pytest.mark.parametrize('body', [
    '<c r="A1"/><c r="A1"/>', '<c r="XFE1"/>', '<c r="A1048577"/>', '<c r="A0"/>',
    '<c r="A1" t="s"><v>1</v></c>', '<c r="A1" t="s"><v>-1</v></c>',
    '<c r="A1" t="b"><v>2</v></c>', '<c r="A1" t="unknown"/>',
    '<c r="A1" t="inlineStr"><f>1</f><is><t>x</t></is></c>',
])
def test_bad_cell_types_references_and_coordinates_are_rejected(body):
    with pytest.raises(ValueError):
        view.read_workbook(workbook({'xl/worksheets/one.xml': sheet(body)}))


@pytest.mark.parametrize('part,content', [
    ('../escape.xml', '<root/>'), ('xl/../escape.xml', '<root/>'), ('xl/vbaProject.bin', b'bytes'),
    ('xl/embeddings/book.xlsx', b'bytes'), ('XL/workbook.xml', '<root/>'),
    ('xl/worksheets/one.xml', '<!DOCTYPE x [<!ENTITY e "expand">]><x>&e;</x>'),
    ('xl/worksheets/one.xml', '<!DOCTYPE x><x/>'.encode('utf-16')),
    ('xl/workbook.xml', '<workbook xmlns="http://purl.oclc.org/ooxml/spreadsheetml/main"/>'),
])
def test_unsafe_or_unsupported_package_is_refused(part, content):
    with pytest.raises(ValueError):
        view.read_workbook(workbook({part: content}))


def test_external_relationship_refused_but_safe_parent_reference_stays_in_package():
    name = 'xl/worksheets/_rels/one.xml.rels'
    def relationships(target, mode='Internal'):
        return f'<Relationships xmlns="{view.PKG_REL}"><Relationship Id="extra" Type="{view.DOC_REL}drawing" Target="{target}" TargetMode="{mode}"/></Relationships>'
    for target, mode in [('https://example.com', 'External'), ('../../../escape', 'Internal'), ('file:///C:/secret', 'Internal')]:
        with pytest.raises(ValueError):
            view.read_workbook(workbook({name: relationships(target, mode)}))
    assert view.read_workbook(workbook({name: relationships('../drawings/drawing.xml'), 'xl/drawings/drawing.xml': '<drawing/>'}))['cell_count'] == 9


def test_xml_depth_node_and_output_budgets(monkeypatch):
    for xml in ['<x>' * 65 + '</x>' * 65, '<x>' + '<a/>' * 100001 + '</x>']:
        with pytest.raises(ValueError, match='节点或深度'):
            view.read_workbook(workbook({'xl/sharedStrings.xml': xml}))
    with pytest.raises(ValueError, match='4096'):
        view.read_workbook(workbook({'xl/worksheets/one.xml': sheet('<c r="A1" t="str"><v>' + '长' * 4097 + '</v></c>')}))
    monkeypatch.setattr(view, 'RESULT_LIMIT', 128)
    with pytest.raises(ValueError, match='结果'):
        view.read_workbook(workbook())


def test_zip_budgets_real_directory_count_and_special_files(monkeypatch):
    raw = bytearray(workbook())
    end = raw.rfind(b'PK\x05\x06')
    struct.pack_into('<HH', raw, end + 8, 1, 1)
    with pytest.raises(ValueError, match='数量'):
        view.read_workbook(bytes(raw))
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        info = zipfile.ZipInfo('symlink')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, '/outside')
    with pytest.raises(ValueError, match='特殊文件'):
        view.read_workbook(output.getvalue())
    for constant, limit in [('SOURCE_LIMIT', 100), ('PART_LIMIT', 32), ('EXPANDED_LIMIT', 64), ('CELL_LIMIT', 3)]:
        with monkeypatch.context() as patch:
            patch.setattr(view, constant, limit)
            with pytest.raises(ValueError):
                view.read_workbook(workbook())


def test_resource_api_runs_disposable_worker_preserves_source_and_blocks_edit_and_line_anchor(tmp_path):
    from test_document_files import add
    from test_explorer import PREFIX, client
    raw = workbook()
    with client(tmp_path) as c:
        node, _, path = add(c, tmp_path, '自编多表.XLSX', raw)
        response = c.get(f'{PREFIX}/nodes/{node}/document')
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['type'] == 'spreadsheet' and value['renderer_version'] == 'xlsx-values-v1'
        assert value['sheets'][1]['cells'][0]['address'] == 'XFD1048576'
        assert c.post(f'{PREFIX}/nodes/{node}/working-copy', json={'expected_sha256': value['sha256']}).status_code == 422
        assert c.post(f'{PREFIX}/nodes/{node}/learning-anchor', json={'kind': 'resource'}).status_code == 200
        assert c.post(f'{PREFIX}/nodes/{node}/learning-anchor', json={'kind': 'text_line', 'line': 1, 'expected_sha256': value['sha256']}).status_code == 422
        assert path.read_bytes() == raw
        broken, _, source = add(c, tmp_path, '损坏.xlsx', b'not a ZIP')
        assert c.get(f'{PREFIX}/nodes/{broken}/document').status_code == 422
        assert source.read_bytes() == b'not a ZIP'


def test_phonetic_guides_are_not_concatenated_into_shared_cell_text():
    raw = workbook({'xl/sharedStrings.xml': f'<sst xmlns="{view.MAIN}"><si><r><t>汉字</t></r><rPh sb="0" eb="2"><t>hànzì</t></rPh></si></sst>'})
    assert view.read_workbook(raw)['sheets'][0]['cells'][0]['value'] == '汉字'


@pytest.mark.parametrize('encoded,expected', [
    ('a_x000D_b', 'a\rb'), ('_x005F_x0041_', '_x0041_'),
    ('_xD83D__xDE00_', '😀'), ('_x4E2D__x6587_', '中文'),
])
def test_escaped_xstrings_decode_once_and_preserve_surrogate_pairs(encoded, expected):
    shared = f'<sst xmlns="{view.MAIN}"><si><t>{encoded}</t></si></sst>'
    data = workbook({'xl/sharedStrings.xml': shared,
                     'xl/worksheets/two.xml': sheet(f'<c r="A1" t="str"><f>"cached"</f><v>{encoded}</v></c>')})
    result = view.read_workbook(data)
    assert result['sheets'][0]['cells'][0]['value'] == expected
    assert result['sheets'][1]['cells'][0]['value'] == expected


def test_xstring_budget_is_decoded_characters_and_invalid_surrogate_is_rejected():
    data = workbook({'xl/sharedStrings.xml': f'<sst xmlns="{view.MAIN}"><si><t>{"_x0041_" * 4096}</t></si></sst>'})
    assert view.read_workbook(data)['sheets'][0]['cells'][0]['value'] == 'A' * 4096
    with pytest.raises(ValueError, match='Unicode'):
        view.read_workbook(workbook({'xl/sharedStrings.xml': f'<sst xmlns="{view.MAIN}"><si><t>_xD83D_</t></si></sst>'}))


@pytest.mark.parametrize('changed', [
    {'xl/worksheets/one.xml': f'<worksheet xmlns="{view.MAIN}"/>'},
    {'xl/workbook.xml': f'<workbook xmlns="{view.MAIN}"><sheets/></workbook>'},
    {'xl/sharedStrings.xml': '<broken'},
    {'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{view.PKG_REL}"><Relationship Id="one" Type="{view.DOC_REL}worksheet" Target="missing.xml"/></Relationships>'},
    {'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{view.PKG_REL}"><Relationship Id="same" Type="{view.DOC_REL}worksheet" Target="worksheets/one.xml"/><Relationship Id="same" Type="{view.DOC_REL}worksheet" Target="worksheets/two.xml"/></Relationships>'},
    {'[Content_Types].xml': '<Types><Override ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/></Types>'},
])
def test_missing_data_malformed_xml_duplicate_relationships_and_macro_type_fail(changed):
    from xml.etree.ElementTree import ParseError
    with pytest.raises((ValueError, ParseError)):
        view.read_workbook(workbook(changed))


def test_zip_crc_and_duplicate_name_are_not_silently_accepted():
    raw = bytearray(workbook())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        item = archive.getinfo('xl/worksheets/one.xml')
        offset = item.header_offset
        length, extra = struct.unpack_from('<HH', raw, offset + 26)
        raw[offset + 30 + length + extra + item.compress_size // 2] ^= 0xff
    with pytest.raises((ValueError, zipfile.BadZipFile, zlib.error)):
        view.read_workbook(bytes(raw))
    output = io.BytesIO(workbook())
    with zipfile.ZipFile(output, 'a') as archive:
        with pytest.warns(UserWarning, match='Duplicate name'):
            archive.writestr('xl/workbook.xml', '<duplicate/>')
    with pytest.raises(ValueError, match='重名'):
        view.read_workbook(output.getvalue())
