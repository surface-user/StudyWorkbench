import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from study_workbench.app import create_app
from study_workbench.data_root import DataLock, digest, relocate, validate_root, write_settings

TOKEN = "test-relocation-token-00000000000000000"


def test_denied_lock_creation_reports_directory_without_deleting_data(tmp_path, monkeypatch):
    original = tmp_path / 'personal.txt'
    original.write_text('retained', encoding='utf-8')
    real_open = Path.open

    def denied(path, *args, **kwargs):
        if path.name == '.study.lock':
            raise PermissionError('injected access denied')
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', denied)
    with pytest.raises(PermissionError, match='数据目录不可写') as result:
        DataLock(tmp_path)
    assert str(tmp_path) in str(result.value)
    assert original.read_text(encoding='utf-8') == 'retained'
    assert not (tmp_path / '.study.lock').exists()


def prepare(root):
    with TestClient(create_app(root, TOKEN), base_url="http://127.0.0.1",
                    headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        client.post("/api/attempts", json={"question_id": "demo-proof", "response": {"text": "保留中文作答"}}).raise_for_status()
    (root / "原文件").mkdir()
    (root / "原文件" / "sample.txt").write_text("原件，不可删除", encoding="utf-8")


def test_relocate_unicode_files_database_and_config(tmp_path):
    source, target, config = tmp_path / "旧目录", tmp_path / "new space 中文", tmp_path / "config.json"
    prepare(source)
    before = digest(source / "study.db")
    write_settings(config, source)
    result = relocate(source, target, config)
    assert result["source_retained"]
    assert digest(source / "study.db") == before
    assert (source / "原文件" / "sample.txt").read_bytes() == (target / "原文件" / "sample.txt").read_bytes()
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(target)
    with sqlite3.connect(target / "study.db") as db:
        assert json.loads(db.execute("SELECT response FROM attempts").fetchone()[0])["text"] == "保留中文作答"
    receipt = json.loads((target / "migration-receipt.json").read_text(encoding="utf-8"))
    assert receipt["files"]["study.db"] == digest(target / "study.db")
    assert not list(target.glob(".pending-*"))


@pytest.mark.parametrize("stage", [
    "copying", "hashing", "copying-chunk", "database-backup", "database-compare",
    "copied", "promoted", "validated",
])
def test_relocation_failure_preserves_source_and_old_config(tmp_path, stage):
    source, target, config = tmp_path / "source", tmp_path / "target", tmp_path / "config.json"
    prepare(source)
    write_settings(config, source)
    before = digest(source / "study.db")

    def interrupt(point):
        if point == stage:
            raise OSError("injected copy/validation failure")

    with pytest.raises(OSError, match="injected"):
        relocate(source, target, config, checkpoint=interrupt)
    assert digest(source / "study.db") == before
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(source)
    assert target.exists()  # Failed evidence stays; no cleanup of user data.
    with DataLock(source):
        pass  # Failure releases the lock.


def test_data_lock_and_unsafe_targets(tmp_path):
    source, target, config = tmp_path / "source", tmp_path / "target", tmp_path / "config.json"
    prepare(source)
    with DataLock(source):
        with pytest.raises(RuntimeError, match="实例"):
            relocate(source, target, config)
    for path in (source, source / "child", tmp_path, Path(source.anchor)):
        with pytest.raises(ValueError):
            relocate(source, path, config)
    target.mkdir(exist_ok=True)
    (target / "personal.txt").write_text("untouched")
    with pytest.raises(ValueError, match="空文件夹"):
        relocate(source, target, config)
    assert (target / "personal.txt").read_text() == "untouched"
    with pytest.raises(ValueError, match="安装目录"):
        validate_root(tmp_path / "program" / "data", tmp_path / "program")
    with pytest.raises(ValueError, match="绝对"):
        validate_root(Path("relative"))


def test_config_commit_failure_does_not_switch_or_delete(tmp_path, monkeypatch):
    from study_workbench import data_root
    source, target, config = tmp_path / "source", tmp_path / "target", tmp_path / "config.json"
    prepare(source)
    write_settings(config, source)

    def fail(*args):
        raise PermissionError("config readonly")

    monkeypatch.setattr(data_root, "write_settings", fail)
    with pytest.raises(PermissionError):
        relocate(source, target, config)
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(source)
    assert (source / "study.db").is_file()
    assert (target / "study.db").is_file()


def test_out_of_space_and_corrupt_copy_never_switch_config(tmp_path, monkeypatch):
    from study_workbench import data_root
    source, target, config = tmp_path / "source", tmp_path / "target", tmp_path / "config.json"
    prepare(source)
    write_settings(config, source)
    original_space = data_root.shutil.disk_usage
    monkeypatch.setattr(data_root.shutil, "disk_usage", lambda _: type("Space", (), {"free": 0})())
    with pytest.raises(ValueError, match="空间不足"):
        relocate(source, target, config)
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(source)
    monkeypatch.setattr(data_root.shutil, "disk_usage", original_space)
    monkeypatch.setattr(data_root, "copy_file", lambda original, output, checkpoint: output.write_bytes(b"corrupted"))
    with pytest.raises(RuntimeError, match="复制校验失败"):
        relocate(source, tmp_path / "target2", config)
    assert (source / "原文件" / "sample.txt").read_text(encoding="utf-8") == "原件，不可删除"
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(source)


def test_atomic_config_replace_failure_preserves_previous_file(tmp_path, monkeypatch):
    from study_workbench import data_root
    config = tmp_path / "settings.json"
    write_settings(config, tmp_path / "original")
    original = config.read_bytes()

    def reject(*args):
        raise PermissionError("injected atomic replace failure")

    monkeypatch.setattr(data_root.os, "replace", reject)
    with pytest.raises(PermissionError, match="atomic replace"):
        write_settings(config, tmp_path / "new")
    assert config.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_repeated_relocation_preserves_receipts_and_valid_hashes(tmp_path):
    source, middle, target = (tmp_path / name for name in ("source", "middle", "target"))
    config = tmp_path / "settings.json"
    prepare(source)
    relocate(source, middle, config)
    original_receipt = (middle / "migration-receipt.json").read_bytes()
    relocate(middle, target, config)
    for receipt in target.glob("migration-receipt*.json"):
        document = json.loads(receipt.read_text(encoding="utf-8"))
        for name, expected in document["files"].items():
            assert digest(target / name) == expected, name
    assert (target / "migration-receipt.json").read_bytes() == original_receipt
    assert len(list(target.glob("migration-receipt*.json"))) == 2


def test_cancel_during_large_file_leaves_partial_copy_and_old_config(tmp_path):
    source, target, config = tmp_path / "source", tmp_path / "target", tmp_path / "settings.json"
    prepare(source)
    original = source / "原文件" / "sample.txt"
    original.write_bytes(b"original-content" * 220000)
    before = digest(original)
    write_settings(config, source)
    chunks = 0

    def parent_exited(point):
        nonlocal chunks
        if point == "copying-chunk":
            chunks += 1
            if chunks == 2:
                raise RuntimeError("parent exited during file copy")

    with pytest.raises(RuntimeError, match="parent exited"):
        relocate(source, target, config, checkpoint=parent_exited)
    partial = list(target.glob(".pending-*/原文件/sample.txt"))
    assert len(partial) == 1
    assert 0 < partial[0].stat().st_size < original.stat().st_size
    assert digest(original) == before
    assert json.loads(config.read_text(encoding="utf-8"))["data_dir"] == str(source)
    with DataLock(source), DataLock(target):
        pass


@pytest.mark.skipif(os.name != "nt", reason="Windows mapped-drive API")
def test_mapped_network_drive_is_rejected(tmp_path, monkeypatch):
    import ctypes

    anchors = []

    def remote_drive(anchor):
        anchors.append(anchor.value)
        return 4  # DRIVE_REMOTE, including mapped drive letters without a UNC prefix.

    monkeypatch.setattr(ctypes.windll.kernel32, "GetDriveTypeW", remote_drive)
    with pytest.raises(ValueError, match="本地磁盘"):
        validate_root(tmp_path / "mapped-data")
    assert anchors == [tmp_path.anchor]
