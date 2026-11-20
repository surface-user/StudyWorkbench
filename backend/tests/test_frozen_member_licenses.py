import importlib
import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('frozen_member_licenses')
    stage = tmp_path / 'sample'
    stage.mkdir()
    (stage / 'sample.bin').write_bytes(b'generated fixture')
    fingerprint = tool.sha256(json.dumps(tool.inventory(stage), sort_keys=True).encode())
    origins = tmp_path / 'origins'
    (origins / 'local-members').mkdir(parents=True)
    proof = {'metadata_sha256': 'meta', 'record_sha256': 'record', 'status': 'has_verified_local_members'}
    members = dict(source_head_assertion='a' * 40, payload_fingerprint=fingerprint,
                   member_packages=['pkg:pypi/one@1', 'pkg:pypi/two@1'],
                   build_packages={p: proof for p in ('pkg:pypi/one@1', 'pkg:pypi/two@1')})
    raw = json.dumps(members).encode()
    (origins / 'local-members/members.json').write_bytes(raw)
    (origins / 'origins.json').write_text(json.dumps(dict(source_head_assertion='a' * 40,
                payload_fingerprint=fingerprint, base_members_sha256=tool.sha256(raw))))

    def evidence(identity, target, source):
        data = b'license example'
        digest = tool.sha256(data)
        (target / 'texts' / digest).write_bytes(data)
        return {'files': [{'sha256': digest, 'text_path': 'texts/' + digest}], 'metadata_sha256': 'meta',
                'record_sha256': 'record', 'issues': ['unresolved'] if identity['name'] == 'two' else []}

    monkeypatch.setattr(tool, 'python_evidence', evidence)
    return tool, stage, origins


def test_shared_license_bytes_and_each_package_observation_survive(sample, tmp_path):
    tool, stage, origins = sample
    output = tmp_path / 'one.zip'
    result = tool.collect(stage, origins, tmp_path, output)
    assert result == dict(packages=2, unique_texts=1, text_references=2, packages_with_issues=1,
                          sha256=tool.sha256(output.read_bytes()))
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None and len(z.namelist()) == 2
        index = json.loads(z.read('index.json'))
        for p in index['packages'].values():
            row = p['files'][0]
            assert tool.sha256(z.read(row['text_path'])) == row['sha256']
        assert not index['distribution_obligations_reviewed']
    repeated = tmp_path / 'two.zip'
    assert tool.collect(stage, origins, tmp_path, repeated) == result and repeated.read_bytes() == output.read_bytes()
    with pytest.raises(FileExistsError):
        tool.collect(stage, origins, tmp_path, output)


def test_refuse_unbound_metadata_and_payload_without_creating_bundle(sample, tmp_path, monkeypatch):
    tool, stage, origins = sample
    target = tmp_path / 'out.zip'
    with pytest.raises(ValueError, match='outside'):
        tool.collect(stage, origins, tmp_path, stage / 'out.zip')
    monkeypatch.setattr(tool, 'python_evidence', lambda *args: {'files': [], 'metadata_sha256': 'other'})
    with pytest.raises(ValueError, match='License source'):
        tool.collect(stage, origins, tmp_path, target)
    (stage / 'sample.bin').write_bytes(b'different')
    with pytest.raises(ValueError, match='same frozen'):
        tool.collect(stage, origins, tmp_path, target)
    assert not target.exists()
