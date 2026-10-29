import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/workspace_layout.dart';

void main() {
  test('resource identity survives rename, same blob names stay independent and legacy state roundtrips', () {
    final unknown = {
      'id': 'future',
      'kind': 'future',
      'resource_name': {'unrecognized': true},
      'state': ['草稿', 2],
    };
    final layout = WorkspaceLayout.fromJson({
      'version': 1,
      'tabs': [
        {'id': 'old', 'kind': 'question', 'draft': '旧草稿'},
        unknown,
      ],
      'closed_tabs': [
        {'id': 'web', 'kind': 'web', 'url': 'https://example.com/old'},
      ],
      'active_tab_id': 'old',
    });
    final node = {
      'resource_item_id': 'a' * 32,
      'kind': 'resource',
      'name': '同名.md',
    };
    layout.openResource(node);
    final first = layout.activeId;
    layout.openResource({...node, 'name': '改名.md', 'parent_id': 'folder'});
    expect(layout.activeId, first);
    expect(layout.tabs, hasLength(3));
    expect(layout.tabs.last.title, '改名.md');
    layout.openResource({...node, 'resource_item_id': 'b' * 32});
    expect(layout.tabs, hasLength(4));
    final restored = WorkspaceLayout.fromJson(layout.toJson());
    expect(restored.version, 2);
    expect(restored.tabs.first.draft, '旧草稿');
    expect(restored.tabs[1].toJson(), unknown);
    expect(restored.closed.first.url, 'https://example.com/old');
    restored.close(first!);
    restored.reopen();
    expect(restored.activeId, first);
    restored.tabs.last.documentState['mode'] = 'edit';
    restored.tabs.last.documentState['page'] = 2;
    restored.close(first);
    restored.openResource(node);
    final replacement = restored.activeId;
    expect(replacement, first);
    expect(restored.tabs.last.documentState['mode'], 'edit');
    expect(restored.tabs.last.documentState['page'], 2);
    restored.closed.add(
      WorkbenchTab(
        id: 'alias',
        kind: 'resource',
        resourceItemId: 'a' * 32,
        viewKind: 'document',
      ),
    );
    restored.reopen();
    expect(restored.activeId, replacement);
    expect(
      restored.tabs.where((t) => t.resourceItemId == 'a' * 32),
      hasLength(1),
    );
    expect(restored.closed.last.id, 'alias');
  });
  test('active close prefers left, inactive close stays put and navigation deduplicates by kind', () {
    final layout = WorkspaceLayout.fromJson({
      'tabs': [
        {'id': 'a', 'kind': 'study'},
        {'id': 'b', 'kind': 'question'},
        {'id': 'c', 'kind': 'web'},
      ],
      'closed_tabs': [],
      'active_tab_id': 'b',
    });
    layout.close('b');
    expect(layout.activeId, 'a');
    layout.close('c');
    expect(layout.activeId, 'a');
    layout.openSingleton('study');
    expect(layout.tabs, hasLength(1));
    layout.openSingleton('import');
    layout.openSingleton('import');
    expect(layout.tabs, hasLength(2));
    expect(layout.tabs.last.kind, 'import');
    final restored = WorkspaceLayout.fromJson(layout.toJson());
    expect(restored.activeId, layout.activeId);
    expect(restored.tabs.last.id, layout.tabs.last.id);
  });

  test('closing restores draft and URL without changing other tabs', () {
    final layout = WorkspaceLayout.fromJson({
      'tabs': [
        {'id': 'a', 'kind': 'question', 'draft': '中文草稿'},
        {'id': 'b', 'kind': 'web', 'url': 'https://example.com'},
      ],
      'closed_tabs': [],
      'active_tab_id': 'a',
    });
    layout.close('a');
    expect(layout.activeId, 'b');
    layout.reopen();
    expect(layout.activeId, 'a');
    expect(layout.tabs.last.draft, '中文草稿');
    final restored = WorkspaceLayout.fromJson(layout.toJson());
    expect(restored.tabs.first.url, 'https://example.com');
    expect(restored.tabs.last.draft, '中文草稿');
    restored.reorder('a', 'b');
    expect(restored.tabs.map((tab) => tab.id), ['a', 'b']);
    expect(restored.activeId, 'a');
    restored.reorder('missing', 'b');
    expect(restored.tabs.first.draft, '中文草稿');
    restored.close('a');
    restored.close('b');
    expect(restored.activeId, isNull);
    restored.reopen();
    expect(restored.activeId, 'b');
  });

  test('tab IDs are unique, cycling wraps and limits preserve state', () {
    final layout = WorkspaceLayout.fromJson({
      'tabs': [],
      'closed_tabs': [],
      'active_tab_id': null,
    });
    for (var i = 0; i < 16; i++) {
      layout.add('web');
    }
    expect(layout.tabs.map((t) => t.id).toSet(), hasLength(16));
    expect(() => layout.add('question'), throwsStateError);
    layout.activeId = layout.tabs.first.id;
    layout.cycle(-1);
    expect(layout.activeId, layout.tabs.last.id);
    layout.cycle(1);
    expect(layout.activeId, layout.tabs.first.id);
    for (final id in layout.tabs.map((t) => t.id).toList()) {
      layout.close(id);
    }
    expect(layout.closed, hasLength(10));
  });
}
