import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/web_page.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'M1 workspaces, scoped attempts, dynamic tabs and actual restart',
    (tester) async {
      Future<void> until(bool Function() predicate) async {
        for (var i = 0; i < 150; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (predicate()) return;
        }
        final text = find
            .byType(Text)
            .evaluate()
            .map((e) => (e.widget as Text).data)
            .whereType<String>()
            .join(' | ');
        fail('Windows M1 timed out: $text');
      }

      WorkspaceShellState shell() => tester.state(find.byType(WorkspaceShell));
      Future<void> addTab(String title) async {
        await tester.tap(find.byTooltip('新建标签页'));
        await tester.pumpAndSettle();
        await tester.tap(find.text(title).last);
        await tester.pump(const Duration(milliseconds: 500));
      }

      await tester.pumpWidget(const StudyApp());
      await until(() => find.text('添加资源').evaluate().isNotEmpty);
      final defaultName =
          shell().spaces.firstWhere((s) => s['id'] == 'default')['name']
              as String;
      if (shell().layouts[shell().activeSpace]!.tabs.isEmpty) {
        await addTab('富内容题目');
      }
      await until(() => find.text('选择答案  ').evaluate().isNotEmpty);
      await tester.tap(find.text('选择答案  ').first);
      await until(() => find.textContaining('得分 1.0').evaluate().isNotEmpty);
      await tester.tap(find.text('新建工作空间'));
      await tester.pumpAndSettle();
      final name = 'M1 数学 ${DateTime.now().millisecondsSinceEpoch}';
      await tester.enterText(
        find.byKey(const ValueKey('workspace-name')),
        name,
      );
      await tester.tap(find.text('创建'));
      await until(() => shell().activeSpace != 'default');
      await addTab('富内容题目');
      await until(() => find.text('选择答案  ').evaluate().isNotEmpty);
      final workspaceId = shell().activeSpace!;
      await tester.tap(find.text('选择答案  ').first);
      await until(
        () => find.text('已保存，得分 1.0 · 共 1 次作答').evaluate().isNotEmpty,
      );
      await tester.enterText(find.byType(TextField).first, '第一页中文草稿');
      await addTab('富内容题目');
      await until(() => find.byType(TextField).evaluate().isNotEmpty);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '',
      );
      await tester.enterText(find.byType(TextField).first, '第二页保留草稿');
      final secondTab = shell().layouts[workspaceId]!.activeId!;
      await tester.tap(find.byKey(ValueKey('close-tab-$secondTab')));
      await tester.pump(const Duration(milliseconds: 200));
      if (find.text('保存草稿并关闭').evaluate().isNotEmpty) {
        await tester.tap(find.text('保存草稿并关闭'));
      }
      await tester.pump(const Duration(milliseconds: 500));
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第一页中文草稿',
      );
      await tester.tap(find.byTooltip('重新打开关闭的标签页'));
      await tester.pump(const Duration(milliseconds: 500));
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第二页保留草稿',
      );
      await tester.tap(find.text(defaultName));
      await until(() => shell().activeSpace == 'default');
      await tester.tap(find.text(name));
      await until(() => shell().activeSpace == workspaceId);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第二页保留草稿',
      );
      final row = find.byKey(ValueKey('workspace-$workspaceId'));
      await tester.tap(
        find.descendant(
          of: row,
          matching: find.byType(PopupMenuButton<String>),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('重命名'));
      await tester.pumpAndSettle();
      final renamed = '$name 已重命名';
      await tester.enterText(
        find.byKey(const ValueKey('workspace-name')),
        renamed,
      );
      await tester.tap(find.text('保存名称'));
      await until(() => find.text(renamed).evaluate().isNotEmpty);
      await shell().flush();

      // Recreate the real desktop widget and its Python process against the same SQLite file.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      final capture = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(key: capture, child: const StudyApp()),
      );
      await until(
        () =>
            find.byType(WorkspaceShell).evaluate().isNotEmpty &&
            !shell().loading,
      );
      await until(() => find.byType(TextField).evaluate().isNotEmpty);
      expect(shell().activeSpace, workspaceId);
      expect(shell().layouts[workspaceId]!.activeId, secondTab);
      expect(find.text(renamed), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第二页保留草稿',
      );
      final boundary =
          capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await boundary.toImage(pixelRatio: 1);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      if (evidence.isNotEmpty) {
        await File('$evidence/m1-workbench.png')
            .writeAsBytes(bytes!.buffer.asUint8List());
      }
      image.dispose();

      await tester.tap(
        find.descendant(
          of: find.byKey(ValueKey('workspace-$workspaceId')),
          matching: find.byType(PopupMenuButton<String>),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('移除并保留数据'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(shell().activeSpace, workspaceId);
      await tester.tap(
        find.descendant(
          of: find.byKey(ValueKey('workspace-$workspaceId')),
          matching: find.byType(PopupMenuButton<String>),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('移除并保留数据'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认移除并保留数据'));
      await until(() => shell().activeSpace == 'default');
      await tester.tap(find.text('已移除工作空间'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(SimpleDialog),
          matching: find.text(renamed),
        ),
      );
      await until(
        () =>
            find.byType(SimpleDialog).evaluate().isEmpty &&
            shell().archived.every((v) => v['id'] != workspaceId),
      );
      await tester.tap(find.byKey(ValueKey('workspace-$workspaceId')));
      await until(() => shell().activeSpace == workspaceId);
      await until(() => find.text('选择答案  ').evaluate().isNotEmpty);
      await tester.tap(find.text('选择答案  ').first);
      await until(
        () => find.text('已保存，得分 1.0 · 共 2 次作答').evaluate().isNotEmpty,
      );
      await shell().flush();
      expect(tester.takeException(), isNull);

      await tester.drag(
        find.byKey(ValueKey('select-tab-$secondTab')),
        const Offset(-180, 0),
      );
      await tester.pumpAndSettle();
      expect(shell().layouts[workspaceId]!.tabs.first.id, secondTab);
      await addTab('网页');
      await until(() => find.byType(WebPage).evaluate().isNotEmpty);
      final dynamic webState = tester.state(find.byType(WebPage));
      await until(() => webState.controller != null);
      await tester.tap(find.byKey(ValueKey('select-tab-$secondTab')));
      await tester.pump(const Duration(milliseconds: 500));
      final oldData = shell().widget.backend.dataDir;
      final original = File('$oldData/原文件/中文 sample.txt');
      await original.parent.create(recursive: true);
      await original.writeAsString('M1 原件保留验证');
      // Reject a nonempty destination and restart against the unchanged source.
      await tester.tap(find.text('数据与存储设置'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('data-directory')),
        original.parent.path,
      );
      await tester.tap(find.text('确认迁移并重启工作台'));
      await until(
        () =>
            find.byType(WorkspaceShell).evaluate().isNotEmpty &&
            !shell().loading,
      );
      expect(shell().widget.backend.dataDir, oldData);
      expect(await original.readAsString(), 'M1 原件保留验证');
      await until(() => find.text('关闭提示').evaluate().isNotEmpty);
      await tester.tap(find.text('关闭提示'));
      await tester.pumpAndSettle();

      final target = '$oldData-moved 中文';
      await tester.tap(find.text('数据与存储设置'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('data-directory')),
        target,
      );
      await tester.tap(find.text('确认迁移并重启工作台'));
      await until(
        () =>
            find.byType(WorkspaceShell).evaluate().isNotEmpty &&
            !shell().loading,
      );
      expect(shell().widget.backend.dataDir, target);
      expect(shell().activeSpace, workspaceId);
      await until(() => find.byType(TextField).evaluate().isNotEmpty);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第二页保留草稿',
      );
      expect(
        await File('$target/原文件/中文 sample.txt').readAsString(),
        'M1 原件保留验证',
      );
      expect(await original.exists(), true);
      expect(await File('$target/migration-receipt.json').exists(), true);
      final attempts = await shell().widget.backend.request(
        'GET',
        '/api/workspaces/$workspaceId/attempts',
      ) as List;
      expect(attempts.length, 2);
      await shell().flush();
      final previousPid = shell().widget.backend.process.pid;
      shell().widget.backend.process.kill();
      await until(() => find.text('重启后端并恢复页面').evaluate().isNotEmpty);
      await tester.tap(find.text('重启后端并恢复页面'));
      await until(
        () =>
            find.byType(WorkspaceShell).evaluate().isNotEmpty &&
            !shell().loading,
      );
      expect(shell().widget.backend.process.pid, isNot(previousPid));
      expect(shell().widget.backend.dataDir, target);
      await until(() => find.byType(TextField).evaluate().isNotEmpty);
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller!.text,
        '第二页保留草稿',
      );
      await shell().flush();
      // Exercise the application's cancellable exit callback before the debounce fires.
      await tester.enterText(find.byType(TextField).first, '退出前最后中文草稿');
      expect(
        await tester.binding.handleRequestAppExit(),
        ui.AppExitResponse.exit,
      );
      expect(await shell().widget.backend.process.exitCode, 0);
      final reopened = await Backend.start(dataDir: target);
      try {
        final saved = await reopened.request(
          'GET',
          '/api/workspaces/$workspaceId/layout',
        );
        expect(
          (saved['tabs'] as List).firstWhere(
            (tab) => tab['id'] == secondTab,
          )['draft'],
          '退出前最后中文草稿',
        );
      } finally {
        await reopened.shutdown();
      }
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
    },
  );
}
