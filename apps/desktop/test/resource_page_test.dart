import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/resource_page.dart';
import 'package:study_workbench/workspace_layout.dart';

class _Backend implements Backend {
  bool missing = true;
  int reads = 0;
  @override
  String get dataDir => 'test-profile';
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    reads++;
    if (missing) throw StateError('404');
    if (path.endsWith('/document')) {
      return {'type': 'unsupported', 'sha256': 'test', 'working_copy': false};
    }
    return {
      'resource_item_id': 'a' * 32,
      'name': '改名.pdf',
      'kind': 'resource',
      'status': 'ready',
      'size': 42,
      'sha256': 'test',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'missing resource retains identity and retry resolves without changing tab',
    (tester) async {
      final backend = _Backend();
      final tab = WorkbenchTab(
        id: 'stable-tab',
        kind: 'resource',
        resourceItemId: 'a' * 32,
        viewKind: 'document',
        resourceName: '旧名.pdf',
      );
      var changes = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ResourcePage(
              backend: backend,
              workspaceId: 'default',
              tab: tab,
              onChanged: () => changes++,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('标签与草稿已保留'), findsOneWidget);
      backend.missing = false;
      await tester.tap(find.text('重试打开资源'));
      await tester.pumpAndSettle();
      expect(find.text('改名.pdf'), findsOneWidget);
      expect(tab.id, 'stable-tab');
      expect(tab.resourceItemId, 'a' * 32);
      expect(changes, 1);
      expect(backend.reads, 3);
      expect(tester.takeException(), isNull);
    },
  );
}
