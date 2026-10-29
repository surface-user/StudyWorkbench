import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/question_split_dialog.dart';

class _Backend implements Backend {
  final bodies = <Map<String, dynamic>>[];
  bool fail = false;
  final edits = <Map<String, dynamic>>[];
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    expect(method, 'POST');
    if (path.endsWith('/question-drafts/edit')) {
      edits.add(body!);
      final updated = job;
      final drafts = updated['preview']['question_drafts'] as List;
      drafts[0]['blocks'].addAll(drafts[1]['blocks'] as List);
      drafts.removeLast();
      updated['draft_revision'] = 'b' * 64;
      updated['question_markdown'] = ['题目1内容\n题目2内容\n'];
      return updated;
    }
    expect(path, '/api/workspaces/math/imports/job/question-markdown');
    bodies.add(body!);
    if (fail) throw StateError('409 预览已更新');
    return [];
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> get job => {
  'id': 'job',
  'draft_revision': 'a' * 64,
  'preview': {
    'warnings': ['核对边界'],
    'question_drafts': [
      for (final i in [1, 2])
        {
          'title': '第$i题',
          'blocks': [
            {'type': 'text', 'text': '题目$i内容'},
          ],
        },
    ],
  },
  'question_markdown': ['题目1内容\n', '题目2内容\n'],
};

void main() {
  Future<void> open(WidgetTester tester, _Backend backend) async {
    tester.view.physicalSize = const Size(1200, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              child: const Text('拆题'),
              onPressed: () => showDialog<bool>(
                context: context,
                builder: (_) => QuestionSplitDialog(
                  backend: backend,
                  workspaceId: 'math',
                  job: job,
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('拆题'));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'invalid Word character offset cannot silently split at the block start',
    (tester) async {
      final backend = _Backend();
      await open(tester, backend);
      await tester.tap(find.text('调整位置并拆分'));
      await tester.pumpAndSettle();
      final offset = find.byWidgetPredicate(
        (w) =>
            w is TextField && w.decoration?.labelText == '段内字符位置（留空则从该段开头分割）',
      );
      await tester.enterText(offset, 'abc');
      await tester.pump();
      expect(find.text('请输入非负整数'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '保存分割预览'))
            .onPressed,
        isNull,
      );
      expect(backend.edits, isEmpty);
    },
  );
  testWidgets(
    'merge refreshes the candidate revision before final confirmation',
    (tester) async {
      final backend = _Backend();
      await open(tester, backend);
      await tester.tap(find.text('与下一题合并'));
      await tester.pumpAndSettle();
      expect(backend.edits.single['action'], 'merge_next');
      expect(find.text('题目1内容'), findsOneWidget);
      expect(find.text('题目2内容'), findsOneWidget);
      expect(backend.bodies, isEmpty);
      await tester.tap(find.text('确认逐题保存为 Markdown'));
      await tester.pumpAndSettle();
      expect(backend.bodies.single['expected_revision'], 'b' * 64);
      expect(backend.bodies.single['selected'], [0]);
    },
  );
  testWidgets(
    'each candidate previews independently; only checked questions are confirmed',
    (tester) async {
      final backend = _Backend();
      await open(tester, backend);
      expect(find.text('题目1内容'), findsOneWidget);
      expect(find.text('题目2内容'), findsNothing);
      expect(backend.bodies, isEmpty);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.tap(find.text('下一题'));
      await tester.pumpAndSettle();
      expect(find.text('题目2内容'), findsOneWidget);
      expect(find.text('题目1内容'), findsNothing);
      await tester.tap(find.text('确认逐题保存为 Markdown'));
      await tester.pumpAndSettle();
      expect(backend.bodies.single, {
        'expected_revision': 'a' * 64,
        'selected': [1],
        'confirm': true,
      });
      expect(find.text('逐题裁切与 Markdown 预览'), findsNothing);
    },
  );

  testWidgets('cancel writes nothing and a failed save keeps the preview', (
    tester,
  ) async {
    final backend = _Backend();
    await open(tester, backend);
    await tester.tap(find.text('暂不入库'));
    await tester.pumpAndSettle();
    expect(backend.bodies, isEmpty);
    await tester.tap(find.text('拆题'));
    await tester.pumpAndSettle();
    backend.fail = true;
    await tester.tap(find.text('确认逐题保存为 Markdown'));
    await tester.pumpAndSettle();
    expect(find.textContaining('预览已更新'), findsOneWidget);
    expect(find.text('题目1内容'), findsOneWidget);
    expect(backend.bodies, hasLength(1));
  });
}
