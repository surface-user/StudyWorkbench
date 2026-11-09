"""Bounded, conservative three-way text preview; no filesystem or save authority.

Each side is represented by one changed line span. Multiple distant edits on
one side therefore include the intervening unchanged lines, deliberately
preferring a conflict over guessing how overlapping edits should be combined.
"""

from dataclasses import dataclass

TEXT_LIMIT = 1024 * 1024


@dataclass(frozen=True)
class MergePreview:
    text: str | None
    conflicted: bool


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    lines: tuple[str, ...]


def _validate(text: str) -> None:
    if not isinstance(text, str):
        raise ValueError('Merge inputs must be UTF-8 text')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeError as error:
        raise ValueError('Merge inputs must be UTF-8 text') from error
    if size > TEXT_LIMIT:
        raise ValueError('Merge text exceeds 1MiB UTF-8 budget')


def _lines(text: str) -> list[str]:
    # Only LF separates lines; preserve CR, Unicode separators and final LF.
    parts = text.split('\n')
    return [part + '\n' for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _edit(base: list[str], changed: list[str]) -> _Edit:
    start = 0
    while start < min(len(base), len(changed)) and base[start] == changed[start]:
        start += 1
    end, changed_end = len(base), len(changed)
    while end > start and changed_end > start and base[end - 1] == changed[changed_end - 1]:
        end -= 1
        changed_end -= 1
    return _Edit(start, end, tuple(changed[start:changed_end]))


def _overlap(left: _Edit, right: _Edit) -> bool:
    # An insertion on either edge of a replacement/deletion is ambiguous.
    if left.start == left.end:
        return right.start <= left.start <= right.end
    if right.start == right.end:
        return left.start <= right.start <= left.end
    return max(left.start, right.start) < min(left.end, right.end)


def preview_merge(base: str, local: str, current: str) -> MergePreview:
    """Return a candidate only for equal, unchanged or disjoint line-span edits.

    Inputs and output are limited to 1MiB each, with no normalization. Conflicts
    return no candidate and never inject marker text into Markdown. The caller
    must retain all inputs and authenticate the base separately. A clean preview
    is not permission to save or publish: confirm it and use the normal expected
    hash save against the exact current text. This core has no API/UI caller yet.
    """
    for value in (base, local, current):
        _validate(value)
    if local == current or current == base:
        return MergePreview(local, False)
    if local == base:
        return MergePreview(current, False)
    original = _lines(base)
    left, right = _edit(original, _lines(local)), _edit(original, _lines(current))
    if _overlap(left, right):
        return MergePreview(None, True)
    result = original.copy()
    for edit in sorted((left, right), key=lambda item: item.start, reverse=True):
        result[edit.start:edit.end] = edit.lines
    text = ''.join(result)
    _validate(text)
    return MergePreview(text, False)
