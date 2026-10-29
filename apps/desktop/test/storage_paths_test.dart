import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('study/desktop');
  late Directory home;
  late String dataRoot;
  setUp(() async {
    home = await Directory.systemTemp.createTemp('study-storage-paths-');
    dataRoot = home.path;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          expect(call.method, isIn(['storageRoot', 'settingsRoot']));
          return call.method == 'settingsRoot'
              ? '${home.path}/shared-config'
              : dataRoot;
        });
  });
  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });
  test(
    'remembered settings stay fixed when the process data profile changes',
    () async {
      final settings = await Backend.settingsPath;
      dataRoot = '${home.path}/other-integrity';
      expect(await Backend.defaultData, '$dataRoot/data');
      expect(await Backend.settingsPath, settings);
    },
  );
  test('default user directory needs no picker and settings use the shared profile', () async {
    expect(await Backend.defaultData, '${home.path}/data');
    expect(
      await Backend.settingsPath,
      '${home.path}/shared-config/settings.json',
    );
    expect(await File('${home.path}/data/study.db').exists(), false);
  });
  test(
    'existing M0 database remains the default, empty M0 folder does not',
    () async {
      final old = await Directory('${home.path}/m0').create();
      expect(await Backend.defaultData, '${home.path}/data');
      final db = File('${old.path}/study.db')
        ..writeAsStringSync('preserve legacy database');
      expect(await Backend.defaultData, '${home.path}/m0');
      expect(db.readAsStringSync(), 'preserve legacy database');
    },
  );
  test(
    'invalid platform storage path is rejected without creating a directory',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (_) async => 'relative');
      await expectLater(Backend.defaultData, throwsFormatException);
    },
  );
}
