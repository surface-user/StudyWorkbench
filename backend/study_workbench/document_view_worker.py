"""Disposable rasterizer. Receives bytes, never paths, URLs or business credentials."""
import base64
import io
import json
import sys
import unicodedata
from contextlib import closing

VERSION = 'pdfium-pillow-view-v1'


def column_text(page, *, include_geometry=False):
    import pypdfium2.raw as pdfium

    if page.get_rotation() != 0:
        return {'available': False, 'reason': 'rotated_page'}
    x0, y0, x1, y1 = page.get_bbox()
    width, height = x1 - x0, y1 - y0
    if not 0 < width <= 100000 or not 0 < height <= 100000:
        return {'available': False, 'reason': 'invalid_page_bounds'}
    mid = x0 + width / 2
    columns = [[], []]
    graphics = [[], []]
    characters = 0
    with closing(page.get_textpage()) as textpage:
        if textpage.count_chars() > 20000:
            return {'available': False, 'reason': 'text_budget'}
        for index, obj in enumerate(page.get_objects(max_depth=1, textpage=textpage)):
            if index >= 4000:
                return {'available': False, 'reason': 'object_budget'}
            if obj.type == pdfium.FPDF_PAGEOBJ_FORM:
                return {'available': False, 'reason': 'nested_layout'}
            if obj.type != pdfium.FPDF_PAGEOBJ_TEXT:
                if include_geometry:
                    left, bottom, right, top = obj.get_bounds()
                    if not (x0 <= left <= right <= x1 and y0 <= bottom <= top <= y1) or left < mid < right:
                        return {'available': False, 'reason': 'ambiguous_graphic'}
                    graphics[int(left >= mid)].append(((y1 - top) / height, (y1 - bottom) / height))
                continue
            value = obj.extract().strip()
            if not value:
                continue
            matrix = obj.get_matrix()
            if (matrix.a <= 0 or matrix.d <= 0 or abs(matrix.b) > 1e-5 or abs(matrix.c) > 1e-5
                    or len(value.splitlines()) != 1
                    or any(unicodedata.bidirectional(c) in {'R', 'AL', 'RLO', 'RLE', 'RLI'} for c in value)):
                return {'available': False, 'reason': 'unsupported_text_direction'}
            left, bottom, right, top = obj.get_bounds()
            if not x0 <= left < right <= x1 or not y0 <= bottom < top <= y1:
                return {'available': False, 'reason': 'invalid_text_bounds'}
            if left < mid < right:
                return {'available': False, 'reason': 'cross_column_text'}
            characters += len(value) + 1
            if characters > 20000:
                return {'available': False, 'reason': 'text_budget'}
            columns[int(left >= mid)].append((top, bottom, left, right, value))
    if not all(columns):
        return {'available': False, 'reason': 'empty_column'}
    result = []
    for side, lines in enumerate(columns):
        lines.sort(key=lambda item: (-item[0], item[2]))
        if any(lower[0] > upper[1] for upper, lower in zip(lines, lines[1:])):
            return {'available': False, 'reason': 'overlapping_lines'}
        result.append({'text': '\n'.join(line[4] for line in lines),
                       'box': [(min(line[2] for line in lines) - x0) / width, (y1 - lines[0][0]) / height,
                               (max(line[3] for line in lines) - x0) / width, (y1 - lines[-1][1]) / height]})
        if include_geometry:
            result[-1]['lines'] = [((y1 - line[0]) / height, line[4]) for line in lines]
            result[-1]['graphics'] = graphics[side]
    return {'available': True, 'columns': result}


def render(data, mode, page=1):
    if mode == 'xlsx':
        from .spreadsheet_view import read_workbook
        return read_workbook(data)
    if mode == 'image':
        from PIL import Image
        with Image.open(io.BytesIO(data)) as picture:
            if picture.format not in {'PNG', 'JPEG'} or picture.width * picture.height > 16000000:
                raise ValueError('图片只支持PNG/JPEG且不超过1600万像素')
            picture.thumbnail((2048, 2048))
            output = io.BytesIO()
            picture.convert('RGBA').save(output, 'PNG')
            return {'image_base64': base64.b64encode(output.getvalue()).decode()}
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(data) as document:
        count = len(document)
        if not 0 < count <= 2000:
            raise ValueError('PDF阅读最多2000页，原件已保留')
        if mode == 'pdf-info':
            return {'page_count': count}
        if not 1 <= page <= count:
            raise ValueError('PDF页码超出范围')
        current = document[page - 1]
        try:
            width, height = current.get_size()
            if not 0 < width <= 100000 or not 0 < height <= 100000:
                raise ValueError('PDF页面尺寸异常')
            if mode == 'pdf-columns':
                return {**column_text(current), 'page': page, 'page_count': count}
            bitmap = current.render(scale=min(2.0, 2048 / max(width, height)))
            try:
                picture = bitmap.to_pil()
                try:
                    output = io.BytesIO()
                    picture.save(output, 'PNG')
                finally:
                    picture.close()
                return {'image_base64': base64.b64encode(output.getvalue()).decode(), 'page': page, 'page_count': count}
            finally:
                bitmap.close()
        finally:
            current.close()


def worker(mode):
    try:
        options = json.loads(sys.stdin.buffer.readline(4096))
        limit = (8 if mode == 'pdf-columns' else 128) * 1024 * 1024
        data = sys.stdin.buffer.read(limit + 1)
        if len(data) > limit or mode not in {'image', 'pdf-info', 'pdf-page', 'pdf-columns', 'xlsx'}:
            raise ValueError('查看大小或类型超限')
        value = render(data, mode, options.get('page', 1))
        value['renderer_version'] = {'xlsx': 'xlsx-values-v1', 'pdf-columns': 'pdfium-columns-v1'}.get(mode, VERSION)
    except Exception:
        value = {'error': '文档无法渲染：可能损坏、加密、超出页数/像素预算；原件已保留'}
    print(json.dumps(value), flush=True)
