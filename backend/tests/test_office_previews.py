import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from threading import Event
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session
from study_workbench import office_runtime
from study_workbench.content import DEMO, SUBJECTIVE
from study_workbench.db import DocumentPreview, database, write_transaction
from study_workbench.office_inputs import validate_office
from test_document_files import add
from test_explorer import PREFIX, TOKEN, assert_preserved, client, snapshot

SAMPLES = Path(__file__).parents[2] / 'contracts/samples'


def package(part='word/document.xml', value='<document/>', extras=None):
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('_rels/.rels', '<Relationships/>')
        archive.writestr(part, value)
        for name, content in (extras or {}).items():
            archive.writestr(name, content)
    return output.getvalue()


def wait(c, node, identifier):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = c.get(f'{PREFIX}/nodes/{node}/previews/{identifier}')
        assert response.status_code == 200
        value = response.json()
        if value['status'] not in {'queued', 'running'}:
            return value
        time.sleep(.01)
    raise AssertionError('Preview did not finish')


class FakeRuntime:
    fingerprint = 'a' * 64

    def __init__(self):
        self.calls = 0
        self.entered, self.release = Event(), Event()
        self.release.set()
        self.fail = False

    def convert(self, source, directory, checkpoint):
        self.calls += 1
        self.entered.set()
        while not self.release.wait(.01):
            checkpoint()
        checkpoint()
        if self.fail:
            raise ValueError('转换超过90秒，原件保留')
        (directory / 'output').mkdir()
        output = directory / 'output/source.pdf'
        output.write_bytes((SAMPLES / 'original-study.pdf').read_bytes())
        return output


@pytest.fixture
def fake(monkeypatch):
    value = FakeRuntime()
    monkeypatch.setattr(office_runtime, 'runtime', lambda: value)
    monkeypatch.setattr(office_runtime, 'capability', lambda: dict(
        available=True, fingerprint=value.fingerprint, version=office_runtime.VERSION))
    return value


@pytest.mark.parametrize('suffix', ['.docx', '.pptx'])
def test_ooxml_good_packages_and_boundary_rejections(suffix):
    part = 'word/document.xml' if suffix == '.docx' else 'ppt/presentation.xml'
    validate_office(package(part), suffix)
    attacks = [
        {'word/vbaProject.bin': b'macro'},
        {'word/_rels/document.xml.rels': '<Relationships><Relationship TargetMode="External" Target="https://example.com/secret"/></Relationships>'},
        {'word/_rels/document.xml.rels': '<Relationships><Relationship Target="../../../../secret"/></Relationships>'},
        {'word/_rels/document.xml.rels': '<Relationships><Relationship Target="%5c%5cserver/secret"/></Relationships>'},
        {'word/_rels/document.xml.rels': '<Relationships><Relationship Target="%252e%252e/secret"/></Relationships>'},
        {'word/media/image.svg': '<svg/>'},
        {'word/embeddings/object.bin': b'object'},
        {'../outside': b'x'},
        {'word/custom.xml': '<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///C:/secret">]><x/>'},
        {'word/field.xml': '<instrText>DDEAUTO command</instrText>'},
        {'word/field.xml': '<fldSimple instr="INCLUDETEXT C:/secret"/>'},
        {'word/chunk.xml': '<altChunk id="rId1"/>'},
        {'word/chunk.xml': '<OLEObject/>'},
        {'word/field.xml': '<p><instrText>D</instrText><instrText>DEAUTO command</instrText></p>'},
        {'word/custom.xml': '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x><x/>'.encode('utf-16')},
    ]
    for extras in attacks:
        with pytest.raises(ValueError):
            validate_office(package(part, extras=extras), suffix)
    for raw, kind in [(b'not-zip', suffix), (b'\xd0\xcf\x11\xe0encrypted', suffix), (package(part), '.doc')]:
        with pytest.raises(ValueError):
            validate_office(raw, kind)


def test_real_chart_data_xlsx_is_bounded_and_external_formulas_reject():
    xlsx = package('xl/workbook.xml', extras={'xl/worksheets/sheet1.xml': '<worksheet><v>85</v></worksheet>'})
    validate_office(package('ppt/presentation.xml', extras={'ppt/embeddings/chart.xlsx': xlsx}), '.pptx')
    assert validate_office(package('ppt/presentation.xml', extras={'ppt/charts/chart1.xml': '<chart/>'}), '.pptx')
    assert not validate_office(package(), '.docx')
    assert validate_office(package(value='<document><oMath><sSup/></oMath></document>'), '.docx')
    bad = package('xl/workbook.xml', extras={'xl/worksheets/sheet1.xml': '<worksheet><f>WEBSERVICE("https://example.com")</f></worksheet>'})
    with pytest.raises(ValueError):
        validate_office(package('ppt/presentation.xml', extras={'ppt/embeddings/chart.xlsx': bad}), '.pptx')
    for part, content in [('xl/macrosheets/sheet1.xml', '<macro/>'),
                          ('xl/worksheets/sheet1.xml', '<worksheet><f>SUM(A1:A2)</f></worksheet>'),
                          ('xl/names.xml', '<definedName>EXEC("command")</definedName>')]:
        dynamic = package('xl/workbook.xml', extras={part: content})
        with pytest.raises(ValueError):
            validate_office(package('ppt/presentation.xml', extras={'ppt/embeddings/chart.xlsx': dynamic}), '.pptx')


def test_preview_ready_cache_tamper_scope_and_original_preservation(tmp_path, fake):
    original = package()
    with client(tmp_path) as c:
        node, _, path = add(c, tmp_path, '资料.docx', original)
        endpoint = f'{PREFIX}/nodes/{node}/previews'
        body = {'expected_source_sha256': hashlib.sha256(original).hexdigest()}
        started = c.post(endpoint, json=body)
        assert started.status_code == 200, started.text
        value = wait(c, node, started.json()['id'])
        assert value['status'] == 'ready' and value['page_count'] == 2, value
        assert fake.calls == 1 and path.read_bytes() == original
        assert c.post(endpoint, json=body).json()['id'] == value['id']
        page = c.get(endpoint + f"/{value['id']}/page?page=2")
        assert page.status_code == 200, page.text
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.get(f"/api/workspaces/{other}/nodes/{node}/previews/{value['id']}").status_code == 404
        assert c.post(endpoint, json=dict(body, command='arbitrary')).status_code == 422
        with Session(c.app.state.engine) as session:
            relative = session.get(DocumentPreview, value['id']).relative_pdf
        (tmp_path / relative).write_bytes(b'changed')
        assert c.get(endpoint + f"/{value['id']}/page").status_code == 409
        retry = c.post(endpoint, json=body).json()
        assert retry['id'] != value['id']
        assert wait(c, node, retry['id'])['status'] == 'ready'
        assert fake.calls == 2
        path.write_bytes(b'externally-changed')
        assert c.get(endpoint + f"/{retry['id']}/page").status_code == 409


def test_cancel_duplicate_timeout_retry_and_unsafe_input_never_reach_converter(tmp_path, fake):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '资料.docx', package())
        endpoint = f'{PREFIX}/nodes/{node}/previews'
        body = {'expected_source_sha256': hashlib.sha256(package()).hexdigest()}
        # zip timestamps may differ; read the stored hash rather than synthesizing another archive.
        with Session(c.app.state.engine) as session:
            from study_workbench.db import Resource, WorkspaceNode
            body['expected_source_sha256'] = session.get(Resource, session.get(WorkspaceNode, node).resource_id).sha256
        fake.release.clear()
        first = c.post(endpoint, json=body).json()
        assert fake.entered.wait(5)
        assert c.post(endpoint, json=body).json()['id'] == first['id']
        assert c.post(endpoint + '/' + first['id'] + '/cancel').json()['cancel_requested']
        assert wait(c, node, first['id'])['status'] == 'cancelled'
        fake.release.set()
        fake.fail = True
        failed = c.post(endpoint, json=body).json()
        result = wait(c, node, failed['id'])
        assert result['status'] == 'failed' and '90' in result['error']
        fake.fail = False
        retried = c.post(endpoint, json=body).json()
        assert wait(c, node, retried['id'])['status'] == 'ready'
        malicious = package(extras={'word/vbaProject.bin': b'macro'})
        bad, _, _ = add(c, tmp_path, '宏.docx', malicious)
        before = fake.calls
        job = c.post(f'{PREFIX}/nodes/{bad}/previews', json={'expected_source_sha256': hashlib.sha256(malicious).hexdigest()}).json()
        assert wait(c, bad, job['id'])['status'] == 'failed'
        assert fake.calls == before


def test_missing_component_and_restart_interruption(tmp_path, fake, monkeypatch):
    with client(tmp_path) as c:
        node, resource_id, _ = add(c, tmp_path, '资料.docx', package())
        with Session(c.app.state.engine) as session:
            from study_workbench.db import Resource
            checksum = session.get(Resource, resource_id).sha256
        monkeypatch.setattr(office_runtime, 'capability', lambda: dict(available=False, reason='缺少已核离线组件'))
        assert c.post(f'{PREFIX}/nodes/{node}/previews', json={'expected_source_sha256': checksum}).status_code == 409
        with write_transaction(c.app.state.engine) as session:
            session.add(DocumentPreview(id='f' * 32, workspace_id='default', node_id=node, source_resource_id=resource_id,
                source_sha256=checksum, runtime_fingerprint='a' * 64, converter_version='26.8.1', options_hash='b' * 64,
                status='running', cancel_requested=False, relative_pdf='preserved/output/source.pdf', created_at='2026-10-26'))
        (tmp_path / 'preserved/output').mkdir(parents=True)
        (tmp_path / 'preserved/output/source.pdf').write_bytes(b'partial')
    with client(tmp_path) as c:
        value = c.get(f'{PREFIX}/nodes/{node}/previews/' + 'f' * 32).json()
        assert value['status'] == 'interrupted'
        assert (tmp_path / 'preserved/output/source.pdf').read_bytes() == b'partial'


def test_0008_upgrade_and_failure_retains_workfiles_layout_and_all_old_rows(tmp_path, monkeypatch):
    root = tmp_path / 'old'
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0008')
        for content in (DEMO, SUBJECTIVE):
            connection.execute(text("INSERT INTO questions VALUES (:id,'default',:content)"),
                               dict(id=content['id'], content=json.dumps(content)))
        connection.exec_driver_sql("INSERT INTO resources (id,workspace_id,original_name,relative_path,sha256,size,mime) VALUES ('r','default','原件.md','original.md','hash',3,'text/markdown')")
        connection.exec_driver_sql("INSERT INTO workspace_nodes(id,workspace_id,kind,name,name_key,resource_id) VALUES ('n','default','resource','原件.md','原件.md','r')")
        connection.exec_driver_sql("INSERT INTO document_workfiles VALUES ('n','default','working/current.md','oldhash')")
        connection.exec_driver_sql("UPDATE workspaces SET layout='{\"version\":2,\"future\":\"保留草稿\"}'")
    engine.dispose()
    (root / 'original.md').write_bytes(b'old')
    (root / 'working').mkdir()
    (root / 'working/current.md').write_bytes(b'working')
    before = snapshot(root / 'study.db')
    upgrade = command.upgrade

    def fail(config, revision):
        upgrade(config, revision)
        raise RuntimeError('injected 0010 failure')

    monkeypatch.setattr(command, 'upgrade', fail)
    from study_workbench.app import create_app
    with pytest.raises(RuntimeError, match='0010'):
        create_app(root, TOKEN)
    assert snapshot(root / 'study.db') == before
    monkeypatch.setattr(command, 'upgrade', upgrade)
    with client(root):
        after = snapshot(root / 'study.db')
        assert_preserved(before, after)
        with sqlite3.connect(root / 'study.db') as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert (root / 'working/current.md').read_bytes() == b'working'
    backups = list((root / 'backups').glob('study-before-0012-*.db'))
    assert backups and all(snapshot(path) == before for path in backups)


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object')
@pytest.mark.parametrize('abrupt', [False, True])
def test_owned_process_is_killed_on_cancel_and_owner_exit(tmp_path, abrupt):
    import _winapi
    marker, gate = tmp_path / 'child.pid', tmp_path / 'exit'
    child = tmp_path / 'child.py'
    child.write_text('import os,time,pathlib,sys\npathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\ntime.sleep(120)\n')
    command = [sys._base_executable, str(child), str(marker)]
    job, process, owner, handle = None, None, None, None
    try:
        if abrupt:
            script = tmp_path / 'owner.py'
            script.write_text(
                'import sys,time,os\nfrom pathlib import Path\n'
                f'sys.path.insert(0,{str(Path(__file__).parents[1])!r})\n'
                'from study_workbench.office_runtime import WindowsProcessJob\n'
                f'job=WindowsProcessJob()\nprocess=job.start({command!r},Path({str(tmp_path)!r}),dict(os.environ))\n'
                f'while not Path({str(gate)!r}).exists(): time.sleep(.01)\n'
                'os._exit(3)\n')
            owner = subprocess.Popen([sys.executable, str(script)], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            job = office_runtime.WindowsProcessJob()
            process = job.start(command, tmp_path, dict(os.environ))
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists()
        handle = _winapi.OpenProcess(0x100000, False, int(marker.read_text()))
        if abrupt:
            gate.touch()
            assert owner.wait(10) == 3
        else:
            job.close()
        assert _winapi.WaitForSingleObject(handle, 10000) == 0
    finally:
        if job:
            job.close()
        if process:
            process.wait(10)
            process.close()
        if handle:
            _winapi.CloseHandle(handle)
        if owner and owner.poll() is None:
            gate.touch()
            owner.wait(10)


def test_queue_budget_queued_cancel_and_shutdown(tmp_path, fake):
    with client(tmp_path) as c:
        fake.release.clear()
        jobs = []
        for index in range(5):
            raw = package(value=f'<document><p>{index}</p></document>')
            node, _, _ = add(c, tmp_path, f'{index}.docx', raw)
            response = c.post(f'{PREFIX}/nodes/{node}/previews',
                              json={'expected_source_sha256': hashlib.sha256(raw).hexdigest()})
            if index == 4:
                assert response.status_code == 409
            else:
                assert response.status_code == 200
                jobs.append((node, response.json()['id']))
        assert fake.entered.wait(5)
        node, identifier = jobs[1]
        assert c.post(f'{PREFIX}/nodes/{node}/previews/{identifier}/cancel').status_code == 200
        c.app.state.documents.close()
        assert wait(c, *jobs[0])['status'] == 'interrupted'
        assert all(wait(c, node, identifier)['status'] in {'interrupted', 'cancelled'} for node, identifier in jobs)


def test_runtime_inventory_rejects_missing_changed_unlisted_and_bad_paths(tmp_path):
    root = tmp_path / 'runtime'
    root.mkdir()
    files = {}
    for name in ['program/soffice.com', 'program/soffice.bin', 'license.txt', 'NOTICE']:
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'fixture-only')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(version=office_runtime.VERSION, package_sha256=office_runtime.PACKAGE_SHA256, files=files)
    lock = root / 'runtime-lock.json'
    lock.write_text(json.dumps(manifest))
    runtime = office_runtime.OfficeRuntime(root)
    runtime.verify(lambda: None)
    stage = tmp_path / 'stage'
    stage.mkdir()
    command = [sys.executable, str(Path(__file__).parents[2] / 'tools/stage_office_runtime.py'),
               '--runtime', str(root), '--stage', str(stage)]
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert office_runtime.OfficeRuntime(stage / 'converters/libreoffice').fingerprint == runtime.fingerprint
    assert subprocess.run(command, capture_output=True, timeout=30).returncode != 0
    (root / 'NOTICE').write_bytes(b'tamper')
    with pytest.raises(ValueError, match='变化'):
        runtime.verify(lambda: None)
    (root / 'NOTICE').unlink()
    with pytest.raises(ValueError, match='缺失'):
        runtime.verify(lambda: None)
    (root / 'NOTICE').write_bytes(b'fixture-only')
    (root / 'extra.dll').write_bytes(b'unlisted')
    with pytest.raises(ValueError, match='未登记'):
        runtime.verify(lambda: None)
    files['../escape'] = 'a' * 64
    lock.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='路径'):
        office_runtime.OfficeRuntime(root)


def test_ooxml_decompression_and_source_budgets(monkeypatch):
    from study_workbench import office_inputs
    raw = package(value='<document>' + 'x' * 1000 + '</document>')
    monkeypatch.setattr(office_inputs, 'MAX_EXPANDED', 500)
    with pytest.raises(ValueError, match='预算'):
        validate_office(raw, '.docx')
    monkeypatch.setattr(office_inputs, 'MAX_SOURCE', len(raw) - 1)
    with pytest.raises(ValueError, match='32MiB'):
        validate_office(raw, '.docx')


def test_ooxml_xml_part_node_and_depth_budgets(monkeypatch):
    from study_workbench import office_inputs
    with pytest.raises(ValueError, match='嵌套预算'):
        validate_office(package(value='<a>' * 129 + '</a>' * 129), '.docx')
    monkeypatch.setattr(office_inputs, 'MAX_XML_NODES', 20)
    with pytest.raises(ValueError, match='节点'):
        validate_office(package(value='<document>' + '<p/>' * 21 + '</document>'), '.docx')
    monkeypatch.setattr(office_inputs, 'MAX_XML_PART', 100)
    with pytest.raises(ValueError, match='单个XML'):
        validate_office(package(value='<document>' + 'x' * 101 + '</document>'), '.docx')
