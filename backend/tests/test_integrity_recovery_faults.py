import json
from types import SimpleNamespace

import pytest
from study_workbench import backup_store as store
from study_workbench.data_root import write_settings
from test_backup_store import library, preserved_files


@pytest.mark.parametrize('failure', ['late_edit', 'late_disk_full', 'cleanup_denied'])
def test_restore_faults_preserve_old_library_and_distinguish_activation_from_cleanup(tmp_path, monkeypatch, failure):
    source, target = tmp_path / 'source', tmp_path / 'target'
    package, config = tmp_path / 'backup.zip', tmp_path / 'profile/settings.json'
    _, original = library(source)
    write_settings(config, source)
    store.create_backup(source, package)
    before = ((source / 'study.db').read_bytes(), preserved_files(source), config.read_bytes())
    promoted_original = target / original.relative_to(source)
    promoting = [False]
    disk_usage = store.shutil.disk_usage

    def checkpoint(stage):
        if stage == 'promoting-chunk':
            promoting[0] = True
        if failure == 'late_edit' and stage == 'before-settings':
            promoted_original.write_bytes(b'external change after validation')

    if failure == 'late_disk_full':
        monkeypatch.setattr(store.shutil, 'disk_usage',
                            lambda path: SimpleNamespace(free=0) if promoting[0] else disk_usage(path))
    if failure == 'cleanup_denied':
        def denied(*_):
            raise PermissionError('Simulated retained staging directory')
        monkeypatch.setattr(store, 'clean_owned_stage', denied)
        result = store.restore_backup(package, target, config, checkpoint=checkpoint)
        assert result['data_activated'] is True and result['cleanup_pending'] is True
        assert json.loads(config.read_text())['data_dir'] == str(target)
        assert promoted_original.read_bytes() == original.read_bytes()
    else:
        with pytest.raises(ValueError, match='空间不足|激活前'):
            store.restore_backup(package, target, config, checkpoint=checkpoint)
        assert config.read_bytes() == before[2]
        if failure == 'late_edit':
            assert promoted_original.read_bytes() == b'external change after validation'
    assert ((source / 'study.db').read_bytes(), preserved_files(source)) == before[:2]
    assert list(target.glob('.restore-pending-*'))


def test_backup_stops_when_source_changes_during_packing_without_undoing_external_edit(tmp_path):
    source, package = tmp_path / 'source', tmp_path / 'backup.zip'
    _, original = library(source)
    database = (source / 'study.db').read_bytes()
    changed = [False]

    def edit(stage):
        if stage == 'packing-file' and not changed[0]:
            original.write_bytes(b'external edit during backup')
            changed[0] = True

    with pytest.raises(ValueError):
        store.create_backup(source, package, checkpoint=edit)
    assert changed[0] and not package.exists()
    assert original.read_bytes() == b'external edit during backup'
    assert (source / 'study.db').read_bytes() == database
    assert list(tmp_path.glob('.backup-pending-*'))
