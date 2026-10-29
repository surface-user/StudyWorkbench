"""Offline data relocation. Never remove the source or reuse a nonempty target."""
import hashlib
import json
import os
import shutil
import sqlite3
import stat
from contextlib import AbstractContextManager, closing
from itertools import zip_longest
from pathlib import Path
from uuid import uuid4


class DataLock(AbstractContextManager):
    def __init__(self, root: Path):
        try:
            root.mkdir(parents=True, exist_ok=True)
            self.file = (root / ".study.lock").open("a+b")
        except PermissionError as error:
            raise PermissionError(f"数据目录不可写：{root}。请在启动恢复入口选择可写目录；"
                                  "原目录与学习数据均保留，程序不会自动改用空库。") from error
        try:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                if self.file.read(1) == b"":
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.file.close()
            raise RuntimeError("此数据目录正在被另一个 StudyWorkbench 实例使用，请先关闭它") from error

    def __exit__(self, *args):
        self.file.close()


def write_settings(config: Path, root: Path):
    config.parent.mkdir(parents=True, exist_ok=True)
    pending = config.with_name(f"{config.name}.{uuid4().hex}.tmp")
    try:
        with pending.open("x", encoding="utf-8") as handle:
            json.dump({"version": 1, "data_dir": str(root.resolve())}, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, config)
    finally:
        if pending.exists():
            pending.unlink()


def validate_root(root: Path, install: Path | None = None):
    if not root.is_absolute():
        raise ValueError("数据目录必须使用绝对路径")
    root = root.resolve()
    if root.drive.startswith("\\\\"):
        raise ValueError("SQLite 数据目录必须位于本地磁盘，不能使用网络共享")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root.anchor)) == 4:
            raise ValueError("SQLite 数据目录必须位于本地磁盘，不能使用映射网络驱动器")
    if root == Path(root.anchor):
        raise ValueError("不能将磁盘根目录作为数据目录")
    if install and (root == install.resolve() or root.is_relative_to(install.resolve()) or install.resolve().is_relative_to(root)):
        raise ValueError("数据目录不能位于安装目录内")
    if root.exists() and not root.is_dir():
        raise ValueError("数据路径不是文件夹")
    return root


def digest(path: Path, checkpoint=lambda _: None):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            checkpoint("hashing")
            result.update(chunk)
    return result.hexdigest()


def copy_file(source: Path, target: Path, checkpoint):
    with source.open("rb") as original, target.open("xb") as copied:
        while chunk := original.read(1024 * 1024):
            checkpoint("copying-chunk")
            copied.write(chunk)
    shutil.copystat(source, target)


def relocate(source: Path, target: Path, config: Path, install: Path | None = None, checkpoint=lambda _: None):
    source = validate_root(source)
    target = validate_root(target, install)
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("新旧数据目录不能相同或互相包含")
    if config.resolve().is_relative_to(source) or config.resolve().is_relative_to(target):
        raise ValueError("启动配置必须保存在新旧数据目录之外")
    if not (source / "study.db").is_file():
        raise ValueError("原数据目录中没有学习数据库")
    if target.exists() and any(target.iterdir()):
        raise ValueError("请选择一个空文件夹；不会覆盖已有文件")
    # Hold both locks until the configuration commits. A failed copy stays in .pending for diagnosis.
    with DataLock(source), DataLock(target):
        if any(p.name != ".study.lock" for p in target.iterdir()):
            raise ValueError("目标目录已被其他程序写入，迁移已停止")
        stage = target / f".pending-{uuid4().hex}"
        stage.mkdir()
        files = []
        total = 0
        for path in source.rglob("*"):
            checkpoint("scanning")
            relative = path.relative_to(source)
            if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("数据目录包含符号链接或重解析点，迁移已停止")
            if relative.parts[0].startswith(".pending-"):
                raise ValueError("原目录含有未完成迁移，请先检查")
            if relative.as_posix() in {".study.lock", "study.db-wal", "study.db-shm", "study.db-journal"}:
                continue
            if path.is_file():
                files.append((path, relative))
                total += path.stat().st_size
        if shutil.disk_usage(target).free < total * 2 + 16 * 1024 * 1024:
            raise ValueError("目标磁盘可用空间不足（需预留校验空间）")
        manifest = {}
        for path, relative in files:
            checkpoint("copying")
            output = stage / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            if relative.as_posix() == "study.db":
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as original:
                    with closing(sqlite3.connect(output)) as copied:
                        original.backup(copied, pages=256,
                                        progress=lambda *_: checkpoint("database-backup"))
                        if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            raise RuntimeError("数据库完整性校验失败")
                        if copied.execute("PRAGMA foreign_key_check").fetchall():
                            raise RuntimeError("数据库引用校验失败")
                        for a, b in zip_longest(original.iterdump(), copied.iterdump()):
                            checkpoint("database-compare")
                            if a != b:
                                raise RuntimeError("数据库内容校验失败")
            else:
                before = digest(path, checkpoint)
                copy_file(path, output, checkpoint)
                if digest(output, checkpoint) != before or digest(path, checkpoint) != before:
                    raise RuntimeError(f"文件复制校验失败：{relative}")
            manifest[relative.as_posix()] = digest(output, checkpoint)
        checkpoint("copied")
        # Validate the copied database with the actual application before committing settings.
        from .app import create_app
        app = create_app(stage, "migration-validation-token-0000000000")
        app.state.engine.dispose()
        for name in manifest:
            manifest[name] = digest(stage / name, checkpoint)
        for entry in list(stage.iterdir()):
            os.replace(entry, target / entry.name)
        checkpoint("promoted")
        for name, expected in manifest.items():
            if digest(target / name, checkpoint) != expected:
                raise RuntimeError(f"迁移后校验失败：{name}")
        receipt = target / "migration-receipt.json"
        if receipt.exists():
            receipt = target / f"migration-receipt-{uuid4().hex}.json"
        # Keep earlier receipts intact so the new manifest still matches copied files.
        with receipt.open("x", encoding="utf-8") as handle:
            json.dump({
                "version": 1, "source": str(source), "files": manifest,
                "source_retained": True,
            }, handle, ensure_ascii=False, indent=2)
        checkpoint("validated")
        stage.rmdir()  # Only the empty staging folder, never personal data.
        write_settings(config, target)
    return {"data_dir": str(target), "file_count": len(manifest), "source_retained": True}
