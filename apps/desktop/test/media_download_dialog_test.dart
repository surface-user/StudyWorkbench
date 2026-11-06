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

void main() {
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
