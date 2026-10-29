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
    'Windows Office conversion, PDF pages and restored resource tabs',
    (tester) async {
      const root = String.fromEnvironment('STUDY_ROOT');
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      expect(Backend.testData, isNotEmpty);
      final capture = GlobalKey();
      Future<void> until(bool Function() ready) async {
        for (var i = 0; i < 6000; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (ready()) return;
        }
        fail('Office UI deadline exceeded');
      }

      await tester.pumpWidget(
        RepaintBoundary(key: capture, child: const StudyApp()),
      );
      await until(() => find.byType(WorkspaceShell).evaluate().isNotEmpty);
      final shell = tester.state<WorkspaceShellState>(
        find.byType(WorkspaceShell),
      );
      final backend = shell.widget.backend;
      const prefix = '/api/workspaces/default';
      final nodes = <Map<String, dynamic>>[];
      await tester.runAsync(() async {
        for (final name in ['中文公式.docx', '中文图表.pptx']) {
          final job = await backend.request(
            'POST',
            '$prefix/resource-add-jobs',
            {'source_path': '$root/.local/r3-office/samples/$name'},
          );
          Map? added;
          for (var i = 0; i < 200; i++) {
            added = await backend.request(
              'GET',
              '$prefix/resource-add-jobs/${job['id']}',
            ) as Map;
            if (!['queued', 'running'].contains(added['status'])) break;
            await Future<void>.delayed(const Duration(milliseconds: 50));
          }
          expect(added!['status'], 'completed');
          nodes.add(
            Map<String, dynamic>.from((added['results'] as List).first as Map),
          );
        }
      });
      for (var index = 0; index < nodes.length; index++) {
        shell.openResource(nodes[index]);
        await until(() => find.text('生成分页预览').evaluate().isNotEmpty);
        expect(find.text('打开分页预览'), findsNothing);
        await tester.tap(find.text('生成分页预览'));
        await until(
          () =>
              find.textContaining('第1页 /').evaluate().isNotEmpty &&
              find.byType(Image).evaluate().isNotEmpty,
        );
        if (index == 0) {
          await tester.tap(find.text('Word结构预览'));
          await until(
            () => find.textContaining('Word结构预览 ·').evaluate().isNotEmpty,
          );
          await tester.tap(find.text('打开分页预览'));
          await until(() => find.textContaining('第1页 /').evaluate().isNotEmpty);
        } else {
          expect(find.text('第1页 / 2页'), findsOneWidget);
          await tester.pump(const Duration(milliseconds: 300));
          final boundary =
              capture.currentContext!.findRenderObject()!
                  as RenderRepaintBoundary;
          final image = await boundary.toImage(pixelRatio: 1);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          await tester.runAsync(
            () =>
                File('$evidence/office-chart.png')
                    .writeAsBytes(bytes!.buffer.asUint8List()),
          );
          image.dispose();
          await tester.tap(find.byTooltip('下一页'));
          await until(() => find.text('第2页 / 2页').evaluate().isNotEmpty);
        }
        await until(
          () => find.byType(LinearProgressIndicator).evaluate().isEmpty,
        );
        await tester.pump(const Duration(milliseconds: 500));
        final boundary =
            capture.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await tester.runAsync(
          () =>
              File('$evidence/office-${index + 1}.png')
                  .writeAsBytes(bytes!.buffer.asUint8List()),
        );
        image.dispose();
      }
      await shell.flush();
      shell.openResource(nodes.first);
      await until(() => find.textContaining('第1页 /').evaluate().isNotEmpty);
      shell.openResource(nodes.last);
      await until(() => find.text('第2页 / 2页').evaluate().isNotEmpty);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(milliseconds: 300));
    },
    timeout: const Timeout(Duration(minutes: 25)),
  );
}
