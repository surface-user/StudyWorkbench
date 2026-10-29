import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from study_workbench.app import create_app
from study_workbench.db import Question, database

TOKEN = "workspace-test-" * 4
AUTH = {"Authorization": "Bearer " + TOKEN}


def client(path):
    return TestClient(create_app(path, TOKEN), base_url="http://127.0.0.1", headers=AUTH)


def submit(c, workspace, selected="a"):
    return c.post(f"/api/workspaces/{workspace}/attempts", json={
        "question_id": "demo-integral", "response": {"selected": [selected]}})


def test_scope_isolation_and_restart(tmp_path):
    with client(tmp_path) as c:
        other = c.post("/api/workspaces", json={"name": "数学复习"}).json()["id"]
        assert submit(c, "default").json()["score"] == 1
        assert c.get(f"/api/workspaces/{other}/attempts").json() == []
        engine = database(tmp_path / "study.db")
        try:
            with Session(engine) as session, session.begin():
                question = session.get(Question, ("demo-integral", other))
                content = copy.deepcopy(question.content)
                content["options"][0]["id"] = "other-answer"
                content["answer"] = {"selected": ["other-answer"]}
                question.content = content
            assert submit(c, other).status_code == 422
            assert submit(c, other, "other-answer").json()["score"] == 1
            assert submit(c, "default").status_code == 200
        finally:
            engine.dispose()
        assert len(c.get("/api/attempts").json()) == 2
        assert len(c.get(f"/api/attempts?workspace_id={other}").json()) == 2
        assert c.get(f"/api/questions/demo?workspace_id={other}").json()["options"][0]["id"] == "a"
        assert len(c.get(f"/api/workspaces/{other}/attempts").json()) == 1
    with client(tmp_path) as c:
        assert c.get("/api/workbench").json()["active_workspace_id"] == other
        assert len(c.get(f"/api/workspaces/{other}/attempts").json()) == 1
        assert c.get("/api/workspaces/missing/attempts").status_code == 404
        assert submit(c, "missing").status_code == 404


def test_confirmation_archive_restore_preserves_data_and_selection(tmp_path):
    with client(tmp_path) as c:
        other = c.post("/api/workspaces", json={"name": "英语"}).json()["id"]
        assert submit(c, other).status_code == 200
        assert c.request("DELETE", f"/api/workspaces/{other}", json={"confirm_name": "错名"}).status_code == 409
        assert c.request("DELETE", f"/api/workspaces/{other}", json={"confirm_name": "英语"}).json()["data_preserved"]
        state = c.get("/api/workbench").json()
        assert state["active_workspace_id"] == "default"
        assert state["archived_workspaces"][0]["id"] == other
        assert c.get(f"/api/workspaces/{other}/attempts").status_code == 404
        assert submit(c, other).status_code == 404
        assert c.put("/api/active-workspace", json={"workspace_id": other}).status_code == 404
        assert c.request("DELETE", "/api/workspaces/default", json={"confirm_name": "我的学习空间"}).status_code == 409
        assert c.post(f"/api/workspaces/{other}/restore").status_code == 200
        assert len(c.get(f"/api/workspaces/{other}/attempts").json()) == 1


def test_names_rename_and_controlled_interfaces(tmp_path):
    with client(tmp_path) as c:
        for name in ("", "   ", "x\ny", "x" * 81):
            assert c.post("/api/workspaces", json={"name": name}).status_code == 422
        other = c.post("/api/workspaces", json={"name": "  数学  "}).json()["id"]
        assert c.post("/api/workspaces", json={"name": "数学"}).status_code == 409
        assert c.patch(f"/api/workspaces/{other}", json={"name": "政治"}).json()["name"] == "政治"
        assert c.post("/api/workspaces", json={"name": "hack", "command": "whoami"}).status_code == 422
        assert c.get("/api/workbench", headers={"Authorization": "bad"}).status_code == 401
        assert c.post("/api/workspaces", json={"name": "外部"}, headers={"Origin": "https://example.com"}).status_code == 403


def test_layout_persistence_and_validation(tmp_path):
    layout = {"version": 1, "tabs": [{"id": "question", "kind": "question", "draft": "中文草稿"},
                                      {"id": "browser", "kind": "web", "url": "https://example.com/path"}],
              "closed_tabs": [{"id": "video", "kind": "player"}], "active_tab_id": "browser"}
    with client(tmp_path) as c:
        other = c.post("/api/workspaces", json={"name": "独立布局"}).json()["id"]
        assert c.put("/api/workspaces/default/layout", json=layout).status_code == 200
        assert c.get(f"/api/workspaces/{other}/layout").json() == {
            'version': 1, 'tabs': [], 'closed_tabs': [], 'active_tab_id': None}
        bad = copy.deepcopy(layout)
        bad["active_tab_id"] = "missing"
        assert c.put("/api/workspaces/default/layout", json=bad).status_code == 422
        for url in ("file:///C:/secret", "http://example.com", "https://127.0.0.1", "https://user:password@example.com", "https://x.local"):
            bad = copy.deepcopy(layout)
            bad["tabs"][1]["url"] = url
            assert c.put("/api/workspaces/default/layout", json=bad).status_code == 422
        bad = copy.deepcopy(layout)
        bad["tabs"].append(bad["tabs"][0])
        assert c.put("/api/workspaces/default/layout", json=bad).status_code == 422
        bad = copy.deepcopy(layout)
        bad["version"] = 3
        assert c.put("/api/workspaces/default/layout", json=bad).status_code == 422
        assert c.get("/api/workspaces/default/layout").json()["tabs"][0]["draft"] == "中文草稿"
    with client(tmp_path) as c:
        restored = c.get("/api/workspaces/default/layout").json()
        assert restored["active_tab_id"] == "browser"
        assert restored["closed_tabs"][0]["kind"] == "player"


def test_resource_layout_identity_compatibility_and_unknown_roundtrip(tmp_path):
    with client(tmp_path) as c:
        node = c.post('/api/workspaces/default/nodes', json={
            'name': '资料', 'kind': 'link', 'url': 'https://example.com/resource'}).json()
        identifier = node['resource_item_id']
        tab = {'id': 'file', 'kind': 'resource', 'resource_item_id': identifier,
               'view_kind': 'web', 'resource_name': '资料', 'url': 'https://example.com/visited'}
        unknown = {'id': 'future', 'kind': 'future-view', 'state': {'version': 8, 'draft': '未知草稿'},
                   'resource_name': {'future': True}}
        legacy = {'id': 'old', 'kind': 'question', 'draft': '旧中文草稿'}
        layout = {'version': 2, 'tabs': [tab, legacy, unknown], 'closed_tabs': [
            {'id': 'closed', 'kind': 'web', 'url': 'https://example.org/history'}], 'active_tab_id': 'file'}
        saved = c.put('/api/workspaces/default/layout', json=layout)
        assert saved.status_code == 200, saved.text
        assert saved.json()['tabs'][2] == unknown
        assert saved.json()['tabs'][1]['draft'] == legacy['draft']
        for mutation in [dict(tab, id='duplicate'), dict(tab, resource_item_id='invalid'),
                         dict(tab, view_kind='media'), dict(tab, command='arbitrary'),
                         dict(tab, url='http://127.0.0.1/api?token=secret')]:
            bad = copy.deepcopy(layout)
            if mutation['id'] == 'duplicate':
                bad['tabs'].append(mutation)
            else:
                bad['tabs'][0] = mutation
            assert c.put('/api/workspaces/default/layout', json=bad).status_code == 422
        bad = copy.deepcopy(layout)
        bad['version'] = 1
        assert c.put('/api/workspaces/default/layout', json=bad).status_code == 422
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        assert c.put(f'/api/workspaces/{other}/layout', json=layout).status_code == 422
        missing = copy.deepcopy(layout)
        missing['tabs'][0]['resource_item_id'] = 'f' * 32
        assert c.put('/api/workspaces/default/layout', json=missing).status_code == 200
        assert c.get('/api/workspaces/default/nodes/' + 'f' * 32).status_code == 404
        assert c.put('/api/workspaces/default/layout', json=layout).status_code == 200
    with client(tmp_path) as c:
        restored = c.get('/api/workspaces/default/layout').json()
        assert restored['tabs'][0]['resource_item_id'] == identifier
        assert restored['tabs'][2] == unknown
        assert restored['closed_tabs'][0]['url'] == 'https://example.org/history'


def test_unknown_layout_budget_cannot_bypass_known_validation(tmp_path):
    with client(tmp_path) as c:
        layout = {'version': 2, 'tabs': [{'id': 'future', 'kind': 'future', 'state': 'x' * 65536}],
                  'closed_tabs': [], 'active_tab_id': 'future'}
        assert c.put('/api/workspaces/default/layout', json=layout).status_code == 422
        layout['tabs'] = [{'id': 'future', 'kind': 'question', 'draft': 'x', 'state': 'opaque'}]
        assert c.put('/api/workspaces/default/layout', json=layout).status_code == 422


def old_database(path):
    engine = database(path)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.exec_driver_sql("INSERT INTO questions VALUES ('old-question', '{}')")
        connection.exec_driver_sql("INSERT INTO attempts VALUES (12, 'old-question', '{\"text\":\"original\"}', 'pending_review', NULL, '2026-10-23')")
    engine.dispose()


def test_full_bounded_layout_preserves_long_unicode_drafts(tmp_path):
    tabs = [{"id": f"q{i}", "kind": "question", "draft": "中" * 16000} for i in range(26)]
    layout = {"version": 1, "tabs": tabs[:16], "closed_tabs": tabs[16:], "active_tab_id": "q0"}
    with client(tmp_path) as c:
        assert c.put("/api/workspaces/default/layout", json=layout).status_code == 200
        restored = c.get("/api/workspaces/default/layout").json()
        assert restored["closed_tabs"][-1]["draft"] == "中" * 16000
        invalid = copy.deepcopy(layout)
        invalid["tabs"].append({"id": "overflow", "kind": "question"})
        assert c.put("/api/workspaces/default/layout", json=invalid).status_code == 422
        assert c.post("/api/attempts", json={"question_id": "demo-proof", "response": {"text": "x" * 70000}}).status_code == 413


def test_m0_migration_backup_and_composite_foreign_key(tmp_path):
    old_database(tmp_path / "study.db")
    with client(tmp_path) as c:
        assert c.get("/api/attempts").json()[0]["id"] == 12
        assert c.get("/api/attempts").json()[0]["response"] == {"text": "original"}
    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 1
    with client(tmp_path) as c:
        assert c.get("/api/attempts").json()[0]["id"] == 12
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"
        assert connection.execute("SELECT response FROM attempts").fetchone()[0] == '{"text":"original"}'
    with sqlite3.connect(tmp_path / "study.db") as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT workspace_id FROM attempts WHERE id=12").fetchone()[0] == "default"


def test_migration_failure_rolls_back_and_keeps_backup(tmp_path, monkeypatch):
    old_database(tmp_path / "study.db")
    upgrade = command.upgrade

    def interrupted(config, revision):
        upgrade(config, revision)
        raise RuntimeError("simulated post-DDL failure")

    monkeypatch.setattr(command, "upgrade", interrupted)
    with pytest.raises(RuntimeError, match="simulated"):
        create_app(tmp_path, TOKEN)
    with sqlite3.connect(tmp_path / "study.db") as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"
        assert connection.execute("SELECT id FROM attempts").fetchone()[0] == 12
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='workspaces'").fetchall() == []
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1


def test_concurrent_workspace_mutations_keep_names_unique_and_one_active(tmp_path):
    with client(tmp_path) as c, ThreadPoolExecutor(max_workers=2) as workers:
        for index in range(6):
            start = Barrier(2)

            def create_same():
                start.wait(timeout=5)
                return c.post("/api/workspaces", json={"name": f"并发空间-{index}"}).status_code

            results = list(workers.map(lambda _: create_same(), range(2)))
            assert sorted(results) == [200, 409]
        spaces = c.get("/api/workbench").json()["workspaces"]
        # Reduce to two spaces, then race their removal through the public API.
        for space in spaces[2:]:
            assert c.request("DELETE", f"/api/workspaces/{space['id']}", json={"confirm_name": space["name"]}).status_code == 200
        start = Barrier(2)

        def remove(space):
            start.wait(timeout=5)
            return c.request("DELETE", f"/api/workspaces/{space['id']}", json={"confirm_name": space["name"]}).status_code

        assert sorted(workers.map(remove, spaces[:2])) == [200, 409]
        state = c.get("/api/workbench").json()
        assert len(state["workspaces"]) == 1
        assert state["active_workspace_id"] == state["workspaces"][0]["id"]


def test_workbench_selection_and_list_are_one_snapshot(tmp_path):
    with client(tmp_path) as c, ThreadPoolExecutor(max_workers=1) as worker:
        completed = Event()
        writes = []

        def create():
            try:
                return c.post("/api/workspaces", json={"name": "读取期间新建"})
            finally:
                completed.set()

        def interleave(_, cursor, statement, parameters, context, many):
            if "ORDER BY workspaces.created_at" in statement and not writes:
                writes.append(worker.submit(create))
                completed.wait(0.5)

        engine = c.app.state.engine
        event.listen(engine, "after_cursor_execute", interleave)
        try:
            state = c.get("/api/workbench").json()
            assert writes
            assert state["active_workspace_id"] in {space["id"] for space in state["workspaces"]}
        finally:
            event.remove(engine, "after_cursor_execute", interleave)
            for pending in writes:
                assert pending.result(timeout=10).status_code == 200
