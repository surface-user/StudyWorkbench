import importlib
import json
import struct
import subprocess
from pathlib import Path

import pytest

# Brotli encoding of a generated HTML fixture with two same-name entries and one empty license.
COMPRESSED = bytes.fromhex(
    '1bb701601c07ce39ea74887dc4d8713a494f169bafb3a76ef36e28920724a815405a84c07fee40e8cc'
    'afdb5e9605d41626f0a3e22ca10438e7266350c7192c4df05c152a4b3b39e778aef5bb9f138d87d86fc'
    '5c2627665715bee27ab815cb1d9080dd71909bc92bb49b080d4412fc5e81117ba0d2c88583f42f361bb3f2586ba09')


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('webview_license_evidence')


def resource(content, size=440):
    payload = b'\x1e\x9b' + size.to_bytes(6, 'little') + content
    return struct.pack('<8I', 5, 1, 1, 0, 70, 32, 0, 32 + len(payload)) + payload


def test_exact_credits_entries_and_empty_text(tool):
    data = tool.resource_member(resource(COMPRESSED), 70)
    rows = tool.credit_rows(data)
    assert [row['name'] for row in rows] == ['Example', 'Example', 'Empty']
    assert [row['ordinal'] for row in rows] == [1, 2, 3]
    assert [row['text_present'] for row in rows] == [True, True, False]
    assert rows[0]['license_text'] == 'A & B\n'
    assert rows[0]['text_sha256'] == rows[1]['text_sha256'] == tool.sha256(b'A & B\n')
    for broken in (data.replace(b'Credits', b'Other'), data.replace(b'class="title"', b'class="other"'),
                   data.replace(b'class="product"', b'class="box"')):
        with pytest.raises(ValueError):
            tool.credit_rows(broken)


@pytest.mark.parametrize('fault', ['header', 'table', 'order', 'offset', 'trailer', 'signature', 'large', 'unknown',
                                   'short-body', 'long-body', 'bad-stream'])
def test_broken_resource_is_rejected(tool, fault):
    data = bytearray(resource(COMPRESSED))
    changes = {'table': (8, 200000), 'order': (16, 0), 'offset': (20, 5), 'trailer': (28, 100)}
    identifier = 70
    if fault in changes:
        offset, value = changes[fault]
        struct.pack_into('<I', data, offset, value)
    elif fault == 'header':
        data = data[:4]
    elif fault == 'signature':
        data[32:34] = b'XX'
    elif fault == 'unknown':
        identifier += 1
    elif fault == 'bad-stream':
        data = resource(b'broken')
    else:
        data = resource(COMPRESSED, {'large': tool.MAX_HTML + 1, 'short-body': 441, 'long-body': 439}[fault])
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        tool.resource_member(data, identifier)


@pytest.fixture
def case(tmp_path, tool):
    setup, runtime, pack, notice, bom = [tmp_path / n for n in ('setup', 'outer', 'pack', 'notice', 'bom')]
    for file, raw in ((setup, b'setup'), (runtime, b'outer'), (pack, resource(COMPRESSED)), (notice, b'notice')):
        file.write_bytes(raw)
    def entry(name, data, parent=None):
        c = {'bom-ref': 'file:' + name, 'name': name, 'type': 'file',
             'hashes': [{'alg': 'SHA-256', 'content': tool.sha256(data)}]}
        if parent:
            c['properties'] = [{'name': 'studyworkbench:container', 'value': 'file:' + parent}]
        return c
    nested = 'webview2-updater/nested.exe'
    ref = 'webview2-updater/NOTICE.TXT'
    components = [entry(tool.OUTER, runtime.read_bytes()), entry(nested, b'nested', tool.OUTER),
                  entry(tool.PACKED, b'compressed', nested), entry(tool.INNER, b'inner', tool.PACKED),
                  entry('webview2-runtime/Chrome-bin/1.2.3.4/resources.pak', pack.read_bytes(), tool.INNER),
                  entry(ref, notice.read_bytes(), tool.OUTER),
                  {'bom-ref': 'runtime', 'type': 'application', 'name': 'Microsoft Edge WebView2 Runtime',
                   'version': '1.2.3.4', 'evidence': {'occurrences': [{'location': tool.OUTER}]}}]
    digest = tool.file_digest(setup)
    data = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': components,
            'metadata': {'component': {'bom-ref': 'setup:' + digest, 'hashes': [{'alg': 'SHA-256','content': digest}]}}}
    def write():
        bom.write_text(json.dumps(data), encoding='utf-8')
        return tool.file_digest(bom)
    return tool, data, write, [bom, write(), setup, runtime, pack, 70, [(ref, notice)]]


@pytest.mark.parametrize('fault', ['none', 'bom', 'setup', 'outer', 'pack', 'notice', 'duplicate-ref',
                                   'bad-parent', 'bad-version', 'duplicate-notice', 'unknown-notice'])
def test_evidence_must_match_actual_files_and_container_links(case, fault):
    tool, data, write, args = case
    components = data['components']
    if fault in ('setup', 'outer', 'pack'):
        args[{'setup': 2, 'outer': 3, 'pack': 4}[fault]].write_bytes(b'other')
    elif fault == 'bom':
        args[1] = '0' * 64
    elif fault == 'notice':
        args[-1][0][1].write_bytes(b'other')
    elif fault == 'duplicate-notice':
        args[-1] *= 2
    elif fault == 'unknown-notice':
        args[-1][0] = ('unlisted', args[-1][0][1])
    elif fault in ('duplicate-ref', 'bad-parent', 'bad-version'):
        if fault == 'duplicate-ref':
            components.append(components[0])
        elif fault == 'bad-parent':
            components[3]['properties'][0]['value'] = 'file:' + tool.OUTER
        else:
            components[-1]['version'] = '../../oops'
        args[1] = write()
    if fault == 'none':
        result = tool.generate(*args)
        assert result['selected_notices'] == {'webview2-updater/NOTICE.TXT': {'sha256': tool.sha256(b'notice'), 'bytes': 6}}
        assert len(result['missing_selected_notices']) == 3
        assert len(result['entries']) == 3 and not result['redistribution_review_complete']
        assert str(args[0].parent) not in json.dumps(result)
    else:
        with pytest.raises(ValueError):
            tool.generate(*args)
