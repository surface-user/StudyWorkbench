import hashlib
import io
import os
import struct
import subprocess

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from study_workbench import document_files, media_inputs
from study_workbench.db import MediaEntry
from study_workbench.media_inputs import MP4Input, inspect_media_input
from test_imports import SCOPE, client


def box(kind, payload=b''):
    return struct.pack('>I4s', len(payload) + 8, kind) + payload


def mp4(role='video', *, dref=None, sample_entry=None, extra=b'', sample_count=1):
    """Hand-built structural fixture, with deliberately non-decodable sample bytes."""
    ftyp = box(b'ftyp', b'isom\0\0\0\0isom')
    mdat = box(b'mdat', b'\0' * 4)
    if sample_entry is None:
        if role == 'video':
            sample_entry = box(b'avc1', b'\0' * 6 + b'\0\1' + b'\0' * 70 + box(b'avcC', b'\1' + b'\0' * 6))
        else:
            audio = b'\x05\2\x11\x88'
            decoder = b'\x04' + bytes([13 + len(audio)]) + b'\x40\x15' + b'\0' * 11 + audio
            es = b'\0\1\0' + decoder + b'\x06\1\2'
            esds = b'\0' * 4 + b'\x03' + bytes([len(es)]) + es
            sample_entry = box(b'mp4a', b'\0' * 6 + b'\0\1' + b'\0' * 20 + box(b'esds', esds))
    tables = box(b'stsd', b'\0\0\0\0\0\0\0\1' + sample_entry)
    tables += box(b'stts', struct.pack('>IIII', 0, 1, sample_count, 1))
    tables += box(b'stsc', struct.pack('>IIIII', 0, 1, 1, sample_count, 1))
    tables += box(b'stsz', struct.pack('>III', 0, 4, sample_count))
    tables += box(b'stco', struct.pack('>III', 0, 1, len(ftyp) + 8))
    tables += extra
    reference = box(b'url ', b'\0\0\0\1') if dref is None else dref
    dinf = box(b'dinf', box(b'dref', b'\0\0\0\0\0\0\0\1' + reference))
    header = box(b'vmhd', b'\0\0\0\1' + b'\0' * 8) if role == 'video' else box(b'smhd', b'\0' * 8)
    minf = box(b'minf', header + dinf + box(b'stbl', tables))
    hdlr = box(b'hdlr', b'\0' * 8 + (b'vide' if role == 'video' else b'soun') + b'\0' * 12)
    mdia = box(b'mdia', box(b'mdhd', b'\0' * 24) + hdlr + minf)
    track = box(b'trak', box(b'tkhd', b'\0' * 84) + mdia)
    return ftyp + mdat + box(b'moov', box(b'mvhd', b'\0' * 100) + track)


def inspect_bytes(tmp_path, data, mime='video/mp4'):
    path = tmp_path / 'input.mp4'
    path.write_bytes(data)
    return inspect_media_input(tmp_path, 'input.mp4', len(data), hashlib.sha256(data).hexdigest(), mime)


@pytest.mark.parametrize('role,mime,codec', [('video', 'video/mp4', 'h264'), ('audio', 'audio/mp4', 'aac')])
def test_declared_structure_only_and_original_retained(tmp_path, role, mime, codec):
    data = mp4(role)
    result = inspect_bytes(tmp_path, data, mime)
    assert result == {'policy_version': 'local-mp4-input-v1', 'container': 'mp4',
                      'streams': [{'role': role, 'declared_codec': codec}],
                      'native_probe_performed': False, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    assert (tmp_path / 'input.mp4').read_bytes() == data


@pytest.mark.parametrize('reference', [
    box(b'url ', b'\0' * 4 + b'https://example.invalid/a\0'),
    box(b'url ', b'\0' * 4 + b'\\\\server\\share\\a\0'),
    box(b'url ', b'\0' * 4 + b'../secret\0'),
    box(b'url ', b'\0\0\0\1' + b'ignored-extra'),
    box(b'urn ', b'\0' * 4), box(b'alis', b'\0' * 160),
    box(b'url ', b'\0\0\0\1') * 2,
])
def test_external_or_ambiguous_data_references_rejected(tmp_path, reference):
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, mp4(dref=reference))
    assert caught.value.status_code == 422


@pytest.mark.parametrize('extra', [b'moof', b'mvex', b'sinf', b'schi', b'tenc', b'pssh', b'uuid', b'rmra', b'rdrf', b'cmov'])
def test_unsupported_fragment_encryption_and_alternate_layouts_rejected(tmp_path, extra):
    data = mp4() + box(extra)
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, data)
    assert caught.value.status_code == 422 and (tmp_path / 'input.mp4').read_bytes() == data


@pytest.mark.parametrize('entry', [box(b'encv', b'\0' * 78), box(b'hvc1', b'\0' * 78),
                                  box(b'avc1', b'\0' * 6 + b'\0\2' + b'\0' * 70 + box(b'avcC', b'\1' * 7)),
                                  box(b'avc1', b'\0' * 6 + b'\0\1' + b'\0' * 70 + box(b'sinf'))])
def test_unsupported_codec_sample_reference_and_encrypted_sample_entry(tmp_path, entry):
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, mp4(sample_entry=entry))
    assert caught.value.status_code == 422


@pytest.mark.parametrize('transform', [
    lambda data: data[:-1],
    lambda data: b'\0\0\0\0' + data[4:],
    lambda data: b'\0\0\0\1' + data[4:],
    lambda data: data.replace(b'isom', b'qt  '),
    lambda data: data.replace(b'stco\0\0\0\0\0\0\0\1', b'stco\0\0\0\0\xff\xff\xff\xff'),
    lambda data: data.replace(b'stco\0\0\0\0\0\0\0\1\0\0\0\x1c', b'stco\0\0\0\0\0\0\0\1\0\0\0\1'),
    lambda data: data + box(b'ftyp', b'isom\0\0\0\0'),
    lambda data: data + b'garbage',
])
def test_bad_bounds_duplicate_brands_and_sample_tables(tmp_path, transform):
    data = mp4()
    changed = transform(data)
    assert changed != data
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, changed)
    assert caught.value.status_code == 422


def test_sample_count_track_role_and_metadata_limits(tmp_path, monkeypatch):
    for data, mime in [(mp4(sample_count=2), 'video/mp4'), (mp4(), 'audio/mp4'),
                       (mp4(extra=box(b'stsd')), 'video/mp4'), (mp4(extra=box(b'sgpd')), 'video/mp4')]:
        with pytest.raises(HTTPException) as caught:
            inspect_bytes(tmp_path, data, mime)
        assert caught.value.status_code == 422
    monkeypatch.setattr(media_inputs, 'METADATA_LIMIT', 16)
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, mp4())
    assert caught.value.status_code == 413


def test_box_count_time_and_input_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(media_inputs, 'BOX_LIMIT', 1)
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, mp4())
    assert caught.value.status_code == 413
    with pytest.raises(HTTPException) as caught:
        MP4Input(io.BytesIO(mp4()), len(mp4()), 0).inspect('video/mp4')
    assert caught.value.status_code == 413
    monkeypatch.setattr(media_inputs, 'INPUT_LIMIT', 1)
    with pytest.raises(HTTPException) as caught:
        inspect_bytes(tmp_path, mp4())
    assert caught.value.status_code == 413


def test_hash_size_change_and_source_replacement_rejected(tmp_path, monkeypatch):
    data = mp4()
    path = tmp_path / 'input.mp4'
    path.write_bytes(data)
    for size, sha in [(len(data) - 1, hashlib.sha256(data).hexdigest()), (len(data), '0' * 64)]:
        with pytest.raises(HTTPException) as caught:
            inspect_media_input(tmp_path, 'input.mp4', size, sha, 'video/mp4')
        assert caught.value.status_code == 409
    original = MP4Input.inspect
    def replace_source(self, mime):
        result = original(self, mime)
        other = tmp_path / 'replacement.mp4'
        other.write_bytes(data)
        os.replace(other, path)
        return result
    monkeypatch.setattr(MP4Input, 'inspect', replace_source)
    with pytest.raises(HTTPException) as caught:
        inspect_media_input(tmp_path, 'input.mp4', len(data), hashlib.sha256(data).hexdigest(), 'video/mp4')
    assert caught.value.status_code == 409 and path.read_bytes() == data


def test_input_preview_identity_auth_strict_body_readonly_and_busy(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        data = mp4()
        item = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=data).json()
        route = f"{SCOPE}/media/{item['id']}/input-preview"
        body = {'expected_sha256': item['sha256']}
        assert c.post(route, json=body).json()['media_id'] == item['id']
        for invalid in [{}, {'expected_sha256': 1}, {'expected_sha256': 'A' * 64},
                        {**body, 'path': 'C:/arbitrary.mp4'}, {**body, 'headers': {}}]:
            assert c.post(route, json=invalid).status_code == 422
        assert c.post(route, json={'expected_sha256': '0' * 64}).status_code == 409
        assert c.post(route, json=body, headers={'Authorization': 'bad'}).status_code == 401
        assert c.post(route, json=body, headers={'Origin': 'https://example.invalid'}).status_code == 403
        other = c.post('/api/workspaces', json={'name': '隔离预检'}).json()['id']
        assert c.post(f"/api/workspaces/{other}/media/{item['id']}/input-preview", json=body).status_code == 404
        slots = document_files.VIEW_SLOTS
        assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
        try:
            assert c.post(route, json=body).status_code == 429
        finally:
            slots.release()
            slots.release()
        assert c.post(route, json=body).status_code == 200
        assert c.get(f'{SCOPE}/media').json() == [item]
        with Session(c.app.state.engine) as session, session.begin():
            saved = session.get(MediaEntry, item['id'])
            saved.status = 'failed'
        assert c.post(route, json=body).status_code == 409
        assert (tmp_path / f"workspaces/default/media/{item['id']}.mp4").read_bytes() == data


def test_webm_magic_import_compatibility_not_native_policy_acceptance(tmp_path):
    with client(tmp_path) as c:
        data = b'\x1aE\xdf\xa3' + b'\0' * 20
        item = c.post(f'{SCOPE}/media/import?filename=old.webm', content=data).json()
        assert item['status'] == 'ready'
        response = c.post(f"{SCOPE}/media/{item['id']}/input-preview", json={'expected_sha256': item['sha256']})
        assert response.status_code == 422
        assert 'input.mp4' not in response.text and 'example.invalid' not in response.text


def test_aac_url_flags_and_wrong_object_type_are_not_aac_declarations(tmp_path):
    data = mp4('audio')
    flags_offset = data.index(b'esds') + 12
    flagged = data[:flags_offset] + b'\x40' + data[flags_offset + 1:]
    for changed in [flagged,
                    data.replace(b'\x40\x15', b'\x66\x15'),
                    data.replace(b'\x05\2\x11\x88', b'\x05\2\xf9\x88')]:
        assert changed != data
        with pytest.raises(HTTPException) as caught:
            inspect_bytes(tmp_path, changed, 'audio/mp4')
        assert caught.value.status_code == 422


def test_noncanonical_and_cross_workspace_database_paths_are_not_sources(tmp_path):
    with client(tmp_path) as c:
        item = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=mp4()).json()
        for relative in [f"workspaces/other/media/{item['id']}.mp4", '../outside.mp4',
                         f"workspaces/default/media/./{item['id']}.mp4", 'workspaces/default/originals/file.mp4']:
            with Session(c.app.state.engine) as session, session.begin():
                session.get(MediaEntry, item['id']).relative_path = relative
            response = c.post(f"{SCOPE}/media/{item['id']}/input-preview", json={'expected_sha256': item['sha256']})
            assert response.status_code == 409
            assert relative not in response.text


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows junction boundary')
def test_real_managed_root_junction_is_rejected_without_touching_original(tmp_path):
    source, alias = tmp_path / 'real', tmp_path / 'alias'
    source.mkdir()
    data = mp4()
    (source / 'input.mp4').write_bytes(data)
    quoted_source, quoted_alias = str(source).replace("'", "''"), str(alias).replace("'", "''")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        f"New-Item -ItemType Junction -Path '{quoted_alias}' -Target '{quoted_source}' | Out-Null"],
        capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    with pytest.raises(HTTPException) as caught:
        inspect_media_input(alias, 'input.mp4', len(data), hashlib.sha256(data).hexdigest(), 'video/mp4')
    assert caught.value.status_code in (409, 422)
    assert (source / 'input.mp4').read_bytes() == data
