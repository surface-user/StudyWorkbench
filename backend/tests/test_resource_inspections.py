from pathlib import Path

from test_explorer import PREFIX, client, start


def test_inspection_is_read_only_mixed_types_and_safe_errors(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    files = {'note.md': b'# note', 'lecture.pdf': b'%PDF-1.7',
             'video.webm': b'\x1aE\xdf\xa3fixture', 'unknown.xyz': b'opaque',
             'broken.mp4': b'not mp4', 'fake.pdf': b'not pdf', 'denied.txt': b'private'}
    for name, data in files.items():
        (source / name).write_bytes(data)
    original_open = Path.open

    def deny(path, *args, **kwargs):
        if path.name == 'denied.txt':
            raise PermissionError('injected')
        return original_open(path, *args, **kwargs)

    with client(tmp_path / 'data') as c:
        monkeypatch.setattr(Path, 'open', deny)
        response = c.post(PREFIX + '/resource-inspections', json={
            'source_paths': [str(source / name) for name in files] + [str(source / 'missing'), str(source)]})
        assert response.status_code == 200, response.text
        rows = {r['name']: r for r in response.json()}
        assert rows['note.md']['type'] == 'Markdown 笔记'
        assert rows['lecture.pdf']['warning'] is None
        assert rows['video.webm']['kind'] == 'media'
        assert rows['video.webm']['size'] == len(files['video.webm'])
        assert rows['unknown.xyz']['warning'] and rows['unknown.xyz']['error'] is None
        assert rows['fake.pdf']['warning'] and rows['fake.pdf']['error'] is None
        assert rows['broken.mp4']['error']
        assert rows['denied.txt']['error'] and rows['missing']['error']
        assert rows['source']['kind'] == 'folder'
        assert c.get(PREFIX + '/nodes').json() == []
        assert c.get(PREFIX + '/resource-add-jobs').json() == []
        assert c.post(PREFIX + '/resource-inspections', json={'source_paths': ['relative.txt']}).json()[0]['error']
        assert c.post(PREFIX + '/resource-inspections', json={'source_paths': [str(source)]},
                      headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(PREFIX + '/resource-inspections', json={'source_paths': [str(source)]},
                      headers={'Authorization': 'bad'}).status_code == 401
        assert c.post(PREFIX + '/resource-inspections', json={'source_paths': []}).status_code == 422


def test_analysis_reuses_original_and_requires_explicit_confirmation(tmp_path):
    file = tmp_path / 'source.md'
    file.write_text('# note\noriginal text', encoding='utf-8')
    root = tmp_path / 'data'
    with client(root) as c:
        copied = start(c, file)
        node_id = copied['results'][0]['resource_item_id']
        node = c.get(PREFIX + '/nodes/' + node_id).json()
        originals = list((root / 'workspaces/default/originals').iterdir())
        response = c.post(f"{PREFIX}/resources/{node['resource_id']}/analyze")
        assert response.status_code == 200, response.text
        job = response.json()
        assert job['resource_id'] == node['resource_id'] and job['status'] == 'preview'
        assert c.get(PREFIX + '/notes').json() == []
        assert list((root / 'workspaces/default/originals').iterdir()) == originals
        assert len(c.get(PREFIX + '/nodes').json()) == 1
        repeated = c.post(f"{PREFIX}/resources/{node['resource_id']}/analyze").json()
        assert repeated['id'] == job['id'] and repeated['duplicate']
        other = c.post('/api/workspaces', json={'name': 'other'}).json()['id']
        assert c.post(f"/api/workspaces/{other}/resources/{node['resource_id']}/analyze").status_code == 404
        assert file.read_text(encoding='utf-8') == '# note\noriginal text'


def test_inspection_size_and_data_root_rejection(tmp_path, monkeypatch):
    from study_workbench import explorer

    file = tmp_path / 'large.txt'
    file.write_bytes(b'1234')
    with client(tmp_path / 'data') as c:
        monkeypatch.setattr(explorer, 'FILE_LIMIT', 2)
        row = c.post(PREFIX + '/resource-inspections', json={'source_paths': [str(file)]}).json()[0]
        assert row['error'] and row['size'] == 4
        assert c.get(PREFIX + '/resource-add-jobs').json() == []
        assert c.post(PREFIX + '/resource-inspections', json={
            'source_paths': [str(tmp_path / 'data')]}).json()[0]['error']


def test_resource_search_is_workspace_wide_literal_and_hides_removed(tmp_path):
    folder = tmp_path / 'folder'
    folder.mkdir()
    (folder / 'Lecture%_Note.md').write_bytes(b'note')
    with client(tmp_path / 'data') as c:
        start(c, folder)
        found = c.get(PREFIX + '/nodes', params={'search': 'lecture%_'}).json()
        assert len(found) == 1 and found[0]['name'] == 'Lecture%_Note.md'
        assert c.get(PREFIX + '/nodes', params={'search': 'nomatch'}).json() == []
        assert c.get(PREFIX + '/nodes', params={'search': '%_'}).json() == found
        other = c.post('/api/workspaces', json={'name': 'other'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/nodes', params={'search': 'lecture'}).json() == []
        assert c.delete(PREFIX + '/nodes/' + found[0]['resource_item_id']).status_code == 200
        assert c.get(PREFIX + '/nodes', params={'search': 'lecture'}).json() == []
