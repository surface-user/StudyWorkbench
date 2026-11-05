"""Offline library snapshots and restore to an empty directory. Source libraries are never replaced."""
import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import backup_archive as envelope
from .data_root import DataLock, digest, validate_root, write_settings

CHUNK = 1024 * 1024
VALUE_LIMIT = 64 * CHUNK
APP_VERSION = '1.0.0+1'


def no_links(path):
    for part in [*reversed(path.parents), path]:
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('备份/恢复不跟随符号链接或重解析点')


def runtime_file(relative):
    if relative.split('/')[0] in {'web-profile', 'player-profile'}:
        return True
    if relative in {'.study.lock', 'study.db-wal', 'study.db-shm', 'study.db-journal'}:
        return True
    parts = relative.split('/')
    if len(parts) >= 3 and parts[0] == 'workspaces':
        if parts[2] == 'link-web':
            return True
        if len(parts) >= 4 and parts[2] in {'web', 'player', 'resource'}:
            return re.fullmatch(r'[A-Za-z0-9_-]{1,64}', parts[3]) is not None
    return False


def connect(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON')
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.execute('PRAGMA temp_store=FILE')
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, VALUE_LIMIT)
    connection.row_factory = sqlite3.Row
    return connection


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def atom(value):
    if value is None:
        return ['null']
    if isinstance(value, bytes):
        return ['blob', base64.b64encode(value).decode('ascii')]
    if isinstance(value, float):
        return ['float64', value.hex()]
    if isinstance(value, int):
        return ['integer', str(value)]
    return ['text', value]


def table_summary(connection, checkpoint=lambda _: None, columns=None):
    result = {}
    tables = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    for name, sql in tables:
        if sql and re.match(r'\s*CREATE\s+VIRTUAL\s+TABLE', sql, re.I):
            raise ValueError('备份暂不支持虚拟表')
        info = connection.execute(f'PRAGMA table_info({quoted(name)})').fetchall()
        names = [row['name'] for row in info] if columns is None else columns.get(name)
        if names is None:
            continue
        if not set(names) <= {row['name'] for row in info}:
            raise ValueError('迁移后旧列缺失')
        primary = [row['name'] for row in sorted(info, key=lambda row: row['pk']) if row['pk'] and row['name'] in names]
        order = primary + [field for field in names if field not in primary]
        ordering = ','.join(f'typeof({quoted(field)}),{quoted(field)} COLLATE BINARY,hex(CAST({quoted(field)} AS BLOB))' for field in order)
        selected = ','.join(quoted(field) for field in names)
        checksum, count = hashlib.sha256(), 0
        for row in connection.execute(f'SELECT {selected} FROM {quoted(name)} ORDER BY {ordering}'):
            checkpoint('table-rows')
            checksum.update(json.dumps([atom(value) for value in row], ensure_ascii=False, allow_nan=False,
                                       separators=(',', ':')).encode('utf-8') + b'\n')
            count += 1
        result[name] = dict(rows=count, sha256=checksum.hexdigest())
    return result


def database_info(path, checkpoint=lambda _: None):
    with closing(connect(path)) as connection:
        connection.set_progress_handler(lambda: (checkpoint('database-check'), 0)[1], 10000)
        if [row[0] for row in connection.execute('PRAGMA integrity_check')] != ['ok']:
            raise ValueError('备份SQLite完整性检查失败')
        if connection.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('备份SQLite关系检查失败')
        revisions = [row[0] for row in connection.execute('SELECT version_num FROM alembic_version')]
        if len(revisions) != 1 or not '0001' <= revisions[0] <= envelope.SUPPORTED_SCHEMA:
            raise ValueError('备份数据库版本不支持')
        return revisions[0], table_summary(connection, checkpoint)


def check_references(root, files):
    """Check required managed bytes; interrupted save/creation artifacts remain byte-preserved, not replayed."""
    def require(relative, sha=None, size=None):
        relative = envelope.archive_path(relative)
        item = files.get(relative)
        if item is None or sha is not None and item['sha256'] != sha or size is not None and item['size'] != size:
            raise ValueError('备份缺失受管文件或记录hash/大小不符：' + relative)
    with closing(connect(root / 'study.db')) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('resources', 'media_entries'):
            if table not in tables:
                continue
            for row in connection.execute(f'SELECT * FROM {table}'):
                if table == 'resources' or row['status'] == 'ready':
                    require(row['relative_path'], row['sha256'], row['size'])
        if 'document_workfiles' in tables:
            for row in connection.execute('SELECT relative_path FROM document_workfiles'):
                require(row[0])  # An external conflict must remain a conflict, not be overwritten with the indexed hash.
        if 'media_download_jobs' in tables:
            for row in connection.execute("SELECT * FROM media_download_jobs WHERE status='ready'"):
                progress, result = json.loads(row['progress']), json.loads(row['result'])
                require(row['relative_path'], progress['partial_sha256'], progress['received'])
                node = connection.execute('SELECT workspace_id,media_id FROM workspace_nodes WHERE id=?',
                                          (result.get('resource_item_id'),)).fetchone()
                if node is None or node[0] != row['workspace_id'] or node[1] != result.get('media_id'):
                    raise ValueError('下载结果关系不完整或跨空间')
        if 'analysis_review_drafts' in tables:
            for row in connection.execute('SELECT * FROM analysis_review_drafts'):
                content = json.loads(row['content'])
                encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
                if hashlib.sha256(encoded).hexdigest() != row['payload_sha256']:
                    raise ValueError('审核候选内容hash不符')
                seen = 0
                for revision, raw_snapshot in connection.execute('SELECT revision,snapshot FROM analysis_review_revisions WHERE draft_id=? ORDER BY revision', (row['id'],)):
                    seen += 1
                    if revision != seen:
                        raise ValueError('审核修订序列不完整')
                    snapshot = json.loads(raw_snapshot)
                    encoded_snapshot = json.dumps(snapshot['content'], ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
                    if (snapshot['id'], snapshot['workspace_id'], snapshot['revision']) != (row['id'], row['workspace_id'], revision) or hashlib.sha256(encoded_snapshot).hexdigest() != snapshot['payload_sha256']:
                        raise ValueError('审核修订身份或内容hash不符')
                if seen != row['revision'] - 1:
                    raise ValueError('审核修订序列不完整')
                references = content['references']
                if not isinstance(references, list) or not 1 <= len(references) <= 100:
                    raise ValueError('审核候选引用数量无效')
                for reference in references:
                    attempt = connection.execute('SELECT workspace_id,question_id,question_version_id FROM attempts WHERE id=?',
                                                 (reference['attempt_id'],)).fetchone()
                    if attempt is None or tuple(attempt) != (row['workspace_id'], reference['question_id'], reference['question_version_id']):
                        raise ValueError('审核候选引用缺失或跨空间')
                    if reference.get('confirmed_metadata_sha256') is not None:
                        version = connection.execute('SELECT workspace_id,content_sha256 FROM question_versions WHERE id=?',
                                                     (reference['question_version_id'],)).fetchone()
                        if version is None or tuple(version) != (row['workspace_id'], reference['confirmed_metadata_sha256']):
                            raise ValueError('审核候选确认版引用不符')
                result = json.loads(row['result'])
                if result.get('resource_item_id'):
                    node = connection.execute('SELECT workspace_id,resource_id FROM workspace_nodes WHERE id=?',
                                              (result['resource_item_id'],)).fetchone()
                    if node is None or node[0] != row['workspace_id'] or not node[1]:
                        raise ValueError('审核采用笔记关系不完整或跨空间')
        if 'document_previews' in tables:
            for row in connection.execute("SELECT * FROM document_previews WHERE status='ready'"):
                require(row['relative_pdf'], row['pdf_sha256'], row['pdf_size'])
        if 'question_versions' in tables:
            for row in connection.execute('SELECT * FROM question_versions'):
                content, assets = json.loads(row['content']), json.loads(row['attachments'])
                hashed = hashlib.sha256(json.dumps({'content': content, 'attachments': assets}, ensure_ascii=False,
                                                  sort_keys=True, allow_nan=False).encode()).hexdigest()
                if hashed != row['content_sha256']:
                    raise ValueError('确认版元数据hash不符')
                require(row['relative_path'], row['markdown_sha256'])
                parent = row['relative_path'].rsplit('/', 1)[0]
                for item in assets.values():
                    name = envelope.archive_path(item['path'])
                    require(parent + '/' + name, item['sha256'], item['size'])


def inventory(root, checkpoint=lambda _: None):
    files, excluded = [], []
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            checkpoint('scanning')
            no_links(path)
            relative = path.relative_to(root).as_posix()
            envelope.archive_path(relative)
            if runtime_file(relative):
                excluded.append(relative)
            elif path.is_dir():
                pending.append(path)
            elif path.is_file():
                files.append((relative, path))
                if len(files) > envelope.COUNT_LIMIT:
                    raise ValueError('备份文件数量超过100000')
            else:
                raise ValueError('备份不支持特殊文件')
    return sorted(files), sorted(excluded)


def clean_owned_stage(stage, parent):
    if stage.parent.resolve() != parent.resolve() or not stage.name.startswith(('.backup-pending-', '.restore-pending-')):
        raise ValueError('临时目录不属于本次操作')
    no_links(stage)
    inventory(stage)  # Reject reparse points anywhere before deleting only our verified staging copies.
    shutil.rmtree(stage)


def create_backup(source, output, *, app_version=APP_VERSION, install=None, checkpoint=lambda _: None):
    no_links(source)
    source = validate_root(source, install)
    envelope.archive_path(output.name)
    if output.drive.startswith('\\\\.\\'):
        raise ValueError('备份ZIP不能使用设备路径')
    no_links(output)
    if not output.is_absolute() or output.resolve().is_relative_to(source) or source.is_relative_to(output.resolve()):
        raise ValueError('备份ZIP必须位于数据目录外的绝对路径')
    if install and output.resolve().is_relative_to(install.resolve()):
        raise ValueError('备份ZIP不能放在安装目录内')
    if output.exists() or not output.parent.is_dir():
        raise ValueError('请选择不存在的ZIP文件名和已有可写父目录')
    if not (source / 'study.db').is_file():
        raise ValueError('源目录缺少学习数据库')
    stage = output.parent / f'.backup-pending-{uuid4().hex}'
    with DataLock(source):
        initial, _ = inventory(source, checkpoint)
        total_size = sum(path.stat().st_size for _, path in initial)
        database_size = (source / 'study.db').stat().st_size
        if (source / 'study.db-wal').exists():
            database_size += (source / 'study.db-wal').stat().st_size
        if shutil.disk_usage(output.parent).free < 2 * total_size + database_size + 16 * CHUNK:
            raise ValueError('备份磁盘空间不足，需预留暂存/发布校验空间')
        stage.mkdir()
        snapshot = stage / 'study.db'
        with closing(connect(source / 'study.db')) as original, closing(sqlite3.connect(snapshot)) as copied:
            original.backup(copied, pages=256, progress=lambda *_: checkpoint('database-backup'))
        revision, tables = database_info(snapshot, checkpoint)
        files, excluded = inventory(source, checkpoint)
        files = [(name, snapshot if name == 'study.db' else path) for name, path in files]
        manifest = dict(format='studyworkbench-backup', version=1, schema_revision=revision,
                        app_version=app_version, created_at=datetime.now(timezone.utc).isoformat(),
                        files=[], tables=tables, excluded=excluded)
        pending = stage / 'package.zip'
        total = 0
        with zipfile.ZipFile(pending, 'x', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for name, path in files:
                checkpoint('packing-file')
                no_links(path)
                size, checksum = 0, hashlib.sha256()
                with path.open('rb') as original, archive.open('payload/' + name, 'w', force_zip64=True) as target:
                    while chunk := original.read(CHUNK):
                        checkpoint('packing-chunk')
                        size += len(chunk)
                        total += len(chunk)
                        if size > envelope.FILE_LIMIT or total > envelope.TOTAL_LIMIT:
                            raise ValueError('备份文件大小超过预算')
                        if shutil.disk_usage(stage).free < len(chunk) + 16 * CHUNK:
                            raise ValueError('备份磁盘空间不足，未发布的字节保留')
                        target.write(chunk)
                        checksum.update(chunk)
                sha = checksum.hexdigest()
                if digest(path, checkpoint) != sha:
                    raise ValueError('备份期间源文件发生变化')
                manifest['files'].append(dict(path=name, size=size, sha256=sha))
            check_references(stage, {item['path']: item for item in manifest['files']})
            encoded = json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode()
            envelope.manifest_bytes(encoded)
            archive.writestr('backup-manifest.json', encoded)
        envelope.inspect_archive(pending, checkpoint)
        # Recheck the inventory and bytes before publishing; never overwrite an existing chosen ZIP.
        latest, _ = inventory(source, checkpoint)
        if [name for name, _ in latest] != [name for name, _ in files]:
            raise ValueError('备份期间文件清单发生变化')
        expected = {item['path']: item for item in manifest['files']}
        for name, path in latest:
            if name != 'study.db' and digest(path, checkpoint) != expected[name]['sha256']:
                raise ValueError('备份期间源文件发生变化')
        if database_info(source / 'study.db', checkpoint) != (revision, tables):
            raise ValueError('备份期间数据库内容发生变化')
        checkpoint('publishing')
        with output.open('xb') as target, pending.open('rb') as original:
            while chunk := original.read(CHUNK):
                checkpoint('publishing-chunk')
                if shutil.disk_usage(output.parent).free < len(chunk) + 16 * CHUNK:
                    raise ValueError('备份发布空间不足，未完成字节保留')
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if digest(output, checkpoint) != digest(pending, checkpoint):
            raise ValueError('备份发布后hash不符，源目录保留')
        cleanup_pending = False
        try:
            clean_owned_stage(stage, output.parent)
        except (OSError, ValueError):
            cleanup_pending = True
    return dict(file_count=len(files), total_bytes=total, schema_revision=revision, source_retained=True,
                data_activated=False, cleanup_pending=cleanup_pending)


def restore_backup(package, target, config, *, install=None, checkpoint=lambda _: None):
    envelope.archive_path(package.name)
    if package.drive.startswith('\\\\.\\'):
        raise ValueError('备份ZIP不能使用设备路径')
    no_links(package)
    no_links(target)
    target = validate_root(target, install)
    if not package.is_absolute() or package.resolve().is_relative_to(target):
        raise ValueError('备份ZIP须为目标目录外的绝对路径')
    if not config.is_absolute() or config.resolve().is_relative_to(target):
        raise ValueError('启动配置须在目标数据目录之外')
    no_links(config)
    if config.exists():
        previous = json.loads(config.read_text(encoding='utf-8'))
        if previous.get('version') != 1 or not isinstance(previous.get('data_dir'), str):
            raise ValueError('已有启动配置无效，保留配置，请先排查')
        if not Path(previous['data_dir']).is_absolute():
            raise ValueError('原数据配置路径不是绝对路径')
        old = Path(previous['data_dir']).resolve()
        if old == target or old.is_relative_to(target) or target.is_relative_to(old) or config.resolve().is_relative_to(old):
            raise ValueError('恢复目标/配置与原数据目录交叠')
    if target.exists() and any(target.iterdir()):
        raise ValueError('恢复只允许新空目录，不覆盖已有文件')
    package_hash = digest(package, checkpoint)
    manifest = envelope.inspect_archive(package, checkpoint)
    if any(runtime_file(item['path']) for item in manifest['files']):
        raise ValueError('备份payload含运行时锁/日志/profile，不允许恢复')
    if not target.parent.is_dir():
        raise ValueError('请选择已有父目录中的新空数据目录')
    total_size = sum(item['size'] for item in manifest['files'])
    migration_size = next(item['size'] for item in manifest['files'] if item['path'] == 'study.db')
    if manifest['schema_revision'] == envelope.SUPPORTED_SCHEMA:
        migration_size = 0
    if shutil.disk_usage(target.parent).free < 2 * total_size + 2 * migration_size + 16 * CHUNK:
        raise ValueError('恢复磁盘空间不足，需预留暂存/迁移/提升空间')
    with DataLock(config.parent / 'session'), DataLock(target):
        if any(path.name != '.study.lock' for path in target.iterdir()):
            raise ValueError('目标目录已被其他进程写入')
        stage = target / f'.restore-pending-{uuid4().hex}'
        stage.mkdir()
        total = 0
        with envelope.bounded_zip(package) as archive:
            if {info.filename for info in archive.infolist()} != {
                'backup-manifest.json', *('payload/' + item['path'] for item in manifest['files'])
            } or envelope.manifest_bytes(archive.read('backup-manifest.json')) != manifest:
                raise ValueError('备份包在检查后发生变化')
            for item in manifest['files']:
                checkpoint('restoring-file')
                output = stage / item['path']
                output.parent.mkdir(parents=True, exist_ok=True)
                no_links(output)
                size, checksum = 0, hashlib.sha256()
                with archive.open('payload/' + item['path']) as original, output.open('xb') as copied:
                    while chunk := original.read(CHUNK):
                        checkpoint('restoring-chunk')
                        size += len(chunk)
                        total += len(chunk)
                        if size > item['size'] or total > envelope.TOTAL_LIMIT:
                            raise ValueError('恢复实际字节超出清单/预算')
                        if shutil.disk_usage(target).free < len(chunk) + 16 * CHUNK:
                            raise ValueError('恢复磁盘空间不足，旧配置保持')
                        copied.write(chunk)
                        checksum.update(chunk)
                    copied.flush()
                    os.fsync(copied.fileno())
                if size != item['size'] or checksum.hexdigest() != item['sha256']:
                    raise ValueError('恢复字节与清单不符')
        revision, tables = database_info(stage / 'study.db', checkpoint)
        if revision != manifest['schema_revision'] or tables != manifest['tables']:
            raise ValueError('恢复数据库版本/行数/行摘要与清单不符')
        check_references(stage, {item['path']: item for item in manifest['files']})
        allowed = {item['path'] for item in manifest['files']}
        if revision != envelope.SUPPORTED_SCHEMA:
            from .db import database
            from .migrate import migrate
            with closing(connect(stage / 'study.db')) as old:
                columns = {row[0]: [field['name'] for field in old.execute(f'PRAGMA table_info({quoted(row[0])})')]
                           for row in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")}
                before = table_summary(old, checkpoint, columns)
            engine = database(stage / 'study.db')
            prior_backups = set((stage / 'backups').glob('*'))
            try:
                migrate(engine, stage / 'study.db')
            finally:
                engine.dispose()
            with closing(connect(stage / 'study.db')) as new:
                if table_summary(new, checkpoint, columns) != before:
                    raise ValueError('恢复迁移改变旧记录，未激活')
            database_info(stage / 'study.db', checkpoint)
            for path in set((stage / 'backups').glob('*')) - prior_backups:
                if not re.fullmatch(rf'study-before-{envelope.SUPPORTED_SCHEMA}-[a-f0-9]{{32}}\.db', path.name):
                    raise ValueError('迁移产生未知文件，未激活')
                allowed.add(path.relative_to(stage).as_posix())
        checkpoint('restore-validated')
        promote = inventory(stage, checkpoint)[0]
        if {name for name, _ in promote} != allowed or digest(package, checkpoint) != package_hash:
            raise ValueError('恢复目录或原ZIP在校验后发生变化')
        expected = {name: digest(path, checkpoint) for name, path in promote}
        for item in manifest['files']:
            if item['path'] != 'study.db' and expected[item['path']] != item['sha256']:
                raise ValueError('恢复文件在校验后发生变化')
        no_links(target)
        if any(path.name not in {'.study.lock', stage.name} for path in target.iterdir()):
            raise ValueError('目标被其他进程写入，未激活')
        # Exclusive destination creation preserves unexpected external files even if promotion races.
        for name, path in promote:
            output = target / name
            output.parent.mkdir(parents=True, exist_ok=True)
            no_links(output)
            with path.open('rb') as original, output.open('xb') as copied:
                while chunk := original.read(CHUNK):
                    checkpoint('promoting-chunk')
                    if shutil.disk_usage(target).free < len(chunk) + 16 * CHUNK:
                        raise ValueError('恢复提升阶段磁盘空间不足，旧配置保持')
                    copied.write(chunk)
                copied.flush()
                os.fsync(copied.fileno())
            if digest(output, checkpoint) != expected[name] or digest(path, checkpoint) != expected[name]:
                raise ValueError('恢复提升后hash不符，未激活')
        checkpoint('before-settings')
        # The source stage is not activated; only fully rechecked promoted bytes may become the new library.
        for name in expected:
            if digest(target / name, checkpoint) != expected[name]:
                raise ValueError('激活前目标文件发生变化，旧配置保持')
        database_info(target / 'study.db', checkpoint)
        write_settings(config, target)
        cleanup_pending = False
        try:
            clean_owned_stage(stage, target)
        except (OSError, ValueError):
            cleanup_pending = True
    return dict(data_dir=str(target), schema_revision=envelope.SUPPORTED_SCHEMA,
                file_count=len(manifest['files']), database_semantics_checked=True, data_activated=True,
                cleanup_pending=cleanup_pending)
