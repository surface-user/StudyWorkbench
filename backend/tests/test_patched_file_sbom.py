import importlib.util
import json
from pathlib import Path

import pytest


def test_backend_sbom_retains_each_file_and_refuses_other_inputs(tmp_path):
    report = Path(__file__).parents[2] / 'dev/records/2026-11-20-patched-backend-sbom/export_sbom.py'
    spec = importlib.util.spec_from_file_location('patched_file_sbom', report)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    payload = tmp_path / 'stage'
    payload.mkdir()
    (payload / 'one.dll').write_bytes(b'generated sample')
    (payload / 'two.dll').write_bytes(b'generated sample')
    files = tool.inventory(payload)
    fingerprint = tool.digest(json.dumps(files, sort_keys=True).encode())
    head = 'a' * 40
    coverage = dict(physical_files=files, input_fingerprint=fingerprint, source_head_assertion=head)
    coverage_path = tmp_path / 'coverage.json'
    coverage_path.write_text(json.dumps(coverage))
    purl = 'pkg:pypi/example@1.0'
    bom = json.dumps({'components': [{'type': 'library', 'name': 'example', 'version': '1.0',
                                     'purl': purl, 'bom-ref': purl}]}).encode()
    (tmp_path / 'python-origins.cdx.json').write_bytes(bom)
    origins = dict(coverage_sha256=tool.digest(coverage_path.read_bytes()), payload_fingerprint=fingerprint,
                   bom_sha256=tool.digest(bom), source_head_assertion=head)
    (tmp_path / 'origins.json').write_text(json.dumps(origins))
    output = tmp_path / 'backend.cdx.json'
    assert tool.export(payload, coverage_path, tmp_path, output)['files'] == 2
    result = json.loads(output.read_bytes())
    assert [c['name'] for c in result['components']] == ['example', 'one.dll', 'two.dll']
    assert result['components'][1]['hashes'] == result['components'][2]['hashes']
    assert result['compositions'][0]['aggregate'] == 'incomplete'
    with pytest.raises(FileExistsError):
        tool.export(payload, coverage_path, tmp_path, output)
    with pytest.raises(ValueError, match='outside'):
        tool.export(payload, coverage_path, tmp_path, payload / 'out')
    (payload / 'two.dll').write_bytes(b'changed')
    with pytest.raises(ValueError, match='same build'):
        tool.export(payload, coverage_path, tmp_path, tmp_path / 'new')
    assert not (tmp_path / 'new').exists()
