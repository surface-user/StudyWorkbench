"""Self-authored source archives; no upstream configure or network runs here."""
import hashlib
import importlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest


@pytest.fixture
def component(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('prepare_ffmpeg_component')


def archive_bytes(component, files, extras=()):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:xz') as archive:
        for relative, data in files.items():
            info = tarfile.TarInfo(component.ARCHIVE_ROOT + '/' + relative)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        for info, data in extras:
            archive.addfile(info, io.BytesIO(data) if data else None)
    return output.getvalue()


def pinned_fixture(component, monkeypatch, tmp_path, files=None, extras=()):
    files = files if files is not None else {name: ('self-authored ' + name).encode() for name in component.REQUIRED}
    raw = archive_bytes(component, files, extras)
    package = tmp_path / 'source.tar.xz'
    package.write_bytes(raw)
    monkeypatch.setattr(component, 'PACKAGE_SIZE', len(raw))
    monkeypatch.setattr(component, 'PACKAGE_SHA256', hashlib.sha256(raw).hexdigest())
    git = {name: hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
           for name, data in files.items() if name in component.GIT_FILES}
    monkeypatch.setattr(component, 'GIT_FILES', git)
    return package, tmp_path / 'prepared', files


def test_pinned_source_preserves_every_original_and_hash_preimage(component, monkeypatch, tmp_path):
    package, target, files = pinned_fixture(component, monkeypatch, tmp_path)
    original = package.read_bytes()
    value = component.prepare_source(package, target)
    assert package.read_bytes() == original
    assert set(value) == {'payload', 'snapshot_sha256'} and 'snapshot_sha256' not in value['payload']
    assert value['snapshot_sha256'] == hashlib.sha256(component.canonical(value['payload'])).hexdigest()
    assert set(value['payload']['files']) == set(files)
    assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == {*files, component.SOURCE_LOCK}
    assert component.verify_source(package, target) == value
    assert {name: (target / name).read_bytes() for name in files} == files


def test_wrong_archive_rejected_before_parse_or_destination_creation(component, monkeypatch, tmp_path):
    package = tmp_path / 'unknown.tar.xz'
    package.write_bytes(b'not the authenticated source')
    monkeypatch.setattr(component.tarfile, 'open', lambda **_k: pytest.fail('Unknown archive parsed'))
    with pytest.raises(ValueError, match='archive size/hash'):
        component.prepare_source(package, tmp_path / 'new')
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('kind', ['traversal', 'absolute', 'wrong_root', 'case_collision', 'file_parent',
                                  'reserved', 'device_name', 'trailing_dot', 'backslash', 'symlink', 'hardlink', 'fifo'])
def test_unsafe_source_members_are_rejected_before_writing(component, monkeypatch, tmp_path, kind):
    root = component.ARCHIVE_ROOT + '/'
    names = {'traversal': root + '../escape', 'absolute': '/escape', 'wrong_root': 'wrong/Makefile',
             'case_collision': root + 'makefile', 'file_parent': root + 'Makefile/child',
             'reserved': root + component.SOURCE_LOCK, 'device_name': root + 'CON.txt',
             'trailing_dot': root + 'unsafe.', 'backslash': root + 'unsafe\\path'}
    info = tarfile.TarInfo(names.get(kind, root + 'linked'))
    data = b'bad'
    info.size = len(data)
    if kind in {'symlink', 'hardlink', 'fifo'}:
        info.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE, 'fifo': tarfile.FIFOTYPE}[kind]
        info.linkname, info.size, data = '../outside', 0, b''
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path, extras=[(info, data)])
    with pytest.raises(ValueError):
        component.prepare_source(package, target)
    assert not target.exists() and not (tmp_path / 'escape').exists()


@pytest.mark.parametrize('kind', ['license', 'member_size', 'total_size', 'count', 'git_association'])
def test_source_origin_legal_and_budgets_fail_closed(component, monkeypatch, tmp_path, kind):
    files = {name: b'owned fixture' for name in component.REQUIRED}
    if kind == 'license':
        files.pop('COPYING.LGPLv2.1')
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path, files)
    if kind == 'member_size':
        monkeypatch.setattr(component, 'MAX_MEMBER', 1)
    elif kind == 'total_size':
        monkeypatch.setattr(component, 'MAX_BYTES', 1)
    elif kind == 'count':
        monkeypatch.setattr(component, 'MAX_ENTRIES', 1)
    elif kind == 'git_association':
        monkeypatch.setitem(component.GIT_FILES, 'configure', '0' * 40)
    with pytest.raises(ValueError):
        component.prepare_source(package, target)
    if target.exists():
        assert not (target / component.SOURCE_LOCK).exists()


def test_existing_destination_and_its_bytes_are_preserved(component, monkeypatch, tmp_path):
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path)
    target.mkdir()
    (target / 'owned.txt').write_bytes(b'keep')
    with pytest.raises(ValueError, match='Destination exists'):
        component.prepare_source(package, target)
    assert (target / 'owned.txt').read_bytes() == b'keep'


@pytest.mark.parametrize('kind', ['file', 'extra', 'missing', 'rehash_forgery'])
def test_rehashed_or_changed_source_never_becomes_authenticated(component, monkeypatch, tmp_path, kind):
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path)
    value = component.prepare_source(package, target)
    if kind == 'extra':
        (target / 'extra.txt').write_bytes(b'extra')
    elif kind == 'missing':
        (target / 'Makefile').unlink()
    else:
        (target / 'Makefile').write_bytes(b'changed')
    if kind == 'rehash_forgery':
        value['payload']['files']['Makefile']['size'] = 7
        value['payload']['files']['Makefile']['sha256'] = hashlib.sha256(b'changed').hexdigest()
        (target / component.SOURCE_LOCK).write_text(json.dumps(component.envelope(value['payload'])), encoding='utf-8')
    with pytest.raises(ValueError):
        component.verify_source(package, target)


def test_snapshot_rejects_duplicate_nonfinite_and_self_including_preimage(component, tmp_path):
    with pytest.raises(ValueError, match='own preimage'):
        component.envelope({'snapshot_sha256': '0' * 64})
    for raw in [b'{"payload":{},"payload":{},"snapshot_sha256":"x"}',
                b'{"payload":{"x":NaN},"snapshot_sha256":"x"}']:
        path = tmp_path / 'snapshot.json'
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            component.read_snapshot(path)


def test_source_or_snapshot_links_are_not_followed(component, monkeypatch, tmp_path):
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path)
    component.prepare_source(package, target)
    outside = tmp_path / 'outside.json'
    outside.write_bytes(b'outside original')
    (target / component.SOURCE_LOCK).unlink()
    try:
        (target / component.SOURCE_LOCK).symlink_to(outside)
    except OSError as error:
        if os.name == 'nt' and error.winerror == 1314:
            pytest.skip('This user lacks file-symlink privilege; real directory reparse case runs separately')
        raise
    with pytest.raises(ValueError, match='links/reparse'):
        component.verify_source(package, target)
    assert outside.read_bytes() == b'outside original'


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction guard')
def test_real_directory_reparse_point_is_rejected(component, monkeypatch, tmp_path):
    package, target, _ = pinned_fixture(component, monkeypatch, tmp_path)
    component.prepare_source(package, target)
    alias = tmp_path / 'alias'
    quoted_alias = str(alias).replace("'", "''")
    quoted_target = str(target).replace("'", "''")
    command = f"New-Item -ItemType Junction -Path '{quoted_alias}' -Target '{quoted_target}' | Out-Null"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError, match='links/reparse'):
        component.verify_source(package, alias)
    assert (target / component.SOURCE_LOCK).is_file()
