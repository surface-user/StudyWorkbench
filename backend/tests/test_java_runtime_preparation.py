import hashlib
import importlib
import io
import json
import stat
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

import pytest


@pytest.fixture
def java(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('prepare_java_runtime')


def fixture_files(java):
    files = {name: ('self-authored ' + name).encode() for name in java.REQUIRED}
    files['release'] = (b'IMPLEMENTOR="Eclipse Adoptium"\nSEMANTIC_VERSION="21.0.13+9"\n'
                        b'OS_NAME="Windows"\nOS_ARCH="x86_64"\nIMAGE_TYPE="JRE"\n')
    files['legal/java.base/extra.md'] = b'additional third party notice'
    files['lib/modules'] = b'fixture modules'
    return files


def make_zip(java, files, extra=()):
    data = io.BytesIO()
    with ZipFile(data, 'w') as archive:
        for name, content in files.items():
            archive.writestr(java.ARCHIVE_ROOT + '/' + name, content)
        for name in extra:
            if isinstance(name, str) and ('\\' in name or '\x00' in name):
                entry = ZipInfo('placeholder')
                entry.filename = name
                name = entry
            archive.writestr(name, b'extra')
    data.seek(0)
    return data


@pytest.fixture
def prepared(java, tmp_path, monkeypatch):
    files = fixture_files(java)
    raw = make_zip(java, files).getvalue()
    package = tmp_path / 'self-authored.zip'
    package.write_bytes(raw)
    monkeypatch.setattr(java, 'PACKAGE_SIZE', len(raw))
    monkeypatch.setattr(java, 'PACKAGE_SHA256', hashlib.sha256(raw).hexdigest())
    images = []

    def image(path, fast_load):
        assert fast_load
        state = {'path': path, 'closed': False}
        images.append(state)
        return SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=0x8664),
                               OPTIONAL_HEADER=SimpleNamespace(Magic=0x20B),
                               close=lambda: state.update(closed=True))
    monkeypatch.setattr(java.pefile, 'PE', image)
    return package, tmp_path / 'runtime', files, images


def test_complete_payload_and_notices_are_retained_in_locked_layout(java, prepared):
    package, target, files, images = prepared
    original = package.read_bytes()
    value = java.prepare(package, target)
    assert package.read_bytes() == original
    assert value['version'] == java.VERSION and value['source_url'] == java.SOURCE_URL
    assert value['package_sha256'] == hashlib.sha256(original).hexdigest()
    assert value['bytes'] == sum(map(len, files.values()))
    assert value['files'] == {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == {*files, java.LOCK_NAME}
    assert json.loads((target / java.LOCK_NAME).read_text()) == value
    assert len(images) == 3 and all(image['closed'] for image in images)
    java.verify_runtime(target, value['files'])


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/drive', 'bin/../escape', 'bin//empty',
                                 'bin\\escape', 'bin/NUL', 'bin/COM1.txt', 'bin/trailing.', 'bin/colon:ads',
                                 'bin/trailing ', 'bin/JAVA.exe', 'bin/name\x00tail', 'bin/dir//'])
def test_unsafe_or_case_colliding_entries_are_rejected(java, name):
    with ZipFile(make_zip(java, fixture_files(java), [java.ARCHIVE_ROOT + '/' + name])) as archive:
        with pytest.raises(ValueError):
            java.package_entries(archive)


@pytest.mark.parametrize('mode', [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFCHR | 0o600])
def test_special_entries_are_rejected(java, mode):
    info = ZipInfo(java.ARCHIVE_ROOT + '/bin/special')
    info.create_system = 3
    info.external_attr = mode << 16
    with ZipFile(make_zip(java, fixture_files(java), [info])) as archive:
        with pytest.raises(ValueError, match='special'):
            java.package_entries(archive)


@pytest.mark.parametrize('damage', ['missing_notice', 'file_parent', 'duplicate', 'wrong_root', 'lock', 'inventory'])
def test_incomplete_or_ambiguous_archives_are_rejected(java, damage):
    files = fixture_files(java)
    extra = []
    if damage == 'missing_notice':
        del files['NOTICE']
    elif damage == 'file_parent':
        files['bin'] = b'not a directory'
    elif damage == 'duplicate':
        extra = [java.ARCHIVE_ROOT + '/NOTICE']
    elif damage == 'wrong_root':
        extra = ['other/NOTICE']
    else:
        files[java.LOCK_NAME if damage == 'lock' else 'build-inventory.json'] = b'{}'
    with ZipFile(make_zip(java, files, extra)) as archive:
        with pytest.raises(ValueError):
            java.package_entries(archive)


@pytest.mark.parametrize('budget', ['MAX_BYTES', 'MAX_ENTRIES'])
def test_archive_budgets_are_enforced_before_writes(java, monkeypatch, budget):
    monkeypatch.setattr(java, budget, 1)
    with ZipFile(make_zip(java, fixture_files(java))) as archive:
        with pytest.raises(ValueError, match='budget'):
            java.package_entries(archive)


@pytest.mark.parametrize('damage', ['size', 'hash'])
def test_wrong_official_package_is_rejected_without_destination(java, prepared, damage):
    package, target, _, _ = prepared
    content = package.read_bytes()
    package.write_bytes(content + b'x' if damage == 'size' else b'x' + content[1:])
    with pytest.raises(ValueError, match='size/hash'):
        java.prepare(package, target)
    assert not target.exists()


def test_existing_destination_is_preserved(java, prepared):
    package, target, _, _ = prepared
    target.mkdir()
    (target / 'existing').write_bytes(b'preserve')
    with pytest.raises(ValueError, match='exists'):
        java.prepare(package, target)
    assert list(target.iterdir()) == [target / 'existing']
    assert (target / 'existing').read_bytes() == b'preserve'


def test_failed_validation_retains_files_without_success_lock(java, prepared, monkeypatch):
    package, target, files, images = prepared
    def fail(*args):
        raise ValueError('wrong architecture')
    monkeypatch.setattr(java, 'verify_runtime', fail)
    with pytest.raises(ValueError, match='architecture'):
        java.prepare(package, target)
    assert not (target / java.LOCK_NAME).exists()
    assert (target / 'NOTICE').read_bytes() == files['NOTICE']
    assert not images


@pytest.mark.parametrize('damage', ['extra', 'missing', 'hash', 'inventory', 'release', 'architecture'])
def test_runtime_revalidation_detects_changes(java, prepared, monkeypatch, damage):
    package, target, _, _ = prepared
    manifest = java.prepare(package, target)
    if damage == 'extra':
        (target / 'extra').write_text('extra')
    elif damage == 'missing':
        (target / 'NOTICE').unlink()
    elif damage == 'hash':
        (target / 'NOTICE').write_text('altered')
    elif damage == 'inventory':
        (target / 'build-inventory.json').write_text('{}')
    elif damage == 'release':
        (target / 'release').write_text('OS_ARCH="x86"')
        manifest['files']['release'] = hashlib.sha256((target / 'release').read_bytes()).hexdigest()
    else:
        monkeypatch.setattr(java.pefile, 'PE', lambda *args, **kwargs: SimpleNamespace(
            FILE_HEADER=SimpleNamespace(Machine=0x14C), OPTIONAL_HEADER=SimpleNamespace(Magic=0x10B), close=lambda: None))
    with pytest.raises(ValueError):
        java.verify_runtime(target, manifest['files'])


def test_reparse_parent_is_rejected_before_extraction(java, prepared, monkeypatch):
    package, target, _, _ = prepared
    original = Path.lstat
    def lstat(path):
        info = original(path)
        if path == target.parent:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ValueError, match='reparse'):
        java.prepare(package, target)
    assert not target.exists()
