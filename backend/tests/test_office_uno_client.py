import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('check_office_uno_client')


def test_native_server_exposes_one_service_with_only_fixed_bootstrap_settings(checker, tmp_path):
    runtime = SimpleNamespace(root=tmp_path, command=lambda *_: [
        'soffice.com', '-env:UNO_TYPES=project-registry', '--headless', '--convert-to', 'pdf', 'ordinary.docx'])
    pipe, instance = '1' * 32, 'a' * 32
    assert checker.server_command(runtime, tmp_path, pipe, instance) == [
        str(tmp_path / 'program/uno.exe'), '-env:UNO_TYPES=project-registry',
        '-env:LO_LIB_DIR=' + (tmp_path / 'program').as_uri(), '-s', 'com.sun.star.util.URLTransformer',
        '-u', f'uno:pipe,name=StudyWorkbench{pipe};urp;Probe{instance}', '--singleaccept', '--quiet']


@pytest.mark.parametrize(('pipe', 'instance'), [
    ('x' * 32, 'a' * 32), ('a' * 31, 'b' * 32), ('a' * 32, 'uno.ComponentContext'),
    ('a' * 32, 'a' * 32), ('a' * 32, 'b' * 32 + ';socket')])
def test_foreign_endpoint_or_reused_identifier_rejected(checker, pipe, instance):
    with pytest.raises(ValueError, match='distinct'):
        checker.server_command(None, None, pipe, instance)


def test_client_source_and_rpc_receipt_are_bound(checker, tmp_path):
    original = checker.fixed_probe_source(checker.CLIENT_SOURCE, checker.CLIENT_SHA256)
    copy = tmp_path / 'client.java'
    copy.write_bytes(original + b' ')
    with pytest.raises(ValueError, match='source changed'):
        checker.fixed_probe_source(copy, checker.CLIENT_SHA256)
    receipt = tmp_path / 'ready'
    raw = b'11\ncom.sun.star.comp.framework.URLTransformer\nparseStrict\nassemble\n'
    receipt.write_bytes(raw)
    checker.check_receipt(receipt, 11)
    for wrong in (raw.replace(b'11', b'12'), raw.replace(b'parseStrict', b''), raw + b'x' * 2000):
        receipt.write_bytes(wrong)
        with pytest.raises(ValueError, match='receipt'):
            checker.check_receipt(receipt, 11)
