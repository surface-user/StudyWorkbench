import importlib
import sys
from pathlib import Path

import pytest


def test_probe_is_opt_in_before_starting_or_creating_data(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('check_bilibili_previews')
    target = tmp_path / 'must-not-create'
    monkeypatch.setattr(sys, 'argv', ['check_bilibili_previews', '--test-root', str(target)])
    monkeypatch.setattr(tool.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('Not opted in'))
    with pytest.raises(SystemExit) as error:
        tool.main()
    assert error.value.code == 2 and not target.exists()


def test_probe_private_field_check_covers_nested_formats(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('check_bilibili_previews')
    tool.no_private_fields({'result': {'formats': [{'format_id': 'video-0', 'size_bytes': None}]}})
    with pytest.raises(AssertionError):
        tool.no_private_fields({'result': {'formats': [{'url': 'https://private.invalid/?token=fixture'}]}})
