import copy
import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from study_workbench import backup_archive as backup


def test_supported_schema_matches_real_migration_head():
    assert ScriptDirectory(str(Path(__file__).resolve().parents[1] / 'migrations')).get_current_head() == backup.SUPPORTED_SCHEMA


def manifest(payload=None):
    payload = payload or {'study.db': b'not-a-database: envelope-only fixture', 'workspaces/default/workfiles/note.md': '正文'.encode()}
    return dict(format='studyworkbench-backup', version=1, schema_revision='0014', app_version='0.1-test',
                created_at='2026-11-04T00:00:00+00:00',
                files=[dict(path=name, size=len(data), sha256=hashlib.sha256(data).hexdigest()) for name, data in payload.items()],
                tables={'alembic_version': {'rows': 1, 'sha256': 'a' * 64}}, excluded=['.study.lock']), payload


def pack(path, value=None, payload=None, *, compression=zipfile.ZIP_DEFLATED, extra=None):
    default, content = manifest(payload)
    with zipfile.ZipFile(path, 'w', compression=compression, allowZip64=True) as archive:
        archive.writestr('backup-manifest.json', json.dumps(default if value is None else value, ensure_ascii=False).encode())
        for name, data in content.items():
            archive.writestr('payload/' + name, data)
        if extra:
            for name, data in extra.items():
                archive.writestr(name, data)
    return path


@pytest.mark.parametrize('name', [
    '../escape', '/absolute', 'a//b', './a', 'a/../b', 'C:/data', '\\server\\share', 'a\\b',
    'a:stream', 'a/CON.txt', 'a/LPT1', 'COM¹.bin', 'NUL', 'CONOUT$', 'a.', 'a ', 'a\x00b',
    'a\nb', 'a\u202eb', 'e\u0301.txt', 'a/' + 'x' * 256, '', 'x' * 2049,
])
def test_windows_paths_are_rejected_before_extraction(name):
    with pytest.raises(ValueError):
        backup.archive_path(name)


def test_valid_zip64_read_only_inspection_and_cli_do_not_activate_data(tmp_path, monkeypatch):
    path = pack(tmp_path / 'plain.zip')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    value = backup.inspect_archive(path)
    assert value['schema_revision'] == '0014' and len(value['files']) == 2
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    monkeypatch.setattr(zipfile, 'ZIP64_LIMIT', 20)
    zip64 = pack(tmp_path / 'zip64.zip')
    assert b'PK\x06\x06' in zip64.read_bytes()
    assert backup.inspect_archive(zip64) == value
    result = subprocess.run([sys.executable, '-m', 'study_workbench', '--inspect-backup', str(path)],
                            cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
                                              'PYTHONIOENCODING': 'utf-8'},
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary['payload_integrity_verified'] is True
    assert summary['database_semantics_checked'] is False and summary['data_activated'] is False
    assert set(p.name for p in tmp_path.iterdir()) == {'plain.zip', 'zip64.zip'}


@pytest.mark.parametrize('field,value', [
    ('version', True), ('version', 2), ('schema_revision', '0017'), ('schema_revision', 14),
    ('format', 'other'), ('created_at', '2026-11-04T00:00:00'), ('created_at', '2026-11-04T08:00:00+08:00'),
    ('files', []), ('tables', {}), ('excluded', ['.study.lock', '.STUDY.LOCK']), ('excluded', ['study.db']),
])
def test_unknown_or_inconsistent_manifest_is_rejected(field, value):
    original, _ = manifest()
    original[field] = value
    with pytest.raises(ValueError):
        backup.manifest_bytes(json.dumps(original).encode())


def test_duplicate_json_keys_nan_size_hash_and_windows_collisions():
    for raw in [b'{"version":1,"version":1}', b'{"x":NaN}', b'\xff']:
        with pytest.raises(ValueError):
            backup.manifest_bytes(raw)
    original, _ = manifest()
    changes = [
        {'path': 'STUDY.DB', 'size': 0, 'sha256': 'a' * 64},
        {'path': 'study.db/child', 'size': 0, 'sha256': 'a' * 64},
        {'path': 'x', 'size': True, 'sha256': 'a' * 64},
        {'path': 'x', 'size': backup.FILE_LIMIT + 1, 'sha256': 'a' * 64},
        {'path': 'x', 'size': 0, 'sha256': 'A' * 64},
    ]
    for change in changes:
        value = copy.deepcopy(original)
        value['files'].append(change)
        with pytest.raises(ValueError):
            backup.manifest_bytes(json.dumps(value).encode())
    original['tables']['alembic_version']['rows'] = True
    with pytest.raises(ValueError):
        backup.manifest_bytes(json.dumps(original).encode())


@pytest.mark.parametrize('extra', [{'unexpected.txt': b'x'}, {'payload/../escape': b'x'}, {'payload/WORKSPACES': b'x'}])
def test_unlisted_payload_and_traversal_never_create_files(tmp_path, extra):
    path = pack(tmp_path / 'bad.zip', extra=extra)
    with pytest.raises(ValueError):
        backup.inspect_archive(path)
    assert list(tmp_path.iterdir()) == [path]


def test_payload_hash_crc_size_missing_and_compression_fail_closed(tmp_path):
    original, payload = manifest()
    wrong_hash = copy.deepcopy(original)
    wrong_hash['files'][0]['sha256'] = '0' * 64
    wrong_size = copy.deepcopy(original)
    wrong_size['files'][0]['size'] += 1
    for i, value in enumerate([wrong_hash, wrong_size]):
        with pytest.raises(ValueError):
            backup.inspect_archive(pack(tmp_path / f'bad{i}.zip', value, payload))
    with pytest.raises(ValueError):
        backup.inspect_archive(pack(tmp_path / 'missing.zip', original, {'study.db': payload['study.db']}))
    with pytest.raises(ValueError):
        backup.inspect_archive(pack(tmp_path / 'bzip.zip', compression=zipfile.ZIP_BZIP2))
    stored = pack(tmp_path / 'crc.zip', compression=zipfile.ZIP_STORED)
    with zipfile.ZipFile(stored) as archive:
        info = archive.getinfo('payload/study.db')
        offset = info.header_offset
    raw = bytearray(stored.read_bytes())
    name_len, extra_len = struct.unpack_from('<HH', raw, offset + 26)
    raw[offset + 30 + name_len + extra_len] ^= 1
    stored.write_bytes(raw)
    with pytest.raises(ValueError):
        backup.inspect_archive(stored)


@pytest.mark.parametrize('attribute', [(stat.S_IFLNK | 0o777) << 16, 0x400])
def test_symlink_and_reparse_attributes_are_rejected(tmp_path, attribute):
    path = pack(tmp_path / 'links.zip')
    with zipfile.ZipFile(path, 'a') as archive:
        info = zipfile.ZipInfo('payload/evil')
        info.external_attr = attribute
        archive.writestr(info, b'../outside')
    with pytest.raises(ValueError):
        backup.inspect_archive(path)


def test_duplicate_zip_entries_and_misleading_directory_counts_are_rejected(tmp_path, monkeypatch):
    path = pack(tmp_path / 'duplicates.zip')
    with pytest.warns(UserWarning), zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('payload/study.db', b'evil')
    with pytest.raises(ValueError):
        backup.inspect_archive(path)
    path = pack(tmp_path / 'counts.zip')
    raw = bytearray(path.read_bytes())
    end = raw.rfind(b'PK\x05\x06')
    struct.pack_into('<HH', raw, end + 8, 1, 1)
    path.write_bytes(raw)
    monkeypatch.setattr(backup, 'COUNT_LIMIT', 1)
    # Reject the real directory count before ZipFile can allocate per-entry objects.
    monkeypatch.setattr(zipfile, 'ZipFile', lambda *_: pytest.fail('unbounded ZIP parsing reached'))
    with pytest.raises(ValueError):
        backup.inspect_archive(path)


def test_metadata_and_actual_payload_budget_and_cancellation(tmp_path, monkeypatch):
    path = pack(tmp_path / 'limits.zip')
    monkeypatch.setattr(backup, 'DIRECTORY_LIMIT', 1)
    with pytest.raises(ValueError):
        backup.inspect_archive(path)
    monkeypatch.setattr(backup, 'DIRECTORY_LIMIT', 64 * 1024 * 1024)
    monkeypatch.setattr(backup, 'MANIFEST_LIMIT', 30)
    with pytest.raises(ValueError):
        backup.inspect_archive(path)
    monkeypatch.setattr(backup, 'MANIFEST_LIMIT', 32 * 1024 * 1024)
    monkeypatch.setattr(backup, 'TOTAL_LIMIT', 1)
    with pytest.raises(ValueError):
        backup.inspect_archive(path)
    monkeypatch.setattr(backup, 'TOTAL_LIMIT', 100 * 1024 ** 3)
    def cancel(stage):
        if stage == 'payload-hashing':
            raise RuntimeError('cancelled')
    with pytest.raises(ValueError):
        backup.inspect_archive(path, checkpoint=cancel)
    assert list(tmp_path.iterdir()) == [path]


def test_unknown_zip_metadata_is_not_reinterpreted_as_ntfs_or_unicode_paths(tmp_path):
    path = pack(tmp_path / 'extra.zip')
    with zipfile.ZipFile(path, 'a') as archive:
        info = zipfile.ZipInfo('payload/extra')
        info.extra = struct.pack('<HH', 0x000a, 0)
        archive.writestr(info, b'x')
    with pytest.raises(ValueError, match='ZIP64'):
        backup.inspect_archive(path)
