"""Bounded offline document conversion in a disposable child process."""
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from .question_splitting import START, DraftSplitter, all_blocks, split_blocks

MAX_ASSETS = 64 * 1024 * 1024


def convert_document(data, name):
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.extend(["-m", "study_workbench"])
    command.extend(["--parse-document", Path(name).suffix.lower()])
    try:
        result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=25, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                                     "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                                     "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
    except subprocess.TimeoutExpired as error:
        raise ValueError("文档解析超过 25 秒，原件已保留；请拆分或转为文本 PDF") from error
    if result.returncode or len(result.stdout) > 96 * 1024 * 1024:
        raise ValueError("文档解析未完成，可能损坏、加密或超限；原件已保留")
    value = json.loads(result.stdout)
    if "error" in value:
        raise ValueError(value["error"])
    return value


def extract(data, suffix, *, page_range=None):
    from PIL import Image
    from pydantic import TypeAdapter

    from .question_protocol import Content

    if page_range is not None and suffix != '.pdf':
        raise ValueError('PDF 页区间只适用于 PDF 原件')
    blocks, assets = [], []
    total = 0

    def text(value):
        if value.strip():
            if len(value) > 200000:
                raise ValueError("文档提取文本过长，请拆分")
            blocks.extend({"type": "text", "text": value[i:i + 20000]} for i in range(0, len(value), 20000))

    def image(picture, label, *, append=True):
        nonlocal total
        width, height = picture.size
        if not 0 < width <= 8192 or not 0 < height <= 8192 or width * height > 16000000:
            raise ValueError("文档图片尺寸超限，请缩小后重试")
        output = io.BytesIO()
        picture.convert("RGB").save(output, format="PNG")
        raw = output.getvalue()
        total += len(raw)
        if len(raw) > 8 * 1024 * 1024 or total > MAX_ASSETS:
            raise ValueError("文档图片总量超限，请拆分")
        identifier = uuid4().hex
        assets.append({"id": identifier, "data": base64.b64encode(raw).decode(), "name": f"{label}.png"})
        block = {"type": "image", "attachment_id": identifier, "alt": label}
        if append:
            blocks.append(block)
        return block

    if suffix == ".docx":
        from docling.backend.msword_backend import MsWordDocumentBackend
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.document import InputDocument
        from docling_core.types.doc import ContentLayer

        try:
            with ZipFile(io.BytesIO(data)) as archive:
                files = archive.infolist()
                if len(files) > 2000 or sum(f.file_size for f in files) > 64 * 1024 * 1024:
                    raise ValueError("Word 解压大小或文件数超限")
                for member in files:
                    name = member.filename.lower()
                    if member.flag_bits & 1 or any(s in name for s in ("vbaproject", "word/embeddings/", "word/charts/")):
                        raise ValueError("此 Word 含宏、嵌入对象或复杂图表；请转换为 PDF 后导入")
                    if name.startswith("word/media/") and not name.endswith((".png", ".jpg", ".jpeg")):
                        raise ValueError("Word 含非 PNG/JPEG 图片，请转换为 PDF 后导入")
                    if name.endswith((".xml", ".rels")):
                        raw = archive.read(member)
                        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                            raise ValueError("Word XML 含不允许的外部声明")
                        if name.endswith(".rels") and b'TargetMode="External"' in raw:
                            # Offline conversion does not dereference even benign external links.
                            raise ValueError("Word 含外部引用，请移除引用或转换为 PDF 后导入")
            document = InputDocument(io.BytesIO(data), filename="source.docx", format=InputFormat.DOCX,
                                     backend=MsWordDocumentBackend)
            if not document.valid:
                raise ValueError("Word 文档结构无效")
            try:
                converted = document._backend.convert()
                for item, _ in converted.iterate_items(included_content_layers=set(ContentLayer)):
                    if str(item.label) == "formula":
                        blocks.append({"type": "latex", "tex": item.text, "display": True})
                    elif str(item.label) == "table":
                        # Preserve all text and cell order without flattening merged cells into false columns.
                        text(item.export_to_markdown(doc=converted))
                    elif getattr(item, "text", ""):
                        marker = f"{item.marker} " if getattr(item, 'enumerated', False) else ''
                        text(marker + item.text)
                    elif str(item.label) == "picture" and item.image:
                        with Image.open(io.BytesIO(base64.b64decode(str(item.image.uri).split(",", 1)[1]))) as embedded:
                            image(embedded, f"Word 图片 {len(assets) + 1}")
            finally:
                document._backend.unload()
        except BadZipFile as error:
            raise ValueError("Word ZIP 结构无效") from error
        warnings = ["Word按内容顺序与显式题号拆为MD候选，表格保留Markdown。不是实际分页截图；请核对复杂版式、图片顺序和题目边界，不推断缺失答案。",
                    "仅显式材料标题和完整有序题号范围自动归组为候选；其他卷头/材料仍在整篇预览，须核对或手动归组。"]
        drafts = split_blocks(blocks, warnings)
    elif suffix == ".pdf":
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        splitter = DraftSplitter()
        current = None
        try:
            page_count = len(document)
            if page_range is None:
                if not 0 < page_count <= 20:
                    raise ValueError("PDF 最多 20 页，请拆分后导入")
                first, last = 1, page_count
            else:
                first, last = page_range
                if (type(first) is not int or type(last) is not int
                        or not 1 <= first <= last <= page_count <= 2000 or last - first >= 20):
                    raise ValueError('PDF 页区间无效，每块最多 20 页，原件最多 2000 页')
            fragments = []
            question_count = material_count = 0
            for index in range(first - 1, last):
                page = document[index]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0 or height / width > 5 or width / height > 5:
                        raise ValueError("PDF 页面尺寸异常")
                    text(f"第 {index + 1} 页")
                    textpage = page.get_textpage()
                    try:
                        if page_range is not None and textpage.count_chars() > 200000:
                            raise ValueError('PDF 单页提取文本过长')
                        page_text = textpage.get_text_bounded()
                        text(page_text)
                        starts = []
                        missing_position = False
                        search_index = 0
                        for match in START.finditer(page_text):
                            if page_range is not None:
                                if match['first'] is None:
                                    question_count += 1
                                else:
                                    material_count += 1
                                if max(question_count, material_count) > 200:
                                    raise ValueError('PDF 分块超过 200 道题目或 200 组材料')
                            search = textpage.search(match.group().strip(), index=search_index)
                            try:
                                found = search.get_next()
                            finally:
                                search.close()
                            if found is None:
                                missing_position = True
                                continue
                            search_index = found[0] + found[1]
                            left, bottom, right, top = textpage.get_charbox(found[0])
                            starts.append((match, max(0, height - top - 3)))
                    finally:
                        textpage.close()
                    bitmap = page.render(scale=min(2.0, 1600 / width))
                    try:
                        picture = bitmap.to_pil()
                        page_image = image(picture, f"PDF 第 {index + 1} 页原貌")
                        # Single-column candidates only; retain full-width regions and expose them for review.
                        ambiguous = any(a[1] >= b[1] for a, b in zip(starts, starts[1:]))
                        if page_range is not None:
                            ambiguous = (ambiguous or missing_position or any(
                                not 0 <= top < height for _, top in starts))
                        if ambiguous:
                            starts = []
                            current = None
                            if splitter.group is not None:
                                splitter.warn('PDF题号位置次序不可靠，共享材料未自动关联；请核对整页原图。')
                                splitter.group = None
                            splitter.current = None
                        segments = []
                        if page_range is not None:
                            current = {'marker': None, 'ambiguous': ambiguous,
                                       'blocks': [], 'regions': [], 'source_pages': []}
                        if current is not None:
                            end = starts[0][0].start() if starts else len(page_text)
                            segments.append((current, 0, starts[0][1] if starts else height, page_text[:end]))
                        for position, (match, top) in enumerate(starts):
                            if page_range is None:
                                current = splitter.begin(match)
                            else:
                                current = {'marker': match.group().strip(), 'ambiguous': False,
                                           'blocks': [], 'regions': [], 'source_pages': []}
                            end = starts[position + 1][0].start() if position + 1 < len(starts) else len(page_text)
                            bottom = starts[position + 1][1] if position + 1 < len(starts) else height
                            if current is not None:
                                segments.append((current, top, bottom, page_text[match.start():end]))
                        for draft, top, bottom, value in segments:
                            if bottom - top < 1:
                                continue
                            if page_range is not None and top == 0 and bottom == height:
                                draft['blocks'].append(page_image)
                            else:
                                crop = picture.crop((0, int(top / height * picture.height), picture.width,
                                                     min(picture.height, int(bottom / height * picture.height) + 1)))
                                try:
                                    draft['blocks'].append(image(crop, f"第{index + 1}页题目区域", append=False))
                                finally:
                                    crop.close()
                            if value.strip():
                                draft['blocks'].extend({'type': 'text', 'text': value[i:i + 20000]}
                                                       for i in range(0, len(value), 20000))
                            if page_range is not None:
                                fragments.append(draft)
                            draft['source_pages'].append(index + 1)
                            draft['regions'].append({'page': index + 1, 'box': [0, top / height, 1, bottom / height]})
                        picture.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        finally:
            document.close()
        if page_range is not None:
            warnings = []
            if first > 1:
                warnings.append('选区起点之前可能有题干或材料')
            if last < page_count:
                warnings.append('选区末尾可能截断题目或材料')
            return {'page_count': page_count, 'first_page': first, 'last_page': last,
                    'blocks': blocks, 'fragments': fragments, '_assets': assets, 'warnings': warnings}
        drafts = splitter.finish()
        warnings = ["PDF按显式题号生成单栏裁切候选，跨页延续同题或材料；裁图保留公式和插图，文字仅供检索。扫描件无OCR，多栏及未支持题号需手动处理；不推断缺失答案。",
                    "仅显式材料标题和完整有序题号范围自动归组为候选；其他卷头/材料仍在整篇预览，须核对或手动归组。",
                    *splitter.warnings]
    else:
        raise ValueError("不支持此文档格式")
    if not blocks:
        raise ValueError("文档没有可提取内容，请核对原件")
    TypeAdapter(Content).validate_python(blocks)
    for draft in drafts:
        TypeAdapter(Content).validate_python(all_blocks(draft))
    if not drafts:
        warnings.append('未识别到可靠题号，原资料保留；当前不能自动拆题，请勿将整篇笔记视为逐题入库。')
    return {"kind": "note", "blocks": blocks, "question_drafts": drafts, "warnings": warnings, "_assets": assets}


def worker(suffix, *, page_range=None):
    data = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
    try:
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("文档超过 8 MiB")
        if page_range is not None:
            if any(not value.isascii() or not value.isdecimal() or len(value) > 4 for value in page_range):
                raise ValueError('PDF 页码必须为 1 至 2000 的十进制整数')
            page_range = tuple(map(int, page_range))
        value = extract(data, suffix, page_range=page_range)
        if page_range is not None:
            raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            if len(raw) > 96 * 1024 * 1024:
                raise ValueError('PDF 分块输出超限')
            sys.stdout.buffer.write(raw)
            return
    except ValueError as error:
        # Only our own policy errors may be shown; native errors contain input fragments.
        message = str(error)
        safe = message if message.startswith(("文档", "Word", "PDF", "此 Word", "不支持")) else "文档解析失败，请检查格式、加密和大小；原件保留"
        value = {"error": safe[:240]}
    except Exception:
        value = {"error": "文档解析失败，请检查格式、加密和大小；原件保留"}
    print(json.dumps(value, ensure_ascii=page_range is not None), flush=True)
