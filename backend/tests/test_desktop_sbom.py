import gzip
import hashlib
import importlib
import io
import json
import stat
import struct
import sys
import tarfile
import zipfile

import pytest
import test_frozen_python_members
import yaml

collector = test_frozen_python_members.collector


def pe_image(tag=b'Never execute this self-authored PE fixture'):
    raw = bytearray(1024)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3c, 0x80)
    raw[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', raw, 0x84, 0x8664, 1, 1, 0, 0, 240, 0x22)
    struct.pack_into('<H', raw, 0x98, 0x20b)
    struct.pack_into('<IIQII', raw, 0x98 + 16, 0x1000, 0x1000, 0x140000000, 0x1000, 0x200)
    struct.pack_into('<II', raw, 0x98 + 56, 0x2000, 0x200)
    struct.pack_into('<H', raw, 0x98 + 68, 3)
    struct.pack_into('<I', raw, 0x98 + 108, 16)
    struct.pack_into('<8sIIIIIIHHI', raw, 0x188, b'.text', len(tag), 0x1000, 512, 512, 0, 0, 0, 0, 0x60000020)
    raw[512:512 + len(tag)] = tag
    return bytes(raw)


def tar_bytes(contents, extra=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, raw in contents.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
        if extra is not None:
            archive.addfile(extra, io.BytesIO(b''))
    return stream.getvalue()


def zip_bytes(contents, extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, raw in contents.items():
            archive.writestr(name, raw)
        if extra is not None:
            archive.writestr(extra, b'')
    return stream.getvalue()


def refresh_tree(d):
    entries = []
    for path in sorted(d['source'].rglob('*')):
        if path.is_file():
            raw = path.read_bytes()
            entries.append({'path': path.relative_to(d['source']).as_posix(), 'mode': '100644', 'type': 'blob',
                            'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
    d['source_tree_file'].write_text(json.dumps({'commit': 'a' * 40, 'tree': 'b' * 40, 'entries': entries}))


def repin_artifact(d):
    p = json.loads(d['provenance_file'].read_text())
    p['artifact']['digest'] = 'sha256:' + d['tool'].sha256(d['artifact'].read_bytes())
    p['artifact']['size_in_bytes'] = d['artifact'].stat().st_size
    d['provenance_file'].write_text(json.dumps(p))


@pytest.fixture
def desktop(tmp_path, collector, monkeypatch):
    tool = importlib.import_module('desktop_sbom')
    source, sdk, pubs = [tmp_path / n for n in ('source', 'sdk', 'pubs')]
    for path in (source, sdk / 'bin/cache/artifacts/engine/windows-x64', pubs):
        path.mkdir(parents=True)
    (sdk / 'bin/cache/flutter.version.json').write_text(json.dumps({'frameworkVersion': '3.47.1',
        'engineRevision': tool.ENGINE_REVISION, 'dartSdkVersion': '3.13.1'}))
    (sdk / 'bin/cache/artifacts/engine/windows-x64/icudtl.dat').write_bytes(b'Self-authored ICU fixture')
    payload = {'data/app.so': b'\x7fELF self-authored nonexecutable AOT fixture',
               'study_workbench.exe': pe_image(), 'flutter_windows.dll': pe_image(b'Engine fixture'),
               'WebView2Loader.dll': pe_image(b'Loader fixture'),
               'data/icudtl.dat': b'Self-authored ICU fixture',
               'data/flutter_assets/packages/asset_demo/assets/demo.txt': b'Observed copied asset',
               'data/flutter_assets/assets/project.json': b'{\r\n  "fixture": true\r\n}\r\n',
               'data/flutter_assets/NOTICES.Z': b'Opaque notice fixture'}
    packages = {}
    for name in ['asset_demo', 'flutter_inappwebview_windows', 'url_launcher_windows']:
        contents = {'pubspec.yaml': f'name: {name}\nversion: 1.2.3\n'.encode()}
        if name == 'asset_demo':
            contents['lib/assets/demo.txt'] = b'Observed copied asset'
        else:
            contents['windows/CMakeLists.txt'] = b"raise RuntimeError('Must never execute CMake source')"
            payload[name + '_plugin.dll'] = pe_image(name.encode())
        raw = tar_bytes(contents)
        (pubs / (name + '-1.2.3.tar.gz')).write_bytes(raw)
        packages[name] = {'source': 'hosted', 'version': '1.2.3', 'description': {'name': name,
                         'url': 'https://pub.dev', 'sha256': tool.sha256(raw)}}
    packages['flutter'] = {'source': 'sdk', 'version': '0.0.0', 'description': 'flutter'}
    for name, raw in {'backend/requirements.lock.txt': b'sample==1.2.3\n',
                      'apps/desktop/pubspec.lock': yaml.safe_dump({'packages': packages}).encode(),
                      'apps/desktop/pubspec.yaml': b'name: study_workbench\n',
                      'apps/desktop/lib/main.dart': b"throw 'must not execute project code';\n",
                      'apps/desktop/windows/runner/CMakeLists.txt': b'Generated target declarations fixture\n',
                      'apps/desktop/assets/project.json': b'{\n  "fixture": true\n}\n'}.items():
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    engine, webview, artifact = [tmp_path / n for n in ('engine.zip', 'webview.nupkg', 'artifact.zip')]
    engine.write_bytes(zip_bytes({'flutter_windows.dll': payload['flutter_windows.dll']}))
    loader_paths = ['build/native/x64/WebView2Loader.dll', 'runtimes/win-x64/native/WebView2Loader.dll']
    web_contents = {n: payload['WebView2Loader.dll'] for n in loader_paths}
    web_contents['Microsoft.Web.WebView2.nuspec'] = (f'<package><metadata><id>Microsoft.Web.WebView2</id>'
        f'<version>{tool.WEBVIEW_VERSION}</version></metadata></package>').encode()
    webview.write_bytes(zip_bytes(web_contents))
    for name, file in [('ENGINE', engine), ('WEBVIEW', webview)]:
        monkeypatch.setattr(tool, name + '_SHA256', tool.sha256(file.read_bytes()))
        monkeypatch.setattr(tool, name + '_BYTES', file.stat().st_size)
    artifact_contents = {tool.DESKTOP_PREFIX + n: raw for n, raw in payload.items()}
    artifact_contents['dist/study_backend/ignored.bin'] = b'Out-of-scope backend fixture'
    artifact_contents['apps/desktop/build/windows/x64/packages/BuildOnly/header.h'] = b'Build input, not a runtime member'
    artifact.write_bytes(zip_bytes(artifact_contents))
    provenance = {'run': {'id': 1, 'head_sha': 'a' * 40, 'status': 'completed', 'conclusion': 'success'},
                  'artifact': {'id': 2, 'name': 'windows-release-inputs-' + 'a' * 40, 'digest': 'sha256:' + tool.sha256(artifact.read_bytes()),
                               'size_in_bytes': artifact.stat().st_size, 'workflow_run': {'id': 1, 'head_sha': 'a' * 40}},
                  'checkout': {'commit': 'c' * 40, 'tree': 'b' * 40}}
    provenance_file, source_tree_file = [tmp_path / n for n in ('provenance.json', 'source-tree.json')]
    provenance_file.write_text(json.dumps(provenance))
    d = {'tool': tool, 'source': source, 'sdk': sdk, 'pub_archives': pubs, 'artifact': artifact,
         'engine_archive': engine, 'webview_package': webview, 'provenance_file': provenance_file,
         'source_tree_file': source_tree_file, 'output': tmp_path / 'result', 'payload': payload,
         'artifact_contents': artifact_contents, 'web_contents': web_contents, 'packages': packages}
    refresh_tree(d)
    return d


def run(d):
    return d['tool'].generate(*(d[k] for k in ('artifact', 'provenance_file', 'source_tree_file', 'source',
        'engine_archive', 'webview_package', 'pub_archives', 'sdk', 'output')))


def test_actual_files_and_archives_do_not_project_build_packages_or_generated_code(desktop):
    d = desktop
    r = run(d)
    assert len(r['physical_files']) == len(d['payload']) == 10
    assert len(r['copied_member_packages']) == 3
    assert len(r['excluded_artifact_files']) == 2
    assert not r['product_sbom_complete'] and not r['upstream_provenance_verified'] and not r['source_tree_authenticated']
    assert not r['AOT_source_equivalence_verified'] and not r['reproducible_build_verified'] and not r['signatures_verified']
    assert r['physical_files']['data/app.so']['source_identity'] is None
    assert r['physical_files']['data/icudtl.dat']['role'] == 'local_sdk_cache_byte_match'
    assert r['physical_files']['data/icudtl.dat']['source_identity'] is None
    assert not r['physical_files']['data/icudtl.dat']['sources'][0]['official_archive_verified']
    assert not r['physical_files']['data/flutter_assets/assets/project.json']['source_bytes_identical']
    assert not r['physical_files']['data/flutter_assets/assets/project.json']['copied_source_bytes_verified']
    assert r['physical_files']['data/flutter_assets/packages/asset_demo/assets/demo.txt']['sources'][0]['member'] == 'lib/assets/demo.txt'
    assert len(r['physical_files']['WebView2Loader.dll']['sources']) == 2
    assert r['project_build_inputs']['apps/desktop/windows/runner/CMakeLists.txt']['git_blob_sha1']
    for p in r['plugin_producer_associations'].values():
        assert not p['binary_source_equivalence_verified']
    bom = json.loads((d['output'] / 'desktop.cdx.json').read_bytes())
    assert len(bom['components']) == 13 and sum(c['type'] == 'file' for c in bom['components']) == 10
    assert not any(c.get('name') in ['flutter', 'BuildOnly', 'flutter_inappwebview_windows', 'url_launcher_windows'] for c in bom['components'])


@pytest.mark.parametrize('where', ['artifact-digest', 'run-head', 'checkout-tree', 'artifact-run', 'artifact-name', 'failed-run'])
def test_unrelated_or_failed_service_declarations_are_rejected(desktop, where):
    d = desktop
    p = json.loads(d['provenance_file'].read_text())
    if where == 'artifact-digest':
        p['artifact']['digest'] = 'sha256:' + '0' * 64
    elif where == 'run-head':
        p['run']['head_sha'] = 'f' * 40
    elif where == 'checkout-tree':
        p['checkout']['tree'] = 'f' * 40
    elif where == 'artifact-run':
        p['artifact']['workflow_run']['id'] = 99
    elif where == 'artifact-name':
        p['artifact']['name'] = 'old-windows-release'
    else:
        p['run']['conclusion'] = 'failure'
    d['provenance_file'].write_text(json.dumps(p))
    with pytest.raises(ValueError):
        run(d)
    assert not d['output'].exists()


@pytest.mark.parametrize('kind', ['traversal', 'duplicate', 'symlink', 'encrypted'])
def test_unsafe_zip_entries_are_rejected_even_outside_desktop_scope(desktop, kind):
    d = desktop
    if kind in ('traversal', 'duplicate'):
        extra = 'dist/../escape' if kind == 'traversal' else next(iter(d['artifact_contents'])).upper()
        d['artifact'].write_bytes(zip_bytes(d['artifact_contents'], extra))
    elif kind == 'symlink':
        info = zipfile.ZipInfo('dist/link')
        info.create_system, info.external_attr = 3, (stat.S_IFLNK | 0o777) << 16
        d['artifact'].write_bytes(zip_bytes(d['artifact_contents'], info))
    else:
        raw = bytearray(d['artifact'].read_bytes())
        for n in range(len(raw) - 12):
            if raw[n:n + 4] == b'PK\x01\x02':
                raw[n + 8] |= 1
        d['artifact'].write_bytes(raw)
    repin_artifact(d)
    with pytest.raises(ValueError, match='Unsafe'):
        run(d)


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'traversal', 'duplicate'])
def test_pub_archive_names_types_and_duplicates_fail_without_extraction(desktop, kind):
    tool = desktop['tool']
    extra = tarfile.TarInfo('../outside' if kind == 'traversal' else 'pubspec.yaml' if kind == 'duplicate' else 'link')
    if kind in ('symlink', 'hardlink'):
        extra.type, extra.linkname = (tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE), 'secret'
    raw = tar_bytes({'pubspec.yaml': b'name: fixture\nversion: 1.0.0\n'}, extra)
    with pytest.raises(ValueError):
        archive, _ = tool.pub_contents(raw, [0])
        archive.close()


@pytest.mark.parametrize('limit', ['MAX_ARCHIVE_BYTES', 'MAX_INPUT_FILES', 'MAX_INPUT_BYTES', 'MAX_EXPANDED_BYTES', 'MAX_MEMBER_BYTES', 'MAX_READ_BYTES', 'MAX_TAR_BYTES'])
def test_declared_and_actual_input_and_expansion_budgets_fail_closed(desktop, monkeypatch, limit):
    monkeypatch.setattr(desktop['tool'], limit, 1)
    with pytest.raises(ValueError, match='budget|exceeds'):
        run(desktop)
    assert not desktop['output'].exists()


@pytest.mark.parametrize('where', ['engine_archive', 'webview_package', 'pub_asset', 'project_input', 'sdk_version'])
def test_wrong_fixed_sources_are_rejected(desktop, where):
    d = desktop
    path = {'pub_asset': d['pub_archives'] / 'asset_demo-1.2.3.tar.gz',
            'project_input': d['source'] / 'apps/desktop/lib/main.dart',
            'sdk_version': d['sdk'] / 'bin/cache/flutter.version.json'}.get(where, d.get(where))
    if where == 'sdk_version':
        p = json.loads(path.read_text())
        p['engineRevision'] = '0' * 40
        path.write_text(json.dumps(p))
    else:
        path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError):
        run(d)
    assert not d['output'].exists()


def test_non_amd64_native_image_is_not_hidden_as_unknown(desktop):
    d = desktop
    raw = bytearray(d['payload']['study_workbench.exe'])
    struct.pack_into('<H', raw, 0x84, 0x14c)
    d['artifact_contents'][d['tool'].DESKTOP_PREFIX + 'study_workbench.exe'] = bytes(raw)
    d['artifact'].write_bytes(zip_bytes(d['artifact_contents']))
    repin_artifact(d)
    with pytest.raises(ValueError, match='AMD64'):
        run(d)


def test_extra_pub_asset_byte_is_reported_unmapped_without_claiming_owner(desktop):
    d = desktop
    name = d['tool'].DESKTOP_PREFIX + 'data/flutter_assets/packages/asset_demo/assets/demo.txt'
    d['artifact_contents'][name] += b'changed payload'
    d['artifact'].write_bytes(zip_bytes(d['artifact_contents']))
    repin_artifact(d)
    r = run(d)
    p = r['physical_files']['data/flutter_assets/packages/asset_demo/assets/demo.txt']
    assert p['source_identity'] is None and not p['copied_source_bytes_verified']
    assert not any('asset_demo' in purl for purl in r['copied_member_packages'])


@pytest.mark.parametrize('where', ['artifact', 'provenance_file', 'source_tree_file', 'engine_archive', 'webview_package', 'icu', 'project', 'pub', 'lock'])
def test_every_selected_input_is_rechecked_after_source_matching(desktop, monkeypatch, where):
    d, tool = desktop, desktop['tool']
    old = tool.pub_contents
    changed = False

    def mutate(raw, budget):
        nonlocal changed
        result = old(raw, budget)
        if not changed:
            path = {'icu': d['sdk'] / 'bin/cache/artifacts/engine/windows-x64/icudtl.dat',
                    'project': d['source'] / 'apps/desktop/lib/main.dart', 'pub': d['pub_archives'] / 'asset_demo-1.2.3.tar.gz',
                    'lock': d['source'] / tool.LOCKS[0]}.get(where, d.get(where))
            path.write_bytes(path.read_bytes() + b'changed during scan')
            changed = True
        return result
    monkeypatch.setattr(tool, 'pub_contents', mutate)
    with pytest.raises(ValueError, match='changed'):
        run(d)
    assert not d['output'].exists()


@pytest.mark.parametrize('kind', ['wrong-version', 'duplicate-id', 'dtd'])
def test_nuget_metadata_is_checked_after_matching_whole_archive_pin(desktop, monkeypatch, kind):
    d, tool = desktop, desktop['tool']
    name = 'Microsoft.Web.WebView2.nuspec'
    raw = d['web_contents'][name]
    if kind == 'wrong-version':
        raw = raw.replace(tool.WEBVIEW_VERSION.encode(), b'0.0.0')
    elif kind == 'duplicate-id':
        raw = raw.replace(b'</metadata>', b'<id>Microsoft.Web.WebView2</id></metadata>')
    else:
        raw = b'<!DOCTYPE x [<!ENTITY x "external">]>' + raw
    d['web_contents'][name] = raw
    d['webview_package'].write_bytes(zip_bytes(d['web_contents']))
    monkeypatch.setattr(tool, 'WEBVIEW_SHA256', tool.sha256(d['webview_package'].read_bytes()))
    monkeypatch.setattr(tool, 'WEBVIEW_BYTES', d['webview_package'].stat().st_size)
    with pytest.raises((ValueError, tool.DefusedXmlException)):
        run(d)


def test_tar_gzip_actual_budget_is_independent_of_declared_tar_members(desktop, monkeypatch):
    tool = desktop['tool']
    monkeypatch.setattr(tool, 'MAX_TAR_BYTES', 100)
    with pytest.raises(ValueError, match='actual expansion'):
        tool.pub_contents(gzip.compress(b'0' * 1000), [0])


def test_source_growth_cannot_read_past_remaining_total_input_budget(desktop, monkeypatch):
    d, tool = desktop, desktop['tool']
    limit = d['provenance_file'].stat().st_size + 1
    monkeypatch.setattr(tool, 'MAX_INPUT_BYTES', limit)
    original, read_sizes = tool.bounded_file, []

    def growing(path, read_limit):
        if path == d['provenance_file']:
            path.write_bytes(path.read_bytes() + b' ' * 20)
            raw = original(path, read_limit)
            read_sizes.append(len(raw))
            return raw
        return original(path, read_limit)
    monkeypatch.setattr(tool, 'bounded_file', growing)
    with pytest.raises(ValueError, match='budget|exceeds'):
        run(d)
    assert sum(read_sizes) <= limit
    assert not d['output'].exists()


def test_cli_returns_only_incomplete_success_and_refuses_existing_output(desktop, monkeypatch):
    d = desktop
    argv = ['tool']
    for flag, key in [('artifact', 'artifact'), ('provenance', 'provenance_file'), ('source-tree', 'source_tree_file'),
        ('source', 'source'), ('engine-archive', 'engine_archive'), ('webview-package', 'webview_package'),
        ('pub-archives', 'pub_archives'), ('sdk-root', 'sdk'), ('output', 'output')]:
        argv += ['--' + flag, str(d[key])]
    monkeypatch.setattr(sys, 'argv', argv)
    assert d['tool'].main() == 2
    with pytest.raises(SystemExit) as exc:
        d['tool'].main()
    assert exc.value.code == 1
