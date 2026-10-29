import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/media_page.dart';
import 'package:study_workbench/web_page.dart';
import 'package:study_workbench/url_policy.dart';

class _Backend implements Backend {
  final paths = <String>[];
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    paths.add(path);
    if (path.endsWith('/resource-add-jobs')) return [];
    return [
      {'id': 'test', 'title': '自编视频.mp4', 'size': 100, 'status': 'failed'},
    ];
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _PlayerBackend implements Backend {
  _PlayerBackend(this.cap);
  final String cap;
  final paths = <String>[];
  @override
  int get port => 42100;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    paths.add(path);
    return {
      'url': 'http://127.0.0.1:42100/media/library/${'a' * 32}/player?cap=$cap',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'specific media skips library and reacquires capability after backend restart',
    (tester) async {
      final first = _PlayerBackend('first'),
          restarted = _PlayerBackend('restarted');
      Future<void> show(Backend backend) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: MediaPage(
                backend: backend,
                workspaceId: 'default',
                profile: 'test-profile',
                mediaId: 'a' * 32,
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
      }

      await show(first);
      expect(first.paths, ['/api/workspaces/default/media/${'a' * 32}/player']);
      expect(
        tester.widget<WebPage>(find.byType(WebPage)).playerUrl,
        contains('cap=first'),
      );
      await show(restarted);
      expect(restarted.paths, [
        '/api/workspaces/default/media/${'a' * 32}/player',
      ]);
      expect(
        tester.widget<WebPage>(find.byType(WebPage)).playerUrl,
        contains('cap=restarted'),
      );
      expect(tester.takeException(), isNull);
    },
  );
  test('player resource policy pins origin, capability and media id', () {
    const primary =
        'http://127.0.0.1:42100/media/library/id/player?cap=private';
    expect(
      allowedPlayerResource(
        primary,
        'http://127.0.0.1:42100/media/library/id/content?cap=private',
      ),
      isTrue,
    );
    expect(
      allowedPlayerResource(primary, 'blob:http://127.0.0.1:42100/track'),
      isTrue,
    );
    for (final url in [
      'file:///C:/secret',
      'about:blank',
      'http://127.0.0.1:42100/api/health?cap=private',
      'http://127.0.0.1:42101/media/library/id/content?cap=private',
      'http://127.0.0.1:42100/media/library/other/content?cap=private',
      'http://127.0.0.1:42100/media/library/id/content?cap=wrong',
      'blob:https://example.com/track',
    ]) {
      expect(allowedPlayerResource(primary, url), isFalse, reason: url);
    }
  });
  testWidgets(
    'media list exposes failed imports and cancelled picker sends no upload',
    (tester) async {
      final backend = _Backend();
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
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MediaPage(
              backend: backend,
              workspaceId: 'math',
              profile: 'test-profile',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('自编视频.mp4'), findsOneWidget);
      expect(find.textContaining('导入未完成'), findsOneWidget);
      await tester.tap(find.text('添加资源'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('添加文件'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(backend.paths, [
        '/api/workspaces/math/media?limit=50',
        '/api/workspaces/math/resource-add-jobs',
        '/api/workspaces/math/media?limit=50',
      ]);
    },
  );
}
