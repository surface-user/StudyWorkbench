import argparse
import asyncio
import json
import socket
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path

import uvicorn

from .app import create_app
from .data_root import DataLock, relocate, validate_root, write_settings


def main():
    if len(sys.argv) == 5 and sys.argv[1] == '--launch-office':
        from .office_runtime import launch_office
        raise SystemExit(launch_office(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
    if sys.argv[1:] == ['--download-media']:
        from .media_download_worker import worker
        worker()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--inspect-backup':
        from .backup_archive import inspect_archive
        manifest = inspect_archive(Path(sys.argv[2]))
        print(json.dumps({'format': manifest['format'], 'version': manifest['version'],
                          'schema_revision': manifest['schema_revision'], 'file_count': len(manifest['files']),
                          'total_bytes': sum(item['size'] for item in manifest['files']),
                          'payload_integrity_verified': True, 'database_semantics_checked': False,
                          'data_activated': False}), flush=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--view-document':
        from .document_view_worker import worker
        worker(sys.argv[2])
        return
    if len(sys.argv) == 3 and sys.argv[1] == "--parse-document":
        from .documents import worker
        worker(sys.argv[2])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--media", type=Path)
    parser.add_argument("--config", type=Path)
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("--move-data", type=Path)
    operations.add_argument('--backup-to', type=Path)
    operations.add_argument('--restore-backup', type=Path)
    operations.add_argument('--check-library', action='store_true')
    parser.add_argument('--confirm-all-workspaces', action='store_true')
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--parent-pipe", action="store_true")
    args = parser.parse_args()
    install = args.install_dir
    if getattr(sys, "frozen", False):
        install = Path(sys.executable).resolve().parent.parent
    if args.check_library:
        if not args.confirm_all_workspaces or args.config or args.media or args.parent_pipe:
            raise ValueError('巡检须确认全部空间，且不接受配置、媒体或父管道参数')
        from .library_integrity import check_library
        result = check_library(args.data_dir, install=install)
        print(json.dumps({'result': result}), flush=True)
        raise SystemExit(0 if result['healthy'] else 1)
    data = validate_root(args.data_dir, install)
    if args.backup_to or args.restore_backup:
        from .backup_store import create_backup, no_links, restore_backup
        no_links(args.data_dir)
        cancelled = threading.Event()
        if args.parent_pipe:
            def offline_parent():
                sys.stdin.read()
                cancelled.set()
            threading.Thread(target=offline_parent, daemon=True).start()
        last_stage = None
        last_report = 0.0
        def checkpoint(stage):
            nonlocal last_stage, last_report
            if cancelled.is_set():
                raise RuntimeError('离线操作已取消；旧数据/配置和未完成字节保留')
            now = time.monotonic()
            if stage != last_stage and now - last_report >= .2:
                print(json.dumps({'stage': stage}), flush=True)
                last_stage = stage
                last_report = now
        if args.backup_to:
            if not args.confirm_all_workspaces:
                raise ValueError('备份包含全部空间及归档学习数据，必须显式确认')
            with ExitStack() as locks:
                if args.config:
                    if not args.config.is_absolute():
                        raise ValueError('配置路径必须为绝对路径')
                    locks.enter_context(DataLock(args.config.parent / 'session'))
                result = create_backup(data, args.backup_to, install=install, checkpoint=checkpoint)
        else:
            if not args.config:
                raise ValueError('恢复必须提供外部启动配置路径')
            result = restore_backup(args.restore_backup, data, args.config, install=install, checkpoint=checkpoint)
        print(json.dumps({'result': result}), flush=True)
        return
    if data.is_dir() and not (data / "study.db").exists() and any(p.name != ".study.lock" for p in data.iterdir()):
        raise ValueError("请选择空数据文件夹或已有 StudyWorkbench 数据目录，不会混入其他文件")
    warning = None
    with ExitStack() as locks:
        if args.config:
            if not args.config.is_absolute():
                raise ValueError("配置路径必须为绝对路径")
            try:
                locks.enter_context(DataLock(args.config.parent / "session"))
            except OSError:
                if args.move_data:
                    raise  # Migration must commit settings while holding the profile lock.
                warning = settings_warning(args.config)
                args.config = None  # Never write settings without the profile lock.
        if args.move_data:
            if not args.config:
                raise ValueError("迁移必须提供配置路径")
            cancelled = threading.Event()
            if args.parent_pipe:
                def parent_lifetime():
                    sys.stdin.read()
                    cancelled.set()
                threading.Thread(target=parent_lifetime, daemon=True).start()

            def checkpoint(_):
                if cancelled.is_set():
                    raise RuntimeError("桌面进程已退出，迁移已停止，旧数据和原配置保留")

            print(json.dumps(relocate(data, args.move_data, args.config, install, checkpoint)), flush=True)
            return
        locks.enter_context(DataLock(data))
        serve(args, data, warning)


def settings_warning(config):
    return (f"启动配置不可写：{config}。本次数据位置未保存；学习数据仍保存在所选目录，"
            "下次启动可能需要重新选择此目录，或仍使用原配置中的位置。")


def serve(args, data, warning=None):
    token = json.loads(sys.stdin.readline())["token"]
    app = create_app(data, token, args.media.resolve() if args.media else None)
    if args.config:
        try:
            write_settings(args.config, data)
        except OSError:
            warning = settings_warning(args.config)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    print(json.dumps({"port": sock.getsockname()[1], "api_version": 0, "data_dir": str(data),
                      "startup_warning": warning}), flush=True)

    def parent_lifetime():
        # EOF also handles an abruptly terminated desktop parent.
        sys.stdin.read()
        server.should_exit = True

    threading.Thread(target=parent_lifetime, daemon=True).start()
    try:
        # Local TCP only: Selector avoids Proactor reset callbacks stranding shutdown on Windows.
        factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        with asyncio.Runner(loop_factory=factory) as runner:
            runner.run(server.serve(sockets=[sock]))
    finally:
        sock.close()


if __name__ == "__main__":
    main()
