import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_page.dart';
import 'package:study_workbench/learning_marks_dialog.dart';
import 'package:study_workbench/media_page.dart';
import 'package:study_workbench/url_policy.dart';
import 'package:study_workbench/workspace_layout.dart';

class _Backend implements Backend {
  _Backend(this.handle);
  final Future<dynamic> Function(String, String, Map<String, dynamic>?) handle;
  @override
  int get port => 12345;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) => handle(method, path, body);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> point({String kind = 'text_line'}) => {
  'version': 1,
  'workspace_id': 'default',
  'resource_item_id': 'node',
  'content_sha256': 'a' * 64,
  'kind': kind,
  if (kind == 'text_line') 'line': 2,
  if (kind == 'text_line') 'line_sha256': 'b' * 64,
};
Map<String, dynamic> record({String status = 'valid', int revision = 1}) => {
  'id': 'mark',
  'resource_item_id': 'node',
  'title': '已保存书签',
  'note': '旧备注',
  'anchor': point(),
  'revision': revision,
  'removed_at': null,
  'targets': [],
  'target_details': [],
  'location': {
    'status': status,
    'message': status == 'valid' ? '位置有效' : '内容版本已变化',
    'anchor': point(),
    'resource': {
      'resource_item_id': 'node',
      'name': '资料.txt',
      'kind': 'resource',
      'status': 'ready',
    },
  },
};

Future<void> show(
  WidgetTester tester,
  Backend backend, {
  String? node,
  CaptureLearningAnchor? capture,
  ValueChanged<Map<String, dynamic>>? opened,
}) async {
  tester.view.physicalSize = const Size(1400, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () async {
              final result = await showDialog<Map<String, dynamic>>(
                context: context,
                barrierDismissible: false,
                builder: (_) => LearningMarksDialog(
                  backend: backend,
                  workspaceId: 'default',
                  resourceItemId: node,
                  captureCurrent: capture,
                ),
              );
              if (result != null) opened?.call(result);
            },
            child: const Text('打开列表'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('打开列表'));
  await tester.pumpAndSettle();
}

void main() {
  for (final followResource in [false, true]) {
    testWidgets(
      'XLSX restores sheet index but resource links open first sheet: $followResource',
      (tester) async {
        tester.view.physicalSize = const Size(1400, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final tab = WorkbenchTab(
          id: 'sheet-tab',
          kind: 'resource',
          resourceItemId: 'node',
          viewKind: 'document',
          documentState: {'page': 2},
        );
        Map<String, dynamic>? captured;
        final backend = _Backend((method, path, body) async {
          if (path.endsWith('/document')) {
            return {
              'type': 'spreadsheet',
              'sha256': 'a' * 64,
              'position_kind': 'resource',
              'sheets': [
                {'name': '首表', 'state': 'visible', 'cells': []},
                {
                  'name': '次表',
                  'state': 'visible',
                  'cells': [
                    {
                      'address': 'A1',
                      'value': '次表原值',
                      'formula': false,
                      'cache_missing': false,
                    },
                  ],
                },
              ],
            };
          }
          if (path.endsWith('/learning-anchor')) {
            captured = body;
            return point(kind: 'resource');
          }
          return [];
        });
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: DocumentPage(
                backend: backend,
                workspaceId: 'default',
                tab: tab,
                jumpAnchor: followResource ? point(kind: 'resource') : null,
                onChanged: () {},
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        if (followResource) {
          expect(find.text('此表没有单元格值'), findsOneWidget);
        } else {
          expect(find.text('次表原值'), findsOneWidget);
        }
        await tester.tap(find.text('书签与备注'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('记录当前位置'));
        await tester.pumpAndSettle();
        expect(captured, {'kind': 'resource'});
        expect(
          (tab.toJson()['document_state'] as Map)['page'],
          followResource ? 1 : 2,
        );
      },
    );
  }
  testWidgets(
    'generic UTF-8 text stays literal and captures only resource position',
    (tester) async {
      tester.view.physicalSize = const Size(1400, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      const literal = '{"正文":"<script>不执行</script>","formula":"=1+1"}';
      Map<String, dynamic>? captured;
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/document')) {
          return {
            'type': 'text',
            'text': literal,
            'sha256': 'a' * 64,
            'position_kind': 'resource',
            'source_format': 'json',
            'working_copy': false,
          };
        }
        if (path.endsWith('/learning-anchor')) {
          captured = body;
          return point(kind: 'resource');
        }
        return [];
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DocumentPage(
              backend: backend,
              workspaceId: 'default',
              tab: WorkbenchTab(
                id: 'tab',
                kind: 'resource',
                resourceItemId: 'node',
                viewKind: 'document',
              ),
              onChanged: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(literal), findsOneWidget);
      expect(find.text('UTF-8只读原文 · 资料级书签'), findsOneWidget);
      expect(find.byKey(const ValueKey('markdown-editor')), findsNothing);
      await tester.tap(find.text('书签与备注'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('记录当前位置'));
      await tester.pumpAndSettle();
      expect(captured, {'kind': 'resource'});
      expect(find.text('整份资料'), findsOneWidget);
    },
  );
  test('player controls require same local media identity, capability and current URL', () {
    final url =
        'http://127.0.0.1:12345/media/library/${'a' * 32}/player?cap=local';
    expect(isCurrentLibraryPlayer(url, url), true);
    for (final other in [
      'https://example.com',
      url.replaceAll('cap=local', 'cap=other'),
      url.replaceAll('/player', '/content'),
      null,
    ]) {
      expect(isCurrentLibraryPlayer(url, other), false);
    }
    final external =
        'https://example.com/media/library/${'a' * 32}/player?cap=local';
    expect(isCurrentLibraryPlayer(external, external), false);
    expect(
      isCurrentLibraryPlayer(
        'http://127.0.0.1:12345/api/health?cap=local',
        'http://127.0.0.1:12345/api/health?cap=local',
      ),
      false,
    );
    expect(
      learningPosition({'version': 9, 'kind': 'text_line', 'line': 1}),
      contains('不支持'),
    );
  });

  testWidgets(
    'failed creation retries unchanged request; source jump resolves again',
    (tester) async {
      final requests = <Map<String, dynamic>>[];
      Map<String, dynamic>? opened;
      var created = false;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'POST' && path.endsWith('/learning-anchor')) {
            return point(kind: 'resource');
          }
          if (method == 'POST') {
            requests.add(Map.from(body!));
            if (requests.length == 1) throw StateError('response lost');
            created = true;
            return record();
          }
          if (path.contains('?offset=')) return created ? [record()] : [];
          return record();
        }),
        node: 'node',
        opened: (target) => opened = target,
      );
      await tester.tap(find.text('标记整份资料'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存书签'));
      await tester.pumpAndSettle();
      expect(find.textContaining('当前草稿保留'), findsOneWidget);
      await tester.tap(find.text('重试原创建请求'));
      await tester.pumpAndSettle();
      expect(requests[0], requests[1]);
      await tester.tap(find.text('返回来源位置'));
      await tester.pumpAndSettle();
      expect(opened!['resource_item_id'], 'node');
      expect(opened!['learning_anchor'], point());
    },
  );

  testWidgets(
    'changed source cannot jump and failed edits preserve user draft',
    (tester) async {
      Map<String, dynamic>? posted;
      var opened = false;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'PATCH') {
            posted = body;
            throw StateError('409');
          }
          return path.contains('?offset=')
              ? [record()]
              : record(status: 'content_changed');
        }),
        opened: (_) => opened = true,
      );
      await tester.tap(find.widgetWithText(ListTile, '已保存书签'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('返回来源位置'));
      await tester.pumpAndSettle();
      expect(opened, false);
      expect(find.textContaining('内容版本已变化'), findsWidgets);
      await tester.enterText(find.byType(TextField).last, '未保存的疑问');
      await tester.pump();
      await tester.tap(find.text('保存书签'));
      await tester.pumpAndSettle();
      expect(posted!['expected_revision'], 1);
      expect(find.text('未保存的疑问'), findsOneWidget);
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
      expect(find.text('继续编辑'), findsOneWidget);
      await tester.tap(find.text('继续编辑'));
      await tester.pumpAndSettle();
      expect(find.text('未保存的疑问'), findsOneWidget);
    },
  );

  testWidgets(
    'delete confirmation sends revision and removes only current row',
    (tester) async {
      var deleted = false;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'DELETE') {
            expect(body, {'expected_revision': 1});
            deleted = true;
            return record(revision: 2);
          }
          return path.contains('?offset=')
              ? (deleted ? [] : [record()])
              : record();
        }),
      );
      await tester.tap(find.widgetWithText(ListTile, '已保存书签'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('移除书签'));
      await tester.pumpAndSettle();
      expect(deleted, false);
      await tester.tap(find.text('确认移除'));
      await tester.pumpAndSettle();
      expect(deleted, true);
      expect(find.widgetWithText(ListTile, '已保存书签'), findsNothing);
    },
  );

  testWidgets(
    'reanchor uses current capture and expected revision explicitly',
    (tester) async {
      Map<String, dynamic>? edited;
      final next = {...point(), 'line': 3};
      await show(
        tester,
        _Backend((method, path, body) async {
          if (method == 'PATCH') {
            edited = body;
            return record(revision: 2);
          }
          return path.contains('?offset=')
              ? [record()]
              : record(status: 'content_changed');
        }),
        node: 'node',
        capture: () async => next,
      );
      await tester.tap(find.widgetWithText(ListTile, '已保存书签'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('重新关联当前阅读位置'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存书签'));
      await tester.pumpAndSettle();
      expect(edited!['anchor'], next);
      expect(edited!['expected_revision'], 1);
    },
  );

  testWidgets(
    'text anchor restores source line selection and stays out of layout JSON',
    (tester) async {
      final tab = WorkbenchTab(
        id: 'tab',
        kind: 'resource',
        resourceItemId: 'node',
        viewKind: 'document',
      );
      final backend = _Backend(
        (method, path, body) async => {
          'type': 'text',
          'text': '第一行\n目标中文行\n第三行',
          'sha256': 'a' * 64,
          'working_copy': false,
        },
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DocumentPage(
              backend: backend,
              workspaceId: 'default',
              tab: tab,
              jumpAnchor: point(),
              onChanged: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final field = tester.widget<TextField>(
        find.byKey(const ValueKey('source-line-view')),
      );
      expect(
        field.controller!.selection.textInside(field.controller!.text),
        '目标中文行',
      );
      expect(find.text('定位行：目标中文行'), findsOneWidget);
      final layout = WorkspaceLayout.fromJson({
        'version': 2,
        'tabs': [],
        'closed_tabs': [],
        'active_tab_id': null,
      });
      layout.openResource({
        'resource_item_id': 'node',
        'kind': 'resource',
        'name': '资料.txt',
        'learning_anchor': point(),
      });
      expect(layout.tabs.single.pendingAnchor, point());
      expect(layout.toJson().toString().contains('learning_anchor'), false);
    },
  );

  testWidgets(
    'version mismatch does not update expected save hash to unseen content',
    (tester) async {
      var reads = 0;
      final tab = WorkbenchTab(
        id: 'tab',
        kind: 'resource',
        resourceItemId: 'node',
        viewKind: 'document',
        documentState: {'mode': 'edit'},
      );
      final backend = _Backend((method, path, body) async {
        reads++;
        return {
          'type': 'markdown',
          'text': reads == 1 ? 'old text' : 'changed text',
          'sha256': (reads == 1 ? 'a' : 'c') * 64,
          'working_copy': true,
        };
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DocumentPage(
              backend: backend,
              workspaceId: 'default',
              tab: tab,
              jumpAnchor: point(),
              onChanged: () {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('旧位置未自动应用'), findsOneWidget);
      await tester.enterText(
        find.byKey(const ValueKey('markdown-editor')),
        'local edit',
      );
      expect(tab.draftBaseSha256, 'a' * 64);
    },
  );
  testWidgets('unready player cannot fabricate a zero-time bookmark', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var captures = 0;
    final id = 'a' * 32;
    final backend = _Backend((method, path, body) async {
      if (path.endsWith('/player')) {
        return {
          'url': 'http://127.0.0.1:12345/media/library/$id/player?cap=local',
        };
      }
      if (method == 'POST') {
        captures++;
        return point(kind: 'resource');
      }
      return [];
    });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MediaPage(
            backend: backend,
            workspaceId: 'default',
            profile: '.local/lw02-player-test-profile',
            mediaId: id,
            resourceItemId: 'node',
            sourceSha256: 'a' * 64,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('书签与备注'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('记录当前位置'));
    await tester.pumpAndSettle();
    expect(find.textContaining('等待本地媒体加载'), findsOneWidget);
    expect(captures, 0);
    await tester.tap(find.text('标记整份资料'));
    await tester.pumpAndSettle();
    expect(captures, 1);
    expect(find.text('整份资料'), findsOneWidget);
  });

  testWidgets(
    'note relationship failure keeps pending targets available for retry',
    (tester) async {
      var attempts = 0;
      await show(
        tester,
        _Backend((method, path, body) async {
          if (path.contains('/notes?')) {
            return [
              {'id': 'legacy', 'title': '旧课堂笔记'},
            ];
          }
          if (method == 'PUT') {
            attempts++;
            expect(body!['targets'], [
              {'kind': 'legacy_note', 'id': 'legacy'},
            ]);
            throw StateError('409');
          }
          return path.contains('?offset=') ? [record()] : record();
        }),
      );
      await tester.tap(find.widgetWithText(ListTile, '已保存书签'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('关联旧富内容笔记'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ListTile, '旧课堂笔记'));
      await tester.pumpAndSettle();
      expect(attempts, 1);
      expect(find.text('重试保存笔记关联'), findsOneWidget);
      await tester.tap(find.text('重试保存笔记关联'));
      await tester.pumpAndSettle();
      expect(attempts, 2);
    },
  );
  testWidgets(
    'navigation arriving during file save is applied once after save completes',
    (tester) async {
      final saving = Completer<Map<String, dynamic>>();
      var committed = false;
      Map<String, dynamic>? jump;
      late StateSetter rebuild;
      final tab = WorkbenchTab(
        id: 'tab',
        kind: 'resource',
        resourceItemId: 'node',
        viewKind: 'document',
        documentState: {'mode': 'edit'},
      );
      final backend = _Backend((method, path, body) async {
        if (method == 'PUT') {
          final result = await saving.future;
          committed = true;
          return result;
        }
        return {
          'type': 'markdown',
          'text': committed ? 'first\nsecond edited' : 'first\nsecond',
          'working_copy': true,
          'sha256': (committed ? 'c' : 'a') * 64,
        };
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, update) {
                rebuild = update;
                return DocumentPage(
                  backend: backend,
                  workspaceId: 'default',
                  tab: tab,
                  jumpAnchor: jump,
                  onChanged: () => update(() {}),
                );
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('markdown-editor')),
        'first\nsecond edited',
      );
      await tester.pump();
      await tester.tap(find.text('保存工作文件'));
      await tester.pump();
      rebuild(() => jump = {...point(), 'content_sha256': 'c' * 64});
      await tester.pump();
      saving.complete({'sha256': 'c' * 64});
      await tester.pumpAndSettle();
      expect(tab.draftBaseSha256, isNull);
      expect(find.text('定位行：second edited'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
