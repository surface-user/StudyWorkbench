"""Named refusal gates for complex Office packages, without invoking the converter."""
import io
from zipfile import ZipFile

import pytest
from study_workbench.office_inputs import validate_office
from study_workbench.spreadsheet_view import DOC_REL, PKG_REL, read_workbook
from test_office_previews import package
from test_spreadsheet_view import workbook


@pytest.mark.parametrize('part,content,gate', [
    ('word/header1.xml', '<header><instrText>INCLUDETEXT file:///C:/private</instrText></header>', '拆分的外部字段'),
    ('word/footer1.xml', '<footer><fldSimple instr="DDEAUTO command"/></footer>', '外部字段或动态公式'),
    ('word/fontTable.xml', '<fonts><font', '格式损坏或已加密'),
    ('word/_rels/header1.xml.rels', '<Relationships><Relationship TargetMode="External" Target="https://example.invalid"/></Relationships>', '外部关系'),
    ('word/_rels/document.xml.rels', '<Relationships><Relationship Target="../../../outside.xml"/></Relationships>', '越过包根目录'),
    ('word/activeX/control.xml', '<control/>', '宏、活动对象或外部链接'),
    ('word/media/vector.svg', '<svg/>', '图片仅支持PNG/JPEG'),
    ('word/document.xml', '<!DOCTYPE x [<!ENTITY n "expand">]><x>&n;</x>', 'XML含外部声明'),
])
def test_word_complex_parts_refuse_at_named_gate(part, content, gate):
    raw = package(extras={part: content}) if part != 'word/document.xml' else package(value=content)
    with pytest.raises(ValueError, match=gate):
        validate_office(raw, '.docx')


@pytest.mark.parametrize('part,content,gate', [
    ('xl/worksheets/sheet1.xml', '<worksheet><f>SUM(A1:A2)</f></worksheet>', '仅支持静态单元格'),
    ('xl/workbook.xml', '<workbook><definedName>cached</definedName></workbook>', '仅支持静态单元格'),
    ('xl/embeddings/nested.xlsx', b'not-expanded', '嵌入对象仅支持受限图表XLSX'),
    ('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Target="https://example.invalid"/></Relationships>', '外部关系'),
])
def test_chart_embedded_workbooks_refuse_at_named_gate(part, content, gate):
    embedded = package('xl/workbook.xml', value=content if part == 'xl/workbook.xml' else '<workbook/>',
                       extras={} if part == 'xl/workbook.xml' else {part: content})
    raw = package('ppt/presentation.xml', extras={'ppt/embeddings/chart.xlsx': embedded})
    with pytest.raises(ValueError, match=gate):
        validate_office(raw, '.pptx')


def test_static_embedded_chart_keeps_internal_rendering_without_formula_execution():
    embedded = package('xl/workbook.xml', extras={'xl/worksheets/sheet1.xml': '<worksheet><v>85</v></worksheet>'})
    raw = package('ppt/presentation.xml', extras={
        'ppt/charts/chart1.xml': '<chart/>', 'ppt/embeddings/chart.xlsx': embedded})
    assert validate_office(raw, '.pptx') is True


@pytest.mark.parametrize('part,content,gate', [
    ('xl/worksheets/_rels/one.xml.rels', f'<Relationships xmlns="{PKG_REL}"><Relationship Id="chart" Type="{DOC_REL}drawing" Target="../drawings/missing.xml"/></Relationships>', '关系目标缺失'),
    ('xl/worksheets/_rels/one.xml.rels', f'<Relationships xmlns="{PKG_REL}"><Relationship Id="link" Type="{DOC_REL}hyperlink" Target="https://example.invalid" TargetMode="External"/></Relationships>', '外部关系不支持'),
    ('xl/worksheets/_rels/one.xml.rels', f'<Relationships xmlns="{PKG_REL}"><Relationship Id="chart" Type="{DOC_REL}drawing" Target="%2e%2e/outside.xml"/></Relationships>', '关系目标无效'),
    ('xl/embeddings/oleObject1.bin', b'object', '宏/活动对象/外部数据'),
    ('xl/worksheets/one.xml', '<!DOCTYPE x><worksheet/>', 'XML包含外部声明'),
])
def test_workbook_complex_parts_refuse_at_named_gate(part, content, gate):
    with pytest.raises(ValueError, match=gate):
        read_workbook(workbook({part: content}))


def test_unused_workbook_style_and_chart_markup_are_not_evaluated():
    original = workbook()
    assert read_workbook(workbook({'xl/styles.xml': '<!DOCTYPE ignored><style/>',
                                   'xl/charts/chart1.xml': '<malformed-unused'})) == read_workbook(original)


def test_office_duplicate_case_paths_and_corrupt_chart_stream_have_specific_refusals():
    raw = package(extras={'WORD/document.xml': '<document/>'})
    with pytest.raises(ValueError, match='重名或非法包路径'):
        validate_office(raw, '.docx')
    raw = bytearray(package('ppt/presentation.xml', extras={'ppt/charts/chart1.xml': '<chart/>'}))
    with ZipFile(io.BytesIO(raw)) as archive:
        item = archive.getinfo('ppt/charts/chart1.xml')
        offset = item.header_offset + 30 + len(item.filename.encode()) + len(item.extra)
    raw[offset] ^= 0xFF
    with pytest.raises(ValueError, match='格式损坏或已加密'):
        validate_office(bytes(raw), '.pptx')
