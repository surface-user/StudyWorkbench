import copy
import hashlib
import struct
from threading import Event

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from study_workbench import backup_store, library_integrity, media_mux, media_probe_runtime
from study_workbench.db import MediaDownloadAttempt, MediaDownloadJob, MediaEntry, write_transaction
from study_workbench.media_download_http import DownloadError
from study_workbench.media_downloads import MediaDownloads
from study_workbench.media_sources import OutputReceipt, attempt_record, source_digest, source_snapshot
from test_explorer import PREFIX, client
from test_media_downloads import wait
from test_media_inputs import box, mp4
from test_media_sources import metadata, receipt, selection


def boxes(data):
    offset = 0
    while offset < len(data):
        length = struct.unpack_from('>I', data, offset)[0]
        yield data[offset+4:offset+8], data[offset:offset+length]
        offset += length


def pair_bytes():
    # Structural-only fixture: generated sample bytes deliberately do not prove codec validity.
    video, audio = mp4(), mp4('audio')
    ftyp = next(value for kind, value in boxes(video) if kind == b'ftyp')
    vm = next(value[8:] for kind, value in boxes(video) if kind == b'moov')
    am = next(value[8:] for kind, value in boxes(audio) if kind == b'moov')
    header = next(value for kind, value in boxes(vm) if kind == b'mvhd')
    vt = next(value for kind, value in boxes(vm) if kind == b'trak')
    at = bytearray(next(value for kind, value in boxes(am) if kind == b'trak'))
    struct.pack_into('>I', at, at.index(b'stco') + 12, len(ftyp) + 12)
    return ftyp + box(b'mdat', b'\0' * 8) + box(b'moov', header + vt + at)


def imports(c):
    result = []
    for name, data in [('video.mp4', mp4()), ('audio.m4a', mp4('audio'))]:
        value = c.post(PREFIX + '/media/import?filename=' + name, content=data)
        assert value.status_code == 200, value.text
        result.append(value.json())
    return dict(video=dict(media_id=result[0]['id'], expected_sha256=result[0]['sha256'], stream_index=0),
                audio=dict(media_id=result[1]['id'], expected_sha256=result[1]['sha256'], stream_index=0),
                name='pair.mp4', request_id='controlled-local-pair-request', rights_confirmed=True)


def fake_mux(self, job, operation, *, deadline=None):
    """Only a persistence/publication substitute; never counted as actual native mux evidence."""
    source = source_snapshot(job.source_snapshot)
    with Session(self.engine) as session:
        row = session.get(MediaDownloadAttempt, (job.id, job.run_generation))
        record = attempt_record(row.record)
        for selected, frozen in zip(source.tracks, record.tracks, strict=True):
            original = session.get(MediaEntry, selected.media_id)
            path = self.root / frozen.relative_path
            path.write_bytes((self.root / original.relative_path).read_bytes())
            frozen.state = 'probed'
            from study_workbench.media_probes import ProbeMetadata
            frozen.metadata = ProbeMetadata.model_validate(metadata(selected.role))
    total = sum(t.size for t in source.tracks)
    media_mux.progress(self, job, dict(phase='probing', received=total, total=total, record=record.model_dump(mode='json')))
    raw = pair_bytes()
    pending = operation / 'output.pending.mp4'
    pending.write_bytes(raw)
    record.output = OutputReceipt.model_validate(dict(state='prepared', pending_path=pending.relative_to(self.root).as_posix(),
        final_path=job.relative_path, size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        metadata=dict(container='mp4', duration_ms=200, streams=[
            metadata('video')['streams'][0], {**metadata('audio')['streams'][0], 'index': 1}])))
    return record.model_dump(mode='json')


@pytest.mark.parametrize('fault', ['rights_false', 'rights_int', 'extra_path', 'headers', 'snapshot', 'index_bool',
                                  'index_large', 'sha', 'name', 'same_stream', 'foreign', 'changed'])
def test_create_is_strict_scoped_and_does_not_accept_paths_headers_or_arbitrary_snapshots(tmp_path, monkeypatch, fault):
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        body = imports(c)
        if fault == 'rights_false':
            body['rights_confirmed'] = False
        elif fault == 'rights_int':
            body['rights_confirmed'] = 1
        elif fault in {'extra_path', 'headers', 'snapshot'}:
            body[fault] = 'forbidden'
        elif fault == 'index_bool':
            body['video']['stream_index'] = True
        elif fault == 'index_large':
            body['video']['stream_index'] = 2
        elif fault == 'sha':
            body['video']['expected_sha256'] = 'wrong'
        elif fault == 'name':
            body['name'] = 'copy.webm'
        elif fault == 'same_stream':
            body['audio'] = copy.deepcopy(body['video'])
        elif fault == 'foreign':
            other = c.post('/api/workspaces', json={'name': 'other'}).json()['id']
            assert c.post(f'/api/workspaces/{other}/media-downloads/local-pair', json=body).status_code == 404
            return
        else:
            body['video']['expected_sha256'] = 'f' * 64
        expected = 409 if fault == 'changed' else 422
        value = c.post(PREFIX + '/media-downloads/local-pair', json=body)
        assert value.status_code == expected, value.text
        assert c.post(PREFIX + '/media-downloads/local-pair', json=body,
                      headers={'Origin': 'https://example.invalid'}).status_code == 403


def test_same_request_and_output_dedup_preserve_separate_jobs_nodes_and_originals(tmp_path, monkeypatch):
    monkeypatch.setattr(MediaDownloads, 'child', fake_mux)
    with client(tmp_path) as c:
        body = imports(c)
        first = c.post(PREFIX + '/media-downloads/local-pair', json=body)
        assert first.status_code == 200, first.text
        ready = wait(c, first.json()['id'], {'ready', 'failed'})
        assert ready['status'] == 'ready', ready
        assert not ready['can_resume'] and ready['source_snapshot']['kind'] == 'local_pair'
        assert ready['result']['output']['size'] == len(pair_bytes())
        assert c.post(PREFIX + '/media-downloads/local-pair', json=body).json()['id'] == ready['id']
        assert c.post(PREFIX + '/media-downloads/local-pair', json={**body, 'name': 'changed.mp4'}).status_code == 409
        second = c.post(PREFIX + '/media-downloads/local-pair', json={**body, 'name': 'second.mp4',
                                                                   'request_id': 'another-local-pair-request'})
        result = wait(c, second.json()['id'], {'ready', 'failed'})
        assert result['status'] == 'ready' and result['result']['deduplicated'], result
        assert result['result']['media_id'] == ready['result']['media_id']
        assert result['result']['resource_item_id'] != ready['result']['resource_item_id']
        with Session(c.app.state.engine) as session:
            rows = list(session.scalars(select(MediaDownloadAttempt)))
            assert len(rows) == 2 and all(row.status == row.phase == 'ready' for row in rows)
        assert c.post(PREFIX + '/media-downloads/' + ready['id'] + '/retry', json={'mode': 'restart'}).status_code == 409


def test_pause_requires_explicit_restart_and_retains_previous_attempt_files(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    counter = 0
    def blocking(self, job, operation, *, deadline=None):
        nonlocal counter
        result = fake_mux(self, job, operation, deadline=deadline)
        counter += 1
        if counter == 1:
            entered.set()
            assert release.wait(5)
            self.check(job.id)
        return result
    monkeypatch.setattr(MediaDownloads, 'child', blocking)
    with client(tmp_path) as c:
        body = imports(c)
        job = c.post(PREFIX + '/media-downloads/local-pair', json=body).json()
        try:
            assert entered.wait(5)
            assert c.post(PREFIX + '/media-downloads/' + job['id'] + '/pause').status_code == 200
        finally:
            release.set()
        paused = wait(c, job['id'], {'paused'})
        assert not paused['can_resume']
        old = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in
               (tmp_path / f"workspaces/default/downloads/{job['id']}/1").rglob('*') if p.is_file()}
        assert old
        assert c.post(PREFIX + '/media-downloads/' + job['id'] + '/retry', json={'mode': 'resume'}).status_code == 409
        assert c.post(PREFIX + '/media-downloads/' + job['id'] + '/retry', json={'mode': 'restart'}).status_code == 200
        ready = wait(c, job['id'], {'ready', 'failed'})
        assert ready['status'] == 'ready' and ready['attempt'] == 2, ready
        assert all((tmp_path / relative).read_bytes() == data for relative, data in old.items())
        with Session(c.app.state.engine) as session:
            first = session.get(MediaDownloadAttempt, (job['id'], 1))
            second = session.get(MediaDownloadAttempt, (job['id'], 2))
            assert first.status == 'paused' and second.status == 'ready'


@pytest.mark.parametrize('stage', ['before_move', 'after_move'])
def test_publication_failure_preserves_prepared_receipt_backup_and_explicit_recovery(tmp_path, monkeypatch, stage):
    monkeypatch.setattr(MediaDownloads, 'child', fake_mux)
    original = media_mux.publish_output
    injected = False
    def failing(pending, final):
        nonlocal injected
        if injected:
            return original(pending, final)
        injected = True
        if stage == 'after_move':
            original(pending, final)
        raise RuntimeError('owned injected publication failure')
    monkeypatch.setattr(media_mux, 'publish_output', failing)
    root = tmp_path / 'source'
    with client(root) as c:
        body = imports(c)
        job = c.post(PREFIX + '/media-downloads/local-pair', json=body).json()
        failed = wait(c, job['id'], {'failed'})
        assert not failed['result']
        with Session(c.app.state.engine) as session:
            receipt = session.get(MediaDownloadAttempt, (job['id'], 1))
            assert receipt.status == 'failed' and receipt.phase == 'publishing'
            record = attempt_record(receipt.record)
            assert record.output.state == 'prepared'
        old = {p.relative_to(root).as_posix(): p.read_bytes() for p in
               (root / f"workspaces/default/downloads/{job['id']}").rglob('*') if p.is_file()}
    package, restored = tmp_path / 'full.zip', tmp_path / 'restored'
    backup_store.create_backup(root, package)
    backup_store.restore_backup(package, restored, tmp_path / 'settings.json')
    with client(restored) as c:
        assert c.get(PREFIX + '/media-downloads/' + job['id']).json()['status'] == 'failed'
        assert c.post(PREFIX + '/media-downloads/' + job['id'] + '/retry', json={'mode': 'restart'}).status_code == 200
        ready = wait(c, job['id'], {'ready', 'failed'})
        assert ready['status'] == 'ready' and ready['attempt'] == 2, ready
    assert all((root / p).read_bytes() == data and (restored / p).read_bytes() == data for p, data in old.items())


def test_conflicting_destination_is_not_overwritten_and_backup_retains_both_files(tmp_path, monkeypatch):
    def conflict(self, job, operation, *, deadline=None):
        result = fake_mux(self, job, operation, deadline=deadline)
        (self.root / job.relative_path).write_bytes(b'owned unrelated conflicting bytes')
        return result
    monkeypatch.setattr(MediaDownloads, 'child', conflict)
    root = tmp_path / 'source'
    with client(root) as c:
        job = c.post(PREFIX + '/media-downloads/local-pair', json=imports(c)).json()
        failed = wait(c, job['id'], {'failed'})
        assert not failed['result']
        final = root / f"workspaces/default/downloads/{job['id']}/1.mp4"
        assert final.read_bytes() == b'owned unrelated conflicting bytes'
    # The valid pending output is the prepared receipt; the unrelated destination is retained, not adopted.
    checked = library_integrity.check_library(root)
    assert checked['complete'] and not checked['healthy']
    assert any(issue['code'] == 'hash_mismatch' for issue in checked['issues'])
    package, restored = tmp_path / 'full.zip', tmp_path / 'restored'
    backup_store.create_backup(root, package)
    backup_store.restore_backup(package, restored, tmp_path / 'settings.json')
    assert (restored / final.relative_to(root)).read_bytes() == b'owned unrelated conflicting bytes'
    pending = root / f"workspaces/default/downloads/{job['id']}/1/1/output.pending.mp4"
    pending.write_bytes(b'owned damaged pending bytes')
    with pytest.raises(ValueError, match='收据缺失'):
        backup_store.create_backup(root, tmp_path / 'no-valid-output.zip')
    assert not (tmp_path / 'no-valid-output.zip').exists()
    assert final.read_bytes() == b'owned unrelated conflicting bytes'


def test_late_execution_cannot_mark_a_newer_generation_failed_or_publish_old_output(tmp_path, monkeypatch):
    def stale(self, job, operation, *, deadline=None):
        result = fake_mux(self, job, operation, deadline=deadline)
        with write_transaction(self.engine) as session:
            old = session.get(MediaDownloadAttempt, (job.id, job.run_generation))
            old.status = 'interrupted'
            current = session.get(MediaDownloadJob, job.id)
            current.run_generation += 1
            record = copy.deepcopy(old.record)
            for track in record['tracks']:
                track['relative_path'] = track['relative_path'].replace('/1/1/', '/1/2/')
                track['state'], track['metadata'] = 'pending', None
            session.add(MediaDownloadAttempt(job_id=job.id, workspace_id=job.workspace_id, generation=2,
                attempt=1, source_snapshot_sha256=job.source_snapshot_sha256, status='running',
                phase='copying', record=record, created_at='2000-01-01'))
        return result
    monkeypatch.setattr(MediaDownloads, 'child', stale)
    with client(tmp_path) as c:
        value = c.post(PREFIX + '/media-downloads/local-pair', json=imports(c)).json()
        c.app.state.downloads.pool.shutdown(wait=True)
        with Session(c.app.state.engine) as session:
            job = session.get(MediaDownloadJob, value['id'])
            assert job.status == 'running' and job.run_generation == 2 and not job.result
            assert session.get(MediaDownloadAttempt, (job.id, 2)).status == 'running'
        assert not (tmp_path / f"workspaces/default/downloads/{value['id']}/1.mp4").exists()


@pytest.mark.parametrize('case', ['boolean', 'large', 'input', 'third', 'probe_source', 'probe_output'])
def test_native_recipes_have_fixed_local_names_maps_protocol_and_no_external_parameters(tmp_path, case):
    if case.startswith('probe'):
        args = ('http://example.invalid/x', 'probe.json') if case == 'probe_source' else ('source.mp4', '../out')
        with pytest.raises(ValueError):
            media_probe_runtime.probe_command(tmp_path, tmp_path, *args)
        return
    inputs, indices = ['input0.mp4', 'input1.m4a'], [0, 0]
    if case == 'boolean':
        indices[0] = True
    elif case == 'large':
        indices[0] = 2
    elif case == 'input':
        inputs[0] = '//server/share/input'
    else:
        inputs.append('extra.mp4')
    with pytest.raises(ValueError):
        media_probe_runtime.mux_command(tmp_path, tmp_path, inputs, indices)


@pytest.mark.parametrize('fault', ['extra', 'boolean', 'total', 'phase', 'receipt_hash'])
def test_progress_rejects_unknown_fields_boolean_budget_and_identity_before_writing(fault):
    source = source_snapshot(selection())
    class NeverEngine:
        def connect(self):
            raise AssertionError('Invalid IPC reached SQL')
    class Download:
        engine = NeverEngine()
    class Job:
        id = 'a' * 32
        workspace_id = 'default'
        attempt = run_generation = 1
        source_kind = 'local_pair'
        source_url = None
        source_snapshot = source.model_dump(mode='json')
        source_snapshot_sha256 = source_digest(source)
        relative_path = 'workspaces/default/downloads/' + 'a' * 32 + '/1.mp4'
        status = 'running'
    value = {'record': receipt(source), 'phase': 'copying', 'received': 0, 'total': 20}
    if fault == 'extra':
        value['url'] = 'forbidden'
    elif fault == 'boolean':
        value['received'] = True
    elif fault == 'total':
        value['total'] = 21
    elif fault == 'phase':
        value['phase'] = 'network'
    else:
        value['record']['source_snapshot_sha256'] = 'f' * 64
    with pytest.raises((DownloadError, ValueError)):
        media_mux.progress(Download(), Job(), value)


def test_missing_optional_component_never_uses_path_or_launches_a_command(tmp_path, monkeypatch):
    from study_workbench import media_downloads
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('Missing component must not launch anything')
    monkeypatch.setattr(media_downloads.subprocess, 'Popen', forbidden)
    monkeypatch.setenv('STUDY_FFMPEG_RUNTIME', str(tmp_path / 'unavailable-component'))
    with client(tmp_path) as c:
        body = imports(c)
        value = c.post(PREFIX + '/media-downloads/local-pair', json=body)
        assert value.status_code == 200
        failed = wait(c, value.json()['id'], {'failed'})
        assert '组件' in failed['error'] and not failed['result'] and not calls
        with Session(c.app.state.engine) as session:
            receipt = session.get(MediaDownloadAttempt, (failed['id'], 1))
            assert receipt.status == 'failed' and receipt.phase == 'copying'
            assert all(t['state'] == 'pending' and t['metadata'] is None for t in receipt.record['tracks'])
            for selected in (body['video'], body['audio']):
                item = session.get(MediaEntry, selected['media_id'])
                assert hashlib.sha256((tmp_path / item.relative_path).read_bytes()).hexdigest() == selected['expected_sha256']
