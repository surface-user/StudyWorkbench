"""Bounded metadata-only duration reading. Unknown layouts stay unknown, never execute codecs."""
import math
import struct

MAX_DURATION_MS = 604800000


def duration_ms(path, mime):
    try:
        with path.open('rb') as handle:
            end = path.stat().st_size
            budget = [4096]

            def boxes(start, stop):
                while start < stop:
                    budget[0] -= 1
                    if budget[0] < 0 or stop - start < 8:
                        raise ValueError('Box budget/header')
                    handle.seek(start)
                    raw = handle.read(8)
                    size, kind = struct.unpack('>I4s', raw)
                    header = 8
                    if size == 1:
                        size = struct.unpack('>Q', handle.read(8))[0]
                        header = 16
                    elif size == 0:
                        size = stop - start
                    if size < header or start + size > stop:
                        raise ValueError('Box bounds')
                    yield kind, start + header, start + size
                    start += size

            def vint(identifier=False):
                first = handle.read(1)
                if not first or first[0] == 0:
                    raise ValueError('Invalid EBML integer')
                width = 9 - first[0].bit_length()
                if width > (4 if identifier else 8):
                    raise ValueError('EBML integer width')
                raw = first + handle.read(width - 1)
                if len(raw) != width:
                    raise ValueError('Truncated EBML integer')
                value = int.from_bytes(raw, 'big')
                if identifier:
                    return value
                value &= (1 << (7 * width)) - 1
                return None if value == (1 << (7 * width)) - 1 else value

            def elements(start, stop):
                while start < stop:
                    budget[0] -= 1
                    if budget[0] < 0:
                        raise ValueError('Element budget')
                    handle.seek(start)
                    kind, size = vint(True), vint()
                    payload = handle.tell()
                    finish = stop if size is None else payload + size
                    if finish > stop or finish <= start:
                        raise ValueError('Element bounds')
                    yield kind, payload, finish
                    start = finish

            result = None
            if mime == 'video/webm':
                for kind, start, stop in elements(0, end):
                    if kind != 0x18538067:
                        continue
                    for key, begin, finish in elements(start, stop):
                        if key != 0x1549A966:
                            continue
                        scale, duration = 1000000, None
                        for field, offset, last in elements(begin, finish):
                            size = last - offset
                            handle.seek(offset)
                            if field == 0x2AD7B1 and 1 <= size <= 8:
                                scale = int.from_bytes(handle.read(size), 'big')
                            elif field == 0x4489 and size in (4, 8):
                                duration = struct.unpack('>f' if size == 4 else '>d', handle.read(size))[0]
                        if duration is not None and scale > 0:
                            result = duration * scale / 1000000
                        break
                    break
            else:
                for kind, start, stop in boxes(0, end):
                    if kind != b'moov':
                        continue
                    for key, begin, finish in boxes(start, stop):
                        if key != b'mvhd':
                            continue
                        handle.seek(begin)
                        raw = handle.read(min(32, finish - begin))
                        if raw and raw[0] in (0, 1):
                            offset, width = (12, 4) if raw[0] == 0 else (20, 8)
                            if len(raw) >= offset + 4 + width:
                                scale = int.from_bytes(raw[offset:offset + 4], 'big')
                                duration = int.from_bytes(raw[offset + 4:offset + 4 + width], 'big')
                                if scale and duration != (1 << (width * 8)) - 1:
                                    result = duration * 1000 / scale
                        break
                    break
            return int(result) if result is not None and math.isfinite(result) and 0 < result <= MAX_DURATION_MS else None
    except (OSError, ValueError, struct.error, OverflowError):
        return None
