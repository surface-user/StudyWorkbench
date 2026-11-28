import hashlib
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    tool = importlib.import_module('temurin_source_delivery')
    root = tmp_path / 'stage'
    root.mkdir()
    inputs = []
    for kind in ('sources', 'build_sources'):
        path = tmp_path / kind
        path.write_bytes(kind.encode())
        inputs.append(path)
        monkeypatch.setitem(tool.PINS, kind, hashlib.sha256(path.read_bytes()).hexdigest())
    return tool, root, inputs


def test_stage_requires_matching_optional_jre(delivery):
    tool, root, inputs = delivery
    with pytest.raises(FileNotFoundError):
        tool.stage(root, *inputs)
    assert not (root / tool.DEST).exists()


def test_stage_rejects_wrong_archive_before_publishing(delivery, monkeypatch):
    tool, root, inputs = delivery
    monkeypatch.setattr(tool, 'check_java', lambda _: None)
    inputs[1].write_bytes(b'truncated')
    with pytest.raises(ValueError, match='input archive'):
        tool.stage(root, *inputs)
    assert not (root / tool.DEST).parent.exists()


@pytest.mark.parametrize('damage', ['missing', 'extra', 'manifest', 'archive'])
def test_stage_then_verify_optional_installed_sources(delivery, monkeypatch, damage):
    tool, root, inputs = delivery
    monkeypatch.setattr(tool, 'check_java', lambda _: None)
    tool.stage(root, *inputs)
    target = root / tool.DEST
    tool.check_files(target)
    with pytest.raises(ValueError, match='already exists'):
        tool.stage(root, *inputs)
    if damage == 'missing':
        (target / tool.BUILD).unlink()
    elif damage == 'extra':
        (target / 'extra').touch()
    else:
        name = 'manifest.json' if damage == 'manifest' else tool.OPENJDK
        (target / name).write_bytes(b'changed')
    with pytest.raises(ValueError):
        tool.check_files(target)
