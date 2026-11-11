"""Conservative OOXML input gate before an optional native preview converter."""
import io
import posixpath
import re
import zlib
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

MAX_SOURCE = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_XML_PART = 8 * 1024 * 1024
MAX_XML_NODES = 200000
DYNAMIC_FIELD = re.compile(r'(?i)\b(DDE(?:AUTO)?|LINK|DATABASE|INCLUDETEXT|INCLUDEPICTURE|WEBSERVICE|FILTERXML|RTD)\b|(?:https?|file|ftp):|[a-z]:[\\/]|\\\\')


def validate_office(data, suffix):
    if suffix not in {'.docx', '.pptx'}:
        raise ValueError('分页转换仅支持DOCX/PPTX；旧DOC/PPT请先在外部转PDF，原件保留')
    if not 0 < len(data) <= MAX_SOURCE:
        raise ValueError('Office分页转换最多32MiB，原件保留')
    expanded, count, xml_nodes, internal_rendering = 0, 0, 0, False

    def package(raw, kind, depth=0):
        nonlocal expanded, count, xml_nodes, internal_rendering
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                names = set()
                for member in archive.infolist():
                    name = member.filename
                    lower = name.casefold()
                    parts = PurePosixPath(name).parts
                    count += 1
                    expanded += member.file_size
                    if count > 4096 or expanded > MAX_EXPANDED or depth > 1:
                        raise ValueError('Office解压或嵌套预算超限，原件保留')
                    if (not name or lower in names or '\\' in name or name.startswith('/') or
                            any(part in {'.', '..'} or ':' in part for part in parts) or member.flag_bits & 1):
                        raise ValueError('Office包含加密、重名或非法包路径，原件保留')
                    names.add(lower)
                    if re.fullmatch(r'(?:word|ppt)/charts/chart[0-9]+\.xml', lower):
                        internal_rendering = True
                    if member.is_dir():
                        continue
                    if any(token in lower for token in ['vbaproject', 'vbadata', 'activex/', 'oleobject', 'externallinks/', 'macrosheets/', 'dialogsheets/']):
                        raise ValueError('Office包含宏、活动对象或外部链接，转换已拒绝，原件保留')
                    if '/embeddings/' in lower:
                        if not lower.endswith('.xlsx') or depth:
                            raise ValueError('Office嵌入对象仅支持受限图表XLSX数据，原件保留')
                        package(archive.read(member), '.xlsx', depth + 1)
                        continue
                    if '/media/' in lower and not lower.endswith(('.png', '.jpg', '.jpeg')):
                        raise ValueError('Office预览图片仅支持PNG/JPEG；动画/嵌入媒体或其他图片请外部转PDF，原件保留')
                    printer_settings = re.fullmatch(r'(?:word|ppt)/printersettings/printersettings[0-9]+\.bin', lower)
                    if lower.endswith(('.html', '.htm', '.vml', '.svg')) or lower.endswith('.bin') and not printer_settings:
                        raise ValueError('Office包含不支持的活动/旧式部件，原件保留')
                    if lower.endswith(('.xml', '.rels')):
                        if member.file_size > MAX_XML_PART:
                            raise ValueError('Office单个XML部件超过8MiB，原件保留')
                        content = archive.read(member)
                        probe = content.replace(b'\x00', b'').upper()
                        if any(token in probe for token in [b'<!DOCTYPE', b'<!ENTITY', b'<?XML-STYLESHEET']):
                            raise ValueError('Office XML含外部声明，原件保留')
                        depth_xml = 0
                        parser = ET.iterparse(io.BytesIO(content), events=('start', 'end'))
                        for event, _ in parser:
                            if event == 'start':
                                xml_nodes += 1
                                depth_xml += 1
                                if xml_nodes > MAX_XML_NODES or depth_xml > 128:
                                    raise ValueError('Office XML节点或嵌套预算超限，原件保留')
                            else:
                                depth_xml -= 1
                        tree = parser.root
                        instructions = ''.join(''.join(e.itertext()) for e in tree.iter()
                                               if e.tag.rsplit('}', 1)[-1].casefold() == 'instrtext')
                        if DYNAMIC_FIELD.search(instructions):
                            raise ValueError('Office包含拆分的外部字段，转换已拒绝，原件保留')
                        for element in tree.iter():
                            tag = element.tag.rsplit('}', 1)[-1].casefold()
                            if kind == '.docx' and tag == 'omath':
                                internal_rendering = True
                            attrs = {key.rsplit('}', 1)[-1].casefold(): value for key, value in element.attrib.items()}
                            if kind == '.xlsx' and tag in {'f', 'definedname'}:
                                raise ValueError('图表嵌入数据仅支持静态单元格，不计算工作簿公式，原件保留')
                            if tag == 'relationship':
                                target = unquote(attrs.get('target', ''))
                                relation = attrs.get('type', '').rsplit('/', 1)[-1].casefold()
                                if relation in {'oleobject', 'control', 'attachedtemplate', 'vbaproject', 'externallink'}:
                                    raise ValueError('Office包含活动对象关系，转换已拒绝，原件保留')
                                if (attrs.get('targetmode', '').casefold() == 'external' or urlsplit(target).scheme
                                        or '%' in target or target.startswith(('//', '\\')) or '\\' in target):
                                    raise ValueError('Office包含外部关系（含网页/文件链接），转换已拒绝，原件保留')
                                base = posixpath.dirname(posixpath.dirname(name))
                                resolved = posixpath.normpath(posixpath.join(base, target.split('#')[0]))
                                if resolved.startswith(('/', '../')) or resolved == '..' or ':' in resolved:
                                    raise ValueError('Office关系越过包根目录，原件保留')
                            if tag in {'altchunk', 'ddelink', 'ddelinks', 'olelink', 'oleobject', 'applet', 'script'} or tag == 'externaldata' and attrs.get('id') is None:
                                raise ValueError('Office包含外部/动态内容，原件保留')
                            if tag in {'instrtext', 'fldsimple', 'f'}:
                                text = ' '.join(element.itertext()) + ' ' + attrs.get('instr', '')
                                if DYNAMIC_FIELD.search(text):
                                    raise ValueError('Office包含外部字段或动态公式，转换已拒绝，原件保留')
                            for key in ('src', 'href'):
                                value = attrs.get(key, '')
                                if value and not value.startswith('#'):
                                    raise ValueError('Office包含直接外部引用，原件保留')
                required = {'[content_types].xml', '_rels/.rels',
                            {'.docx': 'word/document.xml', '.pptx': 'ppt/presentation.xml', '.xlsx': 'xl/workbook.xml'}[kind]}
                if not required <= names:
                    raise ValueError('Office包结构与扩展名不符，原件保留')
        except (BadZipFile, ET.ParseError, RuntimeError, NotImplementedError, UnicodeError, zlib.error) as error:
            raise ValueError('Office格式损坏或已加密，原件保留') from error

    package(data, suffix)
    return internal_rendering
