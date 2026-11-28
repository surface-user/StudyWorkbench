import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Event

import pytest
from docx import Document
from study_workbench import backup_store, word_jobs
from test_document_files import PREFIX, client
from test_word_candidates import original
from test_word_jobs import API, managed


def word_source():
    doc = Document()
    for _ in range(18):
        doc.add_paragraph("")
    for text in ("阅读下列材料，回答第1-2题：", "共用资料", "1. 第一题", "题干续文", "2. 第二题"):
        doc.add_paragraph(text)
    return original(doc)


def advance(c, url, done):
    return c.post(url + "/advance", params={"expected_completed_positions": done})


def test_material_crosses_chunk_and_selection_survives_restored_checkpoint(tmp_path):
    raw = word_source()
    data, restored = tmp_path / "data", tmp_path / "restored"
    with client(data) as c:
        url, body, _, _ = managed(c, data, raw, 1, 23)
        assert c.get(url).json()["parser_version"] == "docx-range-job-v2"
        assert c.post(API, json={**body, "last_position": 101}).status_code == 422
        assert c.post(url + "/advance").status_code == 409 and advance(c, url, 20).status_code == 409
        first = advance(c, url, 0).json()
        assert first["status"] == "ready" and first["completed_positions"] == 20
        assert c.post(API, json=body).json() == advance(c, url, 0).json() == first
        assert advance(c, url, 1).status_code == 409
        assert c.get(url + "/preview").status_code == 409
        batch = PREFIX + "/imports/" + first["id"]
        assert set(c.get(batch).json()["preview"]) == {"word_range"}
        assert c.post(url + "/cancel").json()["completed_positions"] == 20
        assert advance(c, url, 20).status_code == 409
    package = tmp_path / "checkpoint.zip"
    backup_store.create_backup(data, package)
    backup_store.restore_backup(package, restored, tmp_path / "settings.json")
    with client(restored) as c:
        assert c.get(url).json()["status"] == "cancelled"
        assert c.post(url + "/resume").json()["completed_positions"] == 20
        assert advance(c, url, 20).json()["completed_positions"] == 23
        job = c.get(url + "/preview").json()
        drafts = job["preview"]["question_drafts"]
        assert [d["source_positions"] for d in drafts] == [[21, 22], [23]]
        assert [d["shared_materials"][0]["source_positions"] for d in drafts] == [[19, 20], [19, 20]]
        assert not any("选区末尾" in w or "选区起点" in w for w in job["preview"]["warnings"])
        confirm = dict(selected=[1], expected_revision=job["draft_revision"], confirm=True)
        picked = c.post(batch + "/question-markdown", json=confirm)
        assert picked.status_code == 200, picked.text
        assert c.post(batch + "/question-markdown", json=confirm).json() == picked.json()
        markdown = c.get(PREFIX + "/resources/" + picked.json()[0]["markdown_resource_id"]).content.decode()
        assert "题干续文" not in markdown and "共用资料" in markdown
        assert json.loads(markdown.split("```json\n")[1].split("\n```")[0])["selected_body_range"] == [1, 23]
    with sqlite3.connect(data / "study.db") as db:
        db.execute(
            "UPDATE import_jobs SET preview=json_set(preview,'$.word_range.completed_positions',0) WHERE id=?",
            (first["id"],),
        )
    with pytest.raises(ValueError, match="分块进度"):
        backup_store.create_backup(data, tmp_path / "tampered.zip")


def test_blank_chunk_and_late_result_cannot_move_checkpoint(tmp_path, monkeypatch):
    doc = Document()
    for _ in range(20):
        doc.add_paragraph("")
    doc.add_paragraph("1. 唯一题目")
    with client(tmp_path) as c:
        url, _, path, _ = managed(c, tmp_path, original(doc), 1, 21)
        calls = []
        entered, release = Event(), Event()
        real = word_jobs.parse_word_range

        def parse(data, first, last):
            result = real(data, first, last)
            calls.append((first, last))
            if first == 21 and not entered.is_set():
                entered.set()
                assert release.wait(60)
            return result

        monkeypatch.setattr(word_jobs, "parse_word_range", parse)
        assert advance(c, url, 0).json()["completed_positions"] == 20
        with ThreadPoolExecutor(1) as executor:
            old = executor.submit(advance, c, url, 20)
            try:
                assert entered.wait(35)
                assert c.post(url + "/cancel").json()["completed_positions"] == 20
                saved = path.read_bytes()
                path.write_bytes(saved + b"changed")
                assert c.post(url + "/resume").status_code == 409
                path.write_bytes(saved)
                assert c.post(url + "/resume").json()["completed_positions"] == 20
                assert advance(c, url, 20).json()["status"] == "preview"
            finally:
                release.set()
            assert old.result().status_code == 409
        assert calls == [(1, 20), (21, 21), (21, 21)]
        assert c.get(url + "/preview").json()["preview"]["block_positions"] == [21]


def test_failure_in_second_chunk_preserves_whole_job_budget(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        url, _, _, _ = managed(c, tmp_path, word_source(), 1, 23)

        def output(data, first, last):
            count = 200 if first == 1 else 1
            return dict(
                available=True,
                parser_version="docx-body-candidates-v1",
                first_position=first,
                last_position=last,
                total_positions=23,
                blocks=[{"type": "text", "text": "正文"}] * count,
                block_positions=[first] * count,
                question_drafts=[],
                assets=[],
                uncertain_positions=[],
                table_positions=[],
            )

        monkeypatch.setattr(word_jobs, "parse_word_range", output)
        assert advance(c, url, 0).json()["completed_positions"] == 20
        for _ in range(2):
            assert advance(c, url, 20).status_code == 422
            assert c.get(url + "/preview").status_code == 409
            state = c.post(url + "/resume").json()
            assert state["status"] == "ready" and state["completed_positions"] == 20


def test_question_body_crosses_the_checkpoint_without_a_second_heading(tmp_path):
    doc = Document()
    for _ in range(19):
        doc.add_paragraph("")
    for text in ("1. 题干", "续接上块的正文", "2. 下一题"):
        doc.add_paragraph(text)
    with client(tmp_path) as c:
        url, _, _, _ = managed(c, tmp_path, original(doc), 1, 22)
        assert advance(c, url, 0).json()["completed_positions"] == 20
        assert advance(c, url, 20).json()["completed_positions"] == 22
        view = c.get(url + "/preview").json()["preview"]
        assert [d["source_positions"] for d in view["question_drafts"]] == [[20, 21], [22]]
        assert view["question_drafts"][0]["blocks"][1]["text"] == "续接上块的正文"


def test_partial_rich_assets_are_checked_during_backup(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "tools"))
    from numbered_cell_sample import numbered_cell_docx

    doc = Document(BytesIO(numbered_cell_docx()))
    for _ in range(25):
        doc.add_paragraph("")
    data = tmp_path / "data"
    with client(data) as c:
        url, _, _, _ = managed(c, data, original(doc), 1, 21)
        partial = advance(c, url, 0).json()
        assert partial["completed_positions"] == 20 and partial["asset_bytes"] > 0
    archive, restored = tmp_path / "rich.zip", tmp_path / "restored"
    backup_store.create_backup(data, archive)
    backup_store.restore_backup(archive, restored, tmp_path / "settings.json")
    with client(restored) as c:
        assert advance(c, url, 20).json()["status"] == "preview"
        view = c.get(url + "/preview").json()["preview"]
        image = next(b for b in view["blocks"] if b["type"] == "image")
        assert c.get(PREFIX + "/resources/" + image["attachment_id"]).content.startswith(b"\x89PNG")
    with sqlite3.connect(data / "study.db") as db:
        (raw,) = db.execute("SELECT preview FROM import_jobs WHERE id=?", (partial["id"],)).fetchone()
        stored = json.loads(raw)
        stored["word_range"]["asset_bytes"] = stored["word_chunks"][0]["asset_bytes"] = 0
        db.execute("UPDATE import_jobs SET preview=? WHERE id=?", (json.dumps(stored), partial["id"]))
    with pytest.raises(ValueError, match="图片计数"):
        backup_store.create_backup(data, tmp_path / "wrong-size.zip")
    with sqlite3.connect(data / "study.db") as db:
        stored = json.loads(raw)
        next(b for b in stored["word_chunks"][0]["blocks"] if b["type"] == "image")["attachment_id"] = (
            "missing"
        )
        db.execute("UPDATE import_jobs SET preview=? WHERE id=?", (json.dumps(stored), partial["id"]))
    with pytest.raises(ValueError, match="图片"):
        backup_store.create_backup(data, tmp_path / "missing.zip")


def test_full_hundred_position_selection_reaches_exactly_five_checkpoints(tmp_path):
    doc = Document()
    for position in range(1, 103):
        doc.add_paragraph(f"{position}. 自编题")
    with client(tmp_path) as c:
        url, _, _, _ = managed(c, tmp_path, original(doc), 2, 101)
        for completed in range(0, 100, 20):
            state = advance(c, url, completed).json()
            assert state["completed_positions"] == completed + 20
            assert state["status"] == ("preview" if completed == 80 else "ready")
            assert advance(c, url, completed).json() == state
        view = c.get(url + "/preview").json()["preview"]
        assert [draft["source_positions"] for draft in view["question_drafts"]] == [[i] for i in range(2, 102)]
        assert any("起点" in w for w in view["warnings"]) and any("末尾" in w for w in view["warnings"])
