import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Windows question files confirm, append attempts and preserve a separate answer draft',
    (tester) async {
      const root = String.fromEnvironment('STUDY_ROOT');
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      expect(Backend.testData, isNotEmpty);
      final capture = GlobalKey();
      final previousHitCheck = WidgetController.hitTestWarningShouldBeFatal;
      WidgetController.hitTestWarningShouldBeFatal = true;
      addTearDown(
        () => WidgetController.hitTestWarningShouldBeFatal = previousHitCheck,
      );
      Future<void> until(bool Function() ready) async {
        for (var i = 0; i < 600; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (ready()) return;
        }
        fail(
          'QuestionFile state not reached: ${find.byType(Text).evaluate().map((e) => (e.widget as Text).data).join(" | ")}',
        );
      }

      Future<void> click(Finder target) async {
        await tester.ensureVisible(target);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.tap(target);
      }

      Future<void> screenshot(String name) async {
        await tester.pump(const Duration(milliseconds: 400));
        final boundary =
            capture.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        await tester.runAsync(
          () =>
              File('$evidence/$name.png')
                  .writeAsBytes(data!.buffer.asUint8List()),
        );
        image.dispose();
      }

      Future<void> confirm() async {
        await until(() => find.text('检查后确认题目版本').evaluate().isNotEmpty);
        expect(find.text('保存本次作答'), findsNothing);
        await click(find.text('检查后确认题目版本'));
        await tester.pump(const Duration(milliseconds: 250));
        await click(find.text('确认题目版本'));
        await until(
          () =>
              find.text('保存本次作答').evaluate().isNotEmpty &&
              find.byType(LinearProgressIndicator).evaluate().isEmpty,
        );
      }

      await tester.pumpWidget(
        RepaintBoundary(key: capture, child: const StudyApp()),
      );
      await until(
        () =>
            find.byType(WorkspaceShell).evaluate().isNotEmpty &&
            find.text('添加资源').evaluate().isNotEmpty,
      );
      final shell = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final backend = shell.widget.backend;
      const scope = '/api/workspaces/default';
      late Map<String, dynamic> answered, unanswered;
      await tester.runAsync(() async {
        var job = await backend.request('POST', '$scope/resource-add-jobs', {
          'source_path': '$root/contracts/samples/question-files-v1',
        }) as Map;
        for (var i = 0; i < 200; i++) {
          job = await backend.request(
            'GET',
            '$scope/resource-add-jobs/${job['id']}',
          ) as Map;
          if (!['queued', 'running'].contains(job['status'])) break;
          await Future<void>.delayed(const Duration(milliseconds: 50));
        }
        expect(job['status'], 'completed');
        final results = job['results'] as List;
        Future<Map<String, dynamic>> resolve(
          String name,
        ) async => Map<String, dynamic>.from(
          await backend.request(
            'GET',
            '$scope/nodes/${results.firstWhere((r) => r['name'] == name)['resource_item_id']}',
          ) as Map,
        );
        answered = await resolve('有答案.md');
        unanswered = await resolve('待批改.md');
      });
      await click(find.byTooltip('刷新资源树'));
      await until(() => find.text('question-files-v1').evaluate().isNotEmpty);
      await click(find.text('question-files-v1'));
      shell.openResource(answered);
      await until(() => find.text('检查题目 / 作答').evaluate().isNotEmpty);
      await click(find.text('检查题目 / 作答'));
      await confirm();
      await until(() => find.byType(CheckboxListTile).evaluate().length == 2);
      await tester.ensureVisible(find.byType(CheckboxListTile).first);
      await click(find.byType(CheckboxListTile).first);
      await tester.ensureVisible(find.text('保存本次作答'));
      await click(find.text('保存本次作答'));
      await until(
        () => find.textContaining('作答已保存，得分 1').evaluate().isNotEmpty,
      );
      await tester.ensureVisible(find.textContaining('作答已保存，得分 1'));
      await screenshot('question-file-graded');
      await click(find.text('开始新一次作答'));
      await tester.ensureVisible(find.byType(CheckboxListTile).last);
      await click(find.byType(CheckboxListTile).last);
      await tester.ensureVisible(find.text('保存本次作答'));
      await click(find.text('保存本次作答'));
      await until(
        () => find.textContaining('作答已保存，得分 0').evaluate().isNotEmpty,
      );
      await tester.runAsync(() async {
        final history =
            await backend.request('GET', '$scope/attempt-history') as List;
        expect(history.length, 2);
        expect(
          history[0]['question_version_id'],
          history[1]['question_version_id'],
        );
        final moved = await backend.request(
          'PATCH',
          '$scope/nodes/${answered['resource_item_id']}',
          {'name': '改名后仍是同一道题.md', 'parent_id': null},
        );
        answered = Map<String, dynamic>.from(moved as Map);
      });
      shell.openResource(unanswered);
      await until(() => find.text('检查题目 / 作答').evaluate().isNotEmpty);
      await click(find.text('检查题目 / 作答'));
      await confirm();
      await tester.ensureVisible(find.byType(TextField));
      await tester.enterText(find.byType(TextField), '未提交的中文解题过程');
      shell.openResource(answered);
      await until(
        () => find.textContaining('作答已保存，得分 0').evaluate().isNotEmpty,
      );
      await click(find.text('重新检查题目文件'));
      await until(() => find.textContaining('当前文件未通过检查').evaluate().isNotEmpty);
      expect(find.text('检查后确认题目版本'), findsNothing);
      shell.openResource(unanswered);
      await until(() => find.byType(TextField).evaluate().isNotEmpty);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '未提交的中文解题过程',
      );
      await shell.flush();
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyW);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await until(() => find.text('保存草稿并关闭').evaluate().isNotEmpty);
      await click(find.text('保存草稿并关闭'));
      await until(() => find.byType(TextField).evaluate().isEmpty);
      shell.openResource(unanswered);
      await until(
        () =>
            find.byType(TextField).evaluate().isNotEmpty &&
            find.text('保存本次作答').evaluate().isNotEmpty,
      );
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '未提交的中文解题过程',
      );
      await tester.ensureVisible(find.text('保存本次作答'));
      await click(find.text('保存本次作答'));
      await until(() => find.text('作答已保存，待人工批改').evaluate().isNotEmpty);
      await tester.ensureVisible(find.text('作答已保存，待人工批改'));
      await screenshot('question-file-pending');
      await tester.runAsync(() async {
        final history =
            await backend.request('GET', '$scope/attempt-history') as List;
        expect(history.length, 3);
        expect(history.first['status'], 'pending_review');
        expect(
          history.every((row) => row['question_version_id'] != null),
          true,
        );
        final layout = await backend.request('GET', '$scope/layout') as Map;
        expect(
          (layout['tabs'] as List)
              .where(
                (t) => t['resource_item_id'] == answered['resource_item_id'],
              )
              .length,
          1,
        );
      });
      await shell.flush();
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(milliseconds: 300));
    },
    timeout: const Timeout(Duration(minutes: 10)),
  );
}
