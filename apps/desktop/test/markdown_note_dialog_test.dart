import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/markdown_note_dialog.dart';
import 'package:study_workbench/resource_explorer.dart';
import 'package:study_workbench/resource_page.dart';
import 'package:study_workbench/workspace_layout.dart';

class _Backend implements Backend {
  _Backend(this.handle);
  final Future<dynamic> Function(String, String, Map<String, dynamic>?) handle;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) => handle(method, path, body);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> note() => {
  'resource_item_id': 'a' * 32,
  'name': '新笔记.md',
  'kind': 'resource',
  'status': 'ready',
};

Future<void> show(
  WidgetTester tester,
  Backend backend,
  ValueChanged<Map<String, dynamic>> opened, {
  String? source,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () async {
              final result = await showDialog<Map<String, dynamic>>(
                context: context,
                builder: (_) => MarkdownNoteDialog(
                  backend: backend,
                  workspaceId: 'default',
                  parentId: 'folder',
                  fromResource: true,
                  sourceResourceItemId: source,
                ),
              );
              if (result != null) opened(result);
            },
            child: const Text('打开'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('打开'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'creation retries same request after lost response and opens editable stable tab',
    (tester) async {
      final bodies = <Map<String, dynamic>>[];
      Map<String, dynamic>? opened;
      final backend = _Backend((method, path, body) async {
        expect(method, 'POST');
        expect(path, '/api/workspaces/default/markdown-notes');
        bodies.add(Map.from(body!));
        if (bodies.length == 1) throw StateError('response lost');
        return note();
      });
      await show(tester, backend, (node) => opened = node);
      expect(find.textContaining('关联来源请使用书签与备注'), findsOneWidget);
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(find.textContaining('未确认创建结果'), findsOneWidget);
      expect(opened, isNull);
      await tester.tap(find.text('重试原请求'));
      await tester.pumpAndSettle();
      expect(bodies[0], bodies[1]);
      expect(bodies[0]['parent_id'], 'folder');
      final layout = WorkspaceLayout.fromJson({
        'version': 2,
        'tabs': [],
        'closed_tabs': [],
        'active_tab_id': null,
      });
      layout.openResource(opened!);
      expect(layout.tabs.single.documentState['mode'], 'edit');
      final restored = WorkspaceLayout.fromJson(layout.toJson());
      expect(restored.tabs.single.resourceItemId, 'a' * 32);
      expect(restored.tabs.single.documentState['mode'], 'edit');
    },
  );

  testWidgets(
    'changing failed creation starts a new request rather than conflicting with old request',
    (tester) async {
      final ids = <String>[];
      await show(
        tester,
        _Backend((method, path, body) async {
          ids.add(body!['request_id'] as String);
          throw StateError('failed');
        }),
        (_) {},
      );
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('修改名称后另建'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '另一份.md');
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(ids.length, 2);
      expect(ids[0], isNot(ids[1]));
    },
  );

  testWidgets(
    'recovery after restart uses persisted request and original parent',
    (tester) async {
      Map<String, dynamic>? posted, opened;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'GET') {
            return [
              {
                'request_id': 'saved-request-1234',
                'requested_name': '已中断.md',
                'requested_parent_id': null,
                'status': 'interrupted',
              },
            ];
          }
          posted = body;
          return note();
        }),
        (node) => opened = node,
      );
      await tester.tap(find.text('恢复创建'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('已中断.md'));
      await tester.pumpAndSettle();
      expect(posted, {
        'request_id': 'saved-request-1234',
        'name': '已中断.md',
        'parent_id': null,
      });
      expect(opened!['open_in_edit'], true);
    },
  );

  testWidgets(
    'select existing note rechecks tombstone and rejects non Markdown',
    (tester) async {
      var removed = true;
      var opens = 0;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (path.contains('/markdown-notes?')) return [note()];
          if (path.endsWith('/document')) {
            return {'type': 'text', 'working_copy': false};
          }
          return {...note(), 'status': removed ? 'removed' : 'ready'};
        }),
        (_) => opens++,
      );
      await tester.tap(find.text('选择已有Markdown笔记'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ListTile, '新笔记.md'));
      await tester.pumpAndSettle();
      expect(find.textContaining('笔记已移除'), findsOneWidget);
      removed = false;
      await tester.tap(find.widgetWithText(ListTile, '新笔记.md'));
      await tester.pumpAndSettle();
      expect(find.textContaining('不是Markdown笔记'), findsOneWidget);
      expect(opens, 0);
    },
  );
  testWidgets(
    'explorer folder creation passes folder and opens note after refresh',
    (tester) async {
      Map<String, dynamic>? posted, opened;
      final backend = _Backend((method, path, body) async {
        if (method == 'POST') {
          posted = body;
          return note();
        }
        return [
          {
            'resource_item_id': 'folder',
            'name': '课程',
            'kind': 'folder',
            'status': 'ready',
          },
        ];
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                ResourceExplorer(
                  backend: backend,
                  workspaceId: 'default',
                  onOpen: (node) => opened = node,
                ),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('新建笔记'), findsOneWidget);
      await tester.tap(find.byTooltip('资源操作'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('在此新建笔记'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(posted!['parent_id'], 'folder');
      expect(opened!['open_in_edit'], true);
    },
  );

  testWidgets(
    'document resource note action links source before opening editor',
    (tester) async {
      Map<String, dynamic>? opened;
      var linked = false;
      final backend = _Backend((method, path, body) async {
        if (method == 'GET' && path.contains('/learning-marks?')) return [];
        if (method == 'POST' && path.endsWith('/learning-anchor')) {
          return {'kind': 'resource', 'version': 1};
        }
        if (method == 'POST' && path.endsWith('/learning-marks')) {
          linked = true;
          expect(body!['targets'], [
            {'kind': 'file_note', 'id': 'a' * 32},
          ]);
          return {'id': 'mark', 'targets': body['targets'], 'removed_at': null};
        }
        if (method == 'POST') return note();
        if (path.endsWith('/document')) {
          return {'type': 'unsupported', 'sha256': 'a' * 64};
        }
        return {...note(), 'name': '教材.pdf', 'parent_id': 'course'};
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ResourcePage(
              backend: backend,
              workspaceId: 'default',
              tab: WorkbenchTab(
                id: 'doc',
                kind: 'resource',
                resourceItemId: 'b' * 32,
                viewKind: 'document',
              ),
              onChanged: () {},
              onOpenNote: (node) => opened = node,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('记笔记'));
      await tester.pumpAndSettle();
      expect(find.textContaining('会关联这份资料'), findsOneWidget);
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(opened!['resource_item_id'], 'a' * 32);
      expect(linked, true);
    },
  );
  testWidgets(
    'source association retry does not create a second note or change request',
    (tester) async {
      var notesCreated = 0;
      final associations = <Map<String, dynamic>>[];
      Map<String, dynamic>? opened;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'GET' && path.contains('/learning-marks?')) return [];
          if (path.endsWith('/markdown-notes')) {
            notesCreated++;
            return note();
          }
          if (path.endsWith('/learning-anchor')) {
            return {'version': 1, 'kind': 'resource'};
          }
          if (path.endsWith('/learning-marks')) {
            associations.add(Map.from(body!));
            if (associations.length == 1) throw StateError('response lost');
            return {
              'id': 'source-mark',
              'targets': body['targets'],
              'removed_at': null,
            };
          }
          fail('unexpected $method $path');
        }),
        (value) => opened = value,
        source: 'source',
      );
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(opened, isNull);
      expect(find.textContaining('笔记已保存，来源关联未确认'), findsOneWidget);
      await tester.tap(find.text('重试保存来源关联'));
      await tester.pumpAndSettle();
      expect(notesCreated, 1);
      expect(associations[0], associations[1]);
      expect(opened!['resource_item_id'], 'a' * 32);
    },
  );
  testWidgets(
    'removed source receipt is not reported as a confirmed association',
    (tester) async {
      var opened = false;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'GET' && path.contains('/learning-marks?')) return [];
          if (path.endsWith('/markdown-notes')) return note();
          if (path.endsWith('/learning-anchor')) {
            return {'version': 1, 'kind': 'resource'};
          }
          return {'id': 'removed', 'removed_at': '2026-11-04', 'targets': []};
        }),
        (_) => opened = true,
        source: 'source',
      );
      await tester.tap(find.text('创建并编辑'));
      await tester.pumpAndSettle();
      expect(opened, false);
      expect(find.textContaining('关联已被移除或修改'), findsOneWidget);
    },
  );
  testWidgets(
    'existing source relationship is reused without another bookmark',
    (tester) async {
      var opened = false;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method != 'GET') {
            fail('unexpected duplicate source operation $method $path');
          }
          if (path.contains('/markdown-notes?')) return [note()];
          if (path.endsWith('/document')) {
            return {'type': 'markdown', 'working_copy': true};
          }
          if (path.contains('/learning-marks?')) {
            expect(
              path,
              contains('resource_item_id=source&note_resource_item_id='),
            );
            return [
              {'id': 'already-related'},
            ];
          }
          return note();
        }),
        (_) => opened = true,
        source: 'source',
      );
      await tester.tap(find.text('选择已有Markdown笔记'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ListTile, '新笔记.md'));
      await tester.pumpAndSettle();
      expect(opened, true);
    },
  );
}
