import copy
import importlib
import os
import sys
from pathlib import Path

import pytest
from test_imports import client


@pytest.fixture
def scale(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('check_learning_scale')
    root = tmp_path / 'scale'
    root.mkdir()
    (root / 'fixture-marker').write_text(tool.MARKER, encoding='utf-8')
    with client(root / 'data') as c:
        other = c.post('/api/workspaces', json={'name': 'Synthetic isolation'}).json()['id']
    fixture = tool.seed(root / 'data', other, 400, event_count=200)
    return tool, root, fixture


def requester(c):
    def api(method, path, body=None, *, expected=200, headers=None):
        response = c.request(method, path, json=body, headers=headers)
        assert response.status_code == expected, response.text
        return response.json()
    return api


def test_generated_history_and_full_event_projection_are_complete_and_reads_do_not_mutate(scale):
    tool, root, fixture = scale
    with client(root / 'data') as c:
        before = tool.logical_hash(root / 'data/study.db')
        originals = {p: p.read_bytes() for p in (root / 'data').rglob('scale-note.txt')}
        result = {}
        tool.verify_reads(requester(c), fixture, result)
        assert result['history_pages'] == 4 and result['event_pages'] == 2
        assert result['statistics']['attempts'] == 400 and result['statistics']['mastered'] == 25
        record = c.get(f"{tool.SCOPE}/attempts/{fixture['focus']}/record?limit=100").json()
        assert not any(e.get('knowledge_points') == [] for e in record['events'])
        assert record['effective_knowledge_points'] == []  # The correction is outside this page.
        assert tool.logical_hash(root / 'data/study.db') == before
        assert originals == {p: p.read_bytes() for p in originals}


def test_new_attempt_does_not_shift_older_cursor_or_change_other_historical_rows(scale):
    tool, root, fixture = scale
    with client(root / 'data') as c:
        before = tool.logical_hash(root / 'data/study.db')
        added = tool.verify_append(requester(c), fixture)
        assert tool.logical_hash(root / 'data/study.db') != before
        assert tool.logical_hash(root / 'data/study.db', exclude_attempt_id=added) == before
        foreign = c.get(f"/api/workspaces/{fixture['other']}/attempt-history?limit=100").json()
        assert [a['id'] for a in foreign] == fixture['foreign_ids'][::-1]
        assert all(a['status'] == 'pending_review' and a['response'] == {'text': tool.TEXT} for a in foreign)


@pytest.mark.parametrize('damage', ['duplicate', 'foreign-id', 'latest-score', 'lost-review', 'answer'])
def test_history_oracle_rejects_real_page_corruption(scale, damage):
    tool, root, fixture = scale
    with client(root / 'data') as c:
        page = c.get(tool.SCOPE + '/attempt-history?limit=100').json()
    page = copy.deepcopy(page)
    if damage == 'duplicate':
        page[1] = page[0]
    elif damage == 'foreign-id':
        page[0]['id'] = fixture['foreign_ids'][-1]
    elif damage == 'latest-score':
        page[0]['score'] = 1
    elif damage == 'lost-review':
        next(row for row in page if row['reviews'])['reviews'].pop()
    else:
        page[0]['response'] = {'text': 'changed'}
    with pytest.raises(AssertionError):
        tool.verify_history(page, fixture['main_ids'][::-1][:100],
                            {identifier: index for index, identifier in enumerate(fixture['main_ids'])})


@pytest.mark.parametrize('damage', ['page-only-label', 'review-count', 'lost-note', 'algorithm'])
def test_projection_oracle_rejects_incomplete_page_derived_results(scale, damage):
    tool, root, fixture = scale
    with client(root / 'data') as c:
        record = c.get(f"{tool.SCOPE}/attempts/{fixture['focus']}/record?limit=1").json()
    if damage == 'page-only-label':
        record['effective_knowledge_points'] = None
    elif damage == 'review-count':
        record['reviewed_count'] = 1
    elif damage == 'lost-note':
        record['related_notes'].pop()
    else:
        record['knowledge_projection_algorithm'] = 'page-local'
    with pytest.raises(AssertionError):
        tool.verify_record(record, fixture)


def test_fixture_refuses_reseeding_a_populated_database_without_changing_it(scale):
    tool, root, fixture = scale
    before = tool.logical_hash(root / 'data/study.db')
    with pytest.raises(AssertionError):
        tool.seed(root / 'data', fixture['other'], 400, event_count=200)
    assert tool.logical_hash(root / 'data/study.db') == before
    (root / 'fixture-marker').write_text('not this fixture', encoding='utf-8')
    with pytest.raises(AssertionError):
        tool.seed(root / 'data', fixture['other'], 400, event_count=200)
    assert tool.logical_hash(root / 'data/study.db') == before


def test_cli_preserves_an_existing_output_directory(scale, monkeypatch):
    tool, root, _ = scale
    monkeypatch.setattr(sys, 'argv', ['check_learning_scale', '--test-root', str(root)])
    with pytest.raises(FileExistsError):
        tool.main()
    assert (root / 'fixture-marker').read_text('utf-8') == tool.MARKER


def test_p95_uses_nearest_rank_with_no_discarded_outliers(scale):
    tool, _, _ = scale
    assert tool.p95(list(range(100, 0, -1))) == 95
    assert tool.p95([1] * 28 + [500, 10000]) == 500


@pytest.mark.parametrize('values', [[], [float('nan')], [float('inf')], [-1]])
def test_invalid_measurements_are_rejected(scale, values):
    tool, _, _ = scale
    with pytest.raises(AssertionError):
        tool.p95(values)


@pytest.mark.skipif(os.name != 'nt', reason='The registered process counters are Windows-only')
def test_memory_observation_uses_a_real_bounded_child_process(scale):
    tool, root, _ = scale
    with tool.backend(root, None) as (api, process):
        result = {}
        with tool.memory_samples(process, api.port, Path(sys._base_executable), result) as sample:
            assert api('GET', '/api/health')['status'] == 'ok'
            sample()
        assert result['samples'] >= 3 and result['peak_working_set_bytes'] > 0
        assert result['baseline_private_bytes'] > 0 and result['observed_private_growth_bytes'] >= 0
        assert result['service_pid'] == tool.listener_pid(api.port)
        assert result['process_chain'][0]['pid'] == result['service_pid']
        assert result['process_chain'][-1]['pid'] == process.pid


@pytest.mark.skipif(os.name != 'nt', reason='Windows listener ownership binding')
def test_memory_observer_rejects_an_unrelated_executable(scale):
    tool, root, _ = scale
    with tool.backend(root, None) as (api, process):
        with pytest.raises(AssertionError, match='executable differs'):
            with tool.memory_samples(process, api.port, Path(__file__), {}):
                raise AssertionError('Must reject before collecting unrelated process memory')


@pytest.mark.skipif(os.name != 'nt', reason='Windows listener ownership binding')
def test_memory_observer_rejects_listener_owner_change(scale, monkeypatch):
    tool, root, _ = scale
    with tool.backend(root, None) as (api, process):
        with pytest.raises(AssertionError, match='PID changed'):
            with tool.memory_samples(process, api.port, Path(sys._base_executable), {}) as sample:
                owner = tool.listener_pid(api.port)
                monkeypatch.setattr(tool, 'listener_pid', lambda _: owner + 1)
                sample()
