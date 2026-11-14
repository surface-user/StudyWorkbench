import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/media_site_preview_dialog.dart';

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

Map<String, dynamic> ready(String id) => {
  'id': id,
  'status': 'ready',
  'result': {
    'title': '自编格式标题',
    'duration_seconds': 120,
    'formats': [
      {
        'format_id': 'video-0',
        'delivery': 'dash_video',
        'height': 720,
        'container': 'mp4',
        'codecs': 'avc1.fixture',
        'size_bytes': null,
        'limitation': '暂不支持分轨下载',
      },
    ],
  },
};

Future<void> show(
  WidgetTester tester,
  Backend backend, {
  String workspace = 'default',
  double dpi = 1,
}) async {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = dpi;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: MediaSitePreviewDialog(backend: backend, workspaceId: workspace),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> consentAndStart(WidgetTester tester) async {
  await tester.enterText(
    find.byType(TextField),
    'https://www.bilibili.com/video/BV1234567890',
  );
  await tester.tap(find.byType(CheckboxListTile));
  await tester.pump();
  await tester.tap(find.text('预览格式'));
  await tester.pump();
}

void main() {
  for (final dpi in [1.0, 2.0, 3.0]) {
    testWidgets('preview fits simulated ${dpi * 100} percent DPI', (
      tester,
    ) async {
      await show(tester, _Backend((_, _, _) async => {}), dpi: dpi);
      expect(find.text('关闭'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    });
  }
  testWidgets(
    'explicit consent previews scoped formats and never creates a download',
    (tester) async {
      final requests = <String>[];
      final backend = _Backend((method, path, body) async {
        requests.add('$method $path');
        if (path.endsWith('/cancel')) return {};
        expect(path, '/api/workspaces/default/media-site-previews');
        expect(body!['rights_confirmed'], true);
        expect(body['request_id'], matches(RegExp(r'^[0-9a-f]{48}$')));
        return ready('preview-id');
      });
      await show(tester, backend);
      expect(requests, isEmpty);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );
      await consentAndStart(tester);
      await tester.pumpAndSettle();
      expect(find.text('自编格式标题'), findsOneWidget);
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('720p · 视频轨 · mp4').last);
      await tester.pumpAndSettle();
      expect(find.text('大小未知'), findsOneWidget);
      expect(find.text('暂不支持分轨下载'), findsOneWidget);
      expect(find.textContaining('private='), findsNothing);
      expect(
        requests.where((line) => line.contains('/media-downloads')),
        isEmpty,
      );
      await tester.enterText(
        find.byType(TextField),
        'https://www.bilibili.com/video/BV0000000000',
      );
      await tester.pumpAndSettle();
      expect(find.text('自编格式标题'), findsNothing);
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        false,
      );
      expect(requests.last, endsWith('/preview-id/cancel'));
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets('cancel before creation response cancels the late owned id', (
    tester,
  ) async {
    final pending = Completer<dynamic>();
    final requests = <String>[];
    final backend = _Backend((method, path, body) async {
      requests.add('$method $path');
      if (path.endsWith('/cancel')) return {};
      return await pending.future;
    });
    await show(tester, backend);
    await consentAndStart(tester);
    expect(requests, isNotEmpty);
    expect(
      find.text('正在获取格式…'),
      findsOneWidget,
      reason: tester
          .widgetList<Text>(find.byType(Text))
          .map((text) => text.data)
          .join(' | '),
    );
    await tester.tap(find.text('取消预览'));
    await tester.pump();
    pending.complete(ready('late-id'));
    await tester.pumpAndSettle();
    expect(find.text('自编格式标题'), findsNothing);
    expect(
      requests.last,
      'POST /api/workspaces/default/media-site-previews/late-id/cancel',
    );
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('cancel discards in-flight poll and does not fetch again', (
    tester,
  ) async {
    final poll = Completer<dynamic>();
    final requests = <String>[];
    final backend = _Backend((method, path, body) async {
      requests.add('$method $path');
      if (method == 'GET') return poll.future;
      if (path.endsWith('/cancel')) return {};
      return {'id': 'owned-id', 'status': 'running'};
    });
    await show(tester, backend);
    await consentAndStart(tester);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump();
    await tester.tap(find.text('取消预览'));
    await tester.pump();
    poll.complete(ready('owned-id'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('自编格式标题'), findsNothing);
    expect(requests.where((line) => line.startsWith('GET ')).length, 1);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'closed preview cancels a creation result arriving after dispose',
    (tester) async {
      final pending = Completer<dynamic>();
      final cancelled = <String>[];
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/cancel')) {
          cancelled.add(path);
          return {};
        }
        return pending.future;
      });
      await show(tester, backend);
      await consentAndStart(tester);
      await tester.pumpWidget(const SizedBox());
      pending.complete(ready('disposed-id'));
      await tester.pumpAndSettle();
      expect(cancelled, [
        '/api/workspaces/default/media-site-previews/disposed-id/cancel',
      ]);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'scope change cancels the old owner and rejects its late response',
    (tester) async {
      final pending = Completer<dynamic>();
      final cancelled = <String>[];
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/cancel')) {
          cancelled.add(path);
          return {};
        }
        return pending.future;
      });
      await show(tester, backend);
      await consentAndStart(tester);
      await show(tester, backend, workspace: 'other');
      pending.complete(ready('old-workspace-id'));
      await tester.pumpAndSettle();
      expect(find.text('自编格式标题'), findsNothing);
      expect(cancelled, [
        '/api/workspaces/default/media-site-previews/old-workspace-id/cancel',
      ]);
      expect(
        tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
        false,
      );
      await tester.pumpWidget(const SizedBox());
    },
  );
}
