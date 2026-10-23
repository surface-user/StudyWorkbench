import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/main.dart' as app;
import 'package:study_workbench/web_page.dart';

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
      await File('$root/docs/evidence/m0-question.png')
          .writeAsBytes(bytes!.buffer.asUint8List());
      image.dispose();
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
      await tester.tap(find.text('本地播放器'));
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
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
    },
  );
}
