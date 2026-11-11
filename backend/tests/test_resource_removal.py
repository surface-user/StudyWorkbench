import sqlite3

from sqlalchemy import event
from test_explorer import PREFIX, client, start
from test_question_files import convert, preview, publish


def test_remove_subtree_keeps_files_records_and_does_not_reappear(tmp_path):
    source = tmp_path / '资料'
    source.mkdir()
    (source / '讲义.md').write_text('保留原文', encoding='utf-8')
    root = tmp_path / 'data'
    with client(root) as c:
        job = start(c, source)
        folder = c.get(PREFIX + '/nodes').json()[0]['resource_item_id']
        child = c.get(PREFIX + '/nodes?parent_id=' + folder).json()[0]
        node = child['resource_item_id']
        c.post(PREFIX + '/nodes', json=dict(kind='link', name='链接', parent_id=folder,
                                          url='https://example.com')).raise_for_status()
        before = c.get(PREFIX + '/attempts').json()
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        endpoint = PREFIX + '/nodes/' + folder
        assert c.delete(f'/api/workspaces/{other}/nodes/{folder}').status_code == 404
        assert c.delete(endpoint, headers={'Authorization': 'bad'}).status_code == 401
        assert c.delete(endpoint, headers={'Origin': 'https://example.com'}).status_code == 403
        response = c.delete(endpoint)
        assert response.status_code == 200, response.text
        assert len(response.json()['removed_ids']) == 3
        assert c.delete(endpoint).json() == {'removed_ids': []}
        assert c.get(PREFIX + '/nodes').json() == []
        assert c.get(PREFIX + '/nodes/' + node).json()['status'] == 'removed'
        # Open editors can still save/read their retained workfiles; removal is not file erasure.
        assert c.get(PREFIX + '/nodes/' + node + '/document').status_code == 200
        assert c.get(PREFIX + '/attempts').json() == before
        assert c.post(PREFIX + '/nodes', json=dict(kind='folder', name='子目录', parent_id=folder)).status_code == 409
        assert c.patch(PREFIX + '/nodes/' + node, json=dict(name='移回.md', parent_id=None)).status_code == 409
        replacement = c.post(PREFIX + '/nodes', json=dict(kind='folder', name='资料')).json()
        assert replacement['name'] == '资料'
        for row in job['results']:
            if row.get('copied_path'):
                assert (root / row['copied_path']).read_bytes() == (source / '讲义.md').read_bytes()
    with client(root) as c:
        assert [n['resource_item_id'] for n in c.get(PREFIX + '/nodes').json()] == [replacement['resource_item_id']]
        assert (source / '讲义.md').read_text(encoding='utf-8') == '保留原文'


def test_removal_is_atomic_and_blocks_active_copies(tmp_path):
    with client(tmp_path) as c:
        folder = c.post(PREFIX + '/nodes', json=dict(kind='folder', name='资料')).json()['resource_item_id']
        child = c.post(PREFIX + '/nodes', json=dict(kind='folder', name='子目录', parent_id=folder)).json()['resource_item_id']
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO resource_add_jobs VALUES ('busy','default',NULL,'unused','queued',0,'[]',NULL)")
        assert c.delete(PREFIX + '/nodes/' + folder).status_code == 409
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("UPDATE resource_add_jobs SET status='cancelled' WHERE id='busy'")

        def fail(_, cursor, statement, parameters, context, many):
            if statement.startswith('UPDATE workspace_nodes'):
                raise RuntimeError('injected removal failure')

        event.listen(c.app.state.engine, 'before_cursor_execute', fail)
        try:
            response = c.delete(PREFIX + '/nodes/' + folder)
            assert response.status_code == 500 and response.json()['error']['code'] == 'internal_error'
            assert response.json()['detail'] == '请求未完成，请稍后重试'
            assert 'injected removal failure' not in response.text
        finally:
            event.remove(c.app.state.engine, 'before_cursor_execute', fail)
        assert c.get(PREFIX + '/nodes/' + folder).json()['status'] == 'ready'
        assert c.get(PREFIX + '/nodes/' + child).json()['status'] == 'ready'


def test_removal_preserves_confirmed_version_attempt_and_open_editor(tmp_path):
    with client(tmp_path) as c:
        node = convert(c, 'demo-integral')
        version = publish(c, node, preview(c, node)).json()
        attempt = c.post(PREFIX + '/attempts', json=dict(question_id='demo-integral',
            question_version_id=version['id'], response={'selected': ['a']})).json()
        before = c.get(PREFIX + '/attempts').json()
        document = PREFIX + '/nodes/' + node + '/document'
        current = c.get(document).json()
        c.delete(PREFIX + '/nodes/' + node).raise_for_status()
        c.put(document, json=dict(expected_sha256=current['sha256'], text=current['text'] + '\n')).raise_for_status()
        record = c.get(f"{PREFIX}/attempts/{attempt['id']}/record").json()
        assert record['resource_item_id'] is None
        assert record['question_version_id'] == version['id'] and record['version_status'] == 'known'
        assert c.get(PREFIX + '/attempts').json() == before


def test_0011_upgrade_retains_tree_and_creates_backup(tmp_path):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from study_workbench.db import database

    root = tmp_path / 'old'
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as conn:
        config.attributes['connection'] = conn
        command.upgrade(config, '0011')
        conn.exec_driver_sql("INSERT INTO workspace_nodes(id,workspace_id,kind,name,name_key) VALUES ('old','default','folder','资料','资料')")
    engine.dispose()
    with client(root) as c:
        assert c.get(PREFIX + '/nodes').json()[0]['resource_item_id'] == 'old'
        assert c.delete(PREFIX + '/nodes/old').status_code == 200
    backup = list((root / 'backups').glob('study-before-0016-*.db'))
    assert len(backup) == 1
    with sqlite3.connect(backup[0]) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0011',)
        assert db.execute('SELECT id FROM workspace_nodes').fetchall() == [('old',)]
