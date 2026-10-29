import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/main.dart';

void main() {
  testWidgets('app configuration supplies Chinese editing labels', (
    tester,
  ) async {
    await tester.pumpWidget(
      Builder(
        builder: (context) {
          final app = const StudyApp().build(context) as MaterialApp;
          return MaterialApp(
            locale: app.locale,
            supportedLocales: app.supportedLocales,
            localizationsDelegates: app.localizationsDelegates,
            home: Builder(
              builder: (context) =>
                  Text(MaterialLocalizations.of(context).pasteButtonLabel),
            ),
          );
        },
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('粘贴'), findsOneWidget);
    expect(find.text('Paste'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
