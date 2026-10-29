import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/add_resources_dialog.dart';
import 'package:study_workbench/backend.dart';

class _Backend implements Backend {
  final submitted = <String>[];
  final inspections = <List<dynamic>>[];
  bool fail = true;
  bool runUntilCancelled = false, cancelled = false;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    if (path.endsWith('/resource-inspections')) {
      inspections.add(body!['source_paths'] as List);
      return [
        for (final source in body['source_paths'] as List)
          {
            'source_path': source,
            'name': (source as String).split('/').last,
            'kind': source.endsWith('.mp4') ? 'media' : 'file',
            'type': source.endsWith('.mp4') ? '视频' : 'Markdown 笔记',
            'size': 1024,
            'error': source.contains('denied') ? '文件不可读取（权限不足）' : null,
            'warning': source.endsWith('.xyz') ? '可保存原件，当前不支持独立预览' : null,
          },
      ];
    }
    if (path.endsWith('/resource-add-jobs')) {
      if (method == 'GET') return [];
      submitted.add(body!['source_path'] as String);
      return {'id': '${submitted.length}'};
    }
    if (path.endsWith('/cancel')) {
      cancelled = true;
      return {};
    }
    if (path.contains('/resource-add-jobs/')) {
      if (runUntilCancelled) {
        return {
          'status': cancelled ? 'cancelled' : 'running',
          'results': <dynamic>[],
          'error': cancelled ? '复制已停止；已完成部分保留' : null,
        };
      }
      final failed = submitted.last.endsWith('fail.md') && fail;
      return {
        'status': failed ? 'partial' : 'completed',
        'results': [
          {
            'name': submitted.last.split('/').last,
            'status': failed ? 'failed' : 'added',
            if (failed) 'error': '来源在复制时变化',
          },
        ],
      };
    }
    throw StateError('$method $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> _show(WidgetTester tester, _Backend backend) async {
  tester.view.physicalSize = const Size(1100, 950);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) =>
                  AddResourcesDialog(backend: backend, workspaceId: 'default'),
            ),
            child: const Text('open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

Future<void> native(WidgetTester tester, String method, dynamic args) async {
  await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
    'study/desktop',
    const StandardMethodCodec().encodeMethodCall(MethodCall(method, args)),
    (_) {},
  );
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('study/desktop'),
          (call) async => call.method == 'chooseResourceFiles'
              ? ['D:/note.md', 'D:/clip.mp4', 'D:/note.md']
              : null,
        );
  });
  tearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('study/desktop'), null),
  );

  testWidgets(
    'stopping an active copy cancels that job and does not submit remaining files',
    (tester) async {
      final backend = _Backend()..runUntilCancelled = true;
      await _show(tester, backend);
      await native(tester, 'resourceDrop', ['D:/note.md', 'D:/second.md']);
      await tester.tap(find.text('确认导入'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('停止导入'), findsOneWidget);
      await tester.tap(find.text('停止导入'));
      await tester.pumpAndSettle();
      expect(backend.cancelled, isTrue);
      expect(backend.submitted, ['D:/note.md']);
      expect(find.textContaining('复制已停止'), findsOneWidget);
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
    },
  );

  testWidgets(
    'single and mixed native drops share picker queue; duplicates, removal, clearing and cancellation never copy',
    (tester) async {
      final backend = _Backend();
      await _show(tester, backend);
      await native(tester, 'resourceDrag', true);
      expect(find.text('松开鼠标，添加文件'), findsOneWidget);
      await native(tester, 'resourceDrop', ['D:/note.md']);
      await native(tester, 'resourceDrag', false);
      expect(find.text('note.md'), findsOneWidget);
      await tester.tap(find.text('添加文件'));
      await tester.pumpAndSettle();
      expect(find.text('note.md'), findsOneWidget);
      expect(find.text('clip.mp4'), findsOneWidget);
      expect(find.textContaining('跳过 2'), findsOneWidget);
      await native(tester, 'resourceDrop', [
        'd:/NOTE.md',
        'D:/denied.txt',
        'D:/unknown.xyz',
      ]);
      expect(find.textContaining('权限不足'), findsOneWidget);
      expect(find.textContaining('不支持独立预览'), findsOneWidget);
      await tester.ensureVisible(find.byTooltip('移除 clip.mp4'));
      await tester.tap(find.byTooltip('移除 clip.mp4'));
      await tester.pumpAndSettle();
      expect(find.text('clip.mp4'), findsNothing);
      await tester.ensureVisible(find.text('清空列表'));
      await tester.tap(find.text('清空列表'));
      await tester.pumpAndSettle();
      expect(find.text('待导入资源（0）'), findsOneWidget);
      await native(tester, 'resourceDrop', ['D:/note.md']);
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(backend.submitted, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'confirm rechecks files, preserves partial success and retries only failed entries',
    (tester) async {
      final backend = _Backend();
      await _show(tester, backend);
      await native(tester, 'resourceDrop', [
        'D:/note.md',
        'D:/fail.md',
        'D:/denied.txt',
      ]);
      await tester.tap(find.text('确认导入'));
      await tester.pumpAndSettle();
      expect(backend.submitted, ['D:/note.md', 'D:/fail.md']);
      expect(backend.inspections, hasLength(4));
      expect(find.text('已导入'), findsOneWidget);
      await tester.ensureVisible(find.byTooltip('移除 denied.txt'));
      await tester.tap(find.byTooltip('移除 denied.txt'));
      await tester.pumpAndSettle();
      backend.fail = false;
      await tester.tap(find.text('重试未完成项'));
      await tester.pumpAndSettle();
      expect(backend.submitted, ['D:/note.md', 'D:/fail.md', 'D:/fail.md']);
      expect(find.text('已导入'), findsNWidgets(2));
      await tester.tap(find.text('完成'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );
}
