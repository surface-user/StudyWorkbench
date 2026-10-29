import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_page.dart';
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

WorkbenchTab tab() => WorkbenchTab(
  id: 'document',
  kind: 'resource',
  resourceItemId: 'a' * 32,
  viewKind: 'document',
  resourceName: '讲义.md',
);

Future<void> show(
  WidgetTester tester,
  Backend backend,
  WorkbenchTab tab,
) async {
  tester.view.physicalSize = const Size(1300, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: StatefulBuilder(
          builder: (context, update) => DocumentPage(
            backend: backend,
            workspaceId: 'default',
            tab: tab,
            onChanged: () => update(() {}),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'Office preview is explicit, polls, paginates and restores state',
    (tester) async {
      final current = tab();
      final requests = <String>[];
      var posted = false;
      final backend = _Backend((method, path, body) async {
        requests.add('$method $path');
        if (path.endsWith('/document')) {
          return {
            'type': 'office',
            'sha256': 'a' * 64,
            'source_sha256': 'a' * 64,
            'preview_capability': {'available': true},
            'preview': null,
          };
        }
        if (method == 'POST') {
          expect(body, {'expected_source_sha256': 'a' * 64});
          posted = true;
          return {'id': 'job', 'status': 'queued'};
        }
        if (path.endsWith('/previews/job')) {
          return {'id': 'job', 'status': 'ready', 'page_count': 2};
        }
        if (path.contains('/previews/job/page?')) {
          return {
            'image_base64': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
          };
        }
        fail('Unexpected request $path');
      });
      await show(tester, backend, current);
      expect(posted, false);
      await tester.tap(find.text('生成分页预览'));
      await tester.pumpAndSettle();
      expect(posted, true);
      await tester.pump(const Duration(milliseconds: 900));
      await tester.pumpAndSettle();
      expect(find.text('第1页 / 2页'), findsOneWidget);
      await tester.tap(find.byTooltip('下一页'));
      await tester.pumpAndSettle();
      expect(requests.last, contains('/previews/job/page?page=2'));
      final restored = WorkbenchTab.fromJson(current.toJson());
      expect(restored.documentState['representation'], 'paginated');
      expect(restored.documentState['page'], 2);
      expect(jsonEncode(current.toJson()), isNot(contains('image_base64')));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Office cancellation and retry retain source; dispose stops polling',
    (tester) async {
      var polls = 0, cancels = 0;
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/document')) {
          return {
            'type': 'word',
            'sha256': 'a' * 64,
            'source_sha256': 'a' * 64,
            'blocks': <dynamic>[],
            'assets': <dynamic>[],
            'warnings': <dynamic>[],
            'preview_capability': {'available': true},
            'preview': {'id': 'job', 'status': 'running'},
          };
        }
        if (path.endsWith('/cancel')) {
          cancels++;
          return {'id': 'job', 'status': 'running', 'cancel_requested': true};
        }
        polls++;
        return {'id': 'job', 'status': 'cancelled', 'error': '转换已停止；原件保留'};
      });
      await show(tester, backend, tab());
      await tester.tap(find.text('取消转换'));
      await tester.pumpAndSettle();
      expect(cancels, 1);
      await tester.pump(const Duration(milliseconds: 900));
      await tester.pumpAndSettle();
      expect(find.text('重试生成分页预览'), findsOneWidget);
      expect(polls, 1);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 3));
      expect(polls, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Closing a running Office preview releases its polling timer', (
    tester,
  ) async {
    var polls = 0;
    final backend = _Backend((method, path, body) async {
      if (!path.endsWith('/document')) polls++;
      return {
        'type': 'office',
        'sha256': 'a' * 64,
        'source_sha256': 'a' * 64,
        'preview_capability': {'available': true},
        'preview': {'id': 'job', 'status': 'running'},
      };
    });
    await show(tester, backend, tab());
    expect(find.text('取消转换'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 3));
    expect(polls, 0);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Missing Office component gives a disabled explicit action', (
    tester,
  ) async {
    final backend = _Backend(
      (method, path, body) async => {
        'type': 'office',
        'sha256': 'a' * 64,
        'source_sha256': 'a' * 64,
        'message': '原件保留',
        'preview_capability': {'available': false, 'reason': '离线组件缺失'},
      },
    );
    await show(tester, backend, tab());
    expect(find.text('离线组件缺失'), findsOneWidget);
    final button = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, '生成分页预览'),
    );
    expect(button.onPressed, isNull);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Markdown edit is explicit, preview blocks remote images, failed saves retain draft',
    (tester) async {
      final current = tab();
      var copies = 0, writes = 0, blocked = true;
      const initial = r'''# 标题
**正文** 与公式 $x^2$
![远程图片](https://example.com/private.png)''';
      final backend = _Backend((method, path, body) async {
        if (method == 'GET' && path.endsWith('/document')) {
          return {
            'type': 'markdown',
            'sha256': 'a' * 64,
            'text': initial,
            'working_copy': false,
          };
        }
        if (method == 'POST' && path.endsWith('/working-copy')) {
          copies++;
          expect(body!['expected_sha256'], 'a' * 64);
          return {'sha256': 'a' * 64, 'working_copy': true};
        }
        if (method == 'PUT' && path.endsWith('/document')) {
          writes++;
          expect(body, {'expected_sha256': 'a' * 64, 'text': '# 编辑草稿'});
          if (blocked) throw StateError('409 conflict');
          return {'sha256': 'b' * 64};
        }
        fail('Unexpected request $method $path');
      });
      await show(tester, backend, current);
      expect(find.textContaining('已阻止外部或绝对图片'), findsOneWidget);
      expect(find.byKey(const ValueKey('markdown-editor')), findsNothing);
      await tester.tap(find.text('创建工作副本并编辑'));
      await tester.pumpAndSettle();
      expect(copies, 1);
      await tester.enterText(
        find.byKey(const ValueKey('markdown-editor')),
        '# 编辑草稿',
      );
      await tester.pumpAndSettle();
      expect(current.draftBaseSha256, 'a' * 64);
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(current.draft, '# 编辑草稿');
      expect(find.textContaining('409 conflict'), findsOneWidget);
      await tester.tap(find.text('阅读预览'));
      await tester.pumpAndSettle();
      expect(find.text('编辑草稿'), findsOneWidget);
      blocked = false;
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(writes, 2);
      expect(current.draftBaseSha256, isNull);
      expect(current.draft, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'restored unsaved empty file survives refresh and a changed source',
    (tester) async {
      final current = tab()..draftBaseSha256 = 'a' * 64;
      current.documentState['mode'] = 'edit';
      final backend = _Backend(
        (method, path, body) async => {
          'type': 'markdown',
          'sha256': 'b' * 64,
          'text': '外部新内容',
          'working_copy': true,
        },
      );
      await show(tester, backend, current);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '',
      );
      expect(current.draftBaseSha256, 'a' * 64);
      expect(find.textContaining('恢复的草稿保留'), findsOneWidget);
      await tester.tap(find.text('刷新文件'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '',
      );
      expect(current.toJson()['draft_base_sha256'], 'a' * 64);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'PDF page selection and zoom state persist without storing page bytes',
    (tester) async {
      final current = tab();
      final requests = <String>[];
      final backend = _Backend((method, path, body) async {
        requests.add(path);
        if (path.endsWith('/document')) {
          return {'type': 'pdf', 'sha256': 'a' * 64, 'page_count': 21};
        }
        return {
          'image_base64': base64Encode(
            base64Decode(
              'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            ),
          ),
        };
      });
      await show(tester, backend, current);
      await tester.tap(find.byTooltip('下一页'));
      await tester.pumpAndSettle();
      expect(current.documentState['page'], 2);
      expect(requests.last, endsWith('/document-page?page=2'));
      expect(jsonEncode(current.toJson()).contains('image_base64'), false);
      final restored = WorkbenchTab.fromJson(current.toJson());
      expect(restored.documentState['page'], 2);
      expect(tester.takeException(), isNull);
    },
  );
}
