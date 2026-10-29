"""Create self-authored Office fixtures; python-pptx is an authoring-only tool."""
import argparse
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output
    root.mkdir()
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = '中文分页验证：表格与图表'
    table = slide.shapes.add_table(3, 2, Inches(.4), Inches(1.5), Inches(4), Inches(2)).table
    for i, row in enumerate([['科目', '分数'], ['数学', '85'], ['英语', '90']]):
        for j, value in enumerate(row):
            table.cell(i, j).text = value
    data = CategoryChartData()
    data.categories = ['数学', '英语']
    data.add_series('分数', [85, 90])
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(4.7), Inches(1.5), Inches(4), Inches(3), data)
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = '第二页：公式与中文'
    slide.shapes.add_textbox(Inches(1), Inches(2), Inches(7), Inches(2)).text = '学习公式 x² + y² = z²\n静态预览，原件保留'
    presentation.save(root / '中文图表.pptx')
    (root / '中文公式.docx').write_bytes(
        (Path(__file__).resolve().parents[1] / 'contracts/samples/original-study.docx').read_bytes())
    print('Self-authored Word OMML/table/image and PPT table/chart fixtures created')


if __name__ == '__main__':
    main()
