import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/spreadsheet_view.dart';

void main() {
  testWidgets(
    'sheet selection preserves literal cached values and missing-cache notice',
    (tester) async {
      final controller = ScrollController();
      addTearDown(controller.dispose);
      var index = 0;
      final workbook = <String, dynamic>{
        'sheets': [
          {
            'name': '数据',
            'state': 'visible',
            'cells': [
              {
                'address': 'A1',
                'value': '<script>字面原文</script>',
                'formula': false,
                'cache_missing': false,
              },
              {
                'address': 'B1',
                'value': '公式无缓存值',
                'formula': true,
                'cache_missing': true,
              },
              {
                'address': 'C1',
                'value': '2',
                'formula': true,
                'cache_missing': false,
              },
            ],
          },
          {
            'name': '隐藏数据',
            'state': 'hidden',
            'cells': [
              {
                'address': 'XFD1048576',
                'value': '稀疏值',
                'formula': false,
                'cache_missing': false,
              },
            ],
          },
        ],
      };
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) => SpreadsheetView(
                workbook: workbook,
                sheetIndex: index,
                scrollController: controller,
                onSheetChanged: (value) => setState(() => index = value),
              ),
            ),
          ),
        ),
      );
      expect(find.text('<script>字面原文</script>'), findsOneWidget);
      expect(find.text('公式无缓存值'), findsOneWidget);
      expect(find.text('未计算'), findsOneWidget);
      expect(find.text('公式缓存（未重新计算）'), findsOneWidget);
      await tester.tap(find.byType(DropdownButton<int>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('2. 隐藏数据（隐藏表）').last);
      await tester.pumpAndSettle();
      expect(index, 1);
      expect(find.text('XFD1048576'), findsOneWidget);
      expect(find.text('稀疏值'), findsOneWidget);
      expect(find.text('公式无缓存值'), findsNothing);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'large sparse sheet builds a bounded visible list and stale index is clamped',
    (tester) async {
      final controller = ScrollController();
      addTearDown(controller.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SpreadsheetView(
              workbook: {
                'sheets': [
                  {
                    'name': '大表',
                    'state': 'visible',
                    'cells': [
                      for (var i = 1; i <= 10000; i++)
                        {
                          'address': 'A$i',
                          'value': 'value $i',
                          'formula': false,
                          'cache_missing': false,
                        },
                    ],
                  },
                ],
              },
              sheetIndex: 999,
              onSheetChanged: (_) {},
              scrollController: controller,
            ),
          ),
        ),
      );
      expect(find.text('A1'), findsOneWidget);
      expect(find.text('A10000'), findsNothing);
      expect(find.byType(SelectableText).evaluate().length, lessThan(60));
      await tester.pumpWidget(const SizedBox());
    },
  );
}
