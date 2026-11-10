"""Bounded offline diagnostics. Findings never authorize deleting or repairing bytes."""
import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from contextlib import closing
from pathlib import Path, PurePosixPath

from .backup_archive import SUPPORTED_SCHEMA, archive_path
from .backup_store import connect, no_links, runtime_file
from .data_root import DataLock, validate_root
from .question_splitting import all_blocks

ENTRY_LIMIT = 20000
ROW_LIMIT = 50000
BYTE_LIMIT = 512 * 1024 * 1024
ISSUE_LIMIT = 200
SECONDS = 30
DERIVED = {'working', 'question-files', 'question-versions', 'previews', 'questions'}


class Incomplete(Exception):
    pass


def check_library(directory, *, install=None):
    no_links(directory)
    root = validate_root(directory, install)
    no_links(root / 'study.db')
    if not (root / 'study.db').is_file():
        raise ValueError('巡检只接受已有学习库，不会创建或迁移数据库')
    no_links(root / '.study.lock')
    result = dict(schema_version=1, complete=True, healthy=False, data_modified=False,
                  repair_performed=False, entries_checked=0, rows_checked=0, bytes_hashed=0,
                  issues=[], retained_preview_tasks=0, checked_scope='managed_files_and_derived_directories')
    deadline = time.monotonic() + SECONDS
    owned, hashes = set(), {}

    def checkpoint():
        if time.monotonic() >= deadline:
            raise Incomplete('time_limit')

    def issue(code, relative=None, severity='error'):
        if len(result['issues']) >= ISSUE_LIMIT:
            raise Incomplete('issue_limit')
        item = dict(code=code, severity=severity)
        if relative is not None:
            item['relative_path'] = relative
        result['issues'].append(item)

    def owner(relative):
        parts = PurePosixPath(relative).parts
        if len(parts) >= 4 and parts[0] == 'workspaces' and parts[2] in DERIVED:
            owned.add('/'.join(parts[:4]))
            if parts[2] == 'working' and len(parts) >= 5:
                owned.add('/'.join(parts[:5]))

    def path_for(relative, workspace=None):
        checkpoint()
        try:
            archive_path(relative)
            parts = PurePosixPath(relative).parts
            if workspace is not None and len(parts) >= 2 and parts[0] == 'workspaces' and parts[1] != workspace:
                issue('cross_workspace_reference')
                return None
            path = root / relative
            no_links(path)
        except (ValueError, OSError, TypeError):
            issue('unsafe_reference')
            return None
        owner(relative)
        return path

    def verify(relative, expected=None, size=None, *, optional=False, working=False, workspace=None):
        path = path_for(relative, workspace)
        if path is None:
            return
        try:
            if not path.exists() and optional:
                return
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                issue('not_regular_file', relative)
                return
            if size is not None and info.st_size != size:
                issue('size_mismatch', relative)
            if expected is None:
                return
            if relative not in hashes:
                if info.st_size > BYTE_LIMIT - result['bytes_hashed']:
                    raise Incomplete('byte_limit')
                checksum = hashlib.sha256()
                with path.open('rb') as stream:
                    remaining = info.st_size
                    while remaining:
                        checkpoint()
                        block = stream.read(min(1024 * 1024, remaining))
                        if not block:
                            issue('file_changed_during_scan', relative)
                            break
                        remaining -= len(block)
                        result['bytes_hashed'] += len(block)
                        checksum.update(block)
                no_links(path)
                after = path.stat()
                if (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                    issue('file_changed_during_scan', relative)
                hashes[relative] = checksum.hexdigest()
            if hashes[relative] != expected:
                issue('workfile_index_changed' if working else 'hash_mismatch', relative,
                      'warning' if working else 'error')
        except FileNotFoundError:
            issue('missing_file', relative)
        except (OSError, ValueError):
            issue('unreadable_file', relative)

    def rows(db, table):
        for row in db.execute('SELECT * FROM ' + table):  # Only fixed internal table names.
            checkpoint()
            result['rows_checked'] += 1
            if result['rows_checked'] > ROW_LIMIT:
                raise Incomplete('row_limit')
            yield row

    with DataLock(root):
        try:
            with closing(connect(root / 'study.db')) as db:
                db.execute('BEGIN')
                db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
                if [row[0] for row in db.execute('PRAGMA integrity_check')] != ['ok']:
                    issue('database_integrity')
                    result['complete'] = False
                    return result
                if db.execute('PRAGMA foreign_key_check').fetchone():
                    issue('database_relationship')
                versions = [row[0] for row in db.execute('SELECT version_num FROM alembic_version')]
                if versions != [SUPPORTED_SCHEMA]:
                    issue('unsupported_schema')
                    result['complete'] = False
                    return result
                resources = {}
                for table in ['resources', 'media_entries']:
                    for row in rows(db, table):
                        if table == 'resources':
                            resources[row['id']] = row
                        verify(row['relative_path'], row['sha256'], row['size'],
                               workspace=row['workspace_id'],
                               optional=table == 'media_entries' and row['status'] != 'ready')
                for row in rows(db, 'markdown_questions'):
                    directory = f"workspaces/{row['workspace_id']}/questions/{row['id']}"
                    markdown = resources.get(row['markdown_resource_id'])
                    if (markdown is None or markdown['workspace_id'] != row['workspace_id']
                            or markdown['relative_path'] != directory + '/question.md'):
                        issue('invalid_legacy_question_reference')
                        continue
                    for block in all_blocks(json.loads(row['content'])):
                        checkpoint()
                        if block['type'] != 'image':
                            continue
                        asset = resources.get(block['attachment_id'])
                        if asset is None or asset['workspace_id'] != row['workspace_id']:
                            issue('invalid_legacy_attachment_reference')
                            continue
                        verify(f"{directory}/assets/{asset['id']}.png", asset['sha256'], asset['size'],
                               workspace=row['workspace_id'])
                workspaces = {}
                for row in rows(db, 'document_workfiles'):
                    workspaces[row['node_id']] = row['workspace_id']
                    verify(row['relative_path'], row['indexed_sha256'], working=True, workspace=row['workspace_id'])
                for row in rows(db, 'document_saves'):
                    verify(row['backup_path'], row['old_sha256'], workspace=workspaces.get(row['node_id']))
                    verify(row['pending_path'], row['new_sha256'], optional=True, workspace=workspaces.get(row['node_id']))
                    if row['status'] == 'prepared':
                        issue('save_requires_reconciliation', severity='warning')
                for row in rows(db, 'markdown_note_creations'):
                    path_for(f"workspaces/{row['workspace_id']}/working/{row['id']}/note/current.md")
                    if row['status'] in {'prepared', 'interrupted', 'conflict'}:
                        issue('note_creation_requires_reconciliation', severity='warning')
                for row in rows(db, 'document_previews'):
                    if row['status'] == 'ready':
                        if (not isinstance(row['pdf_sha256'], str)
                                or not re.fullmatch('[a-f0-9]{64}', row['pdf_sha256'])
                                or type(row['pdf_size']) is not int or row['pdf_size'] <= 0
                                or type(row['page_count']) is not int or row['page_count'] <= 0):
                            issue('invalid_ready_preview_metadata')
                        verify(row['relative_pdf'], row['pdf_sha256'], row['pdf_size'], workspace=row['workspace_id'])
                    else:
                        path_for(row['relative_pdf'], row['workspace_id'])
                        result['retained_preview_tasks'] += 1
                for row in rows(db, 'question_versions'):
                    verify(row['relative_path'], row['markdown_sha256'], workspace=row['workspace_id'])
                    assets = json.loads(row['attachments'])
                    content = json.loads(row['content'])
                    raw = json.dumps(dict(content=content, attachments=assets), ensure_ascii=False,
                                     sort_keys=True, allow_nan=False).encode()
                    if hashlib.sha256(raw).hexdigest() != row['content_sha256']:
                        issue('confirmed_metadata_mismatch')
                    for asset in assets.values():
                        relative = str(PurePosixPath(row['relative_path']).parent / archive_path(asset['path']))
                        verify(relative, asset['sha256'], asset['size'], workspace=row['workspace_id'])
                # Include empty directories; runtime browser/player profiles are intentionally excluded.
                pending = [root]
                candidates = set()
                while pending:
                    checkpoint()
                    with os.scandir(pending.pop()) as entries:
                        for entry in entries:
                            checkpoint()
                            result['entries_checked'] += 1
                            if result['entries_checked'] > ENTRY_LIMIT:
                                raise Incomplete('entry_limit')
                            relative = Path(entry.path).relative_to(root).as_posix()
                            info = entry.stat(follow_symlinks=False)
                            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                                issue('reparse_point', relative)
                                continue
                            if runtime_file(relative):
                                continue
                            parts = PurePosixPath(relative).parts
                            if len(parts) == 1 and entry.is_dir(follow_symlinks=False) and entry.name.startswith(
                                    ('.pending-', '.backup-pending-', '.restore-pending-')):
                                issue('retained_operation_directory', relative, 'warning')
                                continue
                            if len(parts) >= 4 and parts[0] == 'workspaces' and parts[2] in DERIVED:
                                group = '/'.join(parts[:4])
                                if group in owned and parts[2] == 'working' and len(parts) >= 5:
                                    group = '/'.join(parts[:5])
                                if group not in owned and not any(group == c or group.startswith(c + '/') for c in candidates):
                                    issue('unreferenced_derived_candidate', group, 'warning')
                                    candidates.add(group)
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(Path(entry.path))
            result['healthy'] = not result['issues']
        except Incomplete as stopped:
            result['complete'], result['limit_reason'] = False, str(stopped)
        except sqlite3.Error:
            result['complete'] = False
            if time.monotonic() >= deadline:
                result['limit_reason'] = 'time_limit'
            else:
                result['issues'].append(dict(code='database_unreadable', severity='error'))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
            result['complete'] = False
            result['issues'].append(dict(code='scan_unreadable', severity='error'))
    return result
