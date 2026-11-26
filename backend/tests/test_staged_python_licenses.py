import hashlib
import importlib
import io
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def bundle_case(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('frozen_member_licenses')
    collector = importlib.import_module('release_inventory')
    stage = tmp_path / 'stage'
    backend = stage / 'backend'
    backend.mkdir(parents=True)
    (backend / 'study_backend.exe').write_bytes(b'Self-authored frozen component fixture; never executed.')
    (backend / 'asset.txt').write_bytes(b'Self-authored payload fixture.')
    text = b'Self-authored license text.'
    digest = tool.sha256(text)
    index = {'scope': 'mapped frozen PyPI distributions', 'source_head': None,
             'payload_fingerprint': tool.sha256(json.dumps(tool.inventory(backend), sort_keys=True).encode()),
             'distribution_obligations_reviewed': False,
             'packages': {'pkg:pypi/example@1': {'metadata_sha256': 'a' * 64, 'record_sha256': 'b' * 64,
                          'issues': ['unresolved fixture condition'],
                          'files': [{'text_path': 'texts/' + digest, 'sha256': digest, 'bytes': len(text)}]}}}
    archive = tmp_path / 'licenses.zip'

    def write(data=None, extra=(), flags=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            tool.write_entry(z, 'index.json', json.dumps(index if data is None else data).encode())
            tool.write_entry(z, 'texts/' + digest, text)
            for name, raw in extra:
                item = zipfile.ZipInfo(name)
                if flags:
                    item.create_system = 3
                    item.external_attr = flags << 16
                z.writestr(item, raw)
        archive.write_bytes(buffer.getvalue())
        return tool.sha256(archive.read_bytes())

    expected = write()
    return tool, collector, stage, backend, archive, index, expected, write


def snapshot(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def test_bound_archive_is_copied_once_and_issues_remain_explicit(bundle_case):
    tool, collector, stage, backend, archive, _, expected, _ = bundle_case
    originals = snapshot(backend), archive.read_bytes()
    plan = collector.python_license_plan(stage, collector.stage_files(stage), archive, expected)
    record = collector.stage_python_license_bundle(stage, plan)
    assert record['packages'] == record['unique_texts'] == record['text_references'] == 1
    assert record['packages_with_issues'] == 1
    assert record['source_head'] is None
    assert record['distribution_obligations_reviewed'] is record['upstream_provenance_verified'] is record['release_ready'] is False
    target = stage / tool.BUNDLE_PATH
    stamp, before = target.stat().st_mtime_ns, snapshot(stage)
    collector.stage_python_license_bundle(stage, collector.python_license_plan(stage, collector.stage_files(stage), archive, expected))
    assert snapshot(stage) == before and target.stat().st_mtime_ns == stamp
    assert collector.verify_staged_python_licenses(stage, collector.stage_files(stage), record, expected) == record
    assert (snapshot(backend), archive.read_bytes()) == originals


def test_backend_cannot_omit_bundle_but_generic_stage_keeps_legacy_behavior(bundle_case, monkeypatch):
    _, collector, stage, backend, _, _, _, _ = bundle_case
    before = snapshot(stage)
    monkeypatch.setattr(sys, 'argv', ['release_inventory.py', '--stage', str(stage)])
    with pytest.raises(ValueError, match='requires --python-license-bundle'):
        collector.main()
    assert snapshot(stage) == before and not (stage / 'licenses').exists()
    with pytest.raises(ValueError, match='evidence is missing'):
        collector.verify_staged_python_licenses(stage, collector.stage_files(stage), None)
    (backend / 'study_backend.exe').rename(backend / 'component-fixture.exe')
    plan = collector.python_license_plan(stage, collector.stage_files(stage))
    assert not plan['record']['applied']
    assert collector.verify_staged_python_licenses(stage, collector.stage_files(stage), None) == plan['record']


@pytest.mark.parametrize('damage', ['payload', 'archive', 'hash', 'half-input', 'existing-destination', 'blocked-parent'])
def test_wrong_or_conflicting_inputs_fail_before_any_copy(bundle_case, damage):
    tool, collector, stage, backend, archive, _, expected, _ = bundle_case
    target = stage / tool.BUNDLE_PATH
    if damage == 'payload':
        (backend / 'asset.txt').write_bytes(b'Changed owned test payload.')
    elif damage == 'archive':
        archive.write_bytes(archive.read_bytes() + b'Changed archive.')
    elif damage == 'hash':
        expected = '0' * 64
    elif damage == 'existing-destination':
        target.parent.mkdir(parents=True)
        target.write_bytes(b'Pre-existing conflict, must survive.')
    elif damage == 'blocked-parent':
        (stage / 'licenses').write_bytes(b'Pre-existing file, must survive.')
    before = snapshot(stage)
    with pytest.raises(ValueError):
        collector.python_license_plan(stage, collector.stage_files(stage), archive, None if damage == 'half-input' else expected)
    assert snapshot(stage) == before


@pytest.mark.parametrize('damage', ['scope', 'fingerprint', 'reviewed', 'head', 'empty-packages', 'package-id',
                                  'metadata', 'record', 'empty-files', 'reference-size', 'reference-hash', 'reference-path', 'issues'])
def test_semantically_invalid_index_is_rejected_even_with_its_current_zip_hash(bundle_case, damage):
    tool, _, _, backend, archive, index, _, write = bundle_case
    package = index['packages']['pkg:pypi/example@1']
    if damage == 'scope':
        index['scope'] = 'Environment packages are not shipped identities.'
    elif damage == 'fingerprint':
        index['payload_fingerprint'] = '0' * 64
    elif damage == 'reviewed':
        index['distribution_obligations_reviewed'] = True
    elif damage == 'head':
        index['source_head'] = 'Unverified version text.'
    elif damage == 'empty-packages':
        index['packages'] = {}
    elif damage == 'package-id':
        index['packages'] = {'../example': package}
    elif damage in ('metadata', 'record'):
        package[damage + '_sha256'] = 'invalid'
    elif damage == 'empty-files':
        package['files'] = []
    elif damage.startswith('reference-'):
        field = {'reference-size': 'bytes', 'reference-hash': 'sha256', 'reference-path': 'text_path'}[damage]
        package['files'][0][field] = -1 if field == 'bytes' else 'unbound'
    else:
        package['issues'] = 'Not an array.'
    expected = write()
    with pytest.raises(ValueError):
        tool.verify_bundle(backend, archive, expected)


@pytest.mark.parametrize('name,mode', [('../outside', None), ('texts/../outside', None), ('extra', None),
                                    ('texts/' + 'c' * 64, stat.S_IFLNK | 0o777), ('index.json/', None)])
def test_unsafe_zip_members_are_never_extracted(bundle_case, name, mode):
    tool, _, stage, backend, archive, _, _, write = bundle_case
    expected = write(extra=[(name, b'owned malformed ZIP fixture')], flags=mode)
    before = snapshot(stage)
    with pytest.raises(ValueError, match='Unsafe'):
        tool.verify_bundle(backend, archive, expected)
    assert snapshot(stage) == before


@pytest.mark.parametrize('budget,value', [('MAX_BUNDLE_BYTES', 8), ('MAX_BUNDLE_ENTRIES', 1),
                                       ('MAX_BUNDLE_EXPANDED', 8), ('MAX_INDEX_BYTES', 8), ('MAX_LICENSE_BYTES', 8),
                                       ('MAX_LICENSE_REFERENCES', 0)])
def test_each_archive_budget_is_enforced(bundle_case, monkeypatch, budget, value):
    tool, _, _, backend, archive, _, expected, _ = bundle_case
    monkeypatch.setattr(tool, budget, value)
    with pytest.raises(ValueError, match='budget|bounded'):
        tool.verify_bundle(backend, archive, expected)


@pytest.mark.parametrize('damage', ['duplicate-member', 'duplicate-json-key', 'wrong-text-bytes', 'unreferenced-text'])
def test_archive_ambiguity_and_changed_text_are_rejected(bundle_case, damage):
    tool, _, _, backend, archive, index, _, write = bundle_case
    if damage == 'duplicate-member':
        with pytest.warns(UserWarning, match='Duplicate name'):
            expected = write(extra=[('index.json', b'{}')])
    elif damage == 'unreferenced-text':
        raw = b'Unreferenced owned license text.'
        expected = write(extra=[('texts/' + tool.sha256(raw), raw)])
    else:
        encoded = json.dumps(index).encode()
        if damage == 'duplicate-json-key':
            encoded = encoded.replace(b'{"scope":', b'{"scope":"duplicate","scope":', 1)
        with zipfile.ZipFile(archive, 'w') as target:
            tool.write_entry(target, 'index.json', encoded)
            row = index['packages']['pkg:pypi/example@1']['files'][0]
            tool.write_entry(target, row['text_path'], b'Wrong owned text bytes.' if damage == 'wrong-text-bytes' else b'Self-authored license text.')
        expected = tool.sha256(archive.read_bytes())
    with pytest.raises(ValueError):
        tool.verify_bundle(backend, archive, expected)


def test_actual_read_budget_is_enforced_after_safe_declared_sizes(bundle_case, monkeypatch):
    tool, _, _, backend, archive, _, expected, _ = bundle_case
    original_open = zipfile.ZipFile.open
    monkeypatch.setattr(tool, 'MAX_INDEX_BYTES', 1024)

    def oversized_stream(self, item, *args, **kwargs):
        if isinstance(item, zipfile.ZipInfo) and item.filename == 'index.json':
            return io.BytesIO(b'x' * 1025)
        return original_open(self, item, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, 'open', oversized_stream)
    with pytest.raises(ValueError, match='actual byte budget'):
        tool.verify_bundle(backend, archive, expected)


def test_linked_license_input_is_refused_before_open(bundle_case, monkeypatch):
    tool, _, _, backend, archive, _, expected, _ = bundle_case
    original_stat, original_open, opened = Path.lstat, Path.open, []

    def linked(path, *args, **kwargs):
        value = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT) if path == archive else value

    def track_open(path, *args, **kwargs):
        if path == archive:
            opened.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', linked)
    monkeypatch.setattr(Path, 'open', track_open)
    with pytest.raises(ValueError, match='reparse'):
        tool.verify_bundle(backend, archive, expected)
    assert not opened


@pytest.mark.parametrize('change', ['source', 'backend', 'destination'])
def test_changes_after_preflight_are_refused_and_existing_bytes_survive(bundle_case, change):
    tool, collector, stage, backend, archive, _, expected, _ = bundle_case
    plan = collector.python_license_plan(stage, collector.stage_files(stage), archive, expected)
    if change == 'source':
        archive.write_bytes(b'Changed owned source ZIP fixture.')
    elif change == 'backend':
        (backend / 'asset.txt').write_bytes(b'Changed owned payload fixture.')
    else:
        target = stage / tool.BUNDLE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(b'Conflicting bytes must survive.')
    before = snapshot(stage)
    with pytest.raises(ValueError):
        collector.stage_python_license_bundle(stage, plan)
    assert snapshot(stage) == before


def test_external_expected_hash_prevents_outer_manifest_rehash_bypass(bundle_case):
    tool, collector, stage, backend, archive, index, expected, write = bundle_case
    record = collector.stage_python_license_bundle(stage, collector.python_license_plan(stage, collector.stage_files(stage), archive, expected))
    index['packages']['pkg:pypi/example@1']['issues'] = []
    new_hash = write()
    (stage / tool.BUNDLE_PATH).write_bytes(archive.read_bytes())
    forged = tool.verify_bundle(backend, archive, new_hash)
    assert forged != record
    before = snapshot(stage)
    with pytest.raises(ValueError, match='expected SHA256'):
        collector.verify_staged_python_licenses(stage, collector.stage_files(stage), forged, expected)
    assert snapshot(stage) == before


def test_partial_archive_copy_is_kept_without_overwriting_old_manifest(bundle_case, monkeypatch):
    tool, collector, stage, _, archive, _, expected, _ = bundle_case
    old_manifest = b'{"preserve_owned_prior_manifest":true}'
    (stage / 'build-inventory.json').write_bytes(old_manifest)
    plan = collector.python_license_plan(stage, collector.stage_files(stage), archive, expected)
    destination, original_open = stage / tool.BUNDLE_PATH, Path.open

    def fail_copy(path, mode='r', *args, **kwargs):
        if path == destination and mode == 'xb':
            with original_open(path, mode, *args, **kwargs) as stream:
                stream.write(b'partial owned output')
            raise OSError('Self-authored copy failure fixture')
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', fail_copy)
    with pytest.raises(OSError, match='copy failure'):
        collector.stage_python_license_bundle(stage, plan)
    assert destination.read_bytes() == b'partial owned output'
    assert (stage / 'build-inventory.json').read_bytes() == old_manifest
    with pytest.raises(ValueError, match='conflicts'):
        collector.python_license_plan(stage, collector.stage_files(stage), archive, expected)


@pytest.mark.parametrize('change', [False, True])
def test_default_collection_uses_unique_actual_members_and_keeps_unknown_head(bundle_case, tmp_path, monkeypatch, change):
    tool, _, _, backend, _, index, _, _ = bundle_case
    matcher = importlib.import_module('frozen_python_members')
    frozen = importlib.import_module('frozen_sbom')
    locks = importlib.import_module('source_sbom')
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'lock').write_bytes(b'Self-authored source lock fixture.')
    build_input = tmp_path / 'build-input'
    build_input.write_bytes(b'Self-authored recorded build input.')
    monkeypatch.setattr(locks, 'LOCKS', ('lock',))
    monkeypatch.setattr(locks, 'lock_inventory', lambda raw: ({'pkg:pypi/example@1': {'name': 'example', 'version': '1'}}, {}, {}))
    parsed = {'pyz': {'example': {'package_identity': 'unmapped'}, 'shared': {'package_identity': 'unmapped'},
                      'unknown': {'package_identity': 'unmapped'}, 'study_workbench': {'package_identity': 'application_source_compared'}}}
    monkeypatch.setattr(frozen, 'embedded', lambda *args: parsed)
    monkeypatch.setattr(frozen, 'metadata', lambda *args: {})
    proof = {'metadata_sha256': 'a' * 64, 'record_sha256': 'b' * 64}
    candidate = {'purl': 'pkg:pypi/example@1'}
    inputs = {build_input: {'limit': 1024, 'sha256': tool.sha256(build_input.read_bytes())}}
    monkeypatch.setattr(matcher, 'local_matches', lambda *args: (
        {'example': [candidate], 'shared': [candidate, {'purl': 'pkg:pypi/environment-only@1'}]}, {},
        {'pkg:pypi/example@1': proof, 'pkg:pypi/environment-only@1': {}}, inputs, 3, 3))

    def evidence(identity, output, checkout):
        assert identity == {'name': 'example', 'version': '1'} and checkout == source
        row = index['packages']['pkg:pypi/example@1']
        raw = b'Self-authored license text.'
        (output / 'texts' / tool.sha256(raw)).write_bytes(raw)
        if change:
            build_input.write_bytes(b'Changed owned build input.')
        return row

    monkeypatch.setattr(tool, 'python_evidence', evidence)
    output = tmp_path / 'generated.zip'
    if change:
        with pytest.raises(ValueError, match='build inputs changed'):
            tool.collect(backend, None, source, output)
        assert not output.exists()
    else:
        result = tool.collect(backend, None, source, output)
        assert result['packages'] == 1
        checked = tool.verify_bundle(backend, output, result['sha256'])
        assert checked['source_head'] is None and checked['packages'] == 1
        with zipfile.ZipFile(output) as archive:
            saved = json.loads(archive.read('index.json'))
            assert set(saved['packages']) == {'pkg:pypi/example@1'}
            assert saved['member_matching']['modules_ambiguous'] == saved['member_matching']['modules_unmapped'] == 1
            assert saved['member_matching']['member_mapping_complete'] is False


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows release entry script')
@pytest.mark.parametrize('mode', ['default', 'prebuilt', 'collection-fails', 'missing-hash', 'bundle-without-backend', 'prebuilt-in-renderer'])
def test_release_script_preserves_default_and_prebuilt_control_flow(tmp_path, mode):
    root = tmp_path / 'release-entry'
    scripts = root / 'packaging/windows'
    scripts.mkdir(parents=True)
    original = Path(__file__).parents[2] / 'packaging/windows/build-release.ps1'
    (scripts / 'build-release.ps1').write_bytes(original.read_bytes())
    (root / 'apps/desktop').mkdir(parents=True)
    (root / 'apps/desktop/pubspec.yaml').write_text('version: 1.0.0+1\n', encoding='utf-8')
    (root / 'tools').mkdir()
    # All commands below are authored control-flow fixtures, not a compiler/signature/runtime test.
    (root / 'tools/prepare-windows.ps1').write_text(r'''
function global:flutter { Add-Content -LiteralPath events.txt -Value 'flutter'; $global:LASTEXITCODE=0 }
''', encoding='utf-8')
    (scripts / 'build-backend.ps1').write_text(r'''
param([string]$Python)
Add-Content -LiteralPath events.txt -Value 'backend-build'
New-Item -ItemType Directory -Path dist/study_backend -Force | Out-Null
Set-Content -LiteralPath dist/study_backend/study_backend.exe -Value 'fresh owned backend fixture'
$global:LASTEXITCODE=0
''', encoding='utf-8')
    (root / 'python-fixture.ps1').write_text(r'''
param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
$command=$Arguments[0]
Add-Content -LiteralPath events.txt -Value ($Arguments -join '|')
if ($command -eq 'tools/frozen_member_licenses.py' -and $Arguments -contains '--output') {
    if ($env:SWB_LICENSE_FIXTURE_FAIL -eq '1') { $global:LASTEXITCODE=7; return }
    $output=$Arguments[[array]::IndexOf($Arguments,'--output')+1]
    Set-Content -LiteralPath $output -Value 'fresh owned license archive fixture'
}
if ($command -eq 'tools/release_inventory.py') {
    $stage=$Arguments[[array]::IndexOf($Arguments,'--stage')+1]
    $bundle=$Arguments[[array]::IndexOf($Arguments,'--python-license-bundle')+1]
    $hash=$Arguments[[array]::IndexOf($Arguments,'--python-license-sha256')+1]
    if (-not (Test-Path -LiteralPath "$stage/backend/study_backend.exe")) { throw 'Same backend not staged' }
    if ((Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw 'Bundle input changed' }
}
$global:LASTEXITCODE=0
''', encoding='utf-8')
    (root / 'compiler-fixture.ps1').write_text(r'''
Add-Content -LiteralPath events.txt -Value 'installer-fixture'
Set-Content -LiteralPath dist/StudyWorkbench-M1-setup.exe -Value 'owned installer fixture'
$global:LASTEXITCODE=0
''', encoding='utf-8')
    (root / 'webview-fixture.exe').write_bytes(b'Owned signature fixture.')
    (root / 'crt').mkdir()
    (root / 'crt/fixture.dll').write_bytes(b'Owned CRT fixture.')
    release = root / 'apps/desktop/build/windows/x64/runner/Release'
    release.mkdir(parents=True)
    (release / 'study_workbench.exe').write_bytes(b'Owned renderer fixture.')
    prebuilt = root / 'prebuilt'
    prebuilt.mkdir()
    (prebuilt / 'study_backend.exe').write_bytes(b'Owned prebuilt fixture, must not be rebuilt.')
    bundle = root / 'existing.zip'
    bundle.write_bytes(b'Owned existing archive fixture, must not be regenerated.')
    expected = hashlib.sha256(bundle.read_bytes()).hexdigest()
    extra = ''
    if mode in ('prebuilt', 'missing-hash'):
        extra = " -BackendDirectory 'prebuilt' -PythonLicenseBundle 'existing.zip'"
    elif mode == 'bundle-without-backend':
        extra = " -PythonLicenseBundle 'existing.zip'"
    elif mode == 'prebuilt-in-renderer':
        (release / 'backend').mkdir()
        (release / 'backend/study_backend.exe').write_bytes(b'Owned backend that renderer output must not replace.')
        extra = " -BackendDirectory 'apps/desktop/build/windows/x64/runner/Release/backend' -PythonLicenseBundle 'existing.zip'"
    if mode in ('prebuilt', 'bundle-without-backend', 'prebuilt-in-renderer'):
        extra += " -PythonLicenseSha256 '" + expected + "'"
    harness = r'''
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1')
function global:Get-AuthenticodeSignature { [pscustomobject]@{Status='Valid';SignerCertificate=[pscustomobject]@{Subject='Microsoft Corporation fixture'}} }
try {
    & ./packaging/windows/build-release.ps1 -Iscc './compiler-fixture.ps1' -CrtDirectory './crt' -WebViewInstaller './webview-fixture.exe' -Python './python-fixture.ps1' EXTRA
    exit 0
} catch { Write-Output $_.Exception.Message; exit 1 }
'''.replace('EXTRA', extra)
    if mode == 'collection-fails':
        harness = "$env:SWB_LICENSE_FIXTURE_FAIL='1'\n" + harness
    entry = root / 'harness.ps1'
    entry.write_text(harness, encoding='utf-8')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(entry)],
                            cwd=root, capture_output=True, text=True, timeout=45)
    events = (root / 'events.txt').read_text(encoding='utf-8-sig').splitlines() if (root / 'events.txt').exists() else []
    assert (prebuilt / 'study_backend.exe').read_bytes() == b'Owned prebuilt fixture, must not be rebuilt.'
    assert bundle.read_bytes() == b'Owned existing archive fixture, must not be regenerated.'
    if mode in ('missing-hash', 'bundle-without-backend', 'prebuilt-in-renderer'):
        assert result.returncode == 1 and not events
    elif mode == 'collection-fails':
        assert result.returncode == 1 and 'backend-build' in events
        assert not any('release_inventory' in event or 'installer-fixture' in event for event in events)
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert events[-1] == 'installer-fixture'
        collected = [event for event in events if '--output' in event]
        if mode == 'default':
            assert 'backend-build' in events and len(collected) == 1
            assert events.index('backend-build') < events.index(collected[0])
        else:
            assert 'backend-build' not in events and not collected
            assert events[0].startswith('tools/check_frozen_sources.py')
            assert '--verify-bundle' in events[1]
        assert any('release_inventory.py|--stage|' in event and '--python-license-sha256|' in event for event in events)
        assert any('check_release.py|' in event and '--python-license-sha256|' in event for event in events)
