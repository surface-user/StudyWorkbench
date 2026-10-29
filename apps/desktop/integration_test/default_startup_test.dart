import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/main.dart' as app;
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('native default profile starts without a storage picker', (
    tester,
  ) async {
    expect(Backend.testData, isEmpty);
    final root = await Backend.storageRoot;
    expect(Directory(root).isAbsolute, true);
    final configured = await Backend.configuredData();
    final expected = configured ?? await Backend.defaultData;
    runApp(const app.StudyApp());
    for (
      var i = 0;
      i < 150 && find.byType(WorkspaceShell).evaluate().isEmpty;
      i++
    ) {
      await tester.pump(const Duration(milliseconds: 200));
    }
    expect(find.text('选择学习数据位置'), findsNothing);
    expect(
      find.byType(WorkspaceShell),
      findsOneWidget,
      reason: find
          .byType(Text)
          .evaluate()
          .map((e) => (e.widget as Text).data)
          .join(' | '),
    );
    final shell = tester.widget<WorkspaceShell>(find.byType(WorkspaceShell));
    expect(shell.backend.dataDir, expected);
    expect((await shell.backend.request('GET', '/api/health'))['status'], 'ok');
    expect(await File('$expected/study.db').exists(), true);
    expect(await File('$expected/.study.lock').exists(), true);
    expect(shell.backend.startupWarning, isNull);
    // Do not append test answers to the user's default library.
    await shell.backend.shutdown();
    runApp(const SizedBox.shrink());
    await tester.pump();
    debugPrint('DEFAULT_PROFILE_PASS: $expected');
  });
}
