from pathlib import Path

import pytest


@pytest.mark.parametrize('change', ['clean', 'cache', 'missing', 'modified'])
def test_frozen_migrations_match_source(tmp_path, monkeypatch, change):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    from check_frozen_sources import check_migrations
    from release_inventory import stage_files

    source = tmp_path / 'source'
    payload = tmp_path / 'payload'
    staged = payload / '_internal/migrations'
    for root in (source, staged):
        (root / 'versions').mkdir(parents=True)
        (root / 'env.py').write_bytes(b'# environment')
        (root / 'versions/0018_next.py').write_bytes(b'# migration')
    (source / '__pycache__').mkdir()
    (source / '__pycache__/env.pyc').write_bytes(b'build-only')
    if change == 'clean':
        check_migrations(stage_files(payload), source)
        return
    if change == 'cache':
        (staged / '__pycache__').mkdir()
        (staged / '__pycache__/env.pyc').write_bytes(b'build-only')
    elif change == 'missing':
        (staged / 'env.py').unlink()
    else:
        (staged / 'versions/0018_next.py').write_bytes(b'changed')
    with pytest.raises(ValueError, match='migration files'):
        check_migrations(stage_files(payload), source)
