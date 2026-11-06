import asyncio
import copy
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from study_workbench.app import create_app
from study_workbench.content import DEMO, SUBJECTIVE
from study_workbench.db import database
from study_workbench.request_limits import RequestLimits

TOKEN = "import-test-" * 4
AUTH = {"Authorization": "Bearer " + TOKEN}
SCOPE = "/api/workspaces/default"


def client(root):
    return TestClient(create_app(root, TOKEN), base_url="http://127.0.0.1", headers=AUTH)


def upload(c, value, filename="questions.json", scope=SCOPE):
    data = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, dict) else value
    return c.post(f"{scope}/imports", params={"filename": filename}, content=data)


def bundle():
    question = copy.deepcopy(DEMO)
    question["id"] = "imported-integral"
    question["source"] = {"kind": "official", "title": "不可信的官方声明", "verification": "human_verified"}
    return {"schema_version": 1, "questions": [question], "passages": []}


def confirm(c, job, scope=SCOPE):
    return c.post(f"{scope}/imports/{job['id']}/confirm")


def test_preview_confirm_idempotency_source_and_restart(tmp_path):
    raw = json.dumps(bundle(), ensure_ascii=False).encode()
    with client(tmp_path) as c:
        job = upload(c, raw).json()
        assert job["status"] == "preview"
        assert job["sha256"] == hashlib.sha256(raw).hexdigest()
        assert c.get(f"{SCOPE}/questions/imported-integral").status_code == 404
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
        assert upload(c, raw, "another.json").json()["id"] == job["id"]
        source = job["preview"]["bundle"]["questions"][0]["source"]
        assert source["kind"] == "imported" and source["verification"] == "unverified"
        assert source["original_resource_id"] == job["resource_id"]
        for _ in range(2):
            assert confirm(c, job).json()["status"] == "confirmed"
        assert c.get(f"{SCOPE}/questions/imported-integral").json()["source"] == source
        assert c.get(f"{SCOPE}/imports").json()[0]["status"] == "confirmed"
    with client(tmp_path) as c:
        assert c.get(f"{SCOPE}/questions/imported-integral").status_code == 200
        assert c.get(f"{SCOPE}/imports/{job['id']}").json()["preview"]["kind"] == "questions"
    with sqlite3.connect(tmp_path / "study.db") as db:
        assert db.execute("SELECT COUNT(*) FROM questions WHERE id='imported-integral'").fetchone() == (1,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(("raw", "filename"), [
    (b"not json", "bad.json"), (b"%PDF-unsupported", "book.pdf"),
    (b"\xff\xfe\x00\x00", "bad.txt"), (b"x" * 200001, "large.md"),
    (b"[1,2]", "array.json"), (b"\x89PNG\r\n\x1a\n", "bad.png"),
], ids=["invalid-json", "unsupported-pdf", "binary-text", "oversized-text", "json-array", "truncated-png"])
def test_failed_parse_retains_original_and_never_writes(tmp_path, raw, filename):
    with client(tmp_path) as c:
        response = upload(c, raw, filename)
        assert response.status_code == 200
        job = response.json()
        assert job["status"] == "failed" and job["error"]
        assert job["preview"] == {}
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
        assert confirm(c, job).status_code == 409
        assert len(c.get(f"{SCOPE}/questions").json()) == 2
        assert c.get(f"{SCOPE}/notes").json() == []


def test_notes_html_is_inert_and_confirmation_required(tmp_path):
    raw = '<html><head><title>hidden</title></head><body><p>中文资料</p><script>secret()</script><iframe src="file:///secret">hidden</iframe><img src="https://example.com/x"><p>第二段</p></body></html>'.encode()
    with client(tmp_path) as c:
        job = upload(c, raw, "notes.html").json()
        assert c.get(f"{SCOPE}/notes").json() == []
        text = "".join(b["text"] for b in job["preview"]["blocks"])
        assert "中文资料" in text and "第二段" in text
        assert "secret" not in text and "hidden" not in text and "https:" not in text
        assert confirm(c, job).status_code == 200
        assert confirm(c, job).status_code == 200
        assert len(c.get(f"{SCOPE}/notes").json()) == 1
        response = c.get(f"{SCOPE}/resources/{job['resource_id']}")
        assert response.headers["content-disposition"] == "attachment"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]


def test_conflict_is_atomic_and_does_not_change_answer(tmp_path):
    raw = bundle()
    raw["questions"].append(copy.deepcopy(DEMO))
    with client(tmp_path) as c:
        job = upload(c, raw).json()
        assert job["status"] == "preview"
        assert confirm(c, job).status_code == 409
        assert c.get(f"{SCOPE}/questions/imported-integral").status_code == 404
        assert c.get(f"{SCOPE}/questions/demo-integral").json()["answer"] == DEMO["answer"]
        assert c.get(f"{SCOPE}/imports/{job['id']}").json()["status"] == "preview"


def test_isolation_auth_archive_and_paths(tmp_path):
    with client(tmp_path) as c:
        other_id = c.post("/api/workspaces", json={"name": "独立导入"}).json()["id"]
        other = f"/api/workspaces/{other_id}"
        job = upload(c, bundle()).json()
        assert c.get(f"{other}/imports").json() == []
        assert c.get(f"{other}/imports/{job['id']}").status_code == 404
        assert confirm(c, job, other).status_code == 404
        assert c.get(f"{other}/resources/{job['resource_id']}").status_code == 404
        assert upload(c, bundle(), scope=other).json()["duplicate"] is False
        for name in ("../secret", "C:\\secret.txt", "bad\nname.txt", ".."):
            assert upload(c, b"x", name).status_code == 422
        assert c.get(f"{SCOPE}/imports", headers={"Authorization": "bad"}).status_code == 401
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}", headers={"Origin": "https://example.com"}).status_code == 403
        assert c.request("DELETE", "/api/workspaces/default", json={"confirm_name": "我的学习空间"}).status_code == 200
        assert confirm(c, job).status_code == 404
        assert upload(c, b"x", "x.txt").status_code == 404


def test_original_tampering_prevents_confirm(tmp_path):
    with client(tmp_path) as c:
        job = upload(c, bundle()).json()
        original = tmp_path / "workspaces/default/originals" / (job["resource_id"] + ".bin")
        original.write_bytes(b"changed")
        assert confirm(c, job).status_code == 409
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").status_code == 409
        assert c.get(f"{SCOPE}/questions/imported-integral").status_code == 404


def test_bundle_shared_passage_and_ai_claims(tmp_path):
    raw = bundle()
    q = copy.deepcopy(SUBJECTIVE)
    q.update(id="reading", kind="reading_question", passage_id="article", response_kind="subjective")
    q["source"] = {"kind": "ai_generated", "title": "AI 变式", "verification": "human_verified",
                   "model": "test-model", "generated_at": "2026-10-24T00:00:00Z"}
    raw["questions"].append(q)
    raw["passages"] = [{"id": "article", "content": [{"type": "text", "text": "共享文章"}],
                        "source": copy.deepcopy(DEMO["source"])}]
    with client(tmp_path) as c:
        job = upload(c, raw).json()
        assert job["status"] == "preview"
        assert confirm(c, job).status_code == 200
        assert c.get(f"{SCOPE}/passages/article").json()["content"][0]["text"] == "共享文章"
        source = c.get(f"{SCOPE}/questions/reading").json()["source"]
        assert source["kind"] == "ai_generated" and source["verification"] == "unverified"
        assert source["model"] == "test-model"


def test_attachment_ownership_and_recheck_on_confirm(tmp_path):
    # Minimal valid 1x1 PNG fixture; no remote or personal files.
    import base64
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4WQAAAAASUVORK5CYII=")
    with client(tmp_path) as c:
        image = upload(c, png, "diagram.png").json()
        assert image["status"] == "preview" and image["mime"] == "image/png"
        raw = bundle()
        raw["questions"][0]["stem"].append({"type": "image", "alt": "diagram", "attachment_id": image["resource_id"]})
        job = upload(c, raw).json()
        assert job["status"] == "preview"
        other_id = c.post("/api/workspaces", json={"name": "图片隔离"}).json()["id"]
        assert upload(c, raw, scope=f"/api/workspaces/{other_id}").json()["status"] == "failed"
        original = tmp_path / "workspaces/default/originals" / (image["resource_id"] + ".bin")
        original.write_bytes(b"tampered")
        assert confirm(c, job).status_code == 409


def test_opaque_original_cannot_become_a_formal_attachment(tmp_path):
    with client(tmp_path) as c:
        quarantined = upload(c, b"unsupported binary", "program.exe").json()
        assert quarantined["status"] == "failed"
        raw = bundle()
        raw["questions"][0]["stem"].append({
            "type": "attachment", "label": "未知格式", "attachment_id": quarantined["resource_id"]})
        job = upload(c, raw).json()
        assert job["status"] == "failed"
        assert confirm(c, job).status_code == 409


def test_chunked_body_limit_is_enforced_without_length(tmp_path):
    with client(tmp_path) as c:
        response = c.post(f"{SCOPE}/imports?filename=big.txt", content=iter([b"x" * 1024 * 1024] * 9))
        assert response.status_code == 413
        assert c.post("/api/attempts", content=iter([b"x" * 40000] * 2)).status_code == 413
        assert c.get(f"{SCOPE}/imports").json() == []
        assert not (tmp_path / "workspaces/default/originals").exists()


def test_concurrent_upload_and_confirm_have_one_result(tmp_path):
    with client(tmp_path) as c, ThreadPoolExecutor(max_workers=2) as workers:
        gate = Barrier(2)

        def stage(_):
            gate.wait(timeout=5)
            return upload(c, b"concurrent text", "note.txt").json()

        jobs = list(workers.map(stage, range(2)))
        assert jobs[0]["id"] == jobs[1]["id"]
        assert sorted(job["duplicate"] for job in jobs) == [False, True]
        results = list(workers.map(lambda job: confirm(c, job).status_code, jobs))
        assert results == [200, 200]
        assert len(c.get(f"{SCOPE}/notes").json()) == 1


def test_asgi_limit_counts_separate_frames_and_preserves_allowed_body():
    async def exercise(chunks, expected_status):
        received = []
        output = []
        messages = iter({"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
                        for index, chunk in enumerate(chunks))

        async def receive():
            return next(messages)

        async def send(message):
            output.append(message)

        async def app(scope, receive, send):
            received.append(await receive())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        await RequestLimits(app)({"type": "http", "path": "/api/attempts"}, receive, send)
        assert output[0]["status"] == expected_status
        if expected_status == 200:
            assert received == [{"type": "http.request", "body": b"".join(chunks), "more_body": False}]
        else:
            assert received == []

    asyncio.run(exercise([b"a" * 30000, b"b" * 35536], 200))
    asyncio.run(exercise([b"a" * 30000, b"b" * 35536, b"c"], 413))


def test_m1_upgrade_has_one_backup_and_preserves_attempts(tmp_path):
    engine = database(tmp_path / "study.db")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.exec_driver_sql("INSERT INTO questions VALUES (?, ?, ?)",
                                   (DEMO["id"], "default", json.dumps(DEMO)))
        connection.exec_driver_sql(
            "INSERT INTO attempts VALUES (88, 'default', ?, ?, 'graded', 1.0, '2026-10-24')",
            (DEMO["id"], json.dumps({"selected": ["a"]})))
    engine.dispose()
    for _ in range(2):
        with client(tmp_path) as c:
            attempt = c.get("/api/attempts").json()[0]
            assert attempt["id"] == 88 and attempt["response"] == {"selected": ["a"]}
            assert attempt["score"] == 1.0
    backups = list((tmp_path / "backups").glob("study-before-0016-*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT version_num FROM alembic_version").fetchone() == ("0002",)
        assert backup.execute("SELECT id FROM attempts").fetchone() == (88,)
    with sqlite3.connect(tmp_path / "study.db") as upgraded:
        assert upgraded.execute("SELECT version_num FROM alembic_version").fetchone() == ("0016",)
        assert upgraded.execute("PRAGMA foreign_key_check").fetchall() == []


def test_repository_import_example_can_be_confirmed(tmp_path):
    raw = (Path(__file__).parents[2] / "contracts/import-bundle-v1.json").read_bytes()
    with client(tmp_path) as c:
        job = upload(c, raw).json()
        assert job["status"] == "preview"
        assert confirm(c, job).status_code == 200
        question = c.get(f"{SCOPE}/questions/import-sample-reading").json()
        assert question["source"]["kind"] == "imported"
        assert question["source"]["verification"] == "unverified"
        assert c.get(f"{SCOPE}/passages/{question['passage_id']}").status_code == 200
