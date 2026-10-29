import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Windows managed resource tree and unified link addition preserve layout',
    (tester) async {
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      expect(Backend.testData, isNotEmpty);
      final capture = GlobalKey();
      Future<void> until(bool Function() condition) async {
        for (var i = 0; i < 150; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (condition()) return;
        }
        fail('Windows resource explorer did not reach expected state');
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
      const prefix = '/api/workspaces/default';
      final before = await tester.runAsync(
        () => backend.request('GET', '$prefix/layout'),
      );
      expect(before['tabs'], isEmpty);
      expect(find.text('我的学习空间'), findsOneWidget);
      final source = Directory('${Backend.testData}-source/示例资料');
      Map<String, dynamic>? completed;
      await tester.runAsync(() async {
        await Directory('${source.path}/章节').create(recursive: true);
        await File('${source.path}/阅读.md')
            .writeAsString('# 阅读资料\n保留原文，不要求标准答案。');
        await File('${source.path}/章节/讲义.txt').writeAsString('自编回归样本');
        final started = await backend.request(
          'POST',
          '$prefix/resource-add-jobs',
          {'source_path': source.path},
        ) as Map;
        for (var i = 0; i < 100; i++) {
          final job = await backend.request(
            'GET',
            '$prefix/resource-add-jobs/${started['id']}',
          ) as Map<String, dynamic>;
          if (!['running', 'queued'].contains(job['status'])) {
            completed = job;
            break;
          }
          await Future<void>.delayed(const Duration(milliseconds: 50));
        }
      });
      expect(completed?['status'], 'completed');
      expect((completed!['results'] as List).length, 4);
      await tester.tap(find.byTooltip('刷新资源树'));
      await until(() => find.text('示例资料').evaluate().isNotEmpty);
      await tester.ensureVisible(find.text('示例资料'));
      await tester.tap(find.text('示例资料'));
      await until(() => find.text('阅读.md').evaluate().isNotEmpty);
      await tester.ensureVisible(find.text('阅读.md'));
      await tester.tap(
        find.descendant(
          of: find.widgetWithText(ListTile, '阅读.md'),
          matching: find.byType(PopupMenuButton<String>),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('详情 / 改名 / 移动'));
      await until(() => find.text('资源详情与组织').evaluate().isNotEmpty);
      expect(find.textContaining('状态：可用'), findsOneWidget);
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('添加资源'));
      await tester.tap(find.text('添加资源'));
      await until(() => find.text('保存网页链接').evaluate().isNotEmpty);
      await tester.enterText(
        find.widgetWithText(TextField, '新文件夹 / 链接名称'),
        '参考网页',
      );
      await tester.enterText(
        find.widgetWithText(TextField, '网页 HTTPS 地址'),
        'https://example.com/reading',
      );
      await tester.tap(find.text('保存网页链接'));
      await until(
        () =>
            find.byType(AlertDialog).evaluate().isEmpty &&
            find.text('参考网页').evaluate().isNotEmpty,
      );
      await tester.ensureVisible(find.text('示例资料'));
      await tester.tap(find.text('示例资料'));
      await until(() => find.text('阅读.md').evaluate().isNotEmpty);
      await tester.pumpAndSettle();
      final boundary =
          capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final screenshot = await boundary.toImage(pixelRatio: 1);
      final bytes = await screenshot.toByteData(format: ui.ImageByteFormat.png);
      await File('$evidence/resource-explorer-windows.png')
          .writeAsBytes(bytes!.buffer.asUint8List());
      screenshot.dispose();
      final after = await tester.runAsync(
        () => backend.request('GET', '$prefix/layout'),
      );
      expect(after, before, reason: 'R1 must preserve v1 layout and drafts');
      expect(
        await File('${source.path}/阅读.md').readAsString(),
        '# 阅读资料\n保留原文，不要求标准答案。',
      );
      await File('$evidence/native-results.json').writeAsString(
        jsonEncode({
          'copy_status': completed!['status'],
          'copied_nodes': 4,
          'source_retained': true,
          'layout_unchanged': true,
          'link_added_via_ui': true,
        }),
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
    },
  );
}
