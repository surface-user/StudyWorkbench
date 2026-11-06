"""Disposable rasterizer. Receives bytes, never paths, URLs or business credentials."""
import base64
import io
import json
import sys

VERSION = 'pdfium-pillow-view-v1'


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
        data = sys.stdin.buffer.read(128 * 1024 * 1024 + 1)
        if len(data) > 128 * 1024 * 1024 or mode not in {'image', 'pdf-info', 'pdf-page', 'xlsx'}:
            raise ValueError('查看大小或类型超限')
        value = render(data, mode, options.get('page', 1))
        value['renderer_version'] = 'xlsx-values-v1' if mode == 'xlsx' else VERSION
    except Exception:
        value = {'error': '文档无法渲染：可能损坏、加密、超出页数/像素预算；原件已保留'}
    print(json.dumps(value), flush=True)
