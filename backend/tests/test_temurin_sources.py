import hashlib
import importlib
import io
import json
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    return importlib.import_module('temurin_sources')


def source_inputs(tool, tmp_path, monkeypatch, error=None):
    files = {key: tmp_path / key for key in tool.PINS}
    root = f'jdk-{tool.VERSION}-src/'
    entries = dict.fromkeys(tool.WINDOWS_SOURCES, b'synthetic')
    entries.update({'src/java.base/share/classes/module-info.java': b'module java.base {}',
                    'src/jdk.crypto.mscapi/windows/classes/module-info.java': b'module jdk.crypto.mscapi {}',
                    'LICENSE': b'common', 'src/jdk.crypto.mscapi/windows/legal/example.md': b'example'})
    if error == 'windows':
        entries.pop('src/hotspot/os/windows/os_windows.cpp')
    if error == 'descriptor':
        entries.pop('src/jdk.crypto.mscapi/windows/classes/module-info.java')
    with tarfile.open(files['sources'], 'w:gz') as archive:
        for name, content in entries.items():
            member = tarfile.TarInfo(root + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    with ZipFile(files['jre'], 'w') as archive:
        prefix = tool.ARCHIVE_ROOT + '/'
        archive.writestr(prefix + 'release', f'SOURCE=".:git:{tool.JDK_COMMIT[:12]}"\nBUILD_SOURCE="git:{tool.BUILD_COMMIT}"')
        archive.writestr(prefix + 'NOTICE', b'root notice')
        archive.writestr(prefix + 'legal/java.base/LICENSE', b'common')
        archive.writestr(prefix + 'legal/jdk.crypto.mscapi/LICENSE', b'Please see ../java.base/LICENSE')
        archive.writestr(prefix + 'legal/jdk.crypto.mscapi/example.md', b'changed' if error == 'notice' else b'example')
    with ZipFile(files['build_sources'], 'w') as archive:
        prefix = f'temurin-build-{tool.BUILD_COMMIT}/'
        archive.writestr(prefix + 'makejdk-any-platform.sh', b'build')
        archive.writestr(prefix + 'sbin/NOTICE.template', b'different' if error == 'root' else b'root notice')
    for kind in ('jre', 'sources'):
        metadata = {'binary_type': kind, 'variant': 'temurin', 'os': 'windows' if kind == 'jre' else 'linux',
                    'arch': 'x64', 'sha256': hashlib.sha256(files[kind].read_bytes()).hexdigest(),
                    'scmRef': f'jdk-{tool.VERSION}_adopt',
                    'openjdk_source': 'https://github.com/adoptium/jdk21u/commit/' + tool.JDK_COMMIT,
                    'buildRef': 'https://github.com/adoptium/temurin-build/commit/' + tool.BUILD_COMMIT}
        if error == 'commit' and kind == 'sources':
            metadata['openjdk_source'] += '0'
        files[kind + '_metadata'].write_text(json.dumps(metadata))
    monkeypatch.setattr(tool, 'PINS', {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()})
    return files


def test_archives_and_metadata_link_windows_jre_to_offline_sources(tool, tmp_path, monkeypatch):
    files = source_inputs(tool, tmp_path, monkeypatch)
    result = tool.verify(files)
    assert result['jreLegalModulesWithDescriptor'] == result['matchedDirectModuleTexts'] == 2
    assert result['matchedRootNotice'] and not result['distributionInspected']
    files['sources'].write_bytes(b'truncated')
    with pytest.raises(ValueError, match='pinned input'):
        tool.verify(files)


@pytest.mark.parametrize('error', ['windows', 'descriptor', 'notice', 'root', 'commit'])
def test_partial_or_mismatched_source_evidence_is_rejected(tool, tmp_path, monkeypatch, error):
    with pytest.raises(ValueError):
        tool.verify(source_inputs(tool, tmp_path, monkeypatch, error))
