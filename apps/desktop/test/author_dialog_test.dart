import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/author_dialog.dart';

void main() {
  testWidgets(
    'switching from choice to blanks does not reuse option text as the answer',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: AuthorDialog())),
      );
      final kind = find.byType(DropdownButtonFormField<String>);
      await tester.tap(kind);
      await tester.pumpAndSettle();
      await tester.tap(find.text('单选题').last);
      await tester.pumpAndSettle();
      final options = find.byKey(const ValueKey('选项（每行一个）'));
      await tester.ensureVisible(options);
      await tester.enterText(options, '甲\n乙');
      await tester.pump();
      await tester.ensureVisible(kind);
      await tester.tap(kind);
      await tester.pumpAndSettle();
      await tester.tap(find.text('填空题').last);
      await tester.pumpAndSettle();
      final answer = find.byKey(const ValueKey('填空答案（每行一空，同义答案用 | 分隔）'));
      await tester.ensureVisible(answer);
      final input = find.descendant(
        of: answer,
        matching: find.byType(TextField),
      );
      expect(tester.widget<TextField>(input).controller!.text, isEmpty);
    },
  );

  testWidgets('manual note creates preview data only after valid input', (
    tester,
  ) async {
    Map<String, dynamic>? value;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              child: const Text('录入'),
              onPressed: () async {
                value = await showDialog<Map<String, dynamic>>(
                  context: context,
                  builder: (_) => const AuthorDialog(),
                );
              },
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('录入'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('生成预览'));
    await tester.pumpAndSettle();
    expect(value, isNull);
    await tester.enterText(find.byType(TextFormField).at(0), '我的笔记');
    await tester.enterText(find.byType(TextFormField).at(1), '离线知识点');
    await tester.ensureVisible(find.text('生成预览'));
    await tester.tap(find.text('生成预览'));
    await tester.pumpAndSettle();
    expect(value, {
      'schema_version': 1,
      'kind': 'note',
      'title': '我的笔记',
      'blocks': [
        {'type': 'text', 'text': '离线知识点'},
      ],
    });
  });
}
