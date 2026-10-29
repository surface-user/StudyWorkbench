import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/page_host.dart';

void main() {
  testWidgets(
    'removing and reordering siblings preserves page State and disposes only closed page',
    (tester) async {
      var ids = ['a', 'b', 'c'];
      var active = 'c';
      late StateSetter update;
      await tester.pumpWidget(
        MaterialApp(
          home: StatefulBuilder(
            builder: (context, set) {
              update = set;
              return Material(
                child: PageHost(
                  activeId: active,
                  pages: {
                    for (final id in ids)
                      id: TextField(key: ValueKey('field-$id')),
                  },
                ),
              );
            },
          ),
        ),
      );
      await tester.enterText(find.byKey(const ValueKey('field-c')), '独立草稿');
      final state = tester.state(find.byKey(const ValueKey('field-c')));
      final closed = tester.state(
        find.byKey(const ValueKey('field-b'), skipOffstage: false),
      );
      update(() => ids = ['a', 'c']);
      await tester.pump();
      expect(tester.state(find.byKey(const ValueKey('field-c'))), same(state));
      expect(closed.mounted, false);
      update(() {
        ids = ['c', 'a'];
        active = 'a';
      });
      await tester.pump();
      update(() => active = 'c');
      await tester.pump();
      expect(tester.state(find.byKey(const ValueKey('field-c'))), same(state));
      expect(
        tester.widget<EditableText>(find.byType(EditableText)).controller.text,
        '独立草稿',
      );
    },
  );
}
