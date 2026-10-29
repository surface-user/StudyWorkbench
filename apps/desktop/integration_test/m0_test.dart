import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/main.dart' as app;
import 'package:study_workbench/web_page.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Windows M0 backend, grading, WebView2 and actual video decoding',
    (tester) async {
      final capture = GlobalKey();
      runApp(RepaintBoundary(key: capture, child: const app.StudyApp()));
      Future<void> until(bool Function() condition) async {
        for (var i = 0; i < 100; i++) {
          await tester.pump(const Duration(milliseconds: 200));
          if (condition()) return;
        }
        final status = find
            .byType(Text)
            .evaluate()
            .map((element) => (element.widget as Text).data)
            .whereType<String>()
            .join(' | ');
        fail(
          'Timed out waiting for Windows prototype. Visible status: $status',
        );
      }

      await until(() => find.text('本地后端已连接').evaluate().isNotEmpty);
      final initialShell = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      if (initialShell.layouts[initialShell.activeSpace]!.tabs.isEmpty) {
        await tester.tap(find.byTooltip('新建标签页'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('富内容题目'));
      }
      await until(() => find.text('选择答案  ').evaluate().isNotEmpty);
      await tester.tap(find.text('选择答案  ').first);
      await until(() => find.textContaining('得分 1.0').evaluate().isNotEmpty);
      await tester.enterText(find.byType(TextField).first, '原函数为 x^3/3，代入上下限。');
      await tester.tap(find.text('提交主观作答'));
      await until(() => find.textContaining('待人工批改').evaluate().isNotEmpty);
      final boundary =
          capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await boundary.toImage(pixelRatio: 1);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      const root = String.fromEnvironment('STUDY_ROOT');
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      final screenshot = evidence.isEmpty
          ? '$root/docs/evidence/m0-question.png'
          : '$evidence/m0-packaged-question.png';
      await File(screenshot).writeAsBytes(bytes!.buffer.asUint8List());
      image.dispose();
      await tester.tap(find.byTooltip('新建标签页'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('网页'));
      await tester.pump(const Duration(seconds: 2));
      final dynamic browserState = tester.state(find.byType(WebPage).first);
      await until(() => browserState.controller != null);
      expect(
        await browserState.controller.evaluateJavascript(
          source: 'document.querySelector("h2").textContent',
        ),
        '内置网页',
      );
      await tester.tap(find.byTooltip('新建标签页'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('本地播放器'));
      await tester.pump(const Duration(seconds: 2));
      final workbench = tester.widget<WorkspaceShell>(
        find.byType(WorkspaceShell),
      );
      final workbenchState = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      const sample = String.fromEnvironment('STUDY_MEDIA');
      expect(
        sample,
        isNotEmpty,
        reason: 'Native media regression requires a real generated sample',
      );
      await tester.runAsync(
        () => workbench.backend.uploadMedia(
          workbenchState.activeSpace!,
          File(sample),
          (_) {},
        ),
      );
      await tester.tap(find.text('刷新媒体库'));
      await until(
        () =>
            find.text(File(sample).uri.pathSegments.last).evaluate().isNotEmpty,
      );
      await tester.tap(find.text(File(sample).uri.pathSegments.last));
      await tester.pump(const Duration(seconds: 2));
      final dynamic playerState = tester.state(find.byType(WebPage));
      await until(() => playerState.controller != null);
      var metadata = false;
      for (var i = 0; i < 50; i++) {
        metadata =
            await playerState.controller.evaluateJavascript(
              source: 'document.querySelector("video").readyState >= 1',
            ) ==
            true;
        if (metadata) break;
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(
        metadata,
        true,
        reason:
            'Real local sample must decode, not just render a video element',
      );
      await playerState.controller.evaluateJavascript(
        source: 'document.querySelector("video").muted=true;document.querySelector("video").play();',
      );
      await tester.pump(const Duration(seconds: 1));
      final time = await playerState.controller.evaluateJavascript(
        source: 'document.querySelector("video").currentTime',
      );
      expect((time as num) > 0, true);
      await playerState.controller.evaluateJavascript(
        source: 'document.querySelector("video").pause();document.querySelector("video").currentTime=2;document.querySelector("video").playbackRate=1.5;',
      );
      await tester.pump(const Duration(milliseconds: 500));
      expect(
        await playerState.controller.evaluateJavascript(
          source: 'document.querySelector("video").paused',
        ),
        true,
      );
      expect(
        await playerState.controller.evaluateJavascript(
          source: 'document.querySelector("video").playbackRate',
        ),
        1.5,
      );
      final seekTime = await playerState.controller.evaluateJavascript(
        source: 'document.querySelector("video").currentTime',
      );
      expect((seekTime as num).toDouble(), closeTo(2, 0.25));
      // Test the real Blob/track decoder; the native file chooser is a separate UI check.
      await playerState.controller.evaluateJavascript(
        source: '''
          const transfer = new DataTransfer();
          transfer.items.add(new File([
            'WEBVTT\\n\\n00:00:01.000 --> 00:00:04.000\\nM0 中文字幕\\n'
          ], 'm0.vtt', {type: 'text/vtt'}));
          const input = document.querySelector('input[type="file"]');
          input.files = transfer.files;
          input.dispatchEvent(new Event('change', {bubbles: true}));
        ''',
      );
      var subtitleLoaded = false;
      for (var i = 0; i < 50; i++) {
        subtitleLoaded =
            await playerState.controller.evaluateJavascript(
              source: 'document.querySelector("track")?.readyState === 2',
            ) ==
            true;
        if (subtitleLoaded) break;
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(
        subtitleLoaded,
        true,
        reason: 'Selected WebVTT must load as a real track',
      );
      expect(
        await playerState.controller.evaluateJavascript(
          source: 'document.querySelector("video").textTracks[0].cues[0].text',
        ),
        'M0 中文字幕',
      );
      var stateSaved = false;
      for (var i = 0; i < 30; i++) {
        final entries = await tester.runAsync(
          () => workbench.backend.request(
            'GET',
            '/api/workspaces/${workbenchState.activeSpace}/media',
          ),
        ) as List;
        stateSaved = entries.any(
          (item) =>
              item['playback']['speed'] == 1.5 &&
              ((item['playback']['position'] as num?)?.toDouble() ?? -1) >
                  1.75 &&
              ((item['playback']['position'] as num?)?.toDouble() ?? -1) <
                  2.25 &&
              (item['playback']['subtitle'] as String? ?? '').contains(
                'M0 中文字幕',
              ),
        );
        if (stateSaved) break;
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(
        stateSaved,
        true,
        reason:
            'Position, rate and subtitles must actually persist in the backend',
      );
      final shell = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final playerTab = shell.layouts[shell.activeSpace]!.activeId!;
      await tester.tap(find.byKey(ValueKey('close-tab-$playerTab')));
      await tester.pump(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
      await tester.tap(find.byTooltip('重新打开关闭的标签页'));
      await tester.pump(const Duration(seconds: 2));
      await until(
        () =>
            find.text(File(sample).uri.pathSegments.last).evaluate().isNotEmpty,
      );
      await tester.tap(find.text(File(sample).uri.pathSegments.last));
      await tester.pump(const Duration(seconds: 2));
      final dynamic reopened = tester.state(find.byType(WebPage));
      await until(() => reopened.controller != null);
      var reopenedMetadata = false;
      for (var i = 0; i < 50; i++) {
        reopenedMetadata =
            await reopened.controller.evaluateJavascript(
              source: 'document.querySelector("video").readyState >= 1',
            ) ==
            true;
        if (reopenedMetadata) break;
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(
        reopenedMetadata,
        true,
        reason: 'Closed native player must reopen and decode',
      );
      expect(
        await reopened.controller.evaluateJavascript(
          source: 'document.querySelector("video").playbackRate',
        ),
        1.5,
      );
      expect(
        (await reopened.controller.evaluateJavascript(
          source: 'document.querySelector("video").currentTime',
        ) as num).toDouble(),
        closeTo(2, .25),
      );
      var restoredSubtitle = false;
      for (var i = 0; i < 30; i++) {
        restoredSubtitle =
            await reopened.controller.evaluateJavascript(
              source: 'document.querySelector("video").textTracks[0]?.cues?.[0]?.text === "M0 中文字幕"',
            ) ==
            true;
        if (restoredSubtitle) break;
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(
        restoredSubtitle,
        true,
        reason: 'Saved WebVTT must restore after closing the native player',
      );
      await shell.flush();
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
    },
  );
}
