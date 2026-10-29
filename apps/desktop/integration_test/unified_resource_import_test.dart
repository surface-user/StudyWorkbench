import 'dart:convert';
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

// Set STUDY_NATIVE_PICKER / STUDY_MANUAL_DROP for opt-in manual input.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'unified selection and drop callbacks stage before explicit import',
    (tester) async {
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      expect(Backend.testData, isNotEmpty);
      final capture = GlobalKey();
      Future<void> until(bool Function() done) async {
        for (var i = 0; i < 6000; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (done()) return;
        }
        fail('Waiting for native picker / Explorer drag input timed out');
      }

      Future<void> screenshot(String name) async {
        await tester.pumpAndSettle();
        final boundary =
            capture.currentContext!.findRenderObject() as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await File('$evidence/$name.png')
            .writeAsBytes(bytes!.buffer.asUint8List());
        image.dispose();
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
      await screenshot('navigation');
      await tester.ensureVisible(find.text('添加资源'));
      await tester.tap(find.text('添加资源'));
      await tester.pumpAndSettle();
      await screenshot('add-resources-empty');
      const nativePicker = bool.fromEnvironment('STUDY_NATIVE_PICKER');
      if (!nativePicker) {
        tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          const MethodChannel('study/desktop'),
          (call) async => call.method == 'chooseResourceFiles'
              ? [
                  '${Backend.testData}/../unified-native-source/picker-note.md',
                  '${Backend.testData}/../unified-native-source/picker-video.webm',
                ]
              : null,
        );
      }
      await tester.tap(find.text('添加文件'));
      await until(
        () =>
            find.text('picker-note.md').evaluate().isNotEmpty &&
            find.text('picker-video.webm').evaluate().isNotEmpty,
      );
      await screenshot('selection-staged');
      await tester.runAsync(() async {
        expect(
          await backend.request(
            'GET',
            '/api/workspaces/default/resource-add-jobs',
          ),
          isEmpty,
        );
        expect(
          await backend.request('GET', '/api/workspaces/default/nodes'),
          isEmpty,
        );
      });
      const manualDrop = bool.fromEnvironment('STUDY_MANUAL_DROP');
      if (!manualDrop) {
        await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
          'study/desktop',
          const StandardMethodCodec().encodeMethodCall(
            MethodCall('resourceDrop', [
              '${Backend.testData}/../unified-native-source/drop-only.md',
            ]),
          ),
          (_) {},
        );
      }
      await until(() => find.text('drop-only.md').evaluate().isNotEmpty);
      await screenshot('drop-callback-staged');
      await tester.tap(find.text('确认导入'));
      await until(() => find.text('已导入').evaluate().length == 3);
      await screenshot('import-completed');
      await tester.tap(find.text('完成'));
      await until(
        () =>
            find.byType(AlertDialog).evaluate().isEmpty &&
            find.text('drop-only.md').evaluate().isNotEmpty,
      );
      await screenshot('resource-tree');
      await tester.runAsync(() async {
        final nodes = await backend.request(
          'GET',
          '/api/workspaces/default/nodes',
        ) as List;
        expect(nodes.length, 3);
        expect(nodes.where((n) => n['kind'] == 'media').length, 1);
        expect(
          await backend.request('GET', '/api/workspaces/default/imports'),
          isEmpty,
        );
        expect(shell.layouts['default']!.tabs, isEmpty);
        await File('$evidence/results.json').writeAsString(
          jsonEncode({
            'native_multi_select': nativePicker,
            'selection_callback_injected': !nativePicker,
            'explorer_drop': manualDrop,
            'drop_callback_injected': !manualDrop,
            'staging_did_not_copy': true,
            'imported_nodes': nodes.length,
            'no_auto_analysis': true,
            'no_permanent_import_tab': true,
          }),
        );
      });
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
    },
  );
}
