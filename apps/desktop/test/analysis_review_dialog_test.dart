import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/analysis_review_dialog.dart';
import 'package:study_workbench/backend.dart';

class FakeBackend implements Backend {
  final calls = <Map<String, dynamic>>[];
  Completer<void>? gate;
  bool fail = false;
  String nodeStatus = 'ready';
  Map<String, dynamic>? opened;
  Map<String, dynamic> row = {
    'id': 'draft',
    'revision': 1,
    'payload_sha256': 'abc',
    'status': 'pending',
    'adoption': <String, dynamic>{},
    'result': <String, dynamic>{},
    'content': {
      'title': '候选',
      'source_label': '自填',
      'body': '外部文字',
      'references': <dynamic>[],
    },
  };
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    calls.add({'method': method, 'path': path, 'body': body});
    await gate?.future;
    if (fail) throw BackendError(409, '授权已过期，草稿保留');
    if (method == 'GET' && path.contains('/nodes/')) {
      return {
        'resource_item_id': 'note',
        'status': nodeStatus,
        'name': '分析候选.md',
        'kind': 'resource',
      };
    }
    if (path.endsWith('/adopt')) {
      row = {
        ...row,
        'status': 'adopted',
        'adoption': body,
        'result': {'resource_item_id': 'note'},
      };
    } else if (path.endsWith('/reject')) {
      row = {...row, 'status': 'rejected'};
    } else {
      row = {
        ...row,
        'content': {
          ...row['content'] as Map,
          'title': body!['title'],
          'body': body['body'],
          'source_label': body['source_label'],
        },
      };
    }
    return row;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> open(
  WidgetTester tester,
  FakeBackend backend, {
  bool existing = false,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () => showDialog<Map<String, dynamic>>(
              context: context,
              barrierDismissible: false,
              builder: (_) => AnalysisReviewDialog(
                backend: backend,
                scope: '/api/workspaces/w',
                draft: existing ? backend.row : null,
                grantId: 'grant',
                authorization: const {
                  'context_sha256': 'hash',
                  'scope': 'summary',
                },
              ),
            ).then((note) => backend.opened = note),
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
  testWidgets('已建笔记打开前重验状态，移除时保留候选不再采用', (tester) async {
    final backend = FakeBackend()..nodeStatus = 'removed';
    backend.row = {
      ...backend.row,
      'status': 'adopted',
      'result': {'resource_item_id': 'note'},
    };
    await open(tester, backend, existing: true);
    await tester.tap(find.text('打开已建笔记'));
    await tester.pumpAndSettle();
    expect(find.byType(AnalysisReviewDialog), findsOneWidget);
    expect(backend.opened, isNull);
    expect(backend.calls.single['method'], 'GET');
    backend.nodeStatus = 'ready';
    await tester.tap(find.text('打开已建笔记'));
    await tester.pumpAndSettle();
    expect(backend.opened!['resource_item_id'], 'note');
    expect(backend.calls.every((call) => call['method'] == 'GET'), true);
  });
  testWidgets('结果未知的创建仅在另行确认后放弃窗口，服务端候选不删除', (tester) async {
    final backend = FakeBackend()..fail = true;
    await open(tester, backend);
    await tester.enterText(find.widgetWithText(TextField, '候选标题'), '尚未确认');
    await tester.enterText(find.widgetWithText(TextField, '候选正文'), '保留的文字');
    await expectLater(
      flushAnalysisDraftEditors(),
      throwsA(isA<BackendError>()),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('放弃未保存编辑'));
    await tester.pumpAndSettle();
    expect(find.textContaining('可能已保存的候选仍保留'), findsOneWidget);
    await tester.tap(find.text('保留编辑'));
    await tester.pumpAndSettle();
    expect(find.byType(AnalysisReviewDialog), findsOneWidget);
    await tester.tap(find.text('放弃未保存编辑'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认放弃'));
    await tester.pumpAndSettle();
    expect(find.byType(AnalysisReviewDialog), findsNothing);
    await flushAnalysisDraftEditors();
    expect(backend.calls, hasLength(1));
    expect(backend.calls.single['method'], 'POST');
  });
  testWidgets('新候选退出前保存合并并发刷新；采用需要另行确认', (tester) async {
    final backend = FakeBackend();
    await open(tester, backend);
    await tester.enterText(find.widgetWithText(TextField, '候选标题'), '候选标题文字');
    await tester.enterText(
      find.widgetWithText(TextField, '候选正文'),
      '```<script>外部文字',
    );
    backend.gate = Completer<void>();
    final first = flushAnalysisDraftEditors(),
        second = flushAnalysisDraftEditors();
    await tester.pump();
    expect(backend.calls.length, 1);
    backend.gate!.complete();
    await Future.wait([first, second]);
    await tester.pumpAndSettle();
    expect(backend.calls.single['body']['body'], '```<script>外部文字');
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认采用为笔记'))
          .onPressed,
      isNull,
    );
    await tester.scrollUntilVisible(
      find.byType(CheckboxListTile),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tester.tap(find.text('确认采用为笔记'));
    await tester.pumpAndSettle();
    expect(backend.calls.last['body']['confirm'], true);
    expect(backend.calls.last['body']['expected_revision'], 1);
    expect(find.text('已建独立笔记；内容仍未经验证。'), findsOneWidget);
    await tester.tap(find.text('打开已建笔记'));
    await tester.pumpAndSettle();
    expect(backend.opened!['resource_item_id'], 'note');
    expect(find.byType(AnalysisReviewDialog), findsNothing);
  });

  testWidgets('授权过期时保留文字并阻止应用刷新退出，重试使用原创建请求', (tester) async {
    final backend = FakeBackend()..fail = true;
    await open(tester, backend);
    await tester.enterText(find.widgetWithText(TextField, '候选标题'), '候选');
    await tester.enterText(find.widgetWithText(TextField, '候选正文'), '不能丢失的文字');
    await expectLater(
      flushAnalysisDraftEditors(),
      throwsA(isA<BackendError>()),
    );
    await tester.pumpAndSettle();
    expect(find.text('不能丢失的文字'), findsOneWidget);
    final original = backend.calls.single['body'];
    backend.fail = false;
    await flushAnalysisDraftEditors();
    await tester.pumpAndSettle();
    expect(backend.calls.last['body'], original);
    await tester.tap(find.text('保存并关闭'));
    await tester.pumpAndSettle();
    await flushAnalysisDraftEditors();
    expect(backend.calls.length, 2);
  });

  testWidgets('小窗口审核可滚动，编辑后取消确认；拒绝保留记录', (tester) async {
    tester.view.physicalSize = const Size(600, 450);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final backend = FakeBackend();
    await open(tester, backend, existing: true);
    expect(tester.takeException(), isNull);
    await tester.scrollUntilVisible(
      find.widgetWithText(TextField, '候选标题'),
      80,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(find.widgetWithText(TextField, '候选标题'), '修改标题');
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认采用为笔记'))
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('保存草稿'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('拒绝并保留记录'));
    await tester.pumpAndSettle();
    expect(backend.calls.last['path'], endsWith('/reject'));
    await tester.scrollUntilVisible(
      find.textContaining('状态：rejected'),
      -80,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining('状态：rejected'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('采用响应未知锁住候选编辑，重试原参数；失败收据展示原文件名', (tester) async {
    final backend = FakeBackend();
    await open(tester, backend, existing: true);
    await tester.scrollUntilVisible(
      find.byType(CheckboxListTile),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    backend.fail = true;
    await tester.tap(find.text('确认采用为笔记'));
    await tester.pumpAndSettle();
    final original = backend.calls.single['body'];
    expect(
      tester.widget<TextField>(find.widgetWithText(TextField, '候选正文')).enabled,
      false,
    );
    backend.fail = false;
    await tester.tap(find.text('确认采用为笔记'));
    await tester.pumpAndSettle();
    expect(backend.calls.last['body'], original);
    await tester.tap(find.text('保存并关闭'));
    await tester.pumpAndSettle();
    backend.row = {
      ...backend.row,
      'status': 'failed',
      'adoption': {...original, 'name': '原收据名称.md'},
    };
    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.widgetWithText(TextField, '新笔记文件名'),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('原收据名称.md'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.widgetWithText(TextField, '新笔记文件名'))
          .enabled,
      false,
    );
    await tester.tap(find.text('拒绝并保留记录'));
    await tester.pumpAndSettle();
    expect(backend.row['status'], 'rejected');
    expect(backend.row['adoption']['name'], '原收据名称.md');
  });
}
