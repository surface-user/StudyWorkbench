"""Self-authored single-track fMP4 fixtures; all offsets are within these generated local files."""

import hashlib
import struct
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from study_workbench import media_fragments, media_inputs
from study_workbench.document_files import VIEW_SLOTS
from study_workbench.media_inputs import FRAGMENT_POLICY, inspect_media_input
from test_explorer import PREFIX, client, start
from test_media_inputs import box, mp4


def words(*values):
    return struct.pack(">" + "I" * len(values), *values)


def init(role):
    ordinary = mp4(role)
    offset = ordinary.index(b"stsd") - 4
    description = ordinary[offset : offset + int.from_bytes(ordinary[offset : offset + 4], "big")]
    samples = description + b"".join(box(name, bytes(8)) for name in [b"stts", b"stsc", b"stco"])
    samples += box(b"stsz", bytes(12))
    ref = box(b"dinf", box(b"dref", words(0, 1) + box(b"url ", words(1))))
    media_header = box(b"vmhd", words(1) + bytes(8)) if role == "video" else box(b"smhd", bytes(8))
    minf = box(b"minf", media_header + ref + box(b"stbl", samples))
    handler = box(b"hdlr", bytes(8) + (b"vide" if role == "video" else b"soun") + bytes(12))
    media = box(b"mdia", box(b"mdhd", bytes(12) + words(1000) + bytes(8)) + handler + minf)
    track = box(b"trak", box(b"tkhd", bytes(12) + words(1) + bytes(68)) + media)
    movie = (
        box(b"mvhd", bytes(12) + words(1000) + bytes(84))
        + track
        + box(b"mvex", box(b"trex", words(0, 1, 1, 10, 4, 0)))
    )
    return box(b"ftyp", b"iso5" + words(0) + b"iso6mp41") + box(b"moov", movie)


def fragment(seq, ticks):
    def metadata(offset):
        header = box(b"tfhd", words(0x020000, 1))
        time = box(b"tfdt", words(0, ticks))
        run = box(b"trun", words(1, 2, offset))
        return box(b"moof", box(b"mfhd", words(0, seq)) + box(b"traf", header + time + run))

    moof = metadata(len(metadata(0)) + 8)
    return moof + box(b"mdat", b"owned123")


def owned(role="video", *, indexed=True):
    prefix = init(role)
    first, second = fragment(1, 0), fragment(2, 20)
    if not indexed:
        return prefix + first + second
    references = b"".join(words(len(seg), 20, 0) for seg in (first, second))
    index = box(b"sidx", words(0, 1, 1000, 0, 0, 2) + references)
    begin = len(prefix) + len(index)
    entries = struct.pack(">IIBBB", 0, begin, 1, 1, 1) + struct.pack(
        ">IIBBB", 20, begin + len(first), 1, 1, 1
    )
    tfra = box(b"tfra", words(0, 1, 0, 2) + entries)
    mfra = box(b"mfra", tfra + box(b"mfro", words(0, 8 + len(tfra) + 16)))
    return prefix + index + first + second + mfra


def inspected(path, payload):
    path.write_bytes(payload)
    return inspect_media_input(
        path.parent, path.name, len(payload), hashlib.sha256(payload).hexdigest(), "video/mp4"
    )


@pytest.mark.parametrize("role,codec", [("video", "h264"), ("audio", "aac")])
@pytest.mark.parametrize("indexed", [False, True])
def test_self_contained_fragmented_track_with_or_without_indexes(tmp_path, role, codec, indexed):
    data = owned(role, indexed=indexed)
    path = tmp_path / "owned.m4s"
    result = inspected(path, data)
    assert result["policy_version"] == FRAGMENT_POLICY
    assert result["streams"] == [{"role": role, "declared_codec": codec}]
    assert not result["native_probe_performed"] and path.read_bytes() == data


@pytest.mark.parametrize(
    "target,position,value",
    [
        (b"tfhd", 4, 2),
        (b"tfhd", 0, 0),
        (b"trex", 8, 2),
        (b"trun", 8, 1),
        (b"trun", 4, 3),
        (b"trex", 16, 3),
        (b"tfdt", 4, 1),
        (b"mfhd", 4, 3),
        (b"sidx", 24, 2),
        (b"tfra", 20, 0),
        (b"mfro", 4, 1),
        (b"stsc", 4, 1),
    ],
)
def test_fragment_index_timing_or_extent_mismatch_keeps_original(tmp_path, target, position, value):
    data = bytearray(owned())
    struct.pack_into(">I", data, data.index(target) + 4 + position, value)
    path = tmp_path / "unchanged.m4s"
    with pytest.raises(HTTPException) as error:
        inspected(path, data)
    assert error.value.status_code == 422 and path.read_bytes() == data


@pytest.mark.parametrize(
    "data",
    [
        fragment(1, 0),
        init("video"),
        owned() + fragment(3, 40),
        owned().replace(b"tfdt", b"uuid"),
        owned().replace(b"url ", b"urn "),
    ],
)
def test_missing_init_or_unsupported_layout_is_rejected(tmp_path, data):
    with pytest.raises(HTTPException) as error:
        inspected(tmp_path / "unsupported.m4s", data)
    assert error.value.status_code == 422


def test_sample_budget_is_shared_across_fragments(tmp_path, monkeypatch):
    monkeypatch.setattr(media_fragments, "SAMPLE_LIMIT", 3)
    with pytest.raises(HTTPException) as error:
        inspected(tmp_path / "over.m4s", owned())
    assert error.value.status_code == 413


def test_import_and_explorer_classify_single_track_without_filename_guess(tmp_path):
    audio = owned("audio")
    source = tmp_path / "outside.m4s"
    source.write_bytes(audio)
    with client(tmp_path / "data") as api:
        for role in ("audio", "video"):
            data = owned(role)
            item = api.post(PREFIX + "/media/import?filename=segment.m4s", content=data).json()
            assert item["mime"] == role + "/mp4"
            preview = api.post(
                PREFIX + "/media/" + item["id"] + "/input-preview", json={"expected_sha256": item["sha256"]}
            )
            assert preview.status_code == 200 and preview.json()["policy_version"] == FRAGMENT_POLICY
            assert preview.json()["streams"][0]["role"] == role
        assert (
            api.post(PREFIX + "/media/import?filename=init-only.m4s", content=init("video")).status_code
            == 422
        )
        assert api.post(PREFIX + "/media/import?filename=regular.m4s", content=mp4()).status_code == 422
        copied = start(api, source)
        assert copied["status"] == "completed", copied
        assert source.read_bytes() == audio


@pytest.mark.parametrize("limit", ["BOX_LIMIT", "METADATA_LIMIT", "INPUT_LIMIT"])
def test_file_limits_preserve_fragmented_input(tmp_path, monkeypatch, limit):
    data = owned()
    path = tmp_path / "bounded.m4s"
    monkeypatch.setattr(media_inputs, limit, 8)
    with pytest.raises(HTTPException) as error:
        inspected(path, data)
    assert error.value.status_code == 413 and path.read_bytes() == data


def test_fragmented_file_hash_and_time_budget(tmp_path, monkeypatch):
    data = owned()
    path = tmp_path / "unchanged.m4s"
    path.write_bytes(data)
    with pytest.raises(HTTPException) as error:
        inspect_media_input(tmp_path, path.name, len(data), "0" * 64, "video/mp4")
    assert error.value.status_code == 409
    times = iter([0, 0, 31])
    monkeypatch.setattr(media_inputs, "time", SimpleNamespace(monotonic=lambda: next(times)))
    with pytest.raises(HTTPException) as error:
        inspected(path, data)
    assert error.value.status_code == 413 and path.read_bytes() == data


def test_fragment_import_shares_view_budget(tmp_path):
    with client(tmp_path / "data") as api, VIEW_SLOTS, VIEW_SLOTS:
        response = api.post(PREFIX + "/media/import?filename=local.m4s", content=owned("audio"))
        assert response.status_code == 429
        rows = api.get(PREFIX + "/media").json()
        assert len(rows) == 1 and rows[0]["status"] == "failed" and rows[0]["size"] == len(owned("audio"))
