import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_merge_dialog.dart';
import 'package:study_workbench/workspace_layout.dart';

import 'document_page_test.dart' as fixture;

final a = 'a' * 64, b = 'b' * 64, x = 'f' * 64, receipt = 'c' * 32;
const local = 'A\nb\nc\n', candidate = 'A\nb\nC\n<script>literal</script>';

class _Backend implements Backend {
  String currentHash = b, sourceHash = a, merged = candidate;
  String disk = 'a\nb\nC\n';
  bool conflict = false, failPreview = false, unavailable = false;
  bool working = true;
  String? responseBase;
  Completer<void>? gate;
  final calls = <Map<String, dynamic>>[];
  Map<int, List<Map<String, dynamic>>> pages = {0: []};
  List<Map<String, dynamic>> get posts =>
      calls.where((c) => c['method'] == 'POST').toList();
  List<Map<String, dynamic>> get writes =>
      calls.where((c) => c['method'] == 'PUT').toList();

  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    calls.add({
      'method': method,
      'path': path,
      'body': body == null ? null : Map<String, dynamic>.from(body),
    });
    if (method == 'GET' && path.endsWith('/document')) {
      return {
        'type': 'markdown',
        'working_copy': working,
        'sha256': currentHash,
        'source_sha256': sourceHash,
        'text': disk,
      };
    }
    if (method == 'GET' && path.contains('/document-saves?')) {
      final offset = int.parse(Uri.parse(path).queryParameters['offset']!);
      return pages[offset] ?? [];
    }
    if (method == 'POST' && path.endsWith('/document-merge-preview')) {
      final pending = gate;
      if (pending != null) await pending.future;
      if (failPreview ||
          unavailable ||
          body!['expected_current_sha256'] != currentHash) {
        throw BackendError(409, 'preview version unavailable');
      }
      expectSync(body['expected_base_sha256'], a);
      expectSync(body.keys.toSet(), {
        'base',
        'expected_base_sha256',
        'expected_current_sha256',
        'text',
        if (body['base'] != 'original') 'save_id',
      });
      return {
        'conflicted': conflict,
        'text': conflict ? null : merged,
        'base_sha256': responseBase ?? a,
        'current_sha256': currentHash,
        'local_sha256': 'd' * 64,
      };
    }
    if (method == 'PUT' && path.endsWith('/document')) {
      if (body!['expected_sha256'] != currentHash) {
        throw BackendError(409, 'changed after merge');
      }
      disk = body['text'] as String;
      currentHash = 'e' * 64;
      return {'sha256': currentHash};
    }
    fail('Unexpected request $method $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

WorkbenchTab draft([String content = local]) => fixture.tab()
  ..draft = content
  ..draftBaseSha256 = a
  ..documentState['mode'] = 'edit';

Future<void> open(WidgetTester tester) async {
  await tester.tap(find.text('合并修改'));
  await tester.pumpAndSettle();
}

Future<void> selectOriginal(WidgetTester tester) async {
  await tester.tap(find.byKey(const ValueKey('merge-base-original')));
  await tester.pump();
  await tester.tap(find.text('预览合并'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'verified original preview and confirmation only load a draft; ordinary save remains explicit',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      expect(backend.posts, isEmpty);
      await selectOriginal(tester);
      expect(
        tester
            .widget<SelectableText>(
              find.byKey(const ValueKey('merge-candidate')),
            )
            .data,
        candidate,
      );
      expect(tab.draft, local);
      expect(backend.writes, isEmpty);
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      expect(backend.posts.length, 2);
      expect(backend.posts.first['body'], backend.posts.last['body']);
      expect(backend.posts.first['body'], {
        'base': 'original',
        'expected_base_sha256': a,
        'expected_current_sha256': b,
        'text': local,
      });
      expect(tab.draft, candidate);
      expect(tab.draftBaseSha256, b);
      expect(tab.captureView!()['sha256'], b);
      expect(backend.writes, isEmpty);
      expect(tab.toJson()['draft_base_sha256'], b);
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(backend.writes.single['body'], {
        'expected_sha256': b,
        'text': candidate,
      });
      expect(tab.draftBaseSha256, isNull);
      expect(tab.draft, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  for (final afterPreview in [false, true]) {
    testWidgets(
      'cancel ${afterPreview ? 'after' : 'before'} preview preserves the original draft',
      (tester) async {
        final backend = _Backend(), tab = draft();
        await fixture.show(tester, backend, tab);
        await open(tester);
        if (afterPreview) await selectOriginal(tester);
        await tester.tap(find.text('取消合并'));
        await tester.pumpAndSettle();
        expect(tab.draft, local);
        expect(tab.draftBaseSha256, a);
        expect(backend.writes, isEmpty);
        expect(backend.posts.length, afterPreview ? 1 : 0);
      },
    );
  }

  for (final version in ['before', 'pending']) {
    testWidgets(
      'matching $version receipt is explicitly selected and revalidated',
      (tester) async {
        final backend = _Backend()..sourceHash = x;
        backend.pages[0] = [
          {
            'id': receipt,
            'status': 'interrupted',
            'old_sha256': version == 'before' ? a : x,
            'new_sha256': version == 'pending' ? a : x,
          },
        ];
        final tab = draft();
        await fixture.show(tester, backend, tab);
        await open(tester);
        expect(find.byKey(const ValueKey('merge-base-original')), findsNothing);
        await tester.tap(find.byKey(ValueKey('merge-base-$version-$receipt')));
        await tester.pump();
        await tester.tap(find.text('预览合并'));
        await tester.pumpAndSettle();
        expect(backend.posts.single['body']['base'], version);
        expect(backend.posts.single['body']['save_id'], receipt);
        await tester.tap(find.text('确认载入合并草稿'));
        await tester.pumpAndSettle();
        expect(tab.draft, candidate);
        expect(tab.draftBaseSha256, b);
        expect(backend.writes, isEmpty);
      },
    );
  }

  testWidgets('mismatched baselines are never offered or guessed', (
    tester,
  ) async {
    final backend = _Backend()..sourceHash = x;
    backend.pages[0] = [
      {'id': receipt, 'old_sha256': x, 'new_sha256': x},
    ];
    final tab = draft();
    await fixture.show(tester, backend, tab);
    await open(tester);
    expect(find.textContaining('本页没有与草稿基线一致'), findsOneWidget);
    expect(
      tester
          .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, '预览合并'))
          .onPressed,
      isNull,
    );
    expect(backend.posts, isEmpty);
    await tester.tap(find.text('取消合并'));
    await tester.pumpAndSettle();
    expect(tab.draft, local);
    expect(tab.draftBaseSha256, a);
  });

  testWidgets('history is paginated to find the exact draft base', (
    tester,
  ) async {
    final backend = _Backend()..sourceHash = x;
    backend.pages[0] = List.generate(
      50,
      (i) => {
        'id': i.toString().padLeft(32, '0'),
        'old_sha256': x,
        'new_sha256': x,
      },
    );
    backend.pages[50] = [
      {'id': receipt, 'old_sha256': a, 'new_sha256': x},
    ];
    await fixture.show(tester, backend, draft());
    await open(tester);
    await tester.tap(find.text('加载更多基线记录'));
    await tester.pumpAndSettle();
    expect(
      backend.calls.where(
        (c) => (c['path'] as String).contains('offset=50&limit=50'),
      ),
      hasLength(1),
    );
    await tester.tap(find.byKey(ValueKey('merge-base-before-$receipt')));
    await tester.pump();
    await tester.tap(find.text('预览合并'));
    await tester.pumpAndSettle();
    expect(backend.posts.single['body']['save_id'], receipt);
  });

  testWidgets(
    'a conflict discards an older candidate and cannot load a draft',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      backend.conflict = true;
      await tester.tap(find.text('预览合并'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('merge-candidate')), findsNothing);
      expect(find.textContaining('无法生成合并候选'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '确认载入合并草稿'))
            .onPressed,
        isNull,
      );
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(backend.writes, isEmpty);
    },
  );

  testWidgets(
    'empty draft and empty candidate remain dirty until explicitly saved',
    (tester) async {
      final backend = _Backend()..merged = '';
      final tab = draft('');
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      expect(backend.posts.single['body']['text'], '');
      expect(find.textContaining('合并候选为空文本'), findsOneWidget);
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      expect(tab.draft, '');
      expect(tab.draftBaseSha256, b);
      expect(WorkbenchTab.fromJson(tab.toJson()).draftBaseSha256, b);
      expect(backend.writes, isEmpty);
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(backend.writes.single['body'], {'expected_sha256': b, 'text': ''});
      expect(tab.draftBaseSha256, isNull);
    },
  );

  testWidgets(
    'external change at confirmation rejects stale preview and requires another review',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      backend.currentHash = x;
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      expect(backend.posts.last['body']['expected_current_sha256'], b);
      expect(find.textContaining('必须重新预览'), findsOneWidget);
      expect(find.byKey(const ValueKey('merge-candidate')), findsNothing);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      await tester.tap(find.text('预览合并'));
      await tester.pumpAndSettle();
      expect(backend.posts.last['body']['expected_current_sha256'], x);
      expect(tab.draft, local);
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      expect(tab.draftBaseSha256, x);
      expect(backend.writes, isEmpty);
    },
  );

  testWidgets('changed candidate at confirmation is not silently loaded', (
    tester,
  ) async {
    final backend = _Backend(), tab = draft();
    await fixture.show(tester, backend, tab);
    await open(tester);
    await selectOriginal(tester);
    backend.merged = 'different candidate';
    await tester.tap(find.text('确认载入合并草稿'));
    await tester.pumpAndSettle();
    expect(find.textContaining('预览结果已变化'), findsOneWidget);
    expect(tab.draft, local);
    expect(tab.draftBaseSha256, a);
    expect(backend.writes, isEmpty);
  });

  testWidgets(
    'external change after loading remains guarded by the ordinary save',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      backend.currentHash = x;
      await tester.tap(find.text('保存工作文件'));
      await tester.pumpAndSettle();
      expect(backend.writes.single['body'], {
        'expected_sha256': b,
        'text': candidate,
      });
      expect(tab.draft, candidate);
      expect(tab.draftBaseSha256, b);
      expect(find.textContaining('changed after merge'), findsOneWidget);
    },
  );

  testWidgets(
    'preview failure preserves the draft and permits an explicit retry',
    (tester) async {
      final backend = _Backend()..failPreview = true;
      final tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      expect(find.textContaining('合并预览失败'), findsOneWidget);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      backend.failPreview = false;
      await tester.tap(find.text('预览合并'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('merge-candidate')), findsOneWidget);
      expect(backend.writes, isEmpty);
    },
  );

  for (final confirming in [false, true]) {
    testWidgets(
      'cancel during ${confirming ? 'confirmation' : 'preview'} ignores a late response',
      (tester) async {
        final backend = _Backend(), tab = draft();
        await fixture.show(tester, backend, tab);
        await open(tester);
        if (confirming) {
          await selectOriginal(tester);
        } else {
          await tester.tap(find.byKey(const ValueKey('merge-base-original')));
          await tester.pump();
        }
        final gate = backend.gate = Completer<void>();
        await tester.tap(find.text(confirming ? '确认载入合并草稿' : '预览合并'));
        await tester.pump();
        await tester.tap(find.text('取消合并'));
        await tester.pumpAndSettle();
        gate.complete();
        await tester.pumpAndSettle();
        expect(tab.draft, local);
        expect(tab.draftBaseSha256, a);
        expect(backend.writes, isEmpty);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('repeated open, preview and confirmation callbacks are gated', (
    tester,
  ) async {
    final backend = _Backend(), tab = draft();
    await fixture.show(tester, backend, tab);
    final openAction = tester
        .widget<TextButton>(find.widgetWithText(TextButton, '合并修改'))
        .onPressed!;
    openAction();
    openAction();
    await tester.pumpAndSettle();
    expect(find.byType(DocumentMergeDialog), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('merge-base-original')));
    await tester.pump();
    final previewAction = tester
        .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, '预览合并'))
        .onPressed!;
    previewAction();
    previewAction();
    await tester.pump();
    await tester.pumpAndSettle();
    expect(backend.posts, hasLength(1));
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认载入合并草稿'))
          .onPressed,
      isNotNull,
      reason:
          'busy=${find.byType(LinearProgressIndicator).evaluate().length}; ${tester.widgetList<SelectableText>(find.byType(SelectableText)).map((w) => w.data).toList()}',
    );
    final confirmAction = tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, '确认载入合并草稿'))
        .onPressed!;
    confirmAction();
    confirmAction();
    await tester.pump();
    await tester.pumpAndSettle();
    expect(backend.posts, hasLength(2));
    expect(tab.draft, candidate);
    expect(backend.writes, isEmpty);
  });

  testWidgets(
    'a newer editor draft is not replaced by an older reviewed candidate',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      final editor = tester
          .widget<TextField>(find.byKey(const ValueKey('markdown-editor')))
          .controller!;
      await open(tester);
      await selectOriginal(tester);
      editor.text = 'newer local draft';
      tab.draft = editor.text;
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pumpAndSettle();
      expect(tab.draft, 'newer local draft');
      expect(editor.text, 'newer local draft');
      expect(tab.draftBaseSha256, a);
      expect(find.textContaining('草稿或资源已变化'), findsOneWidget);
      expect(backend.writes, isEmpty);
    },
  );

  testWidgets('page disposal during a pending preview cannot load a draft', (
    tester,
  ) async {
    final backend = _Backend(), tab = draft();
    await fixture.show(tester, backend, tab);
    await open(tester);
    await tester.tap(find.byKey(const ValueKey('merge-base-original')));
    await tester.pump();
    final gate = backend.gate = Completer<void>();
    await tester.tap(find.text('预览合并'));
    await tester.pump();
    await tester.pumpWidget(const SizedBox());
    gate.complete();
    await tester.pumpAndSettle();
    expect(tab.draft, local);
    expect(tab.draftBaseSha256, a);
    expect(backend.writes, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'merge is disabled without a dirty draft and fits a narrow viewport',
    (tester) async {
      final backend = _Backend()..currentHash = a;
      final tab = fixture.tab();
      await fixture.show(tester, backend, tab);
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '合并修改'))
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('原文编辑'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('markdown-editor')),
        local,
      );
      await tester.pumpAndSettle();
      tester.view.physicalSize = const Size(400, 800);
      await tester.pumpAndSettle();
      await open(tester);
      await selectOriginal(tester);
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('取消合并'));
      await tester.pumpAndSettle();
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
    },
  );

  testWidgets(
    'unavailable pending receipt cannot fall back to an original base',
    (tester) async {
      final backend = _Backend()..unavailable = true;
      backend.pages[0] = [
        {'id': receipt, 'old_sha256': x, 'new_sha256': a},
      ];
      final tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await tester.tap(find.byKey(ValueKey('merge-base-pending-$receipt')));
      await tester.pump();
      await tester.tap(find.text('预览合并'));
      await tester.pumpAndSettle();
      expect(backend.posts.single['body']['base'], 'pending');
      expect(backend.posts.single['body']['save_id'], receipt);
      expect(find.byKey(const ValueKey('merge-candidate')), findsNothing);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(backend.writes, isEmpty);
    },
  );

  testWidgets(
    'a changed current file capability stops preview without a POST',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      backend.working = false;
      await selectOriginal(tester);
      expect(find.textContaining('不是可编辑Markdown'), findsOneWidget);
      expect(backend.posts, isEmpty);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
    },
  );

  testWidgets(
    'a response bound to a different base cannot supply a candidate',
    (tester) async {
      final backend = _Backend()..responseBase = x;
      final tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      expect(find.textContaining('返回不一致'), findsOneWidget);
      expect(find.byKey(const ValueKey('merge-candidate')), findsNothing);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(backend.writes, isEmpty);
    },
  );

  testWidgets(
    'late confirmation callbacks during dismissal cannot submit again',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      final confirmAction = tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认载入合并草稿'))
          .onPressed!;
      confirmAction();
      await tester.pump(const Duration(milliseconds: 30));
      await tester.pump(const Duration(milliseconds: 30));
      expect(backend.posts, hasLength(2));
      confirmAction();
      await tester.pumpAndSettle();
      expect(backend.posts, hasLength(2));
      expect(tab.draft, candidate);
      expect(backend.writes, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'cancelling a pending confirmation ignores a response before dismissal ends',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      final gate = backend.gate = Completer<void>();
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pump();
      await tester.tap(find.text('取消合并'));
      gate.complete();
      await tester.pumpAndSettle();
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(find.byKey(const ValueKey('markdown-editor')), findsOneWidget);
      expect(backend.writes, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'system back cancels a pending confirmation before its response arrives',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      await selectOriginal(tester);
      final gate = backend.gate = Completer<void>();
      await tester.tap(find.text('确认载入合并草稿'));
      await tester.pump();
      await tester.binding.handlePopRoute();
      gate.complete();
      await tester.pumpAndSettle();
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(find.byKey(const ValueKey('markdown-editor')), findsOneWidget);
      expect(backend.writes, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'duplicate cancellation callbacks cannot close the document page',
    (tester) async {
      final backend = _Backend(), tab = draft();
      await fixture.show(tester, backend, tab);
      await open(tester);
      final cancelAction = tester
          .widget<TextButton>(find.widgetWithText(TextButton, '取消合并'))
          .onPressed!;
      cancelAction();
      cancelAction();
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('markdown-editor')), findsOneWidget);
      expect(tab.draft, local);
      expect(tab.draftBaseSha256, a);
      expect(backend.posts, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );
}
