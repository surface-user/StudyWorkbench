"""Read one contiguous set of Word body blocks with their original numbering context."""
from collections import Counter

from docling.backend.msword_backend import MsWordDocumentBackend
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from .word_outline import WORD

ALTERNATE_FLOW = {WORD + name for name in ('ins', 'del', 'moveFrom', 'moveTo', 'txbxContent', 'sdt')}
ALTERNATE_FLOW.add('{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent')


def check_table_budget(table, position):
    total_cells = 0
    for nested in table.iter(WORD + 'tbl'):
        rows = nested.findall(WORD + 'tr')
        width = len(nested.findall(WORD + 'tblGrid/' + WORD + 'gridCol'))
        for row in rows:
            columns = 0
            for cell in row.findall(WORD + 'tc'):
                span = cell.find(WORD + 'tcPr/' + WORD + 'gridSpan')
                value = span.get(WORD + 'val', '') if span is not None else '1'
                if not value.isascii() or not value.isdecimal() or len(value) > 3 or not 1 <= int(value) <= 256:
                    raise ValueError(f'Word 第 {position} 个正文位置的表格跨列超限')
                columns += int(value)
            width = max(width, columns)
        total_cells += len(rows) * width
        if width > 256 or total_cells > 10000:
            raise ValueError(f'Word 第 {position} 个正文位置的表格网格超限')
    if sum(len(node.text or '') for node in table.iter(WORD + 't')) > 20000:
        raise ValueError(f'Word 第 {position} 个正文位置的表格超过文本预算')


def definitions_by_id(numbering, tag, key):
    definitions = {}
    if numbering is not None:
        for element in numbering.findall(WORD + tag):
            value = element.get(WORD + key)
            definitions[value] = None if value in definitions else element
    return definitions


def fixed_decimal_list(num, abstracts):
    """Accept only unambiguous, single-level decimal definitions."""
    if num is None or num.find(WORD + 'lvlOverride') is not None:
        return None
    ref = num.find(WORD + 'abstractNumId')
    abstract = abstracts.get(ref.get(WORD + 'val')) if ref is not None else None
    if abstract is None or any(item.tag in {WORD + 'numStyleLink', WORD + 'styleLink'} for item in abstract):
        return None
    if any(k.endswith('}restartNumberingAfterBreak') and v not in {'0', 'false'} for k, v in abstract.attrib.items()):
        return None
    levels = abstract.findall(WORD + 'lvl')
    if len(levels) != 1 or levels[0].get(WORD + 'ilvl') != '0':
        return None
    level = levels[0]
    parts = {node.tag: node.get(WORD + 'val', '') for node in level}
    start, pattern = parts.get(WORD + 'start', ''), parts.get(WORD + 'lvlText', '')
    if (parts.get(WORD + 'numFmt') != 'decimal' or not start.isascii() or not start.isdecimal()
            or len(start) > 4 or pattern not in {'%1.', '%1、', '%1)', '第%1题'} or WORD + 'lvlRestart' in parts):
        return None
    return int(start), pattern


class WordRangeBackend(MsWordDocumentBackend):
    def _get_numId_and_ilvl(self, paragraph):
        # The selected in-memory paragraphs already contain the verified original marker, if available.
        return None, None

    def _walk_linear(self, body, doc):
        if body is not self.docx_obj.element.body:
            return super()._walk_linear(body, doc)

        first, last = self.selected_range
        self.item_positions, self.uncertain = {}, set()
        counters, definitions = Counter(), {}
        alternate_flow = False
        parts = [rel.target_part for rel in self.docx_obj.part.rels.values() if rel.reltype == RT.NUMBERING]
        numbering = parts[0].element if len(parts) == 1 else None
        nums = definitions_by_id(numbering, 'num', 'numId')
        abstracts = definitions_by_id(numbering, 'abstractNum', 'abstractNumId')
        for pos, element in enumerate(body, 1):
            if pos > last:
                break
            if element.tag == WORD + 'tbl' and pos >= first:
                check_table_budget(element, pos)
            if not alternate_flow:
                alternate_flow = any(node.tag in ALTERNATE_FLOW for node in element.iter())
            for paragraph in element.iter(WORD + 'p'):
                props = paragraph.find(WORD + 'pPr/' + WORD + 'numPr')
                wrapped = Paragraph(paragraph, self.docx_obj)
                num_id, level = super()._get_numId_and_ilvl(wrapped)
                if props is not None:
                    ids, levels = props.findall(WORD + 'numId'), props.findall(WORD + 'ilvl')
                    values = [node.get(WORD + 'val', '') for node in [*ids, *levels]]
                    if (len(ids) != 1 or len(levels) > 1 or
                            any(not value.isascii() or not value.isdecimal() for value in values)):
                        # Its list identity may be the same as a later selection.
                        alternate_flow = True
                        if pos >= first:
                            self.uncertain.add(pos)
                        continue
                if num_id == 0:
                    continue
                if num_id is None:
                    if props is not None:
                        alternate_flow = True
                        if pos >= first:
                            self.uncertain.add(pos)
                    continue
                if num_id not in definitions:
                    definitions[num_id] = fixed_decimal_list(nums.get(str(num_id)), abstracts)
                if level not in (None, 0):
                    definitions[num_id] = None
                counters[num_id] += 1
                if pos < first:
                    continue
                if definitions[num_id] is None or alternate_flow:
                    self.uncertain.add(pos)
                    continue
                start, pattern = definitions[num_id]
                run, text = OxmlElement('w:r'), OxmlElement('w:t')
                text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                text.text = pattern.replace('%1', str(start + counters[num_id] - 1)) + ' '
                run.append(text)
                paragraph.insert(1 if paragraph.find(WORD + 'pPr') is not None else 0, run)
            if pos < first:
                continue
            # Keep the original element and its relationships intact, including all rich descendants of a table.
            collections = (doc.texts, doc.tables, doc.pictures)
            starts = [len(items) for items in collections]
            self._force_new_code_block = True
            super()._walk_linear((element,), doc)
            for items, start in zip(collections, starts):
                self.item_positions.update((id(item), (item, pos)) for item in items[start:])
        return doc, []
