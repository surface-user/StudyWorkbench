import io

import pytest
from study_workbench import __main__ as entry
from study_workbench.data_root import DataLock


def test_unwritable_session_keeps_selected_data_lock_and_warns(tmp_path, monkeypatch):
    data = tmp_path / 'selected'
    config = tmp_path / 'profile/settings.json'
    held = []

    def lock(path):
        if path == config.parent / 'session':
            raise PermissionError('profile denied')
        held.append(path)
        return DataLock(path)

    def serve(args, selected, warning=None):
        assert selected == data
        assert args.config is None  # Do not write settings without its session lock.
        assert warning and str(config) in warning
        assert held == [data]
        with pytest.raises(RuntimeError, match='实例'):
            DataLock(data)

    monkeypatch.setattr(entry, 'DataLock', lock)
    monkeypatch.setattr(entry, 'serve', serve)
    monkeypatch.setattr(entry.sys, 'argv', ['backend', '--data-dir', str(data), '--config', str(config)])
    entry.main()
    assert not config.exists()
    with DataLock(data):
        pass


def test_migration_does_not_skip_unwritable_config_lock(tmp_path, monkeypatch):
    config = tmp_path / 'profile/settings.json'
    target = tmp_path / 'target'

    def denied(path):
        raise PermissionError('profile denied')

    monkeypatch.setattr(entry, 'DataLock', denied)
    monkeypatch.setattr(entry.sys, 'argv', [
        'backend', '--data-dir', str(tmp_path / 'source'), '--config', str(config), '--move-data', str(target)])
    with pytest.raises(PermissionError, match='profile denied'):
        entry.main()
    assert not target.exists()


def test_busy_profile_is_not_treated_as_unwritable(tmp_path, monkeypatch):
    config = tmp_path / 'profile/settings.json'
    monkeypatch.setattr(entry.sys, 'argv', ['backend', '--data-dir', str(tmp_path / 'data'), '--config', str(config)])
    with DataLock(config.parent / 'session'), pytest.raises(RuntimeError, match='实例'):
        entry.main()


def test_failed_settings_write_retains_old_config_and_returns_warning(tmp_path, monkeypatch, capsys):
    import json
    from types import SimpleNamespace

    config = tmp_path / 'settings.json'
    config.write_text('old config', encoding='utf-8')
    disposed = []

    def denied(*args):
        raise PermissionError('readonly settings')

    class Server:
        should_exit = False

        def __init__(self, *args):
            pass

        async def serve(self, **kwargs):
            pass

    monkeypatch.setattr(entry, 'write_settings', denied)
    monkeypatch.setattr(entry, 'create_app', lambda *args: disposed.append(args))
    monkeypatch.setattr(entry.uvicorn, 'Server', Server)
    monkeypatch.setattr(entry.uvicorn, 'Config', lambda *args, **kwargs: None)
    monkeypatch.setattr(entry.sys, 'stdin', io.StringIO('{"token":"test-startup-settings-token-000000000"}\n'))
    entry.serve(SimpleNamespace(config=config, media=None), tmp_path / 'selected')
    hello = json.loads(capsys.readouterr().out)
    assert hello['api_version'] == 0 and hello['port'] > 0
    assert str(config) in hello['startup_warning']
    assert '未保存' in hello['startup_warning']
    assert config.read_text(encoding='utf-8') == 'old config'
    assert disposed[0][0] == tmp_path / 'selected'
