"""Assert shipped application bytecode matches source, using the release interpreter."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import CodeType

from PyInstaller.archive.readers import CArchiveReader

CODE_FIELDS = ('co_code', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars', 'co_nlocals',
               'co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_flags',
               'co_stacksize', 'co_exceptiontable')


def equivalent(actual, expected):
    if any(getattr(actual, f) != getattr(expected, f) for f in CODE_FIELDS):
        return False
    if len(actual.co_consts) != len(expected.co_consts):
        return False
    for left, right in zip(actual.co_consts, expected.co_consts):
        if isinstance(left, CodeType) or isinstance(right, CodeType):
            if not isinstance(left, CodeType) or not isinstance(right, CodeType) or not equivalent(left, right):
                return False
        elif left != right:
            return False
    return True


def code_fingerprint(code):
    """Pin inspected frozen behavior with the same code fields as source equivalence."""
    def value(item):
        if isinstance(item, CodeType):
            return ['code', [value(getattr(item, field)) for field in CODE_FIELDS], value(item.co_consts)]
        if isinstance(item, bytes):
            return ['bytes', item.hex()]
        if isinstance(item, tuple):
            return ['tuple', [value(part) for part in item]]
        if isinstance(item, frozenset):
            return ['frozenset', sorted((value(part) for part in item), key=repr)]
        if item is None or item is Ellipsis or isinstance(item, (str, int, float, complex)):
            return [type(item).__name__, repr(item)]
        raise ValueError('Unsupported frozen code constant; loading evidence must be renewed')
    return hashlib.sha256(json.dumps(value(code), ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 13, 17):
        raise RuntimeError('Run with the pinned CPython 3.13.17 release interpreter, not a different bytecode version')
    archive = CArchiveReader(str(args.exe))
    name = next(n for n, item in archive.toc.items() if item[-1] == 'z')
    pyz = archive.open_embedded_archive(name)
    sources = Path(__file__).resolve().parents[1] / 'backend/study_workbench'
    checked = 0
    for source in sorted(sources.glob('*.py')):
        module = 'study_workbench' + ('' if source.stem == '__init__' else '.' + source.stem)
        actual = pyz.extract(module)
        expected = compile(source.read_text(encoding='utf-8'), actual.co_filename, 'exec', dont_inherit=True)
        if not equivalent(actual, expected):
            raise AssertionError(f'Frozen module differs from source: {module}')
        checked += 1
    print(f'PASS: {checked} frozen application modules match current source, including nested code and constants')


if __name__ == '__main__':
    main()
