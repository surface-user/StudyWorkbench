"""Self-authored FMT-01 fixtures; authoring libraries are not product dependencies."""
import argparse
import io
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import OxmlElement
from docx.shared import Inches as WordInches
from docx.shared import Pt as WordPt
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt
from xlsxwriter import Workbook


def make_samples(root):
    root.mkdir()  # A new directory preserves evidence from earlier runs.
    document = Document()
    section = document.sections[0]
    section.header.paragraphs[0].text = 'FMT HEADER 中文页眉'
    section.footer.paragraphs[0].text = 'FMT FOOTER 中文页脚'
    document.styles['Normal'].font.size = WordPt(10)
    document.add_heading('FMT PORTRAIT ONE', 1)
    document.add_paragraph('中文课程：字体、公式与分节。')
    for font, marker in [('Arial', 'FONT AVAILABLE'), ('FMT Nonexistent Font 20261112', 'FONT FALLBACK')]:
        run = document.add_paragraph().add_run(marker)
        run.font.name = font
    paragraph = document.add_paragraph('OMML ')
    math = OxmlElement('m:oMath')
    power = OxmlElement('m:sSup')
    for name, text in [('m:e', 'x'), ('m:sup', '2')]:
        element, run, value = OxmlElement(name), OxmlElement('m:r'), OxmlElement('m:t')
        value.text = text
        run.append(value)
        element.append(run)
        power.append(element)
    math.append(power)
    paragraph._p.append(math)
    document.add_page_break()
    document.add_heading('FMT PORTRAIT TWO', 1)
    table = document.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    for cell, value in zip(table.rows[0].cells, ['ROW', '中文科目', 'VALUE'], strict=True):
        cell.text = value
    for number in range(1, 21):
        for cell, value in zip(table.add_row().cells, [f'R{number:02}', '数学', str(number * 2)], strict=True):
            cell.text = value
    document.add_paragraph('TABLE END')
    section = document.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = WordInches(11.7), WordInches(8.3)
    document.add_heading('FMT LANDSCAPE THREE', 1)
    table = document.add_table(rows=2, cols=4)
    table.style = 'Table Grid'
    table.cell(0, 0).merge(table.cell(0, 3)).text = 'MERGED HEADING'
    for cell, value in zip(table.rows[1].cells, ['LEFT', 'CENTRE A', 'CENTRE B', 'RIGHT'], strict=True):
        cell.text = value
    document.save(root / '复杂分节.docx')

    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Inches(12), Inches(6.75)
    for title in ['FMT CHART ONE', 'FMT COLUMNS TWO', 'FMT FORMULA THREE']:
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = title
    slide = presentation.slides[0]
    table = slide.shapes.add_table(3, 2, Inches(.5), Inches(1.6), Inches(4), Inches(2)).table
    for i, row in enumerate([['科目', '分数'], ['数学', '85'], ['英语', '90']]):
        for j, value in enumerate(row):
            table.cell(i, j).text = value
    data = CategoryChartData()
    data.categories = ['数学', '英语']
    data.add_series('静态成绩', [85, 90])
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6), Inches(1.5), Inches(5), Inches(4), data)
    slide = presentation.slides[1]
    for left, text, font in [(1, 'LEFT COLUMN\n中文段落', 'Arial'), (7, 'RIGHT COLUMN\nFONT FALLBACK', 'FMT Nonexistent Font 20261112')]:
        box = slide.shapes.add_textbox(Inches(left), Inches(2), Inches(4), Inches(2))
        box.text = text
        for paragraph in box.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name, run.font.size = font, Pt(24)
    presentation.slides[2].shapes.add_textbox(Inches(1), Inches(2), Inches(9), Inches(2)).text = '公式 x² + y² = z²\n化学 H₂O；原件保留'
    presentation.save(root / '复杂图表.pptx')

    output = io.BytesIO()
    with Workbook(output, {'in_memory': True}) as workbook:
        first = workbook.add_worksheet('复杂成绩')
        style = workbook.add_format({'bold': True, 'bg_color': '#DDEEFF', 'border': 1})
        first.merge_range('A1:C1', 'MERGED TITLE', style)
        first.write_row('A2', ['数学', 85, True])
        first.write_row('A3', ['英语', 90, False])
        first.write_formula('B4', '=SUM(B2:B3)', None, 175)
        first.write_formula('B5', '=1/0', None, '#DIV/0!')
        first.write_formula('B6', '=2+3')
        chart = workbook.add_chart({'type': 'column'})
        chart.add_series({'categories': '=复杂成绩!$A$2:$A$3', 'values': '=复杂成绩!$B$2:$B$3'})
        first.insert_chart('E2', chart)
        second = workbook.add_worksheet('日期与隐藏')
        second.write_datetime('A1', datetime(2026, 11, 12), workbook.add_format({'num_format': 'yyyy-mm-dd'}))
        second.write_string('B1', '<script>字面数据</script>')
        second.write_string('C1', '=WEBSERVICE("https://example.invalid")')
        second.hide()
    # Explicitly absent formula cache is a supported values-viewer state, never calculated here.
    with ZipFile(io.BytesIO(output.getvalue())) as source, ZipFile(root / '复杂工作簿.xlsx', 'w', ZIP_DEFLATED) as target:
        for item in source.infolist():
            raw = source.read(item)
            if item.filename == 'xl/worksheets/sheet1.xml':
                tree = ET.fromstring(raw)
                ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                cell = tree.find(f'.//{ns}c[@r="B6"]')
                cell.remove(cell.find(ns + 'v'))
                raw = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
            target.writestr(item, raw)
    print(json.dumps({'fixtures': sorted(p.name for p in root.iterdir()), 'self_authored': True}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    make_samples(parser.parse_args().output)
