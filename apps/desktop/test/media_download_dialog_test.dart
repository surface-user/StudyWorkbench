import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/media_download_dialog.dart';

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

Future<void> show(WidgetTester tester, Backend backend) async {
  tester.view.physicalSize = const Size(1400, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: MediaDownloadDialog(backend: backend, workspaceId: 'default'),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Map<String, dynamic> historyRow(int i, {String status = 'paused'}) => {
  'id': i.toRadixString(16).padLeft(32, '0'),
  'name': '历史$i.webm',
  'source_host': 'media.example.com',
  'source_url': 'https://media.example.com/a?signature=private-fixture',
  'status': status,
  'progress': {'received': i},
  'can_resume': false,
  'result': {'resource_item_id': 'node'},
  'error': null,
};

Future<void> press(WidgetTester tester, String text) async {
  await Scrollable.ensureVisible(
    tester.element(find.text(text)),
    alignment: .5,
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text(text));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'history reaches beyond 100, retries a failed page and refreshes its boundary',
    (tester) async {
      final requests = <Uri>[];
      var failSecond = true;
      var inserted = false;
      final backend = _Backend((method, path, body) async {
        final uri = Uri.parse(path);
        requests.add(uri);
        final query = uri.queryParameters;
        expect(query['history'], 'true');
        expect(query['limit'], '51');
        final offset = int.parse(query['offset']!);
        if (offset == 50 && failSecond) throw Exception('offline');
        final all = [
          if (inserted && !query.containsKey('newest_id')) historyRow(999),
          ...List.generate(123, historyRow),
        ];
        return all.skip(offset).take(51).toList();
      });
      await show(tester, backend);
      expect(find.text('第 1 页 · 每页 50 条'), findsOneWidget);
      expect(find.textContaining('signature='), findsNothing);
      await press(tester, '下一页');
      expect(find.text('第 1 页 · 每页 50 条'), findsOneWidget);
      expect(find.textContaining('已显示记录保留'), findsOneWidget);
      failSecond = false;
      await press(tester, '下一页');
      expect(find.text('第 2 页 · 每页 50 条'), findsOneWidget);
      expect(requests.last.queryParameters['newest_id'], historyRow(0)['id']);
      inserted = true;
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(requests.last.queryParameters['offset'], '50');
      await press(tester, '下一页');
      expect(find.text('第 3 页 · 每页 50 条'), findsOneWidget);
      expect(find.text('历史100.webm · 已暂停'), findsOneWidget);
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '下一页'))
            .onPressed,
        isNull,
      );
      await press(tester, '上一页');
      expect(find.text('第 2 页 · 每页 50 条'), findsOneWidget);
      await press(tester, '刷新列表');
      expect(find.text('第 1 页 · 每页 50 条'), findsOneWidget);
      expect(requests.last.queryParameters.containsKey('newest_id'), false);
      expect(find.text('历史999.webm · 已暂停'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await show(tester, backend);
      expect(requests.last.queryParameters.containsKey('newest_id'), false);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'late polling cannot overwrite an action or update a closed dialog',
    (tester) async {
      final stale = Completer<dynamic>();
      final afterClose = Completer<dynamic>();
      var gets = 0;
      var status = 'running';
      final backend = _Backend((method, path, body) async {
        if (method == 'POST') {
          status = 'paused';
          return {};
        }
        gets++;
        if (gets == 2) return stale.future;
        if (gets == 4) return afterClose.future;
        return [historyRow(0, status: status)];
      });
      await show(tester, backend);
      await tester.pump(const Duration(seconds: 2));
      await tester.pump();
      expect(find.text('正在加载…'), findsOneWidget);
      await press(tester, '暂停');
      expect(find.text('历史0.webm · 已暂停'), findsOneWidget);
      stale.complete([historyRow(0, status: 'running')]);
      await tester.pumpAndSettle();
      expect(find.text('历史0.webm · 已暂停'), findsOneWidget);
      await tester.pump(const Duration(seconds: 2));
      await tester.pump();
      await tester.pumpWidget(const SizedBox());
      afterClose.complete([historyRow(0, status: 'ready')]);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'page navigation is disabled until the requested page completes',
    (tester) async {
      final pending = Completer<dynamic>();
      var requests = 0;
      await show(
        tester,
        _Backend((method, path, body) async {
          requests++;
          if (requests > 1) return pending.future;
          return List.generate(51, historyRow);
        }),
      );
      await tester.tap(find.text('下一页'));
      await tester.pump();
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '下一页'))
            .onPressed,
        isNull,
      );
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '刷新列表'))
            .onPressed,
        isNull,
      );
      await tester.pump(const Duration(seconds: 2));
      expect(requests, 2);
      pending.complete([historyRow(50)]);
      await tester.pumpAndSettle();
      expect(find.text('第 2 页 · 每页 50 条'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets('small desktop viewport keeps the entire form scrollable', (
    tester,
  ) async {
    await show(tester, _Backend((method, path, body) async => []));
    tester.view.physicalSize = const Size(600, 450);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets(
    'rights required; uncertain creation retries the identical request without exposing URL in rows',
    (tester) async {
      final attempts = <Map<String, dynamic>>[];
      final backend = _Backend((method, path, body) async {
        if (method == 'GET') return [];
        attempts.add(Map.from(body!));
        if (attempts.length == 1) throw Exception('connection interrupted');
        return {};
      });
      await show(tester, backend);
      await tester.enterText(
        find.widgetWithText(TextField, 'HTTPS媒体直链'),
        'https://media.example.com/a.webm?signature=fixture',
      );
      await tester.enterText(
        find.widgetWithText(TextField, '文件名（含 .mp4 / .webm / .m4a）'),
        '自编.webm',
      );
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '加入下载队列'))
            .onPressed,
        isNull,
      );
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.text('加入下载队列'));
      await tester.pumpAndSettle();
      expect(find.textContaining('操作未完成'), findsOneWidget);
      await tester.tap(find.text('加入下载队列'));
      await tester.pumpAndSettle();
      expect(attempts.length, 2);
      expect(attempts[0]['request_id'], attempts[1]['request_id']);
      expect(attempts[1]['rights_confirmed'], true);
      expect(attempts[1].containsKey('path'), false);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'pause, resume failure, retained restart and stale source feedback',
    (tester) async {
      final commands = <Map<String, dynamic>>[];
      var row = <String, dynamic>{
        'id': 'job',
        'name': '自编.webm',
        'source_host': 'media.example.com',
        'status': 'running',
        'progress': {'received': 32, 'total': 100},
        'can_resume': true,
        'result': {'resource_item_id': 'node'},
        'error': null,
      };
      final backend = _Backend((method, path, body) async {
        if (method == 'GET') {
          if (path.endsWith('/nodes/node')) {
            return {'removed_at': 'date', 'kind': 'media'};
          }
          return [row];
        }
        commands.add({'path': path, ...?body});
        if (path.endsWith('/pause')) row = {...row, 'status': 'paused'};
        if (body?['mode'] == 'resume') {
          throw Exception('partial content changed');
        }
        if (body?['mode'] == 'restart') row = {...row, 'status': 'ready'};
        return row;
      });
      await show(tester, backend);
      await tester.tap(find.text('暂停'));
      await tester.pumpAndSettle();
      expect(find.text('断点重试'), findsOneWidget);
      await tester.tap(find.text('断点重试'));
      await tester.pumpAndSettle();
      expect(find.textContaining('partial content changed'), findsOneWidget);
      expect(find.text('保留旧部分，重新开始'), findsOneWidget);
      await tester.tap(find.text('保留旧部分，重新开始'));
      await tester.pumpAndSettle();
      expect(commands.last['mode'], 'restart');
      await tester.tap(find.text('打开媒体'));
      await tester.pumpAndSettle();
      expect(find.textContaining('来源已从资源树移除'), findsOneWidget);
      expect(find.text('下载媒体'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    },
  );
}
