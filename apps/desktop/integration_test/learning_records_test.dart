import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/learning_record_dialog.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Windows app appends learning event without changing saved attempt',
    (tester) async {
      Future<void> until(bool Function() ready) async {
        for (var i = 0; i < 600; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (ready()) return;
        }
        fail('Learning record UI did not reach expected state');
      }

      final capture = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(key: capture, child: const StudyApp()),
      );
      await until(() => find.byType(WorkspaceShell).evaluate().isNotEmpty);
      final shell = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final backend = shell.widget.backend;
      const scope = '/api/workspaces/default';
      late Map attempt;
      late Map original;
      late Map note;
      await tester.runAsync(() async {
        final job = await backend.uploadImport(
          'default',
          '学习笔记.txt',
          utf8.encode('Windows自编笔记内容'),
        ) as Map;
        await backend.request('POST', '$scope/imports/${job['id']}/confirm');
        note =
            (await backend.request('GET', '$scope/notes') as List).single
                as Map;
        attempt = await backend.request('POST', '$scope/attempts', {
          'question_id': 'demo-integral',
          'response': {
            'selected': ['a'],
          },
        }) as Map;
        original =
            (await backend.request('GET', '$scope/attempts') as List).single
                as Map;
      });
      showDialog<void>(
        context: shell.context,
        builder: (_) => LearningRecordDialog(
          backend: backend,
          scope: scope,
          workspaceId: 'default',
          attemptId: attempt['id'] as int,
        ),
      );
      await until(
        () =>
            find.textContaining('历史版本未知').evaluate().isNotEmpty &&
            find.byType(LinearProgressIndicator).evaluate().isEmpty,
      );
      await tester.ensureVisible(find.text('选择关联笔记'));
      await tester.tap(find.text('选择关联笔记'));
      await until(
        () => find
            .byKey(const ValueKey('related-note-picker'))
            .evaluate()
            .isNotEmpty,
      );
      await tester.ensureVisible(
        find.byKey(const ValueKey('related-note-picker')),
      );
      await tester.tap(find.byKey(const ValueKey('related-note-picker')));
      await tester.pumpAndSettle();
      await tester.tap(find.text(note['title'] as String).last);
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      final points = find.widgetWithText(TextField, '每行一个知识点；留空明确清除记录标签');
      await tester.ensureVisible(points);
      await tester.enterText(points, '积分\n复习');
      await tester.ensureVisible(find.byType(TextField).last);
      await tester.enterText(find.byType(TextField).last, 'Windows实际追加复习说明');
      await tester.ensureVisible(find.text('追加并关闭'));
      await tester.tap(find.text('追加并关闭'));
      await until(() => find.byType(LearningRecordDialog).evaluate().isEmpty);
      await tester.runAsync(() async {
        final record = await backend.request(
          'GET',
          '$scope/attempts/${attempt['id']}/record',
        ) as Map;
        expect((record['events'] as List).single['note'], 'Windows实际追加复习说明');
        expect(record['version_status'], 'unknown');
        expect(record['effective_knowledge_points'], ['积分', '复习']);
        expect((record['related_notes'] as List).single['id'], note['id']);
        final attempts =
            await backend.request('GET', '$scope/attempts') as List;
        expect(attempts.single, original);
      });
      showDialog<void>(
        context: shell.context,
        builder: (_) => LearningRecordDialog(
          backend: backend,
          scope: scope,
          workspaceId: 'default',
          attemptId: attempt['id'] as int,
        ),
      );
      await until(
        () => find.text('相关笔记：${note['title']}').evaluate().isNotEmpty,
      );
      await tester.tap(find.text('相关笔记：${note['title']}'));
      await until(() => find.text('Windows自编笔记内容').evaluate().isNotEmpty);
      await tester.ensureVisible(find.text('Windows自编笔记内容'));
      await tester.pump(const Duration(milliseconds: 300));
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      if (evidence.isNotEmpty) {
        final boundary =
            capture.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        final shot = await boundary.toImage(pixelRatio: 1);
        final bytes = await shot.toByteData(format: ui.ImageByteFormat.png);
        await tester.runAsync(
          () =>
              File('$evidence/learning-record-note.png')
                  .writeAsBytes(bytes!.buffer.asUint8List()),
        );
        shot.dispose();
      }
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(milliseconds: 300));
    },
  );
}
