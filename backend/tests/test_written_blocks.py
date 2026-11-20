import pytest
from study_workbench.backup_store import create_backup, restore_backup
from study_workbench.data_root import write_settings
from study_workbench.question_files_format import serialize_file
from test_document_files import add
from test_imports import SCOPE, client
from test_learning import seed
from test_question_files import file_for

BLOCKS = [{'type': 'text', 'text': '先化简'}, {'type': 'latex', 'tex': r'x^2 + 1', 'display': True}]


@pytest.mark.parametrize('kind', ['calculation', 'proof', 'subjective', 'single_choice', 'multiple_choice', 'fill_blank', 'reading_question'])
def test_blocks_follow_question_response_kind(tmp_path, kind):
    with client(tmp_path) as c:
        q = seed(c, kind)
        result = c.post(SCOPE + '/attempts', json={'question_id': q['id'], 'response': {'blocks': BLOCKS}})
        if kind in {'calculation', 'proof', 'subjective'}:
            assert result.status_code == 200, result.text
            assert result.json()['status'] == 'pending_review' and result.json()['score'] is None
        else:
            assert result.status_code == 422
            assert c.get(SCOPE + '/attempt-history').json() == []


def test_rejected_blocks_do_not_create_or_replay_an_attempt(tmp_path):
    with client(tmp_path) as c:
        base = dict(question_id='demo-proof', request_id='rich-answers-key-01')
        url = '/api/attempts'
        assert c.post(url, json=dict(base, response={'blocks': BLOCKS})).status_code == 200
        invalid = [
            {}, {'blocks': []}, {'blocks': BLOCKS, 'text': '混合'},
            {'blocks': [{'type': 'text', 'text': '  '}]}, {'blocks': [{'type': 'text', 'text': 'x'}] * 201},
            {'blocks': [{'type': 'text', 'text': 'x' * 10001}] * 2},
            {'blocks': [{'type': 'latex', 'tex': r'\input{x}'}]},
            {'blocks': [{'type': 'latex', 'tex': 'x' * 8001}]},
            {'blocks': [{'type': 'image', 'attachment_id': 'other', 'alt': '图片'}]},
            {'blocks': [{'type': 'attachment', 'path': 'outside.txt'}]},
            {'blocks': [BLOCKS[0], dict(BLOCKS[1], display=1)]},
        ]
        for response in invalid:
            assert c.post(url, json={'question_id': 'demo-proof', 'response': response}).status_code == 422
        assert c.post(url, json=dict(base, response=invalid[-1])).status_code == 422
        assert c.post(url, json=dict(base, response={'blocks': list(reversed(BLOCKS))})).status_code == 409
        assert len(c.get(url).json()) == 1


def test_subjective_reading_missing_answer_survives_library_restore(tmp_path):
    source, target, package = tmp_path / 'source', tmp_path / 'restored', tmp_path / 'backup.zip'
    settings = tmp_path / 'profile' / 'settings.json'
    with client(source) as c:
        question = file_for('reading_question', missing=True)
        question.question.id = 'read-and-explain'
        question.question.response_kind = 'subjective'
        question.question.options = []
        node, _, _ = add(c, source, '阅读题.md', serialize_file(question).encode())
        doc = c.get(f'{SCOPE}/nodes/{node}/document').json()
        confirmed = c.post(f'{SCOPE}/nodes/{node}/question-file/confirm', json={
            'expected_sha256': doc['sha256'], 'expected_version_id': None, 'confirm': True})
        assert confirmed.status_code == 200, confirmed.text
        body = dict(question_id=question.question.id, question_version_id=confirmed.json()['id'],
                    request_id='rich-reading-key-01', response={'blocks': BLOCKS})
        first = c.post(SCOPE + '/attempts', json=body)
        assert first.status_code == 200, first.text
        assert first.json()['score'] is None and first.json()['status'] == 'pending_review'
        review = c.post(f"{SCOPE}/attempts/{first.json()['id']}/reviews",
                        json={'confirm': True, 'score': 0.75, 'feedback': '部分正确'})
        assert review.status_code == 200
        assert c.post(SCOPE + '/attempts', json={'question_id': 'demo-proof', 'response': {'text': '旧格式'}}).status_code == 200
        before = c.get(SCOPE + '/attempt-history').json()
    write_settings(settings, source)
    create_backup(source, package)
    assert restore_backup(package, target, settings)['data_activated']
    with client(target) as c:
        assert c.post(SCOPE + '/attempts', json=body).json() == first.json()
        history = c.get(SCOPE + '/attempt-history').json()
        assert history == before and len(history) == 2
        assert history[1]['response'] == body['response'] and history[1]['question_version_id'] == body['question_version_id']
        assert history[1]['score'] == 0.75 and history[1]['reviews'][0]['feedback'] == '部分正确'
