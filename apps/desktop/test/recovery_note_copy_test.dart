import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

import 'document_page_test.dart' as fixture;
import 'document_recovery_test.dart' as recovery;

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

Map<String, dynamic> node() => {
  'resource_item_id': 'b' * 32,
  'kind': 'resource',
  'name': '恢复的笔记.md',
  'status': 'ready',
  'sha256': 'a' * 64,
};
Map<String, dynamic> target(String hash, String text) => {
  'type': 'markdown',
  'working_copy': true,
  'sha256': hash,
  'text': text,
};
bool isTarget(String path) => path.contains('/nodes/${'b' * 32}/');
Future<void> choose(WidgetTester tester) async {
  await tester.tap(find.text('保存恢复点'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('查看待写稿'));
  await tester.pumpAndSettle();
}

void main() {
  for (final invalid in ['', '没有后缀']) {
    testWidgets(
      'invalid copy name remains editable before creating: $invalid',
      (tester) async {
        var creates = 0, reads = 0;
        final backend = _Backend((method, path, body) async {
          if (method == 'POST') {
            creates++;
            return node();
          }
          if (path.endsWith('/document')) throw StateError('missing');
          if (path.contains('/document-saves?')) return recovery.receipts();
          reads++;
          return recovery.preview();
        });
        await fixture.show(tester, backend, fixture.tab(), onNavigate: (_) {});
        await choose(tester);
        final field = find.widgetWithText(TextField, '副本名称（.md）');
        await tester.enterText(field, invalid);
        await tester.tap(find.text('确认另存为新笔记'));
        await tester.pumpAndSettle();
        expect(creates, 0);
        expect(reads, 1);
        expect(tester.widget<TextField>(field).enabled, true);
        await tester.tap(find.text('关闭'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );
  }

  for (final content in ['', '找回正文 <script>literal</script>']) {
    testWidgets(
      'missing source can save an independent copy, including empty literal text: $content',
      (tester) async {
        var writes = 0;
        Map<String, dynamic>? opened;
        final point = {...recovery.preview(), 'text': content};
        final backend = _Backend((method, path, body) async {
          if (path.endsWith('/markdown-notes')) {
            expect(method, 'POST');
            return node();
          }
          if (isTarget(path)) {
            if (method == 'GET') return target('a' * 64, 'initial note');
            expect(method, 'PUT');
            expect(body, {'expected_sha256': 'a' * 64, 'text': content});
            writes++;
            return {'sha256': 'd' * 64};
          }
          expect(
            method,
            'GET',
            reason: 'Original source must never be written',
          );
          if (path.endsWith('/document')) throw StateError('missing source');
          if (path.contains('/document-saves?')) return recovery.receipts();
          return point;
        });
        final originalTab = fixture.tab()..resourceName = '改名后无扩展名';
        await fixture.show(
          tester,
          backend,
          originalTab,
          onNavigate: (value) => opened = value,
        );
        if (content.isEmpty) {
          tester.view.physicalSize = const Size(400, 800);
          await tester.pumpAndSettle();
        }
        await choose(tester);
        expect(
          tester
              .widget<FilledButton>(find.widgetWithText(FilledButton, '载入编辑草稿'))
              .onPressed,
          isNull,
        );
        expect(writes, 0);
        await tester.tap(find.text('确认另存为新笔记'));
        await tester.pumpAndSettle();
        expect(writes, 1);
        expect(opened!['resource_item_id'], 'b' * 32);
        expect(find.textContaining('已保存，可从资源目录打开新笔记'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }

  for (final lost in ['creation', 'save']) {
    testWidgets(
      'lost $lost response retries the same creation and reconciles saved content',
      (tester) async {
        final requests = <Map<String, dynamic>>[];
        var writes = 0, created = 0;
        var saved = false;
        var opened = false;
        final backend = _Backend((method, path, body) async {
          if (path.endsWith('/markdown-notes')) {
            requests.add(Map<String, dynamic>.from(body!));
            if (requests.length == 1) {
              created++;
              if (lost == 'creation') throw StateError('response lost');
            }
            return node();
          }
          if (isTarget(path)) {
            if (method == 'GET') {
              return saved
                  ? target('d' * 64, recovery.preview()['text'] as String)
                  : target('a' * 64, 'initial');
            }
            writes++;
            saved = true;
            if (lost == 'save') throw StateError('response lost');
            return {'sha256': 'd' * 64};
          }
          expect(method, 'GET');
          if (path.endsWith('/document')) throw StateError('missing');
          if (path.contains('/document-saves?')) return recovery.receipts();
          return recovery.preview();
        });
        await fixture.show(
          tester,
          backend,
          fixture.tab(),
          onNavigate: (_) => opened = true,
        );
        await choose(tester);
        await tester.tap(find.text('确认另存为新笔记'));
        await tester.pumpAndSettle();
        expect(opened, false);
        expect(find.textContaining('response lost'), findsOneWidget);
        expect(
          tester
              .widget<TextField>(find.widgetWithText(TextField, '副本名称（.md）'))
              .enabled,
          false,
        );
        await tester.tap(find.text('重试另存并对账'));
        await tester.pumpAndSettle();
        expect(requests.length, 2);
        expect(requests[0], requests[1]);
        expect(created, 1);
        expect(writes, 1);
        expect(opened, true);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets(
    'a changed target is preserved and navigation failure retains a saved copy',
    (tester) async {
      var altered = true, writes = 0;
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/markdown-notes')) return node();
        if (isTarget(path)) {
          if (method == 'GET') {
            return altered
                ? target('e' * 64, 'other user edit')
                : target('a' * 64, 'initial');
          }
          writes++;
          return {'sha256': 'd' * 64};
        }
        expect(method, 'GET');
        if (path.endsWith('/document')) throw StateError('missing');
        if (path.contains('/document-saves?')) return recovery.receipts();
        return recovery.preview();
      });
      await fixture.show(
        tester,
        backend,
        fixture.tab(),
        onNavigate: (_) => throw StateError('tab limit'),
      );
      await choose(tester);
      await tester.tap(find.text('确认另存为新笔记'));
      await tester.pumpAndSettle();
      expect(find.textContaining('新笔记已被修改'), findsOneWidget);
      expect(writes, 0);
      altered = false;
      await tester.tap(find.text('重试另存并对账'));
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(find.textContaining('副本笔记已保存，打开失败'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('changed recovery point and cancellation create nothing', (
    tester,
  ) async {
    var reads = 0, creates = 0;
    final backend = _Backend((method, path, body) async {
      if (method == 'POST') {
        creates++;
        return node();
      }
      if (path.endsWith('/document')) throw StateError('missing');
      if (path.contains('/document-saves?')) return recovery.receipts();
      reads++;
      return reads == 1
          ? recovery.preview()
          : {...recovery.preview(), 'sha256': 'e' * 64};
    });
    await fixture.show(tester, backend, fixture.tab(), onNavigate: (_) {});
    await choose(tester);
    await tester.tap(find.text('确认另存为新笔记'));
    await tester.pumpAndSettle();
    expect(find.textContaining('恢复点已变化'), findsOneWidget);
    expect(creates, 0);
    await tester.tap(find.text('关闭'));
    await tester.pumpAndSettle();
    expect(creates, 0);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'creation in flight blocks closing; disposal after verification stops writes',
    (tester) async {
      final verified = Completer<Map<String, dynamic>>();
      var reads = 0, creates = 0;
      final backend = _Backend((method, path, body) async {
        if (method == 'POST') {
          creates++;
          return node();
        }
        if (path.endsWith('/document')) throw StateError('missing');
        if (path.contains('/document-saves?')) return recovery.receipts();
        reads++;
        return reads == 1 ? recovery.preview() : verified.future;
      });
      await fixture.show(tester, backend, fixture.tab(), onNavigate: (_) {});
      await choose(tester);
      await tester.tap(find.text('确认另存为新笔记'));
      await tester.pump(const Duration(milliseconds: 100));
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '关闭'))
            .onPressed,
        isNull,
      );
      await tester.pumpWidget(const SizedBox());
      verified.complete(recovery.preview());
      await tester.pumpAndSettle();
      expect(creates, 0);
      expect(tester.takeException(), isNull);
    },
  );
}
