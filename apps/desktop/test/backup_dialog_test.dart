import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/backup_dialog.dart';
import 'package:study_workbench/startup_failure.dart';

class _Backend implements Backend {
  _Backend(this.handle);
  final Future<dynamic> Function() handle;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) {
    expect(method, 'GET');
    expect(path, '/api/workbench');
    return handle();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

dynamic spaces() => {
  'workspaces': [
    {'id': 'default', 'name': '当前课程', 'archived': false},
  ],
  'archived_workspaces': [
    {'id': 'old', 'name': '归档课程', 'archived': true},
  ],
};

Directory fixture() {
  const root = String.fromEnvironment('STUDY_ROOT');
  return (Directory(
    '$root/.local/tmp',
  )..createSync(recursive: true)).createTempSync('backup-dialog-');
}

Future<void> show(
  WidgetTester tester, {
  bool restore = false,
  Backend? backend,
  ValueChanged<LibraryBackupPlan>? chosen,
}) async {
  tester.view.physicalSize = const Size(1500, 1200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () async {
              final plan = await showDialog<LibraryBackupPlan>(
                context: context,
                barrierDismissible: false,
                builder: (_) =>
                    LibraryBackupDialog(restore: restore, backend: backend),
              );
              if (plan != null) chosen?.call(plan);
            },
            child: const Text('打开设置'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('打开设置'));
  await tester.pumpAndSettle();
}

Future<void> confirm(WidgetTester tester) async {
  // Run the real filesystem validation to completion without relying on arbitrary widget pump delays.
  final action = tester
      .widget<FilledButton>(find.widgetWithText(FilledButton, '确认并开始离线操作'))
      .onPressed;
  await tester.runAsync(() async {
    await (action as Future<void> Function())();
  });
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'backup lists archived spaces and requires explicit whole-library consent',
    (tester) async {
      final folder = fixture();
      LibraryBackupPlan? chosen;
      await show(
        tester,
        backend: _Backend(() async => spaces()),
        chosen: (value) => chosen = value,
      );
      expect(find.textContaining('归档课程（已归档）'), findsOneWidget);
      expect(find.textContaining('当前课程'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, '确认并开始离线操作'),
            )
            .onPressed,
        isNull,
      );
      await tester.enterText(
        find.byKey(const ValueKey('backup-zip-path')),
        '${folder.path}/new.zip',
      );
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await confirm(tester);
      expect(chosen!.restore, isFalse);
      expect(chosen!.zipPath, '${folder.path}/new.zip');
    },
  );

  testWidgets('scope failure blocks backup and retry retains the chosen path', (
    tester,
  ) async {
    var attempts = 0;
    final backend = _Backend(() async {
      if (attempts++ == 0) throw StateError('offline');
      return spaces();
    });
    await show(tester, backend: backend);
    await tester.enterText(
      find.byKey(const ValueKey('backup-zip-path')),
      '${fixture().path}/saved.zip',
    );
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认并开始离线操作'))
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('重试读取全部空间范围'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('backup-zip-path')))
          .controller!
          .text,
      endsWith('saved.zip'),
    );
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认并开始离线操作'))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('existing backup is preserved and cannot be overwritten', (
    tester,
  ) async {
    final folder = fixture(),
        file = File('${fixture().path}/existing.zip')
          ..writeAsStringSync('keep');
    LibraryBackupPlan? chosen;
    await show(
      tester,
      backend: _Backend(() async => spaces()),
      chosen: (value) => chosen = value,
    );
    await tester.enterText(
      find.byKey(const ValueKey('backup-zip-path')),
      file.path,
    );
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await confirm(tester);
    expect(chosen, isNull);
    expect(file.readAsStringSync(), 'keep');
    expect(find.textContaining('不覆盖已有备份'), findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey('backup-zip-path')),
      '${folder.path}/another.zip',
    );
    await confirm(tester);
    expect(chosen, isNotNull);
  });

  testWidgets(
    'restore refuses nonempty destination and accepts a new empty directory',
    (tester) async {
      final folder = fixture(),
          archive = File('${fixture().path}/archive.zip')
            ..writeAsStringSync('fixture');
      final occupied = Directory('${folder.path}/old')..createSync();
      final old = File('${occupied.path}/keep')..writeAsStringSync('user data');
      LibraryBackupPlan? chosen;
      await show(tester, restore: true, chosen: (value) => chosen = value);
      await tester.enterText(
        find.byKey(const ValueKey('backup-zip-path')),
        archive.path,
      );
      await tester.enterText(
        find.byKey(const ValueKey('backup-target-path')),
        occupied.path,
      );
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await confirm(tester);
      expect(chosen, isNull);
      expect(old.readAsStringSync(), 'user data');
      expect(find.textContaining('目标必须是新空目录'), findsOneWidget);
      await tester.enterText(
        find.byKey(const ValueKey('backup-target-path')),
        '${folder.path}/new',
      );
      await confirm(tester);
      expect(chosen!.target, '${folder.path}/new');
      expect(chosen!.restore, isTrue);
    },
  );

  testWidgets('native backup picker uses dedicated archive operation', (
    tester,
  ) async {
    final seen = <String>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('study/desktop'),
      (call) async {
        seen.add(call.method);
        return call.method == 'chooseDirectory'
            ? 'D:/new-empty'
            : 'D:/archive.zip';
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        const MethodChannel('study/desktop'),
        null,
      ),
    );
    await show(tester, restore: true);
    await tester.tap(find.text('选择备份包'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('选择新空目录'));
    await tester.pumpAndSettle();
    expect(seen, ['chooseBackupArchive', 'chooseDirectory']);
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('backup-target-path')))
          .controller!
          .text,
      'D:/new-empty',
    );
  });

  testWidgets(
    'startup failure offers a restore entry without replacing data implicitly',
    (tester) async {
      var restored = false, retried = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StartupFailure(
              details: 'fixture',
              onRetry: () => retried = true,
              onRestoreBackup: () => restored = true,
            ),
          ),
        ),
      );
      await tester.tap(find.text('从完整学习库备份恢复'));
      await tester.pump();
      expect(restored, isTrue);
      expect(retried, isFalse);
    },
  );
}
