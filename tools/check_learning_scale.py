"""Pre-registered Windows learning-read benchmark, using only freshly generated databases."""
import argparse
import copy
import ctypes
import hashlib
import json
import math
import os
import platform
import queue
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing, contextmanager
from pathlib import Path

from sqlalchemy import delete, insert

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from prepare_java_runtime import no_links
from release_inventory import stage_files
from study_workbench.content import DEMO, SUBJECTIVE  # noqa: E402
from study_workbench.db import (  # noqa: E402
    Attempt,
    AttemptReview,
    LearningEvent,
    Note,
    Question,
    Resource,
    database,
)
from study_workbench.question_protocol import QuestionDocument  # noqa: E402

SCOPE = '/api/workspaces/default'
MARKER = 'fresh-learning-scale-v1'
THRESHOLDS = dict(history=500, statistics=5000, study=5000, record=2000)
MIB = 1024 * 1024
TEXT = 'x' * 1024
BLANKS = {name: 'x' * 256 for name in ('one', 'two', 'three', 'four')}
WRONG_BLANKS = {name: 'y' * 256 for name in BLANKS}
STAMP = '2000-01-01T00:00:00+00:00'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def logical_hash(path, *, exclude_attempt_id=None):
    no_links(path)
    checksum = hashlib.sha256()
    with closing(sqlite3.connect(path.absolute().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('PRAGMA query_only=ON')
        for line in connection.iterdump():
            if exclude_attempt_id is not None and line.startswith(f'INSERT INTO "attempts" VALUES({int(exclude_attempt_id)},'):
                continue
            checksum.update(line.encode('utf-8') + b'\n')
    return checksum.hexdigest()


def seed(data, other, count, event_count=10000):
    """Construct legal historical rows only inside a marked, empty-attempt fixture."""
    assert 400 <= count <= 100000 and count % 100 == 0 and 200 <= event_count <= 10000
    assert (data.parent / 'fixture-marker').read_text('utf-8') == MARKER
    no_links(data)
    engine = database(data / 'study.db')
    main_ids, foreign_ids, event_ids = [], [], []
    try:
        with engine.begin() as connection:
            assert connection.exec_driver_sql('SELECT count(*) FROM attempts').scalar_one() == 0
            for workspace in ('default', other):
                questions = []
                for index in range(100):
                    content = copy.deepcopy(SUBJECTIVE if workspace != 'default' or index % 4 == 2 else DEMO)
                    content.update(id=f'scale-{index:03}', subject='Synthetic scale', knowledge_points=[f'group-{index % 4}'])
                    if workspace == 'default' and index % 4 != 2:
                        content.update(kind='fill_blank', options=[], answer=dict(blanks=[
                            dict(id=name, accepted=[value], normalization='exact') for name, value in BLANKS.items()]))
                    QuestionDocument.model_validate(content)
                    questions.append(dict(id=content['id'], workspace_id=workspace, content=content))
                connection.execute(insert(Question), questions)
                original = data / 'workspaces' / workspace / 'originals' / 'scale-note.txt'
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(b'Self-authored synthetic learning-scale original.\n')
                connection.execute(insert(Resource), dict(id='scale-resource-' + workspace, workspace_id=workspace,
                    original_name='scale-note.txt', relative_path='scale-note.txt', mime='text/plain',
                    sha256=digest(original.read_bytes()), size=original.stat().st_size))
                connection.execute(insert(Note), [dict(id=f'scale-note-{workspace}-{i}', workspace_id=workspace,
                    resource_id='scale-resource-' + workspace, title=f'Synthetic note {i}', content=[])
                    for i in range(3)])
            identifier, review_id = 0, 0
            for start in range(0, count, 1000):
                attempts, reviews = [], []
                for ordinal in range(start, min(start + 1000, count)):
                    identifier += 1
                    main_ids.append(identifier)
                    group = ordinal % 4
                    response = {'text': TEXT} if group == 2 else {'blanks': BLANKS if group < 2 else WRONG_BLANKS}
                    attempts.append(dict(id=identifier, workspace_id='default', question_id=f'scale-{ordinal % 100:03}',
                        response=response, status='pending_review' if group == 2 else 'graded',
                        score=None if group == 2 else 1 if group < 2 else 0, created_at=STAMP,
                        question_revision=1, request_id=None, question_version_id=None))
                    if group < 2:
                        for score in ((0, 1) if group == 0 else (1, 0)):
                            review_id += 1
                            reviews.append(dict(id=review_id, attempt_id=identifier, score=score, feedback=TEXT, created_at=STAMP))
                    if (ordinal + 1) % 10 == 0:
                        identifier += 1
                        foreign_ids.append(identifier)
                        attempts.append(dict(id=identifier, workspace_id=other,
                            question_id=f'scale-{(len(foreign_ids) - 1) % 100:03}', response={'text': TEXT},
                            status='pending_review', score=None, created_at=STAMP,
                            question_revision=1, request_id=None, question_version_id=None))
                connection.execute(insert(Attempt), attempts)
                connection.execute(insert(AttemptReview), reviews)
            events, event_id = [], 0
            for ordinal in range(1, event_count + 1):
                event_id += 1
                event_ids.append(event_id)
                content = dict(kind='reviewed' if ordinal % 2 == 0 else 'annotation', note='Synthetic event',
                               note_id=f'scale-note-default-{ordinal % 3}')
                if ordinal == 1:
                    content['knowledge_points'] = ['initial']
                elif ordinal == event_count - 150:
                    content['knowledge_points'] = []
                elif ordinal == event_count - 2:
                    content['knowledge_points'] = None
                events.append(dict(id=event_id, attempt_id=main_ids[0], request_id=f'scale_event_{ordinal:08}',
                                   content=content, created_at=STAMP))
                if ordinal % 10 == 0:
                    event_id += 1
                    events.append(dict(id=event_id, attempt_id=foreign_ids[0], request_id=f'foreign_event_{ordinal:08}',
                        content=dict(kind='reviewed', note='Foreign stream', knowledge_points=['foreign']), created_at=STAMP))
                if len(events) >= 1000:
                    connection.execute(insert(LearningEvent), events)
                    events = []
            if events:
                connection.execute(insert(LearningEvent), events)
            # Model a note removed AFTER a valid historical relation, never an invalid append API call.
            connection.execute(delete(Note).where(Note.id == 'scale-note-default-2'))
            assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    finally:
        engine.dispose()
    return dict(main_ids=main_ids, foreign_ids=foreign_ids, event_ids=event_ids,
                other=other, count=count, event_count=event_count, focus=main_ids[0])


def verify_history(page, expected_ids, positions):
    assert [row['id'] for row in page] == expected_ids, 'History cursor lost, duplicated or leaked a row'
    for row in page:
        ordinal = positions[row['id']]
        group = ordinal % 4
        assert row['question_id'] == f'scale-{ordinal % 100:03}'
        assert row['question_version_id'] is None and row['question_revision'] == 1
        assert row['status'] == ('pending_review' if group == 2 else 'graded')
        assert row['score'] == (None if group == 2 else 1 if group == 0 else 0)
        assert [r['score'] for r in row['reviews']] == ([0, 1] if group == 0 else [1, 0] if group == 1 else [])
        assert all(r['feedback'] == TEXT for r in row['reviews'])
        assert row['response'] == ({'text': TEXT} if group == 2 else {'blanks': BLANKS if group < 2 else WRONG_BLANKS})


def verify_record(value, fixture):
    assert value['attempt_id'] == fixture['focus'] and value['version_status'] == 'unknown'
    assert value['question_version_id'] is None and value['resource_item_id'] is None
    assert value['source_resource_item_ids'] == []
    assert value['knowledge_points'] is None and value['effective_knowledge_points'] == []
    assert value['reviewed_count'] == fixture['event_count'] // 2
    assert value['knowledge_projection_algorithm'] == 'latest-explicit-annotation-v1'
    assert value['projection_algorithm'] == 'attempt-review-streak-v1'
    assert {n['id']: n['available'] for n in value['related_notes']} == {
        'scale-note-default-0': True, 'scale-note-default-1': True, 'scale-note-default-2': False}


def verify_reads(api, fixture, result):
    ids = fixture['main_ids'][::-1]
    positions = {identifier: ordinal for ordinal, identifier in enumerate(fixture['main_ids'])}
    before, history_pages = None, 0
    for offset in range(0, len(ids), 100):
        started = time.perf_counter()
        page = api('GET', SCOPE + '/attempt-history?limit=100' + (f'&before_id={before}' if before else ''))
        result.setdefault('history_page_ms', []).append((time.perf_counter() - started) * 1000)
        verify_history(page, ids[offset:offset + 100], positions)
        before = page[-1]['id']
        history_pages += 1
    assert api('GET', SCOPE + f'/attempt-history?before_id={before}') == []
    endpoint = f"{SCOPE}/attempts/{fixture['focus']}/record"
    before, event_pages = None, 0
    event_ids = fixture['event_ids'][::-1]
    for offset in range(0, len(event_ids), 100):
        started = time.perf_counter()
        record = api('GET', endpoint + '?limit=100' + (f'&before_id={before}' if before else ''))
        result.setdefault('event_page_ms', []).append((time.perf_counter() - started) * 1000)
        verify_record(record, fixture)
        assert [e['id'] for e in record['events']] == event_ids[offset:offset + 100]
        before = record['events'][-1]['id']
        assert record['next_before_id'] == before
        event_pages += 1
    empty = api('GET', endpoint + f'?before_id={before}')
    verify_record(empty, fixture)
    assert empty['events'] == [] and empty['next_before_id'] is None
    statistics = api('GET', SCOPE + '/statistics')
    assert {k: statistics[k] for k in ('questions', 'attempts', 'mastered', 'wrong', 'pending_review', 'due')} == {
        'questions': 102, 'attempts': fixture['count'], 'mastered': 25, 'wrong': 50, 'pending_review': 25, 'due': 77}
    points = {p['name']: (p['questions'], p['mastered'], p['wrong']) for p in statistics['knowledge_points']
              if p['subject'] == 'Synthetic scale'}
    assert points == {'group-0': (25, 25, 0), 'group-1': (25, 0, 25),
                      'group-2': (25, 0, 0), 'group-3': (25, 0, 25)}
    foreign = '/api/workspaces/' + fixture['other']
    assert api('GET', foreign + '/statistics')['attempts'] == len(fixture['foreign_ids'])
    assert len(api('GET', SCOPE + '/study?mode=wrong&limit=100')) == 50
    study = api('GET', SCOPE + '/study?mode=all&limit=100') + api('GET', SCOPE + '/study?mode=all&limit=100&offset=100')
    assert len(study) == 102 and {r['id'] for r in study} == {'demo-integral', 'demo-proof'} | {
        f'scale-{index:03}' for index in range(100)}
    for row in study:
        if row['id'].startswith('scale-'):
            group = int(row['id'].removeprefix('scale-')) % 4
            assert row['attempt_count'] == fixture['count'] // 100
            assert (row['mastered'], row['wrong'], row['pending_review']) == (
                group == 0, group in {1, 3}, group == 2)
            assert row['knowledge_points'] == [f'group-{group}']
    assert api('GET', f"{SCOPE}/attempts/{fixture['focus']}/notes/scale-note-default-0")['content'] == []
    for path in (foreign + f"/attempts/{fixture['focus']}/record",
                 f"{SCOPE}/attempts/{fixture['focus']}/notes/scale-note-default-2"):
        api('GET', path, expected=404)
    api('GET', endpoint, expected=401, headers={'Authorization': 'Bearer wrong'})
    api('GET', endpoint, expected=403, headers={'Origin': 'https://example.invalid'})
    api('POST', f"{SCOPE}/attempts/{fixture['focus']}/events", dict(request_id='scale_foreign_note_0001',
        kind='annotation', note='Rejected foreign link', note_id=f"scale-note-{fixture['other']}-0"), expected=404)
    result.update(history_pages=history_pages, event_pages=event_pages, statistics=statistics,
                  old_cursor_boundary_verified=True, projection_consistent_across_all_pages=True)


def verify_append(api, fixture):
    first = api('GET', SCOPE + '/attempt-history?limit=100')
    added = api('POST', SCOPE + '/attempts', dict(question_id='demo-integral', response={'selected': ['a']}))
    assert added['id'] > first[0]['id']
    old = api('GET', SCOPE + f"/attempt-history?limit=100&before_id={first[-1]['id']}")
    assert [r['id'] for r in old] == fixture['main_ids'][::-1][100:200]
    assert api('GET', SCOPE + '/attempt-history?limit=1')[0]['id'] == added['id']
    return added['id']


@contextmanager
def backend(root, exe, *, deadline=None):
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    temporary = root / 'runtime-tmp'
    no_links(root)
    temporary.mkdir(exist_ok=True)
    no_links(temporary)
    with tempfile.TemporaryFile(dir=temporary) as probe:
        probe.write(b'Self-authored owned temporary-directory probe')
        probe.flush()
    environment.update(TEMP=str(temporary), TMP=str(temporary))
    repository = Path(__file__).resolve().parents[1]
    command = [str(exe)] if exe else [sys.executable, '-m', 'study_workbench']
    environment['PYTHONPATH'] = str(repository / 'backend')
    if exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    token = secrets.token_urlsafe(32)
    with (root / 'backend-stderr.txt').open('ab') as errors:
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data'), '--config', str(root / 'settings.json')],
            cwd=root if exe else repository / 'backend', env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=errors, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.stdin.write(json.dumps(dict(token=token)) + '\n')
            process.stdin.flush()
            hello = queue.Queue()
            threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
            port = json.loads(hello.get(timeout=30))['port']
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def api(method, path, body=None, *, expected=200, headers=None):
                remaining = 10 if deadline is None else min(10, deadline - time.perf_counter())
                assert remaining > 0, 'Case exceeded 20-minute budget'
                auth = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
                auth.update(headers or {})
                request = urllib.request.Request(f'http://127.0.0.1:{port}' + path, method=method,
                    headers=auth, data=json.dumps(body).encode() if body is not None else None)
                try:
                    response = opener.open(request, timeout=remaining)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    payload = response.read(4 * MIB + 1)
                    assert deadline is None or time.perf_counter() <= deadline, 'Case exceeded 20-minute budget'
                    assert len(payload) <= 4 * MIB and response.status == expected, 'Response status/size differs'
                    return json.loads(payload)

            for _ in range(100):
                try:
                    assert api('GET', '/api/health')['status'] == 'ok'
                    break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise AssertionError('Backend readiness timed out')
            api.port = port
            yield api, process
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError('Backend failed to stop within budget') from None
            assert process.returncode == 0, 'Backend process failed'
            process.stdout.close()


class Counters(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage',
        'PeakPagefileUsage', 'PrivateUsage')]


def listener_pid(port):
    """Read only the owner of this exact IPv4 loopback listener; never publish the TCP table."""
    class Row(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulong) for name in ('state', 'address', 'port', 'remote', 'remote_port', 'pid')]

    function = ctypes.WinDLL('iphlpapi', use_last_error=True).GetExtendedTcpTable
    function.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int,
                         ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    size = ctypes.c_ulong()
    initial = function(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)
    assert initial == 122, f'Windows TCP owner query refused ({initial})'
    for _ in range(3):
        assert 4 <= size.value <= 8 * MIB, 'TCP listener table budget exceeded'
        table = ctypes.create_string_buffer(size.value)
        status = function(table, ctypes.byref(size), False, socket.AF_INET, 3, 0)
        if status == 122:
            continue
        assert status == 0, 'Cannot identify backend listener'
        count = ctypes.c_ulong.from_buffer_copy(table.raw[:4]).value
        assert count <= 20000 and 4 + count * ctypes.sizeof(Row) <= len(table)
        rows = [Row.from_buffer_copy(table, 4 + index * ctypes.sizeof(Row)) for index in range(count)]
        pids = {row.pid for row in rows if row.state == 2 and row.address == 0x0100007F
                and socket.ntohs(row.port & 0xFFFF) == port}
        assert len(pids) == 1 and 0 not in pids, 'Backend listener owner missing or ambiguous'
        return pids.pop()
    raise AssertionError('Backend listener table changed beyond retry budget')


def process_chain(kernel, child, parent):
    class Entry(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('usage', ctypes.c_ulong), ('pid', ctypes.c_ulong),
            ('heap', ctypes.c_size_t), ('module', ctypes.c_ulong), ('threads', ctypes.c_ulong),
            ('parent', ctypes.c_ulong), ('priority', ctypes.c_long), ('flags', ctypes.c_ulong),
            ('name', ctypes.c_wchar * 260)]

    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(Entry)]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    assert snapshot not in (None, ctypes.c_void_p(-1).value), 'Cannot inspect backend ancestry'
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        assert kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        parents = {}
        while True:
            assert len(parents) < 20000, 'Process metadata budget exceeded'
            parents[entry.pid] = (entry.parent, entry.name)
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                assert ctypes.get_last_error() == 18, 'Process snapshot failed'
                break
        chain = []
        for _ in range(8):
            assert child in parents, 'Backend listener is outside the launched process chain'
            previous, name = parents[child]
            chain.append(dict(pid=child, image_name=name))
            if child == parent:
                return chain
            child = previous
        raise AssertionError('Backend ancestry exceeds fixed budget')
    finally:
        kernel.CloseHandle(snapshot)


@contextmanager
def memory_samples(process, port, expected_exe, result):
    kernel, psapi = ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
                                                ctypes.POINTER(ctypes.c_ulong)]
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    pid = listener_pid(port)
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    stopped, failures, lock = threading.Event(), [], threading.Lock()

    def sample():
        assert process.poll() is None and listener_pid(port) == pid, 'Backend listener PID changed or exited'
        exit_code = ctypes.c_ulong()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) and exit_code.value == 259, 'Backend exited'
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        with lock:
            result.setdefault('baseline_private_bytes', counters.PrivateUsage)
            result['peak_working_set_bytes'] = max(result.get('peak_working_set_bytes', 0), counters.PeakWorkingSetSize)
            result['observed_private_bytes'] = max(result.get('observed_private_bytes', 0), counters.PrivateUsage)
            result['samples'] = result.get('samples', 0) + 1

    def observe():
        while not stopped.wait(.05):
            try:
                sample()
            except (OSError, AssertionError) as error:
                failures.append(type(error).__name__)
                return

    try:
        image = ctypes.create_unicode_buffer(32768)
        size = ctypes.c_ulong(len(image))
        assert kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)), 'Cannot inspect backend image'
        actual = Path(image.value)
        assert actual.samefile(expected_exe), 'Listener executable differs from expected backend'
        result.update(service_pid=pid, launcher_pid=process.pid,
                      process_chain=process_chain(kernel, pid, process.pid),
                      image_name=actual.name, image_sha256=digest(actual.read_bytes()),
                      identity_method='exact-loopback-listener+held-process-handle+image+launcher-ancestry')
        sample()
        thread = threading.Thread(target=observe, daemon=True)
        thread.start()
        try:
            yield sample
        finally:
            stopped.set()
            thread.join(timeout=2)
            sample()
        assert not failures and not thread.is_alive(), 'Memory sampling failed'
        result['observed_private_growth_bytes'] = result['observed_private_bytes'] - result['baseline_private_bytes']
        assert result['peak_working_set_bytes'] <= 768 * MIB, 'Peak working set exceeded 768MiB'
        assert result['observed_private_growth_bytes'] <= 256 * MIB, 'Observed private growth exceeded 256MiB'
    finally:
        kernel.CloseHandle(handle)


def p95(values):
    assert values and all(math.isfinite(value) and value >= 0 for value in values)
    return sorted(values)[math.ceil(.95 * len(values)) - 1]


def timed_reads(api, fixture, result, sample):
    paths = dict(history=[SCOPE + '/attempt-history?limit=100'] + [
        SCOPE + f"/attempt-history?limit=100&before_id={fixture['main_ids'][i]}"
        for i in (len(fixture['main_ids']) // 2, 100)], statistics=[SCOPE + '/statistics'],
        study=[SCOPE + '/study?mode=all&limit=100'], record=[f"{SCOPE}/attempts/{fixture['focus']}/record?limit=100"])
    for name, routes in paths.items():
        for index in range(3):
            api('GET', routes[index % len(routes)])
        durations = []
        for index in range(30):
            started = time.perf_counter()
            api('GET', routes[index % len(routes)])
            durations.append((time.perf_counter() - started) * 1000)
            sample()
        result[name] = dict(samples_ms=durations, p95_ms=p95(durations), threshold_ms=THRESHOLDS[name])
        assert result[name]['p95_ms'] <= THRESHOLDS[name], f'{name} p95 exceeded pre-registered threshold'


def payload_identity(directory):
    return digest(json.dumps({name: digest(path.read_bytes()) for name, path in sorted(stage_files(directory).items())},
                             sort_keys=True).encode())


def machine_environment():
    import winreg

    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(name, ctypes.c_ulonglong)
            for name in ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]

    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)), 'Physical memory query failed'
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        processor = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    return dict(os=platform.platform(), python=platform.python_version(), logical_processors=os.cpu_count(),
                processor=processor, physical_ram_bytes=memory.total)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-root', required=True, type=Path, help='New directory; never an existing data root')
    parser.add_argument('--exe', type=Path, help='Existing matching-source frozen backend; not built by this tool')
    parser.add_argument('--attempts', type=int, choices=(1000, 10000, 100000),
                        help='One registered scale per coordinated quiet window; default runs all three')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This pre-registered memory benchmark requires Windows')
    root = args.test_root.absolute()
    no_links(root.parent)
    root.mkdir()
    (root / 'fixture-marker').write_text(MARKER, encoding='utf-8')
    exe = args.exe.absolute() if args.exe else None
    report = dict(status='in_progress', source_head_claim='68eaabd43de808ff0b258ebc4e854a4b355194bd',
        source_head_authenticated=False, collector_sha256=digest(Path(__file__).read_bytes()),
        environment=machine_environment(),
        thresholds_ms=THRESHOLDS, peak_working_set_limit_bytes=768 * MIB, observed_private_growth_limit_bytes=256 * MIB,
        memory_sample_interval_ms=50, warmups=3, samples=30, p95_method='nearest-rank', cases=[],
        temp_policy='per-case-owned-runtime-tmp; write/delete probe; SQLite temp_store unmodified',
        registered_scales=[1000, 10000, 100000], selected_scale=args.attempts,
        frozen=bool(exe), frozen_build_by_this_tool=False, product_performance_certified=False)
    try:
        identity = payload_identity(exe.parent) if exe else None
        if exe:
            checked = subprocess.run([sys.executable, str(Path(__file__).with_name('check_frozen_sources.py')),
                '--exe', str(exe)], capture_output=True, text=True, timeout=60)
            assert checked.returncode == 0, 'Existing frozen backend differs from business source'
            report.update(exe_sha256=digest(exe.read_bytes()), frozen_payload_identity=identity,
                          frozen_source_check=checked.stdout.strip())
        for count in (args.attempts,) if args.attempts else (1000, 10000, 100000):
            case_root = root / str(count)
            case_root.mkdir()
            (case_root / 'fixture-marker').write_text(MARKER, encoding='utf-8')
            with backend(case_root, exe) as (api, _):
                other = api('POST', '/api/workspaces', dict(name='Synthetic isolation'))['id']
            fixture = seed(case_root / 'data', other, count)
            case = dict(attempts=count, foreign_attempts=count // 10, events=10000,
                        foreign_events=1000, correctness={}, metrics={}, memory={})
            report['cases'].append(case)
            started = time.perf_counter()
            with backend(case_root, exe, deadline=started + 1200) as (api, process):
                before = logical_hash(case_root / 'data/study.db')
                originals = {p.relative_to(case_root).as_posix(): digest(p.read_bytes())
                             for p in (case_root / 'data/workspaces').rglob('scale-note.txt')}
                with memory_samples(process, api.port, exe or Path(sys._base_executable), case['memory']) as sample:
                    traverse = time.perf_counter()
                    verify_reads(api, fixture, case['correctness'])
                    case['full_traversal_seconds'] = time.perf_counter() - traverse
                    timed_reads(api, fixture, case['metrics'], sample)
                assert logical_hash(case_root / 'data/study.db') == before, 'Read-only phase changed database'
                assert all(digest((case_root / p).read_bytes()) == value for p, value in originals.items())
                case.update(readonly_logical_sha256=before, originals_sha256=originals)
                added = verify_append(api, fixture)
                assert logical_hash(case_root / 'data/study.db') != before
                assert logical_hash(case_root / 'data/study.db', exclude_attempt_id=added) == before, 'Append changed older data'
                with closing(sqlite3.connect(case_root / 'data/study.db')) as connection:
                    assert connection.execute('SELECT count(*) FROM attempts').fetchone()[0] == count + count // 10 + 1
                    assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
                case['controlled_append_id'] = added
                assert time.perf_counter() - started <= 1200, 'Case exceeded 20-minute budget'
            print(f'PASS: {count} attempts / 10000-event projection / read-only hashes / bounded reads', flush=True)
        if exe:
            assert payload_identity(exe.parent) == identity, 'Existing frozen payload changed during benchmark'
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', failure_type=type(error).__name__, failure=str(error))
        raise
    finally:
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
