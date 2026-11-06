"""Bounded, inert XLSX values for the disposable document-view worker."""
import io
import json
import posixpath
import re
import stat
import struct
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

SOURCE_LIMIT = 16 * 1024 * 1024
EXPANDED_LIMIT = 32 * 1024 * 1024
PART_LIMIT = 8 * 1024 * 1024
CELL_LIMIT = 10000
STRING_LIMIT = 4096
RESULT_LIMIT = 2 * 1024 * 1024
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def xstring(value):
    # Decode once: _x005F_x0041_ is a literal escape, not the letter A.
    decoded = re.sub(r'_x([0-9A-Fa-f]{4})_', lambda match: chr(int(match[1], 16)), value)
    try:
        return decoded.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le')
    except UnicodeError:
        raise ValueError('XLSX字符串含不完整的Unicode代理对') from None


def member_name(name):
    if (not name or len(name) > 512 or '\\' in name or ':' in name or '%' in name
            or any(ord(c) < 32 for c in name) or any(p in {'', '.', '..'} for p in name.split('/'))):
        raise ValueError('XLSX包路径无效')
    return name


def preflight(data):
    if not 0 < len(data) <= SOURCE_LIMIT:
        raise ValueError('XLSX源文件最多16MiB')
    end = data.rfind(b'PK\x05\x06', max(0, len(data) - 65557))
    if end < 0 or end + 22 > len(data):
        raise ValueError('XLSX ZIP结束记录无效')
    _, disk, first, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2LH', data, end)
    if (disk or first or disk_count != count or not 0 < count <= 1024 or size > 256 * 1024
            or offset + size != end or end + 22 + comment != len(data)):
        raise ValueError('XLSX ZIP目录超限，或包含分卷/ZIP64')
    cursor, found = offset, 0
    while cursor < end:
        if cursor + 46 > end or data[cursor:cursor + 4] != b'PK\x01\x02':
            raise ValueError('XLSX ZIP目录条目无效')
        fields = struct.unpack_from('<4s6H3L5H2L', data, cursor)
        found += 1
        if found > 1024 or fields[13]:
            raise ValueError('XLSX实际ZIP条目超限或分卷')
        cursor += 46 + sum(fields[10:13])
    if cursor != end or found != count:
        raise ValueError('XLSX ZIP实际数量不符')


def read_workbook(data):
    preflight(data)
    with ZipFile(io.BytesIO(data)) as archive:
        members, folded, expanded = {}, set(), 0
        for item in archive.infolist():
            name = member_name(item.filename.rstrip('/') if item.is_dir() else item.filename)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (name.casefold() in folded or item.flag_bits & 1 or item.external_attr & 0x400
                    or mode not in {0, stat.S_IFDIR if item.is_dir() else stat.S_IFREG}
                    or item.compress_type not in {ZIP_STORED, ZIP_DEFLATED} or item.file_size > PART_LIMIT):
                raise ValueError('XLSX含重名/加密/特殊文件或部件预算超限')
            folded.add(name.casefold())
            expanded += item.file_size
            if expanded > EXPANDED_LIMIT:
                raise ValueError('XLSX解压总量超过32MiB')
            if any(token in name.casefold() for token in ('vbaproject', 'vbadata', 'activex', 'oleobject',
                                                        'externallinks/', 'macrosheets/', 'dialogsheets/', '/embeddings/')):
                raise ValueError('XLSX含宏/活动对象/外部数据')
            if not item.is_dir():
                members[name] = item
        nodes = 0

        def xml(name):
            nonlocal nodes
            item = members.get(name)
            if item is None:
                raise ValueError('XLSX缺少必要部件')
            with archive.open(item) as stream:
                raw = stream.read(PART_LIMIT + 1)
            if len(raw) != item.file_size or len(raw) > PART_LIMIT:
                raise ValueError('XLSX实际解压大小超限或不符')
            probe = raw.replace(b'\x00', b'').upper()
            if any(t in probe for t in (b'<!DOCTYPE', b'<!ENTITY', b'<?XML-STYLESHEET')):
                raise ValueError('XLSX XML包含外部声明')
            depth = 0
            parser = ET.iterparse(io.BytesIO(raw), events=('start', 'end'))
            for event, _ in parser:
                if event == 'start':
                    nodes += 1
                    depth += 1
                    if nodes > 100000 or depth > 64:
                        raise ValueError('XLSX XML节点或深度超限')
                else:
                    depth -= 1
            return parser.root

        def relationships(name):
            root = xml(name)
            if root.tag != f'{{{PKG_REL}}}Relationships':
                raise ValueError('XLSX关系格式不支持')
            result = {}
            base = posixpath.dirname(posixpath.dirname(name))
            for entry in root:
                identifier, target, kind = (entry.get(k, '') for k in ('Id', 'Target', 'Type'))
                if entry.tag != f'{{{PKG_REL}}}Relationship' or not identifier or identifier in result:
                    raise ValueError('XLSX关系ID重复或无效')
                # Relationships are package references only; never URLs or filesystem paths.
                if entry.get('TargetMode', 'Internal') != 'Internal':
                    raise ValueError('XLSX外部关系不支持')
                if (not target or target.startswith('//') or any(c in target for c in '\\:%?#')
                        or any(ord(c) < 32 for c in target)):
                    raise ValueError('XLSX关系目标无效')
                resolved = posixpath.normpath(target[1:] if target.startswith('/') else posixpath.join(base, target))
                member_name(resolved)
                if resolved not in members:
                    raise ValueError('XLSX关系目标缺失')
                if kind.rsplit('/', 1)[-1].lower() in {'vbaproject', 'oleobject', 'control', 'externallink'}:
                    raise ValueError('XLSX活动对象关系不支持')
                result[identifier] = (kind, resolved)
            return result

        content_types = xml('[Content_Types].xml')
        if any('macroenabled' in str(e.attrib).lower() for e in content_types):
            raise ValueError('XLSX宏内容类型不支持')
        all_relations = {name: relationships(name) for name in members if name.endswith('.rels')}
        roots = [target for kind, target in all_relations.get('_rels/.rels', {}).values() if kind == DOC_REL + 'officeDocument']
        if roots != ['xl/workbook.xml']:
            raise ValueError('XLSX仅支持常见OOXML工作簿结构')
        workbook = xml('xl/workbook.xml')
        if workbook.tag != f'{{{MAIN}}}workbook':
            raise ValueError('XLSX命名空间不支持（含Strict OOXML）')
        relations = all_relations.get('xl/_rels/workbook.xml.rels', {})
        shared_parts = [target for kind, target in relations.values() if kind == DOC_REL + 'sharedStrings']
        if len(shared_parts) > 1:
            raise ValueError('XLSX共享字符串表重复')
        strings = []

        def text(element):
            value = '' if element is None else ''.join(
                e.text or '' for e in [*element.findall(f'{{{MAIN}}}t'), *element.findall(f'{{{MAIN}}}r/{{{MAIN}}}t')])
            return bounded(xstring(value))

        def bounded(value):
            if len(value) > STRING_LIMIT:
                raise ValueError('XLSX单值超过4096字符')
            return value

        if shared_parts:
            root = xml(shared_parts[0])
            if root.tag != f'{{{MAIN}}}sst':
                raise ValueError('XLSX共享字符串格式无效')
            for entry in root:
                if entry.tag != f'{{{MAIN}}}si' or len(strings) >= CELL_LIMIT:
                    raise ValueError('XLSX共享字符串超限或无效')
                strings.append(text(entry))
        sheets = workbook.find(f'{{{MAIN}}}sheets')
        if sheets is None or not 0 < len(sheets) <= 10:
            raise ValueError('XLSX仅支持1至10个工作表')
        output, total, sheet_ids, names = [], 0, set(), set()
        output_size = 0
        for sheet in sheets:
            identifier = sheet.get(f'{{{DOC_REL[:-1]}}}id')
            title = bounded(xstring(sheet.get('name', '')))
            relation = relations.get(identifier)
            if (sheet.tag != f'{{{MAIN}}}sheet' or not 0 < len(title) <= 31
                    or sheet.get('state', 'visible') not in {'visible', 'hidden', 'veryHidden'}
                    or title.casefold() in names or identifier in sheet_ids
                    or relation is None or relation[0] != DOC_REL + 'worksheet'):
                raise ValueError('XLSX工作表关系/名称无效或不支持图表表')
            sheet_ids.add(identifier)
            names.add(title.casefold())
            root = xml(relation[1])
            if root.tag != f'{{{MAIN}}}worksheet' or root.find(f'{{{MAIN}}}sheetData') is None:
                raise ValueError('XLSX工作表格式不支持')
            cells, addresses = [], set()
            for cell in root.findall(f'{{{MAIN}}}sheetData/{{{MAIN}}}row/{{{MAIN}}}c'):
                total += 1
                address = cell.get('r', '')
                match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', address)
                column = 0
                for letter in match[1] if match else '':
                    column = column * 26 + ord(letter) - 64
                if (total > CELL_LIMIT or match is None or column > 16384 or int(match[2]) > 1048576
                        or address in addresses):
                    raise ValueError('XLSX单元格数量/地址无效或重复')
                addresses.add(address)
                kind = cell.get('t', 'n')
                value = cell.find(f'{{{MAIN}}}v')
                formula = cell.find(f'{{{MAIN}}}f') is not None
                if kind not in {'n', 's', 'inlineStr', 'b', 'str', 'e', 'd'} or formula and kind == 'inlineStr':
                    raise ValueError('XLSX单元格类型或公式内联字符串不支持')
                missing = formula and (value is None or value.text is None and kind != 'str')
                raw = (value.text or '') if value is not None else ''
                if missing:
                    raw = '公式无缓存值'
                elif kind == 's':
                    if not raw.isascii() or not raw.isdigit() or len(raw) > 8 or int(raw) >= len(strings):
                        raise ValueError('XLSX共享字符串引用无效')
                    raw = strings[int(raw)]
                elif kind == 'inlineStr':
                    raw = text(cell.find(f'{{{MAIN}}}is'))
                elif kind == 'b':
                    if raw not in {'0', '1'}:
                        raise ValueError('XLSX布尔值无效')
                    raw = 'TRUE' if raw == '1' else 'FALSE'
                elif kind == 'str':
                    raw = xstring(raw)
                elif kind not in {'n', 'str', 'e', 'd'}:
                    raise ValueError('XLSX单元格类型不支持')
                raw = bounded(raw)
                entry = {'address': address, 'value': raw, 'formula': formula, 'cache_missing': missing}
                output_size += len(json.dumps(entry, ensure_ascii=False).encode('utf-8')) + 2
                if output_size > RESULT_LIMIT:
                    raise ValueError('XLSX查看结果超过2MiB')
                cells.append(entry)
            output.append({'name': title, 'state': sheet.get('state', 'visible'), 'cells': cells})
        result = {'sheets': output, 'cell_count': total, 'position_kind': 'resource', 'source_format': 'xlsx'}
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > RESULT_LIMIT:
            raise ValueError('XLSX查看结果超过2MiB')
        return result
