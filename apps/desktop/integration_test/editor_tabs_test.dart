import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/editor_tab_bar.dart';
import 'package:study_workbench/import_page.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/media_page.dart';
import 'package:study_workbench/question_page.dart';
import 'package:study_workbench/study_page.dart';
import 'package:study_workbench/web_page.dart';
import 'package:study_workbench/webview_lifecycle.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Windows editor tabs preserve five page types and release native resources',
    (tester) async {
      final capture = GlobalKey();
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      const sample = String.fromEnvironment('STUDY_MEDIA');
      final results = <String, dynamic>{};
      WorkspaceShellState shell() => tester.state(find.byType(WorkspaceShell));
      Future<void> until(bool Function() condition) async {
        for (var i = 0; i < 150; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (condition()) return;
        }
        fail(
          'Timed out: ${find.byType(Text).evaluate().map((e) => (e.widget as Text).data).join(' | ')}',
        );
      }

      Future<void> screenshot(String name) async {
        await tester.pump();
        final boundary =
            capture.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await File('$evidence/$name.png')
            .writeAsBytes(bytes!.buffer.asUint8List());
        image.dispose();
      }

      Future<String> add(String label) async {
        await tester.tap(find.byTooltip('新建标签页'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(PopupMenuItem<String>, label));
        await tester.pump();
        return shell().layouts[shell().activeSpace]!.activeId!;
      }

      Future<void> select(String id) async {
        // Overflow list is also the keyboard-accessible route to offscreen tabs.
        await tester.tap(find.byTooltip('标签列表与更多操作'));
        await tester.pumpAndSettle();
        final menu = find.byWidgetPredicate(
          (w) => w is PopupMenuItem<String> && w.value == id,
        );
        await tester.tap(menu);
        await tester.pump(const Duration(milliseconds: 300));
      }

      Future<void> shortcut(
        LogicalKeyboardKey key, {
        bool shift = false,
      }) async {
        await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
        if (shift) await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
        await tester.sendKeyEvent(key);
        if (shift) await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
        await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
        await tester.pump(const Duration(milliseconds: 150));
      }

      await tester.pumpWidget(
        RepaintBoundary(key: capture, child: const StudyApp()),
      );
      await until(() => find.text('添加资源').evaluate().isNotEmpty);
      if (shell().layouts[shell().activeSpace]!.tabs.isEmpty) {
        await add('富内容题目');
      }
      await until(
        () =>
            find.byType(QuestionPage).evaluate().isNotEmpty &&
            find.byType(TextField).evaluate().isNotEmpty,
      );
      final first = shell().layouts[shell().activeSpace]!.activeId!;
      final questionState = tester.state(find.byType(QuestionPage));
      await tester.enterText(find.byType(TextField).first, '标签切换后保留的中文作答草稿');
      await shell().flush();

      final import = await add('导入与资料库');
      await until(
        () =>
            find.text('按题目标题检索').evaluate().isNotEmpty &&
            !shell().layouts[shell().activeSpace]!.tabs.last.loading,
      );
      final importState = tester.state(find.byType(ImportPage));
      await tester.enterText(
        find.descendant(
          of: find.byType(ImportPage),
          matching: find.byType(TextField),
        ),
        '检索草稿',
      );
      final study = await add('题库与学习计划');
      await until(
        () => !shell().layouts[shell().activeSpace]!.tabs.last.loading,
      );
      final studyState = tester.state(find.byType(StudyPage));
      final player = await add('本地播放器');
      await until(
        () =>
            find.text('刷新媒体库').evaluate().isNotEmpty &&
            !shell().layouts[shell().activeSpace]!.tabs.last.loading,
      );
      final backend = shell().widget.backend;
      await tester.runAsync(
        () => backend.uploadMedia(shell().activeSpace!, File(sample), (_) {}),
      );
      await tester.tap(find.text('刷新媒体库'));
      final filename = File(sample).uri.pathSegments.last;
      await until(() => find.text(filename).evaluate().isNotEmpty);
      await tester.tap(find.text(filename));
      await until(
        () => find
            .descendant(
              of: find.byType(MediaPage),
              matching: find.byType(WebPage),
            )
            .evaluate()
            .isNotEmpty,
      );
      final dynamic nativePlayer = tester.state(
        find.descendant(
          of: find.byType(MediaPage),
          matching: find.byType(WebPage),
        ),
      );
      await until(() => nativePlayer.controller != null);
      var decoded = false;
      for (var i = 0; i < 100; i++) {
        decoded =
            await nativePlayer.controller.evaluateJavascript(
              source: 'document.querySelector("video")?.readyState >= 1',
            ) ==
            true;
        if (decoded) break;
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(decoded, true);
      await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").pause();document.querySelector("video").currentTime=2;document.querySelector("video").playbackRate=1.5;',
      );
      await tester.pump(const Duration(milliseconds: 500));

      final web = await add('网页');
      expect(shell().layouts[shell().activeSpace]!.tabs, hasLength(5));
      if (shell().layouts[shell().activeSpace]!.tabs.last.loading) {
        await screenshot('editor-five-loading');
        results['loadingScreenshot'] = true;
      }
      final dynamic browser = tester.state(find.byType(WebPage));
      await until(() => browser.controller != null);
      await tester.pump(const Duration(seconds: 1));
      await browser.controller.evaluateJavascript(
        source: 'document.title="离线网页 · 保留浏览状态与长标题的实际窗口验证";window.editorTabMarker="retained";',
      );
      await tester.pump(const Duration(milliseconds: 300));
      await screenshot('editor-five-web');
      final controller = browser.controller;

      for (var i = 0; i < 6; i++) {
        await shortcut(LogicalKeyboardKey.digit1);
        await shortcut(LogicalKeyboardKey.digit9);
      }
      expect(shell().layouts[shell().activeSpace]!.activeId, web);
      expect(tester.state(find.byType(WebPage)), same(browser));
      expect(browser.controller, same(controller));
      expect(
        await controller.evaluateJavascript(source: 'window.editorTabMarker'),
        'retained',
      );
      results['webInstanceAndDocumentRetained'] = true;

      await select(first);
      expect(tester.state(find.byType(QuestionPage)), same(questionState));
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '标签切换后保留的中文作答草稿',
      );
      await screenshot('editor-five-question');
      await select(import);
      expect(tester.state(find.byType(ImportPage)), same(importState));
      expect(
        tester
            .widget<EditableText>(
              find.descendant(
                of: find.byType(ImportPage),
                matching: find.byType(EditableText),
              ),
            )
            .controller
            .text,
        '检索草稿',
      );
      await select(study);
      expect(tester.state(find.byType(StudyPage)), same(studyState));
      await select(player);
      expect(tester.state(find.byType(WebPage)), same(nativePlayer));
      final time = await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").currentTime',
      ) as num;
      expect(time, closeTo(2, 0.3));
      expect(
        await nativePlayer.controller.evaluateJavascript(
          source: 'document.querySelector("video").playbackRate',
        ),
        1.5,
      );
      results['pausedMediaTimeRetained'] = time;
      results['questionImportStudyInstancesRetained'] = true;
      final pointer = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await pointer.addPointer();
      await pointer.moveTo(
        tester.getCenter(find.byKey(ValueKey('select-tab-$first'))),
      );
      await tester.pump(const Duration(milliseconds: 200));
      await screenshot('editor-five-hover-player');
      await pointer.removePointer();
      await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").muted=true;document.querySelector("video").currentTime=1;document.querySelector("video").playbackRate=0.5;document.querySelector("video").play();',
      );
      await select(first);
      await tester.pump(const Duration(milliseconds: 700));
      await select(player);
      final backgroundTime = await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").currentTime',
      ) as num;
      expect(backgroundTime, greaterThan(1));
      expect(
        await nativePlayer.controller.evaluateJavascript(
          source: 'document.querySelector("video").paused',
        ),
        false,
      );
      results['backgroundPlaybackContinues'] = true;
      await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").pause();document.querySelector("video").currentTime=2;',
      );

      // A middle close releases its page and activates its left neighbour.
      await select(study);
      await tester.tap(find.byKey(ValueKey('close-tab-$study')));
      await tester.pump(const Duration(milliseconds: 60));
      await screenshot('editor-middle-closing');
      await tester.pump(const Duration(milliseconds: 350));
      expect(shell().layouts[shell().activeSpace]!.activeId, import);
      expect(studyState.mounted, false);
      await shortcut(LogicalKeyboardKey.keyT, shift: true);
      expect(shell().layouts[shell().activeSpace]!.activeId, study);
      expect(
        browser.mounted,
        true,
        reason: 'closing/reopening a sibling must preserve browser State',
      );
      expect(
        await controller.evaluateJavascript(source: 'window.editorTabMarker'),
        'retained',
        reason: 'sibling close must preserve native document',
      );

      // Actual backend outage must leave the tab controls usable.
      backend.process.kill();
      await until(() => find.text('重启后端并恢复页面').evaluate().isNotEmpty);
      final offlineQuestion = await add('富内容题目');
      await until(
        () => shell().layouts[shell().activeSpace]!.tabs.last.error != null,
      );
      await screenshot('editor-offline-error');
      await select(web);
      expect(
        browser.mounted,
        true,
        reason: 'outage must preserve browser State',
      );
      expect(tester.state(find.byType(WebPage)), same(browser));
      expect(
        browser.controller,
        same(controller),
        reason: 'outage must preserve controller',
      );
      expect(
        await controller.evaluateJavascript(source: 'window.editorTabMarker'),
        'retained',
      );
      results['offlineTabInteraction'] = true;
      await select(offlineQuestion);
      await shortcut(LogicalKeyboardKey.keyW);
      expect(
        shell().layouts[shell().activeSpace]!.tabs.any(
          (t) => t.id == offlineQuestion,
        ),
        false,
      );
      results['tabBarHeight'] = tester
          .getSize(find.byType(EditorTabBar))
          .height;
      expect(results['tabBarHeight'], 38);
      expect(tester.takeException(), isNull);
      await File('$evidence/native-results.json')
          .writeAsString(const JsonEncoder.withIndent('  ').convert(results));
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      await drainWebEnvironments();
      expect(browser.mounted, false);
      expect(nativePlayer.mounted, false);
    },
  );
}
