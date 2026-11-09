"""Offline, metadata-only accounting. No reported file is authorized for deletion."""
import os
import re
import sqlite3
import stat
import time
from contextlib import closing
from pathlib import Path, PurePosixPath

from .backup_archive import SUPPORTED_SCHEMA, archive_path
from .backup_store import connect, no_links
from .data_root import DataLock, validate_root
from .library_integrity import ENTRY_LIMIT, ISSUE_LIMIT, ROW_LIMIT, SECONDS, Incomplete

TOP_LIMIT = 20
KINDS = {'working', 'question-files'}
STATUSES = {'prepared', 'committed', 'interrupted', 'conflict'}
OFFICE_STATUSES = {'queued', 'running', 'ready', 'failed', 'interrupted', 'cancelled'}
DOWNLOAD_STATUSES = {'queued', 'running', 'ready', 'failed', 'interrupted', 'paused'}


def report_recovery_storage(directory, *, install=None):
    return _report_storage(directory, install=install, kind='markdown')


def report_office_storage(directory, *, install=None):
    return _report_storage(directory, install=install, kind='office')


def report_download_storage(directory, *, install=None):
    return _report_storage(directory, install=install, kind='downloads')


def _report_storage(directory, *, install, kind):
    office, download = kind == 'office', kind == 'downloads'
    no_links(directory)
    root = validate_root(directory, install)
    no_links(root / 'study.db')
    if not (root / 'study.db').is_file():
        raise ValueError('容量报告只接受已有学习库，不会创建或迁移数据库')
    no_links(root / '.study.lock')
    statuses = DOWNLOAD_STATUSES if download else OFFICE_STATUSES if office else STATUSES
    kinds = {'downloads'} if download else {'previews'} if office else KINDS
    roles = (['media_referenced_file', 'current_attempt_file', 'lower_numbered_attempt_file', 'other_download_file'] if download else
             [status + '_preview_file' for status in sorted(statuses)] + ['unregistered_preview_file'] if office else
             ['current_workfile', 'before_recovery', 'pending_recovery', 'unreferenced_working_file'])
    scope = 'download_attempt_files' if download else 'office_preview_task_files' if office else 'markdown_working_and_save_recovery_files'
    result = dict(schema_version=1, scope=scope, complete=True,
                  data_modified=False, deletion_authorized=False, content_integrity_checked=False,
                  library_health_checked=False, snapshot_atomic=False, bytes_kind='observed_logical_lengths',
                  entries_checked=0, rows_checked=0, file_count=0, logical_bytes=0,
                  records_by_status={status: 0 for status in sorted(statuses)},
                  largest_files=[], largest_files_limit=TOP_LIMIT,
                  largest_files_truncated=False,
                  categories={role: dict(file_count=0, logical_bytes=0) for role in roles},
                  issues=[])
    if download:
        result.update(missing_optional_download_files=0, media_reference_rows=0, media_referenced_paths=0, attempt_history_checked=False)
    else:
        result['missing_nonready_pdf' if office else 'missing_committed_pending'] = 0
    deadline = time.monotonic() + SECONDS
    references, works, seen, preview_directories = {}, {}, set(), {}
    download_jobs, media_paths = {}, {}

    def checkpoint():
        if time.monotonic() >= deadline:
            raise Incomplete('time_limit')

    def issue(code, relative=None):
        result['complete'] = False
        if len(result['issues']) >= ISSUE_LIMIT:
            raise Incomplete('issue_limit')
        result['issues'].append(dict(code=code, **({'relative_path': relative} if relative else {})))

    def rows(db, sql):
        for row in db.execute(sql):
            checkpoint()
            if result['rows_checked'] >= ROW_LIMIT:
                raise Incomplete('row_limit')
            result['rows_checked'] += 1
            yield row

    def reference(relative, role, status=None):
        if relative in references:
            issue('duplicate_reference', relative)
        else:
            references[relative] = dict(role=role, status=status)

    def signature(info):
        # Windows scandir metadata can omit inode values or round timestamps.
        # Compare two fresh path stats rather than cached DirEntry metadata.
        return info.st_size, info.st_mtime_ns, info.st_ino, stat.S_IFMT(info.st_mode)

    def download_metadata(relative):
        parts = PurePosixPath(relative).parts
        job = download_jobs.get('/'.join(parts[:4]))
        relation = 'other'
        if job and len(parts) == 5:
            matched = re.fullmatch(r'([1-9][0-9]*)' + re.escape(job['suffix']), parts[-1])
            if matched:
                number = int(matched[1])
                relation = 'current' if number == job['attempt'] else 'lower_numbered' if number < job['attempt'] else 'other'
        count = media_paths.get(relative, 0)
        role = ('media_referenced_file' if count else 'current_attempt_file' if relation == 'current' else
                'lower_numbered_attempt_file' if relation == 'lower_numbered' else 'other_download_file')
        return dict(role=role, attempt_relation=relation, current_job_status=job['status'] if job else None,
                    media_reference_count=count)

    with DataLock(root):
        try:
            checkpoint()
            with closing(connect(root / 'study.db')) as db:
                db.execute('BEGIN')
                db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
                if [r[0] for r in db.execute('SELECT version_num FROM alembic_version')] != [SUPPORTED_SCHEMA]:
                    issue('unsupported_schema')
                    return result
                if download:
                    for row in rows(db, 'SELECT d.id,d.workspace_id,d.attempt,d.relative_path,d.status,s.id AS existing_workspace '
                                        'FROM media_download_jobs d LEFT JOIN workspaces s ON s.id=d.workspace_id ORDER BY d.id'):
                        status = row['status'] if row['status'] in statuses else 'unknown'
                        result['records_by_status'][status] = result['records_by_status'].get(status, 0) + 1
                        if status == 'unknown':
                            issue('unknown_download_status')
                            continue
                        try:
                            relative = archive_path(row['relative_path'])
                            parts = PurePosixPath(relative).parts
                            suffix = PurePosixPath(relative).suffix
                            if (not isinstance(row['id'], str) or not re.fullmatch('[a-f0-9]{32}', row['id'])
                                    or type(row['attempt']) is not int or row['attempt'] < 1
                                    or suffix not in {'.mp4', '.webm', '.m4a'} or row['existing_workspace'] != row['workspace_id']
                                    or parts != ('workspaces', row['workspace_id'], 'downloads', row['id'], str(row['attempt']) + suffix)):
                                raise ValueError('Invalid download ownership')
                        except (TypeError, ValueError):
                            issue('unsafe_download_reference')
                            continue
                        download_jobs['/'.join(parts[:4])] = dict(status=status, attempt=row['attempt'], suffix=suffix)
                        references[relative] = dict(required=status == 'ready')
                    for row in rows(db, 'SELECT m.workspace_id,m.relative_path,m.status,s.id AS existing_workspace '
                                        'FROM media_entries m LEFT JOIN workspaces s ON s.id=m.workspace_id ORDER BY m.id'):
                        try:
                            relative = archive_path(row['relative_path'])
                            parts = PurePosixPath(relative).parts
                            if len(parts) < 3 or parts[0] != 'workspaces' or parts[2] != 'downloads':
                                continue
                            if len(parts) < 4 or parts[1] != row['workspace_id'] or row['existing_workspace'] != row['workspace_id']:
                                raise ValueError('Invalid media ownership')
                        except (TypeError, ValueError):
                            issue('unsafe_media_reference')
                            continue
                        if row['status'] not in {'importing', 'ready', 'failed'}:
                            issue('unknown_media_status')
                        media_paths[relative] = media_paths.get(relative, 0) + 1
                        result['media_reference_rows'] += 1
                        required = row['status'] not in {'importing', 'failed'}
                        references.setdefault(relative, dict(required=False))['required'] |= required
                    result['media_referenced_paths'] = len(media_paths)
                if office:
                    for row in rows(db, 'SELECT p.id,p.workspace_id,p.node_id,p.source_resource_id,p.relative_pdf,p.status, '
                                        'n.workspace_id AS node_workspace,n.kind,n.resource_id, '
                                        'r.workspace_id AS source_workspace,s.id AS existing_workspace '
                                        'FROM document_previews p LEFT JOIN workspace_nodes n ON n.id=p.node_id '
                                        'LEFT JOIN resources r ON r.id=p.source_resource_id '
                                        'LEFT JOIN workspaces s ON s.id=p.workspace_id ORDER BY p.id'):
                        status = row['status'] if row['status'] in statuses else 'unknown'
                        result['records_by_status'][status] = result['records_by_status'].get(status, 0) + 1
                        if status == 'unknown':
                            issue('unknown_preview_status')
                            continue
                        try:
                            relative = archive_path(row['relative_pdf'])
                            parts = PurePosixPath(relative).parts
                            expected = f"workspaces/{row['workspace_id']}/previews/{row['id']}/output/source.pdf"
                            if (not isinstance(row['id'], str) or not re.fullmatch('[a-f0-9]{32}', row['id'])
                                    or relative != expected or len(parts) != 6 or parts[1] != row['workspace_id']
                                    or row['existing_workspace'] != row['workspace_id']
                                    or row['node_workspace'] != row['workspace_id'] or row['kind'] != 'resource'
                                    or row['source_workspace'] != row['workspace_id']
                                    or row['resource_id'] != row['source_resource_id']):
                                raise ValueError('Invalid preview ownership')
                        except (TypeError, ValueError):
                            issue('unsafe_preview_reference')
                            continue
                        ref = dict(role=status + '_preview_file', status=status)
                        preview_directories['/'.join(PurePosixPath(relative).parts[:4])] = ref
                        reference(relative, ref['role'], status)
                if kind == 'markdown':
                    for row in rows(db, 'SELECT w.*, n.workspace_id AS node_workspace, n.kind, q.question_id '
                                        'FROM document_workfiles w LEFT JOIN workspace_nodes n ON n.id=w.node_id '
                                        'LEFT JOIN question_files q ON q.node_id=w.node_id AND q.workspace_id=w.workspace_id '
                                        'ORDER BY w.node_id'):
                        try:
                            relative = archive_path(row['relative_path'])
                            parts = PurePosixPath(relative).parts
                            owner = (row['kind'] == 'resource' and row['node_workspace'] == row['workspace_id']
                                     and len(parts) >= 5 and parts[:2] == ('workspaces', row['workspace_id'])
                                     and parts[-1] == 'current.md')
                            valid = owner and ((parts[2] == 'working' and len(parts) == 6 and parts[3] == row['node_id'])
                                               or (parts[2] == 'question-files' and len(parts) == 5
                                                   and parts[3] == row['question_id']))
                            if not valid:
                                raise ValueError('Invalid workfile ownership')
                        except (TypeError, ValueError):
                            issue('unsafe_workfile_reference')
                            continue
                        works[row['node_id']] = PurePosixPath(relative).parent.as_posix()
                        reference(relative, 'current_workfile')
                    for row in rows(db, 'SELECT id,node_id,backup_path,pending_path,status FROM document_saves ORDER BY id'):
                        status = row['status'] if row['status'] in STATUSES else 'unknown'
                        result['records_by_status'][status] = result['records_by_status'].get(status, 0) + 1
                        if status == 'unknown':
                            issue('unknown_receipt_status')
                        directory = works.get(row['node_id'])
                        if directory is None or not isinstance(row['id'], str) or not re.fullmatch('[a-f0-9]{32}', row['id']):
                            issue('unsafe_save_reference')
                            continue
                        for column, version in [('backup_path', 'before'), ('pending_path', 'pending')]:
                            expected = f"{directory}/{row['id']}.{version}.md"
                            if row[column] != expected:
                                issue('unsafe_save_reference')
                                continue
                            reference(expected, version + '_recovery', status)

                scope = root / 'workspaces'
                no_links(scope)
                pending = [scope] if scope.exists() else []
                while pending:
                    checkpoint()
                    directory = pending.pop()
                    no_links(directory)
                    before = directory.stat(follow_symlinks=False)
                    if (not stat.S_ISDIR(before.st_mode)
                            or getattr(before, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                        issue('directory_changed_during_scan', directory.relative_to(root).as_posix())
                        continue
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            checkpoint()
                            if result['entries_checked'] >= ENTRY_LIMIT:
                                raise Incomplete('entry_limit')
                            result['entries_checked'] += 1
                            relative = Path(entry.path).relative_to(root).as_posix()
                            parts = PurePosixPath(relative).parts
                            if len(parts) == 3 and parts[2] not in kinds:
                                continue
                            try:
                                archive_path(relative)
                            except ValueError:
                                issue('unsafe_scope_path')
                                continue
                            try:
                                info = entry.stat(follow_symlinks=False)
                                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                                    issue('reparse_point', relative)
                                    continue
                                if stat.S_ISDIR(info.st_mode):
                                    pending.append(Path(entry.path))
                                    continue
                                if len(parts) < 4:
                                    if len(parts) == 3:
                                        issue('not_scope_directory', relative)
                                    continue
                                if not stat.S_ISREG(info.st_mode):
                                    issue('not_regular_file', relative)
                                    continue
                                no_links(Path(entry.path))
                                fresh = Path(entry.path).stat(follow_symlinks=False)
                                if (info.st_size != fresh.st_size or stat.S_IFMT(info.st_mode) != stat.S_IFMT(fresh.st_mode)
                                        or signature(fresh) != signature(Path(entry.path).stat(follow_symlinks=False))):
                                    issue('file_changed_during_scan', relative)
                                    continue
                                info = fresh
                                if relative in seen:
                                    continue
                                seen.add(relative)
                                ref = (download_metadata(relative) if download else
                                       preview_directories.get('/'.join(parts[:4]), dict(role='unregistered_preview_file', status=None))
                                       if office else references.get(relative, dict(role='unreferenced_working_file', status=None)))
                                group = result['categories'][ref['role']]
                                group['file_count'] += 1
                                group['logical_bytes'] += info.st_size
                                result['file_count'] += 1
                                result['logical_bytes'] += info.st_size
                                item = dict(relative_path=relative, logical_bytes=info.st_size, role=ref['role'])
                                if download:
                                    item.update(ref)
                                else:
                                    item['preview_status' if office else 'save_status'] = ref['status']
                                result['largest_files'].append(item)
                                result['largest_files'].sort(key=lambda item: (-item['logical_bytes'], item['relative_path']))
                                del result['largest_files'][TOP_LIMIT:]
                            except (OSError, ValueError):
                                issue('unreadable_file', relative)
                    no_links(directory)
                    after = directory.stat(follow_symlinks=False)
                    if (before.st_ino, before.st_mtime_ns) != (after.st_ino, after.st_mtime_ns):
                        issue('directory_changed_during_scan', directory.relative_to(root).as_posix())
                for relative, ref in references.items():
                    checkpoint()
                    if relative not in seen:
                        if download:
                            if ref['required']:
                                issue('missing_required_reference', relative)
                            else:
                                result['missing_optional_download_files'] += 1
                        elif office and ref['status'] != 'ready':
                            result['missing_nonready_pdf'] += 1
                        elif ref['role'] == 'pending_recovery' and ref['status'] == 'committed':
                            result['missing_committed_pending'] += 1
                        else:
                            issue('missing_required_reference', relative)
        except Incomplete as stopped:
            result['complete'], result['limit_reason'] = False, str(stopped)
        except sqlite3.Error:
            result['complete'] = False
            if time.monotonic() >= deadline:
                result['limit_reason'] = 'time_limit'
            elif len(result['issues']) >= ISSUE_LIMIT:
                result['limit_reason'] = 'issue_limit'
            else:
                result['issues'].append(dict(code='database_unreadable'))
        except (OSError, ValueError, TypeError, KeyError):
            result['complete'] = False
            if len(result['issues']) >= ISSUE_LIMIT:
                result['limit_reason'] = 'issue_limit'
            else:
                result['issues'].append(dict(code='scan_unreadable'))
    result['largest_files_truncated'] = result['file_count'] > len(result['largest_files'])
    return result
