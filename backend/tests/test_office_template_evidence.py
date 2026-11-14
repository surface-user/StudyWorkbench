import importlib
import io
import json
import stat
import struct
import tarfile
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest


def inert_pe(name):
    """Self-authored PE headers and inert bytes; never a runnable launcher."""
    data = bytearray(1024)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', data, 132, 0x8664, 1, 0, 0, 0, 240, 0x22)
    struct.pack_into('<H', data, 152, 0x20B)
    struct.pack_into('<Q', data, 176, 0x140000000)
    struct.pack_into('<II', data, 184, 4096, 512)
    struct.pack_into('<II', data, 208, 8192, 512)
    struct.pack_into('<H', data, 220, 3)
    struct.pack_into('<I', data, 260, 16)
    data[392:397] = b'.text'
    struct.pack_into('<IIII', data, 400, 512, 4096, 512, 512)
    struct.pack_into('<I', data, 428, 0x60000020)
    marker = ('Self-authored inert resource: ' + name).encode()
    data[512:512 + len(marker)] = marker
    return bytes(data)


@pytest.fixture
def example(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('office_template_evidence')
    office, source, output = tmp_path / 'office', tmp_path / 'source.tar.xz', tmp_path / 'output'
    office.mkdir()
    package_files = {name: inert_pe(name) for name in tool.TEMPLATES}
    package_files.update({name: b'raise RuntimeError("self-authored source fixture must never execute")\n'
                          for name in tool.PRODUCERS})
    package_files['pip/__init__.py'] = b'raise RuntimeError("must not import package fixture")\n'
    package_files['pip/_internal/empty.py'] = b''
    package_files[tool.PATCH_PATH] = b'Self-authored patched resource path\n'
    package_files[tool.RENAMED] = b'Self-authored renamed text fixture\n'
    for name, data in package_files.items():
        path = office / tool.LIB / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    before = b'Self-authored original resource path\n'
    monkeypatch.setattr(tool, 'PATCH_HASHES', (tool.digest(before), tool.digest(package_files[tool.PATCH_PATH])))
    monkeypatch.setattr(tool, 'RENAMED_SHA256', tool.digest(package_files[tool.RENAMED]))
    profiles = {name: dict(value) for name, value in tool.WHEELS.items()}
    members = {}
    for name, profile in profiles.items():
        files = {path: data for path, data in package_files.items() if path.startswith(name + '/')}
        if name == 'setuptools':
            files[tool.PATCH_PATH] = before
            files[tool.ORIGINAL_NAME] = files.pop(tool.RENAMED)
        files[f"{name}-{profile['version']}.dist-info/METADATA"] = (
            f"Metadata-Version: 2.4\nName: {name}\nVersion: {profile['version']}\n").encode()
        members[name] = files

    def component():
        files = {p.relative_to(office).as_posix(): tool.digest(p.read_bytes())
                 for p in office.rglob('*') if p.is_file() and p.name != 'runtime-lock.json'}
        raw = json.dumps(dict(version='26.8.1', java=dict(version='21.0.13+9'), files=files)).encode()
        (office / 'runtime-lock.json').write_bytes(raw)
        monkeypatch.setattr(tool, 'COMPONENT_SHA256', tool.digest(raw))

    def archive(change=None, extra_tar=None, raw_change=None):
        with tarfile.open(source, 'w:xz') as tar:
            for name, files in members.items():
                buffer = io.BytesIO()
                with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as zipfile:
                    for path, data in files.items():
                        zipfile.writestr(path, data)
                    if change and name == 'pip':
                        change(zipfile)
                data = buffer.getvalue()
                if raw_change and name == 'pip':
                    data = raw_change(data)
                profiles[name]['sha256'] = tool.digest(data)
                info = tarfile.TarInfo(tool.TAR_ROOT + profiles[name]['path'])
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if extra_tar:
                if extra_tar.size:
                    # Malformed oversized declaration without allocating its claimed payload.
                    tar.fileobj.write(extra_tar.tobuf())
                else:
                    tar.addfile(extra_tar)
        monkeypatch.setattr(tool, 'WHEELS', profiles)
        monkeypatch.setattr(tool, 'PYTHON_SIZE', source.stat().st_size)
        monkeypatch.setattr(tool, 'PYTHON_SHA256', tool.digest(source.read_bytes()))

    component()
    archive()
    return SimpleNamespace(tool=tool, office=office, source=source, output=output,
                           component=component, archive=archive, members=members)


def test_matches_fixed_sources_patch_rename_and_template_conditions_without_exclusion(example):
    e = example
    before = {p: p.read_bytes() for p in e.office.rglob('*') if p.is_file()}
    report = e.tool.generate(e.office, e.source, e.output)
    assert set(report['packages']) == {'pip', 'setuptools'} and len(report['templates']) == 14
    assert len(report['producers']) == 2
    records = [item for package in report['packages'].values() for item in package['files']]
    assert {r['relation'] for r in records} == {'identical', 'fixed-libreoffice-patch', 'fixed-libreoffice-rename'}
    assert report['packages']['setuptools']['source_distribution_version'] == '79.0.1'
    assert report['runtime_classification'] == 'unclassified'
    assert not report['runtime_exclusion_verified'] and not report['product_release_ready']
    for name, item in report['templates'].items():
        assert not item['zip_archive'] and item['overlay_offset'] is None
        assert item['archive_trailer_absent'] if '/distlib/' in name else item['companion_absent']
    assert before == {p: p.read_bytes() for p in e.office.rglob('*') if p.is_file()}
    assert str(e.office) not in (e.output / 'report.json').read_text('utf-8')


@pytest.mark.parametrize('damage', ['source-bytes', 'component-lock', 'component-bytes', 'missing-template',
                                   'unexplained-change', 'wrong-patch', 'wrong-rename', 'source-metadata',
                                   'missing-producer'])
def test_changed_or_incomplete_source_members_fail_without_success_report(example, damage):
    e = example
    if damage == 'source-bytes':
        e.source.write_bytes(e.source.read_bytes() + b'changed')
    elif damage == 'component-lock':
        path = e.office / 'runtime-lock.json'
        path.write_bytes(path.read_bytes() + b' ')
    elif damage == 'component-bytes':
        (e.office / e.tool.LIB / 'pip/__init__.py').write_bytes(b'changed')
    elif damage in {'missing-template', 'missing-producer'}:
        names = e.tool.TEMPLATES if damage == 'missing-template' else e.tool.PRODUCERS
        (e.office / e.tool.LIB / next(iter(names))).unlink()
        e.component()
    elif damage in {'unexplained-change', 'wrong-patch', 'wrong-rename'}:
        name = {'unexplained-change': 'pip/__init__.py', 'wrong-patch': e.tool.PATCH_PATH,
                'wrong-rename': e.tool.RENAMED}[damage]
        (e.office / e.tool.LIB / name).write_bytes(b'changed')
        e.component()
    else:
        name = 'pip-26.2.1.dist-info/METADATA'
        e.members['pip'][name] = b'Name: pip\nVersion: unknown\n'
        e.archive()
    with pytest.raises((ValueError, KeyError)):
        e.tool.generate(e.office, e.source, e.output)
    assert not (e.output / 'report.json').exists()


@pytest.mark.parametrize('kind', ['duplicate', 'traversal', 'normalized-nul', 'symlink', 'budget'])
def test_unsafe_wheel_members_are_rejected_before_correspondence(example, kind):
    e = example

    def change(archive):
        name = {'duplicate': 'pip/__init__.py', 'traversal': '../outside', 'normalized-nul': 'badXname',
                'symlink': 'pip/link', 'budget': 'pip/large'}[kind]
        info = ZipInfo(name)
        if kind == 'symlink':
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b'x' * (e.tool.MAX_MEMBER + 1) if kind == 'budget' else b'self-authored extra')

    # ZipInfo normalizes NUL on construction; alter both encoded filename headers instead.
    e.archive(change=change, raw_change=(lambda data: data.replace(b'badXname', b'bad\0name'))
              if kind == 'normalized-nul' else None)
    with pytest.raises(ValueError):
        e.tool.generate(e.office, e.source, e.output)
    assert not (e.output / 'report.json').exists()


@pytest.mark.parametrize('kind', ['link', 'duplicate', 'traversal', 'budget'])
def test_tar_links_duplicates_and_unsafe_names_are_rejected_without_extracting(example, kind):
    e = example
    info = tarfile.TarInfo({'link': 'link', 'duplicate': e.tool.TAR_ROOT + e.tool.WHEELS['pip']['path'],
                           'traversal': '../outside', 'budget': 'oversized-member'}[kind])
    if kind == 'link':
        info.type = tarfile.SYMTYPE
        info.linkname = 'outside'
    elif kind == 'budget':
        info.size = 64 * 1024 * 1024 + 1
    e.archive(extra_tar=info)
    with pytest.raises(ValueError):
        e.tool.generate(e.office, e.source, e.output)
    assert not (e.output / 'report.json').exists() and not (e.office.parent / 'outside').exists()


@pytest.mark.parametrize('kind', ['source', 'selected', 'new-companion'])
def test_input_changes_during_collection_are_detected(example, monkeypatch, kind):
    e = example
    original = e.tool.template_structure

    def changed(*args):
        result = original(*args)
        if kind == 'source':
            e.source.write_bytes(e.source.read_bytes() + b'changed')
        elif kind == 'selected':
            (e.office / e.tool.LIB / 'pip/__init__.py').write_bytes(b'changed')
        else:
            (e.office / e.tool.LIB / 'setuptools/cli-script.py').write_bytes(b'self-authored companion')
        return result

    monkeypatch.setattr(e.tool, 'template_structure', changed)
    with pytest.raises(ValueError):
        e.tool.generate(e.office, e.source, e.output)
    assert not (e.output / 'report.json').exists()


def test_existing_output_and_component_nested_output_are_preserved(example):
    e = example
    e.output.mkdir()
    keep = e.output / 'keep'
    keep.write_bytes(b'original output')
    with pytest.raises(ValueError, match='new directory'):
        e.tool.generate(e.office, e.source, e.output)
    with pytest.raises(ValueError, match='outside'):
        e.tool.generate(e.office, e.source, e.office / 'new-output')
    assert keep.read_bytes() == b'original output' and not (e.office / 'new-output').exists()


@pytest.mark.parametrize('kind', ['zip', 'trailer', 'companion'])
def test_generated_launcher_data_is_not_mistaken_for_an_original_template(example, kind):
    e = example
    name = 'setuptools/cli-64.exe' if kind == 'companion' else 'pip/_vendor/distlib/t64.exe'
    data = inert_pe(name)
    component_names = set()
    if kind == 'zip':
        stream = io.BytesIO(data)
        with ZipFile(stream, 'a') as archive:
            archive.writestr('__main__.py', b'raise RuntimeError("never execute fixture")')
        data = stream.getvalue()
    elif kind == 'trailer':
        data += b'PK\x05\x06'
    else:
        component_names.add(e.tool.LIB + 'setuptools/cli-64-script.py')
    with pytest.raises(ValueError):
        e.tool.template_structure(name, data, component_names)


def test_cli_success_remains_source_evidence_and_never_runtime_approval(example, monkeypatch, capsys):
    e = example
    monkeypatch.setattr('sys.argv', ['office_template_evidence', '--office', str(e.office),
        '--python-source', str(e.source), '--output', str(e.output)])
    e.tool.main()
    assert 'runtime exclusion remains unverified' in capsys.readouterr().out
    report = json.loads((e.output / 'report.json').read_text('utf-8'))
    assert not report['runtime_exclusion_verified'] and not report['product_release_ready']
