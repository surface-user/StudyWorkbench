"""Read-only, bounded MP4 input policy. This is not a native probe or a codec validator."""
import hashlib
import os
import re
import stat
import struct
import time
from pathlib import PurePosixPath

from fastapi import HTTPException

from .imports import resource_path

INPUT_LIMIT = 512 * 1024 * 1024
METADATA_LIMIT = 2 * 1024 * 1024
BOX_LIMIT = 4096
SAMPLE_LIMIT = 1000000
POLICY_VERSION = 'local-mp4-input-v1'


def managed_media_path(workspace, identifier, relative):
    parts = PurePosixPath(relative).parts
    local = len(parts) == 4 and parts[2] == 'media' and parts[3] in (
        identifier + '.mp4', identifier + '.m4a', identifier + '.webm')
    downloaded = (len(parts) == 5 and parts[2] == 'downloads' and re.fullmatch('[0-9a-f]{32}', parts[3]) and
                  re.fullmatch(r'[1-9][0-9]*\.(mp4|m4a|webm)', parts[4]))
    if parts[:2] != ('workspaces', workspace) or not (local or downloaded) or PurePosixPath(relative).as_posix() != relative:
        raise HTTPException(409, '媒体来源记录无效，原文件保留')
    return relative


def require(condition):
    if not condition:
        raise HTTPException(422, '此媒体结构尚不支持安全处理，原文件保留；请在外部工具中转换')


def descriptor(raw, offset, tag):
    require(offset < len(raw) and raw[offset] == tag)
    index, length = offset + 1, 0
    for _ in range(4):
        require(index < len(raw))
        value = raw[index]
        index += 1
        length = (length << 7) | (value & 127)
        if not value & 128:
            require(index + length <= len(raw))
            return raw[index:index + length], index + length
    require(False)


class MP4Input:
    def __init__(self, handle, size, deadline, checkpoint=lambda: None):
        self.handle, self.size, self.deadline = handle, size, deadline
        self.external_checkpoint = checkpoint
        self.box_count = self.metadata_bytes = 0

    def checkpoint(self):
        self.external_checkpoint()
        if time.monotonic() > self.deadline:
            raise HTTPException(413, '媒体预检超过时间预算，原文件保留')

    def read(self, start, size):
        self.checkpoint()
        self.metadata_bytes += size
        if self.metadata_bytes > METADATA_LIMIT:
            raise HTTPException(413, '媒体元数据超过2MiB预算，原文件保留')
        require(size >= 0 and 0 <= start <= self.size - size)
        self.handle.seek(start)
        value = self.handle.read(size)
        require(len(value) == size)
        return value

    def boxes(self, start, stop, allowed, multiple=()):
        result = {}
        while start < stop:
            self.box_count += 1
            if self.box_count > BOX_LIMIT:
                raise HTTPException(413, '媒体容器超过4096个结构预算，原文件保留')
            require(stop - start >= 8)
            size, kind = struct.unpack('>I4s', self.read(start, 8))
            header = 8
            if size == 1:
                size = int.from_bytes(self.read(start + 8, 8), 'big')
                header = 16
            # Zero-sized/fragmented/unknown boxes deliberately require a later policy version.
            require(size >= header and start + size <= stop and kind in allowed)
            require(kind in multiple or kind not in result)
            result.setdefault(kind, []).append((start + header, start + size))
            start += size
        require(start == stop)
        return result

    def one(self, boxes, kind):
        require(kind in boxes and len(boxes[kind]) == 1)
        return boxes[kind][0]

    def payload(self, bounds):
        return self.read(bounds[0], bounds[1] - bounds[0])

    def table(self, boxes, kind, width, optional=False):
        if optional and kind not in boxes:
            return []
        raw = self.payload(self.one(boxes, kind))
        require(len(raw) >= 8 and raw[:4] == b'\0' * 4)
        count = int.from_bytes(raw[4:8], 'big')
        require(count <= SAMPLE_LIMIT and len(raw) == 8 + count * width * 4)
        return [struct.unpack_from('>' + 'I' * width, raw, 8 + i * width * 4) for i in range(count)]

    def metadata(self, bounds):
        # Only the ordinary iTunes textual metadata tree is accepted, with no alternate data source.
        udta = self.boxes(*bounds, {b'meta'})
        if not udta:
            return
        start, stop = self.one(udta, b'meta')
        require(self.read(start, 4) == b'\0' * 4)
        meta = self.boxes(start + 4, stop, {b'hdlr', b'ilst'})
        handler = self.payload(self.one(meta, b'hdlr'))
        require(len(handler) >= 24 and handler[:8] == b'\0' * 8 and handler[8:12] == b'mdir')
        if b'ilst' in meta:
            tags = self.boxes(*self.one(meta, b'ilst'), {b'\xa9too', b'\xa9nam', b'\xa9ART', b'\xa9alb', b'\xa9cmt', b'\xa9day'})
            for entries in tags.values():
                data = self.boxes(*entries[0], {b'data'})
                raw = self.payload(self.one(data, b'data'))
                require(len(raw) >= 8 and raw[:4] == b'\0\0\0\1')

    def sample_entry(self, bounds, role):
        start, stop = bounds
        require(self.read(start, 8) == b'\0' * 4 + b'\0\0\0\1')
        entries = self.boxes(start + 8, stop, {b'avc1'} if role == 'video' else {b'mp4a'})
        kind = b'avc1' if role == 'video' else b'mp4a'
        begin, finish = self.one(entries, kind)
        width = 78 if role == 'video' else 28
        require(finish - begin >= width)
        header = self.read(begin, width)
        require(header[:6] == b'\0' * 6 and header[6:8] == b'\0\1')
        if role == 'audio':
            require(header[8:16] == b'\0' * 8)  # QuickTime audio versions/alternate layouts are excluded.
        children = self.boxes(begin + width, finish, {b'avcC', b'pasp', b'btrt'} if role == 'video' else {b'esds', b'btrt'})
        config = self.payload(self.one(children, b'avcC' if role == 'video' else b'esds'))
        if role == 'video':
            require(len(config) >= 7 and config[0] == 1)
        else:
            # ES_Descriptor optional URL/dependency flags are not part of this local AAC subset.
            require(len(config) >= 7 and config[:4] == b'\0' * 4 and config[4] == 3)
            es, end = descriptor(config, 4, 3)
            require(end == len(config) and len(es) >= 3 and es[2] == 0)
            decoder, end = descriptor(es, 3, 4)
            require(len(decoder) >= 15 and decoder[:2] == b'\x40\x15')
            audio, last = descriptor(decoder, 13, 5)
            require(last == len(decoder) and 2 <= len(audio) <= 64 and audio[0] >> 3 == 2)
            frequency = ((audio[0] & 7) << 1) | (audio[1] >> 7)
            channels = (audio[1] >> 3) & 15
            require(frequency < 13 and 1 <= channels <= 7)
            sl, last = descriptor(es, end, 6)
            require(last == len(es) and sl == b'\2')
        for key in (b'pasp', b'btrt'):
            if key in children:
                require(children[key][0][1] - children[key][0][0] == (8 if key == b'pasp' else 12))
        return 'h264' if role == 'video' else 'aac'

    def track(self, bounds, mdats):
        track = self.boxes(*bounds, {b'tkhd', b'edts', b'mdia'})
        tkhd = self.payload(self.one(track, b'tkhd'))
        require(len(tkhd) in (84, 96) and tkhd[0] in (0, 1))
        if b'edts' in track:
            edits = self.boxes(*self.one(track, b'edts'), {b'elst'})
            self.table(edits, b'elst', 3)
        media = self.boxes(*self.one(track, b'mdia'), {b'mdhd', b'hdlr', b'minf'})
        mdhd = self.payload(self.one(media, b'mdhd'))
        require(len(mdhd) in (24, 36) and mdhd[0] in (0, 1))
        handler = self.payload(self.one(media, b'hdlr'))
        require(len(handler) >= 24 and handler[:8] == b'\0' * 8 and handler[8:12] in (b'vide', b'soun'))
        role = 'video' if handler[8:12] == b'vide' else 'audio'
        info = self.boxes(*self.one(media, b'minf'), {b'vmhd' if role == 'video' else b'smhd', b'dinf', b'stbl'})
        header = self.payload(self.one(info, b'vmhd' if role == 'video' else b'smhd'))
        require(header == (b'\0\0\0\1' + b'\0' * 8 if role == 'video' else b'\0' * 8))
        refs = self.boxes(*self.one(info, b'dinf'), {b'dref'})
        # A single self-contained url box, including its exact full-box flags; no URL/path payload.
        require(self.payload(self.one(refs, b'dref')) == b'\0\0\0\0\0\0\0\1\0\0\0\x0curl \0\0\0\1')
        samples = self.boxes(*self.one(info, b'stbl'),
                             {b'stsd', b'stts', b'stsc', b'stsz', b'stco', b'co64', b'stss', b'ctts', b'sgpd', b'sbgp'})
        codec = self.sample_entry(self.one(samples, b'stsd'), role)
        raw = self.payload(self.one(samples, b'stsz'))
        require(len(raw) >= 12 and raw[:4] == b'\0' * 4)
        fixed, count = struct.unpack_from('>II', raw, 4)
        require(0 < count <= SAMPLE_LIMIT and len(raw) == 12 + (0 if fixed else count * 4))
        sizes = [fixed] * count if fixed else [v[0] for v in struct.iter_unpack('>I', raw[12:])]
        require(all(sizes))
        times = self.table(samples, b'stts', 2)
        require(sum(v[0] for v in times) == count and all(a > 0 and b > 0 for a, b in times))
        if b'ctts' in samples:
            require(sum(v[0] for v in self.table(samples, b'ctts', 2)) == count)
        sync = [v[0] for v in self.table(samples, b'stss', 1, optional=True)]
        require(sync == sorted(set(sync)) and all(1 <= v <= count for v in sync))
        require((b'stco' in samples) != (b'co64' in samples))
        if b'stco' in samples:
            offsets = [v[0] for v in self.table(samples, b'stco', 1)]
        else:
            raw = self.payload(self.one(samples, b'co64'))
            require(len(raw) >= 8 and raw[:4] == b'\0' * 4)
            require(len(raw) == 8 + int.from_bytes(raw[4:8], 'big') * 8)
            offsets = [v[0] for v in struct.iter_unpack('>Q', raw[8:])]
        chunks = self.table(samples, b'stsc', 3)
        require(chunks and chunks[0][0] == 1 and chunks[-1][0] <= len(offsets))
        require(all(a < b for a, b in zip([v[0] for v in chunks], [v[0] for v in chunks][1:])))
        require(all(a > 0 and b > 0 and c == 1 for a, b, c in chunks))
        sample_index = chunk_index = 0
        for i, offset in enumerate(offsets, 1):
            self.checkpoint()
            if chunk_index + 1 < len(chunks) and i == chunks[chunk_index + 1][0]:
                chunk_index += 1
            end_index = sample_index + chunks[chunk_index][1]
            require(end_index <= count)
            length = sum(sizes[sample_index:end_index])
            require(any(begin <= offset and offset + length <= finish for begin, finish in mdats))
            sample_index = end_index
        require(sample_index == count)
        if b'sgpd' in samples or b'sbgp' in samples:
            # Only AAC roll-recovery grouping, never encryption or external dependencies.
            require(role == 'audio')
            sgpd = self.payload(self.one(samples, b'sgpd'))
            require(sgpd == b'\1\0\0\0roll\0\0\0\2\0\0\0\1\xff\xff')
            sbgp = self.payload(self.one(samples, b'sbgp'))
            require(len(sbgp) >= 12 and sbgp[:8] == b'\0' * 4 + b'roll')
            require(len(sbgp) == 12 + int.from_bytes(sbgp[8:12], 'big') * 8)
            groups = list(struct.iter_unpack('>II', sbgp[12:]))
            require(sum(n for n, _ in groups) == count and all(n > 0 and group <= 1 for n, group in groups))
        return {'role': role, 'declared_codec': codec}

    def inspect(self, mime):
        top = self.boxes(0, self.size, {b'ftyp', b'moov', b'mdat', b'free'}, {b'mdat', b'free'})
        brand = self.payload(self.one(top, b'ftyp'))
        require(len(brand) >= 8 and len(brand) % 4 == 0)
        brands = [brand[:4], *[brand[i:i + 4] for i in range(8, len(brand), 4)]]
        require(all(v in {b'isom', b'iso2', b'avc1', b'mp41', b'mp42', b'M4A '} for v in brands))
        require(b'mdat' in top and sum(b - a for a, b in top[b'mdat']) > 0)
        movie = self.boxes(*self.one(top, b'moov'), {b'mvhd', b'trak', b'udta'}, {b'trak'})
        header = self.payload(self.one(movie, b'mvhd'))
        require(len(header) in (100, 112) and header[0] in (0, 1))
        require(1 <= len(movie.get(b'trak', [])) <= 2)
        streams = [self.track(bounds, top[b'mdat']) for bounds in movie[b'trak']]
        roles = [stream['role'] for stream in streams]
        require(len(set(roles)) == len(roles) and (mime != 'audio/mp4' or roles == ['audio']))
        if b'udta' in movie:
            self.metadata(self.one(movie, b'udta'))
        return streams


def inspect_media_input(root, relative, size, sha256, mime, checkpoint=lambda: None):
    """Only a server-selected managed path; no write, network, subprocess or grant creation."""
    try:
        # Inspect the supplied root before resource_path resolves it, so a junction is not trusted away.
        path = root / relative
        require(path.is_absolute() and not str(path).startswith(('\\\\', '//')) and ':' not in str(path)[3:])
        if os.name == 'nt':
            import ctypes
            require(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) != 4)
        for component in [*reversed(path.parents), path]:
            info = component.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        path = resource_path(root, relative)
        if not 0 < size <= INPUT_LIMIT:
            raise HTTPException(413, '本地媒体预检最多512MiB，原文件保留')
        require(mime in ('video/mp4', 'audio/mp4'))
        deadline = time.monotonic() + 30
        with path.open('rb') as handle:
            before = os.fstat(handle.fileno())
            named_before = path.stat()
            require(stat.S_ISREG(before.st_mode))
            if before.st_size != size:
                raise HTTPException(409, '媒体已改变，原文件保留；请刷新后重新选择')
            policy = MP4Input(handle, size, deadline, checkpoint)
            checksum = hashlib.sha256()
            for _ in range((size + 1048575) // 1048576):
                policy.checkpoint()
                chunk = handle.read(min(1048576, size - handle.tell()))
                checksum.update(chunk)
            if handle.tell() != size or checksum.hexdigest() != sha256:
                raise HTTPException(409, '媒体校验失败，原文件保留；请刷新后重新选择')
            streams = policy.inspect(mime)
            after, current = os.fstat(handle.fileno()), path.stat()
            def identity(info):
                return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
            # Windows fstat/path.stat expose different ctime semantics; compare each API to itself.
            if (identity(before) != identity(after) or identity(before) != identity(current) or
                    before.st_ctime_ns != after.st_ctime_ns or named_before.st_ctime_ns != current.st_ctime_ns):
                raise HTTPException(409, '媒体在预检期间改变，结果已作废；原文件保留')
        return {'policy_version': POLICY_VERSION, 'container': 'mp4', 'streams': streams,
                'native_probe_performed': False, 'size': size, 'sha256': sha256}
    except OSError as error:
        raise HTTPException(409, '媒体文件不可读取，原文件保留') from error
