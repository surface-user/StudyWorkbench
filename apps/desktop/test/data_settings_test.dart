import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/data_settings.dart';

void main() {
  testWidgets(
    'first run rejects empty path and accepts chosen Chinese folder',
    (tester) async {
      const channel = MethodChannel('study/desktop');
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (
        call,
      ) async {
        expect(call.method, 'chooseDirectory');
        return 'D:/学习 数据';
      });
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          channel,
          null,
        ),
      );
      String? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => TextButton(
              onPressed: () async {
                result = await showDataSettings(
                  context,
                  initial: '',
                  firstRun: true,
                );
              },
              child: const Text('设置'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('设置'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('使用此位置并启动'));
      await tester.pumpAndSettle();
      expect(find.text('请选择或输入数据文件夹'), findsOneWidget);
      await tester.tap(find.text('选择文件夹'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('使用此位置并启动'));
      await tester.pumpAndSettle();
      expect(result, 'D:/学习 数据');
      expect(tester.takeException(), isNull);
    },
  );
}
