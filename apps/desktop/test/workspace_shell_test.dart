import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/workspace_shell.dart';

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

Map<String, dynamic> _state(String active) => {
  'workspaces': [
    {'id': 'default', 'name': '默认', 'archived': false},
    {'id': 'other', 'name': '数学', 'archived': false},
  ],
  'archived_workspaces': [],
  'active_workspace_id': active,
};

Future<void> _show(WidgetTester tester, Backend backend) async {
  tester.view.physicalSize = const Size(1400, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: WorkspaceShell(backend: backend, playerHtml: ''),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'resource answer draft closes into history without submitting or writing Markdown',
    (tester) async {
      final draft = jsonEncode({'version_id': 'v', 'text': '未提交过程'});
      final layouts = <Map<String, dynamic>>[];
      var writes = 0;
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout')) {
          if (method == 'PUT') {
            layouts.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
            return body;
          }
          return {
            'version': 2,
            'tabs': [
              {
                'id': 'file',
                'kind': 'resource',
                'resource_item_id': 'a' * 32,
                'view_kind': 'document',
                'resource_name': '题目.md',
                'question_draft': draft,
                'document_state': {'version': 1, 'mode': 'read'},
              },
            ],
            'closed_tabs': [],
            'active_tab_id': 'file',
          };
        }
        if (method != 'GET') {
          writes++;
          fail('Closing must not submit or edit a file');
        }
        if (path.endsWith('/document')) {
          return {
            'type': 'markdown',
            'sha256': 'b' * 64,
            'working_copy': true,
            'text': '# 文件',
          };
        }
        if (path.endsWith('/nodes/${'a' * 32}')) {
          return {'kind': 'resource', 'status': 'ready', 'name': '题目.md'};
        }
        if (path.contains('/nodes?')) return [];
        fail('Unexpected $path');
      });
      await _show(tester, backend);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyW);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(find.text('保存草稿并关闭'), findsOneWidget);
      await tester.tap(find.text('保存草稿并关闭'));
      await tester.pumpAndSettle();
      await tester
          .state<WorkspaceShellState>(find.byType(WorkspaceShell))
          .flush();
      expect(layouts.last['tabs'], isEmpty);
      expect(layouts.last['closed_tabs'][0]['question_draft'], draft);
      expect(writes, 0);
    },
  );

  testWidgets(
    'persisted file draft still confirms close, conflict retains it, save writes actual file',
    (tester) async {
      var failSave = true, fileSaves = 0;
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout')) {
          return body ??
              {
                'version': 2,
                'tabs': [
                  {
                    'id': 'file',
                    'kind': 'resource',
                    'resource_item_id': 'a' * 32,
                    'view_kind': 'document',
                    'resource_name': '文件.md',
                    'draft': '已持久化但未写文件的草稿',
                    'draft_base_sha256': 'b' * 64,
                    'document_state': {'version': 1, 'mode': 'edit'},
                  },
                ],
                'closed_tabs': [],
                'active_tab_id': 'file',
              };
        }
        if (path.endsWith('/document')) {
          if (method == 'PUT') {
            fileSaves++;
            expect(body, {'expected_sha256': 'b' * 64, 'text': '已持久化但未写文件的草稿'});
            if (failSave) throw StateError('409 文件冲突');
            return {'sha256': 'c' * 64};
          }
          return {
            'type': 'markdown',
            'sha256': 'b' * 64,
            'working_copy': true,
            'text': '旧文件',
          };
        }
        if (path.endsWith('/nodes/${'a' * 32}')) {
          return {'kind': 'resource', 'status': 'ready', 'name': '文件.md'};
        }
        if (path.contains('/nodes?')) return [];
        throw StateError('Unexpected $method $path');
      });
      await _show(tester, backend);
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      await state.flush();
      await tester.tap(find.byKey(const ValueKey('markdown-editor')));
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyW);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(find.text('保存文件并关闭'), findsOneWidget);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyT);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(
        state.layouts['default']!.tabs,
        hasLength(1),
        reason: 'dialog must isolate shortcuts',
      );
      await tester.tap(find.text('保存文件并关闭'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.tabs.single.draft, '已持久化但未写文件的草稿');
      expect(state.layouts['default']!.tabs.single.draftBaseSha256, 'b' * 64);
      failSave = false;
      await tester.tap(find.byKey(const ValueKey('close-tab-file')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存文件并关闭'));
      await tester.pumpAndSettle();
      expect(fileSaves, 2);
      expect(state.layouts['default']!.tabs, isEmpty);
      expect(state.layouts['default']!.closed.single.draftBaseSha256, isNull);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'restored saved draft can close before debounce without a false dirty prompt',
    (tester) async {
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout')) {
          return body ??
              {
                'version': 1,
                'tabs': [],
                'active_tab_id': null,
                'closed_tabs': [
                  {'id': 'saved', 'kind': 'question', 'draft': '原有持久化草稿'},
                ],
              };
        }
        if (path.endsWith('/questions/demo')) {
          return {'id': 'demo', 'subject': '演示', 'stem': [], 'options': []};
        }
        throw StateError('Unexpected $method $path');
      });
      await _show(tester, backend);
      await tester.tap(find.byTooltip('重新打开关闭的标签页'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 170));
      await tester.tap(find.byKey(const ValueKey('close-tab-saved')));
      await tester.pump();
      expect(find.byType(AlertDialog), findsNothing);
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      expect(state.layouts['default']!.tabs, isEmpty);
      expect(state.layouts['default']!.closed.single.draft, '原有持久化草稿');
      await tester.pumpAndSettle();
    },
  );

  testWidgets(
    'dirty close cancels, survives save failure, discards and reopens saved draft',
    (tester) async {
      var failSave = true;
      var questionReads = 0;
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout') && method == 'GET') {
          return {
            'version': 1,
            'tabs': [
              {'id': 'q', 'kind': 'question', 'draft': '已保存草稿'},
              {'id': 'other-q', 'kind': 'question', 'draft': ''},
            ],
            'closed_tabs': [],
            'active_tab_id': 'q',
          };
        }
        if (path.endsWith('/layout') && method == 'PUT') {
          if (failSave) throw StateError('离线写入失败');
          return body;
        }
        if (path.endsWith('/questions/demo')) {
          questionReads++;
          return {'id': 'demo', 'subject': '演示', 'stem': [], 'options': []};
        }
        throw StateError('Unexpected $method $path');
      });
      await _show(tester, backend);
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final originalPage = tester.state(
        find.byWidgetPredicate(
          (w) => w is TextField && w.key != const ValueKey('resource-search'),
        ),
      );
      await tester.enterText(
        find.byWidgetPredicate(
          (w) => w is TextField && w.key != const ValueKey('resource-search'),
        ),
        '未保存的新草稿',
      );
      await tester.tap(find.byKey(const ValueKey('close-tab-q')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消关闭'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.tabs, hasLength(2));
      expect(
        tester
            .widget<TextField>(
              find.byWidgetPredicate(
                (w) =>
                    w is TextField &&
                    w.key != const ValueKey('resource-search'),
              ),
            )
            .controller!
            .text,
        '未保存的新草稿',
      );
      await tester.tap(find.byKey(const ValueKey('close-tab-q')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存草稿并关闭'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.tabs, hasLength(2));
      expect(state.saveError, contains('离线写入失败'));
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.digit9);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.activeId, 'other-q');
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.digit1);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.activeId, 'q');
      expect(
        tester.state(
          find.byWidgetPredicate(
            (w) => w is TextField && w.key != const ValueKey('resource-search'),
          ),
        ),
        same(originalPage),
      );
      expect(questionReads, 2);
      await tester.tap(find.byKey(const ValueKey('close-tab-q')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('放弃更改'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.tabs.single.id, 'other-q');
      expect(state.layouts['default']!.closed.last.draft, '已保存草稿');
      failSave = false;
      await tester.tap(find.byTooltip('重新打开关闭的标签页'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextField>(
              find.byWidgetPredicate(
                (w) =>
                    w is TextField &&
                    w.key != const ValueKey('resource-search'),
              ),
            )
            .controller!
            .text,
        '已保存草稿',
      );
      await tester.enterText(
        find.byWidgetPredicate(
          (w) => w is TextField && w.key != const ValueKey('resource-search'),
        ),
        '最终保存',
      );
      await tester.tap(find.byKey(const ValueKey('close-tab-q')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存草稿并关闭'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.closed.last.draft, '最终保存');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'offline page reports error while new, cycle, positional and close shortcuts work',
    (tester) async {
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout')) {
          return body ??
              {
                'version': 1,
                'tabs': [
                  {'id': 'q', 'kind': 'question'},
                ],
                'closed_tabs': [],
                'active_tab_id': 'q',
              };
        }
        throw StateError('后端离线');
      });
      await _show(tester, backend);
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      expect(state.layouts['default']!.tabs.single.error, contains('后端离线'));
      Future<void> shortcut(
        LogicalKeyboardKey key, {
        bool shift = false,
      }) async {
        await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
        if (shift) await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
        await tester.sendKeyEvent(key);
        if (shift) await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
        await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
        await tester.pumpAndSettle();
      }

      await shortcut(LogicalKeyboardKey.keyT);
      expect(state.layouts['default']!.tabs.last.kind, 'welcome');
      final second = state.layouts['default']!.activeId;
      await shortcut(LogicalKeyboardKey.tab);
      expect(state.layouts['default']!.activeId, 'q');
      await shortcut(LogicalKeyboardKey.tab, shift: true);
      expect(state.layouts['default']!.activeId, second);
      await shortcut(LogicalKeyboardKey.keyW);
      expect(state.layouts['default']!.activeId, 'q');
      await shortcut(LogicalKeyboardKey.keyT, shift: true);
      expect(state.layouts['default']!.activeId, second);
      await tester.tap(find.text('学习计划'));
      await tester.pumpAndSettle();
      expect(
        state.layouts['default']!.tabs,
        hasLength(3),
        reason: 'sidebar activates singleton',
      );
      await tester.tap(find.text('学习计划'));
      await tester.pumpAndSettle();
      expect(state.layouts['default']!.tabs, hasLength(3));
      await shortcut(LogicalKeyboardKey.keyW);
      await shortcut(LogicalKeyboardKey.keyW);
      await shortcut(LogicalKeyboardKey.keyW);
      expect(state.layouts['default']!.tabs, isEmpty);
      expect(find.textContaining('尚未打开页面'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('workbench layout fits simulated 100, 200 and 300 percent DPI', (
    tester,
  ) async {
    final backend = _Backend((method, path, body) async {
      if (path == '/api/workbench') return _state('default');
      if (path.endsWith('/layout')) {
        return {
          'version': 1,
          'tabs': [],
          'closed_tabs': [],
          'active_tab_id': null,
        };
      }
      throw StateError('Unexpected $method $path');
    });
    await _show(tester, backend);
    for (final ratio in [1.0, 2.0, 3.0]) {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = ratio;
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull, reason: 'DPI $ratio');
    }
  });

  testWidgets(
    'archiving active workspace keeps a valid page while reload is pending',
    (tester) async {
      var active = 'other';
      var removing = false;
      final reload = Completer<dynamic>();
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') {
          return removing ? await reload.future : _state(active);
        }
        if (path.endsWith('/layout')) {
          return {
            'version': 1,
            'tabs': [],
            'closed_tabs': [],
            'active_tab_id': null,
          };
        }
        if (method == 'DELETE') {
          removing = true;
          return {'archived': true};
        }
        throw StateError('Unexpected $method $path');
      });
      await _show(tester, backend);
      await tester.tap(
        find.descendant(
          of: find.byKey(const ValueKey('workspace-other')),
          matching: find.byType(PopupMenuButton<String>),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('移除并保留数据'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认移除并保留数据'));
      await tester.pump(const Duration(milliseconds: 400));
      expect(tester.takeException(), isNull);
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      expect(state.activeSpace, 'other');
      expect(
        state.layouts.containsKey('other'),
        true,
        reason:
            'keys=${state.layouts.keys}, loadError=${state.error}, removing=$removing',
      );
      active = 'default';
      final refreshed = _state(active);
      refreshed['workspaces'] = [(refreshed['workspaces'] as List).first];
      refreshed['archived_workspaces'] = [
        {'id': 'other', 'name': '数学', 'archived': true},
      ];
      reload.complete(refreshed);
      await tester.pumpAndSettle();
      expect(state.activeSpace, 'default');
      expect(state.layouts.containsKey('other'), false);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'editing while save is in flight persists the newest draft last',
    (tester) async {
      final firstWrite = Completer<dynamic>();
      final drafts = <String>[];
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workbench') return _state('default');
        if (path.endsWith('/layout') && method == 'GET') {
          return {
            'version': 1,
            'tabs': [
              {'id': 'q', 'kind': 'question', 'draft': ''},
            ],
            'closed_tabs': [],
            'active_tab_id': 'q',
          };
        }
        if (path.endsWith('/questions/demo')) {
          return {
            'id': 'demo-integral',
            'subject': '演示',
            'stem': [],
            'options': [],
          };
        }
        if (method == 'PUT' && path.endsWith('/layout')) {
          final snapshot = jsonDecode(jsonEncode(body)) as Map<String, dynamic>;
          drafts.add(snapshot['tabs'][0]['draft'] as String);
          return drafts.length == 1 ? firstWrite.future : snapshot;
        }
        throw StateError('Unexpected $method $path');
      });
      await _show(tester, backend);
      await tester.enterText(
        find.byWidgetPredicate(
          (w) => w is TextField && w.key != const ValueKey('resource-search'),
        ),
        '旧草稿',
      );
      await tester.pump(const Duration(milliseconds: 400));
      expect(drafts, ['旧草稿']);
      await tester.enterText(
        find.byWidgetPredicate(
          (w) => w is TextField && w.key != const ValueKey('resource-search'),
        ),
        '最新中文草稿',
      );
      final state = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final saved = state.flush();
      firstWrite.complete({});
      await tester.pumpAndSettle();
      await saved;
      expect(drafts, ['旧草稿', '最新中文草稿']);
      expect(state.dirty, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );
}
