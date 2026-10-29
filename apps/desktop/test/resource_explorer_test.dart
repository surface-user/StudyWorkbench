import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/resource_explorer.dart';

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

Map<String, dynamic> node(
  String id,
  String name,
  String kind, {
  String? parent,
}) => {
  'resource_item_id': id,
  'parent_id': parent,
  'name': name,
  'kind': kind,
  'status': 'ready',
  'size': kind == 'resource' ? 12 : null,
};

Future<void> show(WidgetTester tester, Backend backend) async {
  tester.view.physicalSize = const Size(1000, 850);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ListView(
          children: [
            ResourceExplorer(backend: backend, workspaceId: 'default'),
          ],
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('refresh ignores a delayed old tree response', (tester) async {
    final pending = Completer<dynamic>();
    var calls = 0;
    final backend = _Backend((method, path, body) async {
      calls++;
      if (calls == 1) return pending.future;
      return [node('new', '新资源', 'resource')];
    });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ResourceExplorer(backend: backend, workspaceId: 'default'),
        ),
      ),
    );
    await tester.pump();
    await tester.tap(find.byTooltip('刷新资源树'));
    await tester.pumpAndSettle();
    pending.complete([node('old', '旧响应', 'resource')]);
    await tester.pumpAndSettle();
    expect(find.text('新资源'), findsOneWidget);
    expect(find.text('旧响应'), findsNothing);
  });
  testWidgets(
    'tree expands, preserves identity on rename/move and retains failed edit',
    (tester) async {
      final folder = node('folder', '资料', 'folder');
      var file = node('file', '讲义.md', 'resource', parent: 'folder');
      var fail = true;
      final calls = <Map<String, dynamic>>[];
      final backend = _Backend((method, path, body) async {
        if (method == 'PATCH') {
          calls.add(body!);
          if (fail) throw StateError('保存失败');
          file = {...file, ...body};
          return file;
        }
        if (path.endsWith('/nodes/file')) return file;
        if (path.contains('/nodes?')) {
          return path.contains('parent_id=folder') ? [file] : [folder];
        }
        throw StateError(path);
      });
      await show(tester, backend);
      expect(find.text('讲义.md'), findsNothing);
      await tester.tap(find.text('资料'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('讲义.md'));
      await tester.pumpAndSettle();
      expect(find.textContaining('资源编号：file'), findsOneWidget);
      await tester.enterText(find.byType(TextField), '改名.md');
      await tester.tap(find.text('移动到：当前文件夹'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('选择此位置'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('保存名称与位置'));
      await tester.pumpAndSettle();
      expect(find.textContaining('未保存：'), findsOneWidget);
      expect(find.text('改名.md'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('保存名称与位置'));
      await tester.pumpAndSettle();
      expect(calls.last, {'name': '改名.md', 'parent_id': null});
      expect(file['resource_item_id'], 'file');
      expect(find.byType(AlertDialog), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'unified picker starts managed folder copy and cancellation, shows failures',
    (tester) async {
      final calls = <String>[];
      var cancelled = false;
      final backend = _Backend((method, path, body) async {
        calls.add('$method $path');
        if (path.contains('/nodes?')) return [];
        if (path.endsWith('/cancel')) {
          cancelled = true;
          return {};
        }
        if (method == 'POST' && path.endsWith('/resource-add-jobs')) {
          expect(body, {'source_path': 'D:/fixtures/资料', 'parent_id': null});
          return {'id': 'copy'};
        }
        if (path.endsWith('/resource-add-jobs')) {
          return [
            {
              'id': 'copy',
              'status': cancelled ? 'cancelled' : 'running',
              'results': [
                {'name': '损坏.webm', 'status': 'failed', 'error': '容器头不匹配'},
              ],
            },
          ];
        }
        throw StateError(path);
      });
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel('study/desktop'), (
            call,
          ) async {
            expect(call.method, 'chooseResourceDirectory');
            return 'D:/fixtures/资料';
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(
              const MethodChannel('study/desktop'),
              null,
            ),
      );
      await show(tester, backend);
      await tester.tap(find.text('添加资源'));
      await tester.pumpAndSettle();
      expect(find.textContaining('视频下载尚未实现'), findsOneWidget);
      await tester.tap(find.text('复制导入文件夹'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('复制中 · 1 项'));
      await tester.tap(find.text('复制中 · 1 项'));
      await tester.pumpAndSettle();
      expect(find.textContaining('容器头不匹配'), findsOneWidget);
      await tester.ensureVisible(find.text('取消复制'));
      await tester.tap(find.text('取消复制'));
      await tester.pumpAndSettle();
      expect(
        calls,
        contains('POST /api/workspaces/default/resource-add-jobs/copy/cancel'),
      );
      expect(find.text('已取消 · 1 项'), findsOneWidget);
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('tree pagination, missing resources and failed read retry', (
    tester,
  ) async {
    var fail = true;
    final backend = _Backend((method, path, body) async {
      if (fail) throw StateError('离线');
      if (path.endsWith('/nodes/missing')) {
        return {...node('missing', '旧资料', 'resource'), 'status': 'missing'};
      }
      if (path.contains('offset=100')) return [node('last', '末项', 'resource')];
      return [
        for (var i = 0; i < 100; i++)
          node(i == 0 ? 'missing' : '$i', i == 0 ? '旧资料' : '文件$i', 'resource'),
      ];
    });
    await show(tester, backend);
    expect(find.textContaining('资源树读取失败'), findsOneWidget);
    fail = false;
    await tester.tap(find.byTooltip('刷新资源树'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('旧资料'));
    await tester.pumpAndSettle();
    expect(find.textContaining('文件缺失，关系已保留'), findsOneWidget);
    await tester.tap(find.text('关闭'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('加载更多资源'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('加载更多资源'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('末项'));
    expect(find.text('末项'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'adding a link failure keeps its draft, native selection cancellation adds nothing',
    (tester) async {
      var posts = 0;
      final backend = _Backend((method, path, body) async {
        if (method == 'POST') {
          posts++;
          throw StateError('地址无效');
        }
        return [];
      });
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            const MethodChannel('study/desktop'),
            (call) async => null,
          );
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(
              const MethodChannel('study/desktop'),
              null,
            ),
      );
      await show(tester, backend);
      await tester.tap(find.text('添加资源'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('添加文件 / 本地媒体'));
      await tester.pumpAndSettle();
      expect(posts, 0);
      await tester.enterText(find.byType(TextField).first, '网页资料');
      await tester.enterText(find.byType(TextField).last, 'http://invalid');
      await tester.tap(find.text('保存网页链接'));
      await tester.pumpAndSettle();
      expect(find.text('网页资料'), findsOneWidget);
      expect(find.text('http://invalid'), findsOneWidget);
      expect(find.textContaining('添加未完成'), findsOneWidget);
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
    },
  );
}
