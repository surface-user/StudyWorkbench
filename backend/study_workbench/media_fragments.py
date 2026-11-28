"""Bounded, single-track fragmented ISO BMFF with self-contained initialization and media data."""

import struct
from typing import NamedTuple

from fastapi import HTTPException

from .media_inputs import SAMPLE_LIMIT, require

BRANDS = {
    b"isom",
    b"iso2",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"avc1",
    b"dash",
    b"msdh",
    b"msix",
    b"M4A ",
}


def brands(raw):
    require(len(raw) >= 8 and len(raw) % 4 == 0 and raw[:4] in BRANDS)
    require(all(raw[i : i + 4] in BRANDS for i in range(8, len(raw), 4)))


def defaults(policy, bounds, track_id, inherited):
    data = policy.payload(bounds)
    require(len(data) >= 8)
    flags, tid = struct.unpack_from(">II", data)
    require(tid == track_id and flags & 0x020000 and not flags & ~0x02003A)
    mask = [bit for bit in (0x02, 0x08, 0x10, 0x20) if flags & bit]
    require(len(data) == 8 + len(mask) * 4)
    fields = dict(zip(mask, struct.unpack_from(">" + "I" * len(mask), data, 8), strict=True))
    require(fields.get(0x02, 1) == 1)
    return fields.get(0x08, inherited[0]), fields.get(0x10, inherited[1])


class Segment(NamedTuple):
    begin: int
    end: int
    first_pts: int
    earliest_pts: int
    presentation_end: int


def fragment_run(policy, bounds, relative_data, data_size, inherited, available_samples, decode_start):
    raw = policy.payload(bounds)
    require(len(raw) >= 12)
    version_flags, count, offset = struct.unpack_from(">IIi", raw)
    version, flags = divmod(version_flags, 1 << 24)
    require(version in (0, 1) and flags & 1 and not flags & ~0xF05 and not (flags & 4 and flags & 0x400))
    require(count > 0 and offset == relative_data)
    if count > available_samples:
        raise HTTPException(413, "分片轨道样本总数超过预算，原件保留")
    start = 12 + (4 if flags & 4 else 0)
    columns = [bit for bit in (0x100, 0x200, 0x400, 0x800) if flags & bit]
    width = len(columns)
    require(len(raw) == start + count * width * 4)
    default_duration, default_size = inherited
    if not (flags & 0xB00):  # Only optional sample flags, no size, duration or timestamp overrides.
        require(default_duration > 0 and default_size > 0 and default_size * count == data_size)
        end = decode_start + default_duration * count
        return end, count, (decode_start, decode_start, end)
    fields = {bit: i for i, bit in enumerate(columns)}
    layout = ">" + "".join("i" if bit == 0x800 and version == 1 else "I" for bit in columns)
    dts, used_bytes = decode_start, 0
    for i, row in enumerate(struct.iter_unpack(layout, memoryview(raw)[start:])):
        if i % 1024 == 0:
            policy.checkpoint()
        duration = row[fields[0x100]] if 0x100 in fields else default_duration
        size = row[fields[0x200]] if 0x200 in fields else default_size
        require(duration > 0 and size > 0)
        pts = dts + (row[fields[0x800]] if 0x800 in fields else 0)
        if i == 0:
            first_pts = earliest = pts
            presentation_end = pts + duration
        else:
            earliest = min(earliest, pts)
            presentation_end = max(presentation_end, pts + duration)
        dts += duration
        used_bytes += size
    require(used_bytes == data_size)
    return dts, count, (first_pts, earliest, presentation_end)


def index_segments(policy, bounds, segments, track_id, timescale):
    raw = policy.payload(bounds)
    require(len(raw) >= 24)
    vf, tid, scale = struct.unpack_from(">III", raw)
    require(vf in (0, 1 << 24) and tid == track_id and scale == timescale)
    layout = ">II" if vf == 0 else ">QQ"
    start = 12 + struct.calcsize(layout)
    require(len(raw) >= start + 4)
    earliest, skip = struct.unpack_from(layout, raw, 12)
    reserved, count = struct.unpack_from(">HH", raw, start)
    first = segments[0]
    # FFmpeg's global sidx can use a presentation timeline relative to the first packet.
    relative_origin = earliest == 0 and first.earliest_pts == first.first_pts and first.first_pts > 0
    require((earliest == first.earliest_pts or relative_origin) and skip == 0 and bounds[1] == first.begin)
    require(reserved == 0 and count == len(segments) and len(raw) == start + 4 + count * 12)
    for i, segment in enumerate(segments):
        size, ticks, _ = struct.unpack_from(">III", raw, start + 4 + 12 * i)
        next_time = segments[i + 1].earliest_pts if i + 1 < count else segment.presentation_end
        require(size == segment.end - segment.begin and ticks == next_time - segment.earliest_pts and ticks > 0)


def index_random_access(policy, box, segments, track_id):
    _, begin, payload, end = box
    entries = policy.boxes(payload, end, {b"tfra", b"mfro"})
    raw = policy.payload(policy.one(entries, b"tfra"))
    require(len(raw) >= 16)
    vf, tid, lengths, count = struct.unpack_from(">IIII", raw)
    require(vf in (0, 1 << 24) and tid == track_id and lengths == 0 and 0 < count <= len(segments))
    layout = ">IIBBB" if vf == 0 else ">QQBBB"
    width = struct.calcsize(layout)
    require(len(raw) == 16 + count * width)
    known = {segment.begin: segment.first_pts for segment in segments}
    previous = -1
    for i in range(count):
        ticks, offset, traf, trun, sample = struct.unpack_from(layout, raw, 16 + i * width)
        require(known.get(offset) == ticks and offset > previous and (traf, trun, sample) == (1, 1, 1))
        previous = offset
    require(policy.payload(policy.one(entries, b"mfro")) == struct.pack(">II", 0, end - begin))


def inspect_fragmented(policy, top, order, mime):
    require(len(order) >= 4 and [box[0] for box in order[:2]] == [b"ftyp", b"moov"])
    brands(policy.payload(policy.one(top, b"ftyp")))
    movie = policy.boxes(*policy.one(top, b"moov"), {b"mvhd", b"trak", b"mvex", b"udta"})
    header = policy.payload(policy.one(movie, b"mvhd"))
    require((len(header), header[:1]) in ((100, b"\0"), (112, b"\1")))
    require(struct.unpack_from(">I", header, 12 if header[0] == 0 else 20)[0] > 0)
    if b"udta" in movie:
        policy.metadata(policy.one(movie, b"udta"))
    stream, tkhd, mdhd, samples = policy.track_description(policy.one(movie, b"trak"), fragmented=True)
    require(mime != "audio/mp4" or stream["role"] == "audio")
    require((len(tkhd), tkhd[0]) in ((84, 0), (96, 1)) and (len(mdhd), mdhd[0]) in ((24, 0), (36, 1)))
    tid = struct.unpack_from(">I", tkhd, 12 if tkhd[0] == 0 else 20)[0]
    timescale = struct.unpack_from(">I", mdhd, 12 if mdhd[0] == 0 else 20)[0]
    require(tid > 0 and timescale > 0)
    require(set(samples) == {b"stsd", b"stts", b"stsc", b"stsz", b"stco"})
    for name in (b"stts", b"stsc", b"stsz", b"stco"):
        require(policy.payload(policy.one(samples, name)) == bytes(12 if name == b"stsz" else 8))
    mvex = policy.boxes(*policy.one(movie, b"mvex"), {b"trex"})
    trex = policy.payload(policy.one(mvex, b"trex"))
    require(len(trex) == 24)
    vf, track, description, duration, size, _ = struct.unpack(">6I", trex)
    require((vf, track, description) == (0, tid, 1))

    pos = 2
    if order[pos][0] == b"sidx":
        pos += 1
    segments = []
    count = ticks = 0
    while pos < len(order) and order[pos][0] in {b"styp", b"moof"}:
        start = order[pos][1]
        if order[pos][0] == b"styp":
            brands(policy.payload(order[pos][2:]))
            pos += 1
        require(pos + 1 < len(order))
        moof, mdat = order[pos : pos + 2]
        require(moof[0] == b"moof" and mdat[0] == b"mdat")
        content = policy.boxes(*moof[2:], {b"mfhd", b"traf"})
        require(policy.payload(policy.one(content, b"mfhd")) == struct.pack(">II", 0, 1 + len(segments)))
        traf = policy.boxes(*policy.one(content, b"traf"), {b"tfhd", b"tfdt", b"trun"})
        values = defaults(policy, policy.one(traf, b"tfhd"), tid, (duration, size))
        tfdt = policy.payload(policy.one(traf, b"tfdt"))
        require((len(tfdt), tfdt[:4]) in ((8, bytes(4)), (12, b"\1\0\0\0")))
        require(int.from_bytes(tfdt[4:], "big") == ticks)
        ticks, used, presentation = fragment_run(
            policy,
            policy.one(traf, b"trun"),
            mdat[2] - moof[1],
            mdat[3] - mdat[2],
            values,
            SAMPLE_LIMIT - count,
            ticks,
        )
        segments.append(Segment(moof[1], mdat[3], *presentation))
        # A single global index in this profile covers contiguous moof/mdat pairs only.
        require(b"sidx" not in top or start == moof[1])
        count += used
        require(ticks < 1 << 63)
        pos += 2
    require(segments)
    if b"sidx" in top:
        index_segments(policy, policy.one(top, b"sidx"), segments, tid, timescale)
    if pos < len(order) and order[pos][0] == b"mfra":
        index_random_access(policy, order[pos], segments, tid)
        pos += 1
    require(pos == len(order))
    return [stream]
