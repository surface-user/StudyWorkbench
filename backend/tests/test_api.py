from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from study_workbench.app import create_app
from study_workbench.db import Question, database

TOKEN = "test-session-" * 4
AUTH = {"Authorization": "Bearer " + TOKEN}


def client(path, media=None):
    return TestClient(create_app(path, TOKEN, media), base_url="http://127.0.0.1")


def test_auth_origin_and_host(tmp_path):
    with client(tmp_path) as c:
        assert c.get("/api/health").status_code == 401
        assert c.get("/api/health", headers=AUTH).json()["status"] == "ok"
        assert c.get("/api/health", headers={**AUTH, "Origin": "https://example.com"}).status_code == 403
        assert c.get("/api/health", headers={**AUTH, "Host": "evil.example"}).status_code == 400
        assert c.get("/openapi.json").status_code == 404


def test_grading_append_and_restart(tmp_path):
    with client(tmp_path) as c:
        for choice, score in (("a", 1), ("b", 0)):
            response = c.post("/api/attempts", headers=AUTH, json={
                "question_id": "demo-integral", "response": {"selected": [choice]}})
            assert response.status_code == 200
            assert response.json()["score"] == score
        subjective = c.post("/api/attempts", headers=AUTH, json={
            "question_id": "demo-proof", "response": {"text": "与标准答案不同的文字"}}).json()
        assert subjective["status"] == "pending_review"
        assert subjective["score"] is None
    with client(tmp_path) as c:
        attempts = c.get("/api/attempts", headers=AUTH).json()
        assert len(attempts) == 3
        assert len({a["id"] for a in attempts}) == 3
        assert attempts[0]["response"] == {"selected": ["a"]}


def test_invalid_submissions_do_not_write(tmp_path):
    with client(tmp_path) as c:
        for selected in ([], ["a", "b"], ["unknown"], "a", [{}], [None]):
            assert c.post("/api/attempts", headers=AUTH, json={
                "question_id": "demo-integral", "response": {"selected": selected}}).status_code == 422
        assert c.post("/api/attempts", headers=AUTH, json={
            "question_id": "missing", "response": {}}).status_code == 404
        assert c.post("/api/attempts", headers=AUTH, json={
            "question_id": "demo-proof", "response": {"text": " "}}).status_code == 422
        assert c.get("/api/attempts", headers=AUTH).json() == []


def test_grading_uses_protocol_option_ids(tmp_path):
    with client(tmp_path) as c:
        engine = database(tmp_path / "study.db")
        try:
            with Session(engine) as session, session.begin():
                question = session.get(Question, "demo-integral")
                content = dict(question.content)
                content["options"][0]["id"] = "correct-option"
                content["answer"] = {"selected": ["correct-option"]}
                question.content = content
            response = c.post("/api/attempts", headers=AUTH, json={
                "question_id": "demo-integral", "response": {"selected": ["correct-option"]}})
            assert response.status_code == 200
            assert response.json()["score"] == 1.0
            assert c.post("/api/attempts", headers=AUTH, json={
                "question_id": "demo-integral", "response": {"selected": ["a"]}}).status_code == 422
        finally:
            engine.dispose()


def test_media_capability_and_range(tmp_path):
    media = tmp_path / "sample.mp4"
    media.write_bytes(bytes(range(256)) * 8)
    with client(tmp_path / "data", media) as c:
        assert c.get("/media/demo").status_code == 403
        html = c.get("/api/player", headers=AUTH).text
        cap = html.split("?cap=", 1)[1].split("'", 1)[0]
        response = c.get("/media/demo", params={"cap": cap}, headers={"Range": "bytes=10-29"})
        assert response.status_code == 206
        assert response.content == media.read_bytes()[10:30]
        assert response.headers["content-range"] == "bytes 10-29/2048"
        assert c.get("/media/demo", params={"cap": cap}, headers={"Range": "bytes=9999-"}).status_code == 416
        assert c.get("/media/../../study.db", params={"cap": cap}).status_code == 404
    with client(tmp_path / "data", media) as c:
        assert c.get("/media/demo", params={"cap": cap}).status_code == 403
