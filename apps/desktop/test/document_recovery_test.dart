import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_recovery_dialog.dart';

import 'document_page_test.dart' as fixture;

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

Map<String, dynamic> document() => {
  'type': 'markdown',
  'sha256': 'a' * 64,
  'text': '当前正文',
  'working_copy': true,
};
List<Map<String, dynamic>> receipts() => [
  {'id': 'c' * 32, 'status': 'interrupted'},
];
Map<String, dynamic> preview({String? current}) => {
  'id': 'c' * 32,
  'status': 'interrupted',
  'version': 'pending',
  'text': '找回的待写稿 <script>literal</script>',
  'sha256': 'd' * 64,
  'current_sha256': current,
  'unavailable_reason': current == null ? '暂不能载入草稿' : null,
};

Future<void> choose(WidgetTester tester) async {
  await tester.tap(find.text('保存恢复点'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('查看待写稿'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('recovery pagination remains usable in a narrow view', (
    tester,
  ) async {
    final offsets = <int>[];
    final backend = _Backend((method, path, body) async {
      expect(method, 'GET');
      if (path.endsWith('/document')) return document();
      final offset = int.parse(Uri.parse(path).queryParameters['offset']!);
      offsets.add(offset);
      if (offset == 50) {
        return [
          {'id': 'f' * 32, 'status': 'committed'},
        ];
      }
      return List.generate(
        50,
        (i) => {
          'id': i.toRadixString(16).padLeft(32, '0'),
          'status': 'interrupted',
        },
      );
    });
    await fixture.show(tester, backend, fixture.tab());
    tester.view.physicalSize = const Size(400, 800);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存恢复点'));
    await tester.pumpAndSettle();
    final scrolling = find
        .descendant(
          of: find.byType(DocumentRecoveryDialog),
          matching: find.byType(Scrollable),
        )
        .first;
    await tester.scrollUntilVisible(
      find.text('加载更多记录'),
      800,
      scrollable: scrolling,
    );
    await tester.tap(find.text('加载更多记录'));
    await tester.pumpAndSettle();
    expect(offsets, [0, 50]);
    await tester.scrollUntilVisible(
      find.text('f' * 32),
      200,
      scrollable: scrolling,
    );
    expect(find.text('f' * 32), findsOneWidget);
    expect(find.text('加载更多记录'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'preview and cancellation do not change draft or write; explicit save keeps conflict guard',
    (tester) async {
      final current = fixture.tab();
      var writes = 0;
      var failSave = true;
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/document') && method == 'GET') return document();
        if (method == 'PUT') {
          writes++;
          expect(body, {
            'expected_sha256': 'b' * 64,
            'text': preview()['text'],
          });
          if (failSave) throw StateError('409 changed after preview');
          return {'sha256': 'd' * 64};
        }
        expect(method, 'GET');
        if (path.contains('/document-saves?')) return receipts();
        return preview(current: 'b' * 64);
      });
      await fixture.show(tester, backend, current);
      await choose(tester);
      expect(find.text(preview()['text'] as String), findsOneWidget);
      expect(writes, 0);
      expect(current.draftBaseSha256, isNull);
      await tester.tap(find.text('载入编辑草稿'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(current.draftBaseSha256, isNull);
      expect(writes, 0);
      await choose(tester);
      await tester.tap(find.text('载入编辑草稿'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认载入草稿'));
      await tester.pumpAndSettle();
      expect(current.draft, preview()['text']);
      expect(current.draftBaseSha256, 'b' * 64);
      expect(current.documentState['mode'], 'edit');
      expect(writes, 0);
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(current.draftBaseSha256, 'b' * 64);
      expect(current.draft, preview()['text']);
      expect(find.textContaining('changed after preview'), findsOneWidget);
      failSave = false;
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(writes, 2);
      expect(current.draftBaseSha256, isNull);
      expect(current.draft, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('existing dirty draft is preserved before opening recovery', (
    tester,
  ) async {
    final current = fixture.tab()
      ..draft = '已有未保存草稿'
      ..draftBaseSha256 = 'a' * 64;
    var requests = 0;
    final backend = _Backend((method, path, body) async {
      requests++;
      expect(path, endsWith('/document'));
      return document();
    });
    await fixture.show(tester, backend, current);
    await tester.tap(find.text('保存恢复点'));
    await tester.pumpAndSettle();
    expect(find.textContaining('当前有未保存草稿'), findsOneWidget);
    expect(current.draft, '已有未保存草稿');
    expect(current.draftBaseSha256, 'a' * 64);
    expect(requests, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'list retry and invalid recovery keep load disabled without writes',
    (tester) async {
      var attempts = 0;
      final backend = _Backend((method, path, body) async {
        expect(method, 'GET');
        if (path.endsWith('/document')) return document();
        if (path.contains('/document-saves?')) {
          attempts++;
          if (attempts == 1) throw StateError('list unavailable');
          return receipts();
        }
        throw StateError('409 recovery hash mismatch');
      });
      await fixture.show(tester, backend, fixture.tab());
      await tester.tap(find.text('保存恢复点'));
      await tester.pumpAndSettle();
      expect(find.textContaining('list unavailable'), findsOneWidget);
      await tester.tap(find.text('重试读取记录'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('查看旧稿'));
      await tester.pumpAndSettle();
      expect(find.textContaining('recovery hash mismatch'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '载入编辑草稿'))
            .onPressed,
        isNull,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'prepared or unreadable current permits preview but cannot load draft',
    (tester) async {
      final current = fixture.tab();
      final backend = _Backend((method, path, body) async {
        expect(method, 'GET');
        if (path.endsWith('/document')) return document();
        if (path.contains('/document-saves?')) return receipts();
        return preview();
      });
      await fixture.show(tester, backend, current);
      await choose(tester);
      expect(find.textContaining('暂不能载入草稿'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '载入编辑草稿'))
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
      expect(current.draftBaseSha256, isNull);
      expect(tester.takeException(), isNull);
    },
  );
}
