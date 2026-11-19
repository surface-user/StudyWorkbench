import ctypes
import hashlib
import io
import sys
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pypdfium2 as pdfium
import pytest
from fastapi import HTTPException
from study_workbench import agent_access, document_files, resource_grants, resource_pdf
from study_workbench.db import DocumentPreview, Resource, WorkspaceNode, write_transaction
from study_workbench.office_previews import OPTIONS_HASH
from test_document_files import add
from test_explorer import PREFIX, client, snapshot
from test_resource_grants import grant, read

PDF = (Path(__file__).parents[2] / 'contracts/samples/original-study.pdf').read_bytes()
def SHA(raw):
    return hashlib.sha256(raw).hexdigest()


def selection(node, raw=PDF, **extra):
    return dict(kind='resource_node', id=node, mode='text', representation='original_pdf_text',
                expected_sha256=SHA(raw), page=1, **extra)


def preview(c, root, *, status='ready'):
    # A controlled receipt fixture tests reads, not a claim that this test ran LibreOffice.
    raw = b'Self-authored Office receipt source fixture'
    node, source, path = add(c, root, 'selected.docx', raw)
    identifier = uuid4().hex
    relative = f'workspaces/default/previews/{identifier}/output/source.pdf'
    target = root / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(PDF)
    with write_transaction(c.app.state.engine) as session:
        session.add(DocumentPreview(id=identifier, workspace_id='default', node_id=node, source_resource_id=source,
            source_sha256=SHA(raw), runtime_fingerprint='a' * 64, converter_version='receipt-fixture-v1',
            options_hash=OPTIONS_HASH, status=status, cancel_requested=False, relative_pdf=relative,
            pdf_sha256=SHA(PDF), pdf_size=len(PDF), page_count=2, created_at='2026-11-19T00:00:00Z'))
    value = selection(node)
    value.update(representation='office_pdf_text', expected_source_sha256=SHA(raw), preview_id=identifier)
    return value, path, target


def test_pdf_single_page_uses_real_native_child_and_preserves_library(tmp_path):
    with client(tmp_path) as c:
        node, resource, original = add(c, tmp_path, 'selected.pdf', PDF)
        before = snapshot(tmp_path / 'study.db')
        issued = grant(c, selection(node))
        response = read(c, issued)
        assert response.status_code == 200, response.text
        item = response.json()['resources'][0]
        assert item['text'] == resource_pdf.extract(PDF, 1)['text']
        assert item['text'] != resource_pdf.extract(PDF, 2)['text']
        assert item['source_binary_read'] is True and item['citation']['text_sha256'] == SHA(item['text'].encode())
        assert item['citation']['source_resource_id'] == resource
        assert item['citation']['anchor'] == dict(version=1, workspace_id='default', resource_item_id=node,
            kind='pdf_page', content_sha256=SHA(PDF), page=1, representation='original')
        assert 'line' not in item['citation'] and 'image_base64' not in response.text
        assert response.json()['binary_attachments_read'] is response.json()['links_followed'] is False
        assert original.read_bytes() == PDF and snapshot(tmp_path / 'study.db') == before
        assert read(c, issued).json() == response.json()
        assert c.delete(PREFIX + '/agent-grants/' + issued.json()['id']).status_code == 200
        assert read(c, issued).status_code == 404


def test_ready_office_receipt_binds_both_versions_without_converter(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        chosen, source, target = preview(c, tmp_path)
        monkeypatch.setattr(c.app.state.documents.previews, 'read_pdf', lambda *a: pytest.fail('Unbudgeted reader'))
        before = snapshot(tmp_path / 'study.db')
        issued = grant(c, chosen)
        response = read(c, issued)
        assert response.status_code == 200, response.text
        item = response.json()['resources'][0]
        point = item['citation']['anchor']
        assert point['kind'] == 'office_pdf_page' and point['preview_id'] == chosen['preview_id']
        assert point['content_sha256'] == SHA(PDF) and point['source_sha256'] == SHA(source.read_bytes())
        assert item['citation']['options_hash'] == OPTIONS_HASH
        assert snapshot(tmp_path / 'study.db') == before
        target.write_bytes(PDF + b'changed')
        assert read(c, issued).status_code == 409 and target.read_bytes().endswith(b'changed')


@pytest.mark.parametrize('field,value', [('status', 'running'), ('options_hash', 'b' * 64),
    ('source_sha256', 'b' * 64), ('pdf_sha256', 'b' * 64), ('relative_pdf', 'other.pdf'), ('page_count', 1)])
def test_office_invalid_receipt_is_not_replaced_with_latest_or_structural_text(tmp_path, field, value):
    with client(tmp_path) as c:
        chosen, source, target = preview(c, tmp_path)
        chosen['page'] = 2
        with write_transaction(c.app.state.engine) as session:
            setattr(session.get(DocumentPreview, chosen['preview_id']), field, value)
        assert grant(c, chosen).status_code == 409
        assert target.read_bytes() == PDF and source.exists()


@pytest.mark.parametrize('changes', [dict(page=True), dict(page=0), dict(page=1.5), dict(page=2001), dict(line=1),
    dict(preview_id='unrequested-preview'), dict(expected_source_sha256='a' * 64), dict(provider='arbitrary'),
    dict(mode='metadata'), dict(representation='original_text'), dict(kind='learning_mark', expected_revision=1)])
def test_closed_single_page_input_rejects_extra_authority(tmp_path, changes):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, 'selected.pdf', PDF)
        assert grant(c, {**selection(node), **changes}).status_code == 422


def test_page_range_versions_bad_pdf_and_missing_source_are_rejected(tmp_path):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, 'selected.pdf', PDF)
        assert grant(c, {**selection(node), 'page': 3}).status_code == 409
        assert grant(c, {**selection(node), 'expected_sha256': '0' * 64}).status_code == 409
        assert grant(c, selection(node), {**selection(node), 'page': 2}).status_code == 422
        issued = grant(c, selection(node))
        original.unlink()
        assert read(c, issued).status_code == 409
        bad, _, _ = add(c, tmp_path, 'broken.pdf', b'%PDF-damaged')
        assert grant(c, selection(bad, b'%PDF-damaged')).status_code == 422


@pytest.mark.parametrize('value', ['中文🙂\r\nsecond', '', '\x00literal\t'])
def test_utf16_exact_allocation_strict_unicode_and_empty_status(monkeypatch, value):
    raw = value.encode('utf-16-le')
    calls = []

    def native(*args):
        buffer, size = args[-2:]
        calls.append(size)
        if buffer is not None:
            assert size == len(raw) // 2
            ctypes.memmove(buffer, raw, len(raw))
        return len(raw) // 2
    monkeypatch.setattr(pdfium.raw, 'FPDFText_GetBoundedText', native)
    result = resource_pdf.extract(PDF, 1)
    assert result['text'] == value and result['text_sha256'] == SHA(value.encode())
    assert result['text_status'] == ('text' if value else 'no_extractable_text')
    assert calls == ([0, len(raw) // 2] if raw else [0])


@pytest.mark.parametrize('kind', ['units', 'changed', 'surrogate'])
def test_native_count_growth_and_invalid_unicode_fail_without_prefix(monkeypatch, kind):
    calls = []

    def native(*args):
        buffer, size = args[-2:]
        calls.append(size)
        if buffer is None:
            return resource_pdf.TEXT_UNITS + 1 if kind == 'units' else 1
        buffer[0] = 0xd800
        return 2 if kind == 'changed' else 1
    monkeypatch.setattr(pdfium.raw, 'FPDFText_GetBoundedText', native)
    with pytest.raises((resource_pdf.PdfLimit, ValueError, UnicodeError)):
        resource_pdf.extract(PDF, 1)
    if kind == 'units':
        assert calls == [0]


def test_pdf_aliases_share_actual_reads_including_recheck(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, original, _ = add(c, tmp_path, 'selected.pdf', PDF)
        alias = uuid4().hex
        with write_transaction(c.app.state.engine) as session:
            session.add(WorkspaceNode(id=alias, workspace_id='default', kind='resource', resource_id=original,
                name='alias.pdf', name_key='alias.pdf'))
        monkeypatch.setattr(resource_grants, 'FILE_BYTES', len(PDF) * 3)
        assert grant(c, selection(node), selection(alias)).status_code == 413


@pytest.mark.parametrize('office', [False, True])
def test_persisted_path_cannot_cross_workspace_even_with_matching_bytes(tmp_path, monkeypatch, office):
    with client(tmp_path) as c:
        if office:
            chosen, _, _ = preview(c, tmp_path)
            with write_transaction(c.app.state.engine) as session:
                original = session.get(WorkspaceNode, chosen['id']).resource_id
        else:
            node, original, _ = add(c, tmp_path, 'selected.pdf', PDF)
            chosen = selection(node)
        with write_transaction(c.app.state.engine) as session:
            session.get(Resource, original).relative_path = 'workspaces/other/originals/private.pdf'
        monkeypatch.setattr(resource_grants, 'open', lambda *a, **k: pytest.fail('Cross-space path must not open'), raising=False)
        assert grant(c, chosen).status_code == 409


def test_actual_child_output_and_blocked_input_are_terminated_and_slots_released(monkeypatch):
    actual = resource_pdf.subprocess.Popen
    processes = []
    monkeypatch.setenv('TEST_PRIVATE_CREDENTIAL', 'must-not-leave-parent')

    for script, status in [('import sys;sys.stdout.write("x"*200000);sys.stdout.flush()', 413),
                           ('import time;time.sleep(30)', 422)]:
        def start(command, **kwargs):
            assert 'TEST_PRIVATE_CREDENTIAL' not in kwargs['env']
            assert command[-1] == '--read-resource-pdf'
            command = [getattr(sys, '_base_executable', sys.executable), '-c', script]
            process = actual(command, **kwargs)
            processes.append(process)
            return process
        monkeypatch.setattr(resource_pdf.subprocess, 'Popen', start)
        began = monotonic()
        with pytest.raises(HTTPException) as error:
            resource_pdf.page_text(b'x' * (1024 * 1024), 1, began + (5 if status == 413 else .4))
        assert error.value.status_code == status and monotonic() - began < 7
        assert processes[-1].poll() is not None
        assert document_files.VIEW_SLOTS.acquire(blocking=False)
        document_files.VIEW_SLOTS.release()


@pytest.mark.parametrize('raw', [b'not JSON', b'[]', b'{"text":"incomplete"}'])
def test_invalid_child_protocol_is_not_returned_and_releases_slots(monkeypatch, raw):
    actual = resource_pdf.subprocess.Popen
    processes = []

    def start(command, **kwargs):
        process = actual([getattr(sys, '_base_executable', sys.executable), '-c',
                          'import sys;sys.stdout.buffer.write(' + repr(raw) + ')'], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(resource_pdf.subprocess, 'Popen', start)
    with pytest.raises(HTTPException) as error:
        resource_pdf.page_text(PDF, 1, monotonic() + 5)
    assert error.value.status_code == 422 and processes[0].poll() is not None
    assert document_files.VIEW_SLOTS.acquire(blocking=False)
    document_files.VIEW_SLOTS.release()


@pytest.mark.parametrize('office', [False, True])
def test_source_and_office_combination_budget_are_checked_before_file_read(tmp_path, monkeypatch, office):
    with client(tmp_path) as c:
        if office:
            chosen, _, _ = preview(c, tmp_path)
        else:
            node, _, _ = add(c, tmp_path, 'selected.pdf', PDF)
            chosen = selection(node)
        monkeypatch.setattr(resource_grants, 'SOURCE_BYTES', len(PDF) - 1)
        monkeypatch.setattr(resource_grants, 'open', lambda *a, **k: pytest.fail('Oversize must not open'), raising=False)
        assert grant(c, chosen).status_code == 413


@pytest.mark.parametrize('changed', ['pdf', 'office-source', 'office-pdf', 'receipt'])
def test_files_and_receipt_are_rechecked_after_native_extraction(tmp_path, monkeypatch, changed):
    with client(tmp_path) as c:
        if changed == 'pdf':
            node, _, source = add(c, tmp_path, 'selected.pdf', PDF)
            chosen, target = selection(node), source
        else:
            chosen, source, target = preview(c, tmp_path)
        original = resource_grants.page_text

        def mutate(data, page, deadline):
            result = original(data, page, deadline)
            if changed == 'receipt':
                with write_transaction(c.app.state.engine) as session:
                    session.get(DocumentPreview, chosen['preview_id']).runtime_fingerprint = 'b' * 64
            else:
                path = source if changed == 'office-source' else target
                path.write_bytes(path.read_bytes() + b'changed during read')
            return result
        monkeypatch.setattr(resource_grants, 'page_text', mutate)
        assert grant(c, chosen).status_code == 409


def test_shared_context_deadline_is_not_reset_for_each_page(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, resource, _ = add(c, tmp_path, 'selected.pdf', PDF)
        alias = uuid4().hex
        with write_transaction(c.app.state.engine) as session:
            session.add(WorkspaceNode(id=alias, workspace_id='default', kind='resource', resource_id=resource,
                name='alias.pdf', name_key='alias.pdf'))
        clock = [0.]
        monkeypatch.setattr(resource_grants, 'monotonic', lambda: clock[0])

        def expire(data, page, deadline):
            assert deadline == resource_grants.PDF_SECONDS
            clock[0] = deadline + 1
            return resource_pdf.extract(data, page)
        monkeypatch.setattr(resource_grants, 'page_text', expire)
        assert grant(c, selection(node), selection(alias)).status_code == 422


def test_view_slots_are_shared_with_ordinary_document_reads():
    assert document_files.VIEW_SLOTS.acquire(blocking=False)
    assert document_files.VIEW_SLOTS.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as error:
            resource_pdf.page_text(PDF, 1, monotonic() + 10)
        assert error.value.status_code == 429
    finally:
        document_files.VIEW_SLOTS.release()
        document_files.VIEW_SLOTS.release()


def test_exact_native_utf16_limit_is_complete_not_a_prefix(monkeypatch):
    def native(*args):
        buffer, size = args[-2:]
        if buffer is not None:
            assert size == resource_pdf.TEXT_UNITS
            for index in range(size):
                buffer[index] = ord('a')
        return resource_pdf.TEXT_UNITS
    monkeypatch.setattr(pdfium.raw, 'FPDFText_GetBoundedText', native)
    result = resource_pdf.extract(PDF, 1)
    assert result['text'] == 'a' * resource_pdf.TEXT_UNITS
    assert result['text_sha256'] == SHA(result['text'].encode())


def test_office_preview_cannot_be_borrowed_by_another_node(tmp_path):
    with client(tmp_path) as c:
        chosen, _, target = preview(c, tmp_path)
        other, _, _ = add(c, tmp_path, 'other.docx', b'Another independent source')
        assert grant(c, {**chosen, 'id': other, 'expected_source_sha256': SHA(b'Another independent source')}).status_code == 404
        assert target.read_bytes() == PDF


def test_pdf_growth_after_open_cannot_read_past_remaining_input_budget(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, 'selected.pdf', PDF)
        actual = resource_grants.os.fstat
        changed = [False]

        def grow(fd):
            result = actual(fd)
            if not changed[0]:
                changed[0] = True
                original.write_bytes(PDF + b'changed after size check')
            return result
        monkeypatch.setattr(resource_grants, 'FILE_BYTES', len(PDF))
        monkeypatch.setattr(resource_grants.os, 'fstat', grow)
        assert grant(c, selection(node)).status_code == 409
        assert original.read_bytes() == PDF + b'changed after size check'


def test_outer_context_deadline_includes_projection_encoding_and_hash(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, 'selected.pdf', PDF)
        monkeypatch.setattr(agent_access, 'PDF_SECONDS', 0)
        # The reader still has its own normal deadline; its output must not escape an expired outer context.
        response = grant(c, selection(node))
        assert response.status_code == 422 and 'text_sha256' not in response.text
        assert original.read_bytes() == PDF


def test_file_budget_has_no_buffered_read_ahead(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, 'selected.pdf', PDF)
        actual = open
        reads = []

        def observed(path, *args, **kwargs):
            assert path == original and kwargs['buffering'] == 0
            reads.append(path)
            return actual(path, *args, **kwargs)
        monkeypatch.setattr(resource_grants, 'open', observed, raising=False)
        assert grant(c, selection(node)).status_code == 200
        assert len(reads) == 2


def test_real_blank_pdf_reports_only_no_extractable_text():
    with pdfium.PdfDocument.new() as document:
        page = document.new_page(240, 240)
        page.close()
        output = io.BytesIO()
        document.save(output)
    result = resource_pdf.page_text(output.getvalue(), 1, monotonic() + 20)
    assert result['text'] == '' and result['text_status'] == 'no_extractable_text'
    assert result['page_count'] == result['page'] == 1 and result['text_sha256'] == SHA(b'')
