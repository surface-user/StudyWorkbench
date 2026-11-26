import importlib
import io
import json
import lzma

import pytest
from test_staged_python_licenses import bundle_case as bundle_case


@pytest.fixture
def installer(request, tmp_path):
    _, collector, stage, _, archive, _, expected, _ = request.getfixturevalue('bundle_case')
    tool = importlib.import_module('base_installer_sbom')
    record = collector.stage_python_license_bundle(stage, collector.python_license_plan(
        stage, collector.stage_files(stage), archive, expected))
    inputs = collector.stage_files(stage)
    index = stage / 'build-inventory.json'
    index.write_text(json.dumps({'python_license_bundle': record, 'files': {
        name: tool.file_digest(file) for name, file in inputs.items()}}), encoding='utf8')
    runtime = tmp_path / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    runtime.write_bytes(b'synthetic native file\xe8\xf0\xff\xff\xff' + bytes(65536) + b'\xe9\x03\x00\x00\x00')
    paths = [index, *inputs.values(), runtime]
    log = tmp_path / 'compiler.log'
    log.write_text('\n'.join('  Compressing: ' + str(p) for p in paths[:-1])
                   + '\n  Compressing: ' + str(runtime) + '   (1.2.3.4)\n', encoding='utf-8')
    setup = tmp_path / 'setup.exe'
    output = tmp_path / 'base.cdx.json'

    def pack(raw):
        filters = [{'id': lzma.FILTER_LZMA2, 'dict_size': 4096}]
        data = b'file stream fixture' + b'zlb\x1a\x00' + lzma.compress(raw, lzma.FORMAT_RAW, filters=filters)
        setup.write_bytes(data)

    raw = runtime.read_bytes()
    body = b''.join(p.read_bytes() for p in paths[:-1])
    body += b''.join(tool.encoded_calls(raw[i:i + tool.BLOCK], i) for i in range(0, len(raw), tool.BLOCK))
    pack(body)
    return tool, (stage, setup, runtime, log, output), body, pack


def test_installer_matches_all_inputs_and_keeps_absolute_paths_out(installer):
    tool, args, _, _ = installer
    files, packages = tool.generate(*args)
    assert (files, packages) == (4, 1)
    raw = args[-1].read_bytes()
    report = json.loads(raw)
    components = {c['bom-ref']: c for c in report['components']}
    assert len(components) == 6
    assert components['pkg:pypi/example@1']['version'] == '1'
    assert components['file:app/build-inventory.json']['hashes'][0]['content'] == tool.file_digest(args[0] / 'build-inventory.json')
    assert report['metadata']['component']['hashes'][0]['content'] == tool.file_digest(args[1])
    assert report['compositions'][0]['aggregate'] == 'incomplete'
    assert str(args[0].parent).encode() not in raw
    with pytest.raises(ValueError):
        tool.generate(*args)
    assert raw == args[-1].read_bytes()


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'foreign', 'swapped', 'stage-change', 'runtime-change',
                                   'truncated', 'extra-bytes', 'broken-stream', 'bad-inventory'])
def test_invalid_installer_inputs_never_produce_an_sbom(installer, fault):
    tool, args, body, pack = installer
    stage, setup, runtime, log, output = args
    lines = log.read_text(encoding='utf8').splitlines()
    if fault == 'duplicate':
        lines.append(lines[0])
    elif fault == 'missing':
        lines.pop()
    elif fault == 'foreign':
        lines[-1] = '   Compressing: unrelated.exe'
    elif fault == 'swapped':
        lines[0], lines[1] = lines[1], lines[0]
    elif fault == 'stage-change':
        (stage / 'backend/asset.txt').write_bytes(b'changed')
    elif fault == 'runtime-change':
        runtime.write_bytes(b'X' * runtime.stat().st_size)
    elif fault == 'truncated':
        pack(body[:-1])
    elif fault == 'extra-bytes':
        pack(body + b'?')
    elif fault == 'broken-stream':
        setup.write_bytes(b'zlb\x1a\x00bogus')
    else:
        (stage / 'build-inventory.json').write_text('{}')
    log.write_text('\n'.join(lines), encoding='utf8')
    with pytest.raises((ValueError, KeyError)):
        tool.generate(*args)
    assert not output.exists()


def test_filter_handles_negative_offsets_and_does_not_cross_blocks(installer):
    tool, _, _, _ = installer
    assert tool.encoded_calls(b'\xe8\xfb\xff\xff\xff', 0) == b'\xe8\x00\x00\x00\x00'
    assert tool.encoded_calls(b'\xe9\x01\x00\x00\x00', 65536) == b'\xe9\x06\x00\x01\x00'
    assert tool.encoded_calls(b'\xe8\x00\xe9\x00\x17\xe9', 0) == b'\xe8\x00\xe9\x00\x17\xe9'


def test_file_cannot_switch_filter_modes_between_blocks(installer, tmp_path):
    tool, _, _, _ = installer
    blob = b'\xe8\x00\x00\x00\x00' + bytes(tool.BLOCK - 5)
    path = tmp_path / 'switch.exe'
    path.write_bytes(blob + blob)
    mixed = io.BytesIO(blob + tool.encoded_calls(blob, tool.BLOCK))
    with pytest.raises(ValueError, match='differ'):
        tool.verify_stream(mixed, ['switch'], {'switch': path}, {'switch': {'bytes': tool.BLOCK * 2, 'sha256': tool.file_digest(path)}})


def test_desktop_sources_require_equal_bytes_and_verified_origin(installer, tmp_path):
    tool, args, _, _ = installer
    path = 'backend/asset.txt'
    files = tool.inventory(args[0])
    row = dict(files[path], source_identity='pkg:pub/example@1?hosted_url=pub.dev', copied_source_bytes_verified=True,
               sources=[{'sha256': files[path]['sha256']}])
    evidence = tmp_path / 'desktop.json'
    def write():
        evidence.write_text(json.dumps({'scope': 'Windows-desktop-artifact-and-selected-copy-origins',
                                        'physical_files': {path: row}}), encoding='utf8')
    write()
    assert tool.compare_desktop(evidence, files) == {row['source_identity']: [{'location': 'app/' + path}]}
    row['sources'][0]['sha256'] = '0' * 64
    write()
    with pytest.raises(ValueError):
        tool.compare_desktop(evidence, files)
    row['sha256'] = '9' * 64
    write()
    assert not tool.compare_desktop(evidence, files)


def test_runtime_version_comes_from_matching_x64_installer_manifest(installer, tmp_path):
    tool, args, _, _ = installer
    manifest = tmp_path / 'manifest.yaml'
    data = {'PackageIdentifier': 'Microsoft.EdgeWebView2Runtime', 'PackageVersion': '1.20.300.4',
            'Installers': [{'Architecture': 'x64', 'InstallerSha256': tool.file_digest(args[2]).upper()}]}
    manifest.write_text(json.dumps(data))
    tool.generate(*args, webview_manifest=manifest)
    assert any(c.get('version') == '1.20.300.4' for c in json.loads(args[-1].read_bytes())['components'])
    data['Installers'][0]['Architecture'] = 'arm64'
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        tool.webview_version(manifest, tool.file_digest(args[2]))


@pytest.mark.parametrize('fault', ['none', 'bad-file', 'missing-file', 'duplicate-file', 'missing-package',
                                   'unknown-target', 'duplicate-edge', 'duplicate-source'])
def test_backend_graph_requires_this_exact_component_set(installer, tmp_path, fault):
    tool, args, _, _ = installer
    files = tool.inventory(args[0])
    package = 'pkg:pypi/example@1'
    other = 'pkg:pypi/second@2'
    components = [{'type': 'file', 'name': name.removeprefix('backend/'),
                   'hashes': [{'alg': 'SHA-256', 'content': row['sha256']}]}
                  for name, row in files.items() if name.startswith('backend/')]
    components += [{'type': 'library', 'bom-ref': p, 'purl': p} for p in (package, other)]
    graph = [{'ref': package, 'dependsOn': [other]}]
    if fault == 'bad-file':
        components[0]['hashes'][0]['content'] = '1' * 64
    elif fault == 'missing-file':
        components.pop(0)
    elif fault == 'duplicate-file':
        components.append(components[0])
    elif fault == 'missing-package':
        components.pop()
    elif fault == 'unknown-target':
        graph[0]['dependsOn'] = ['pkg:pypi/unknown@1']
    elif fault == 'duplicate-edge':
        graph[0]['dependsOn'].append(other)
    elif fault == 'duplicate-source':
        graph.append(graph[0])
    path = tmp_path / 'dependencies.json'
    path.write_text(json.dumps({'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': components,
                                'dependencies': graph}))
    if fault == 'none':
        assert tool.backend_dependencies(path, files, {package, other}) == ({package: None, other: None}, graph)
    else:
        with pytest.raises(ValueError):
            tool.backend_dependencies(path, files, {package, other})
