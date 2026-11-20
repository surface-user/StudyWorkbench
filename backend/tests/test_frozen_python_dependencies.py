import importlib
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement


def test_verified_graph_markers_extras_cycles_and_missing_targets(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    graph = importlib.import_module('frozen_python_dependencies').declared_graph
    requirements = {
        'child': ('1', {'feature'}, ['leaf; extra == "feature"', 'parent; platform_system == "Windows"']),
        'parent': ('2', set(), ['child[feature]', 'optional; extra == "test"', 'outside', 'leaf>=9',
                               'child[unknown]', 'link @ https://example.test/release']),
        'leaf': ('1', set(), []),
    }
    packages = {k: (v, extras, list(map(Requirement, rows))) for k, (v, extras, rows) in requirements.items()}
    edges, missing, inactive, extras = graph(packages, {**default_environment(), 'platform_system': 'Windows'})
    assert edges == {'parent': {'child'}, 'child': {'leaf', 'parent'}}
    assert missing == [('parent', 'child', 'undeclared-requested-extra'), ('parent', 'leaf', 'version-mismatch'),
                       ('parent', 'link', 'direct-reference'), ('parent', 'outside', 'not-in-mapped-subset')]
    assert inactive == 1 and extras == {'child': ['feature']}
    assert graph(dict(reversed(list(packages.items()))), {**default_environment(), 'platform_system': 'Windows'}) == (
        edges, missing, inactive, extras)


def test_optional_only_and_incompatible_requirements_never_create_edges(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    graph = importlib.import_module('frozen_python_dependencies').declared_graph
    packages = {'root': ('1', set(), [Requirement('lib>2'), Requirement('absent; extra == "optional"')]),
                'lib': ('1', set(), [])}
    edges, unresolved, inactive, extras = graph(packages, default_environment())
    assert not edges and not extras and inactive == 1
    assert unresolved == [('root', 'lib', 'version-mismatch')]
