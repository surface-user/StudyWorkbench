import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/external_page.dart';

void main() {
  test('rejected URLs never reach the browser', () async {
    var launches = 0;
    await expectLater(
      openExternalPage(
        'file:///C:/secret',
        validate: (_) async => false,
        launch: (_) async {
          launches++;
          return true;
        },
      ),
      throwsArgumentError,
    );
    expect(launches, 0);
  });

  test('browser launch failure is reported instead of ignored', () async {
    await expectLater(
      openExternalPage(
        'https://example.com',
        validate: (_) async => true,
        launch: (_) async => false,
      ),
      throwsStateError,
    );
  });

  test('native launch exceptions remain visible to the caller', () async {
    await expectLater(
      openExternalPage(
        'https://example.com',
        validate: (_) async => true,
        launch: (_) async => throw PlatformException(code: 'launch_failed'),
      ),
      throwsA(isA<PlatformException>()),
    );
  });

  test('validated HTTPS URL is handed to browser once', () async {
    final launched = <Uri>[];
    await openExternalPage(
      'https://example.com/path',
      validate: (_) async => true,
      launch: (uri) async {
        launched.add(uri);
        return true;
      },
    );
    expect(launched, [Uri.parse('https://example.com/path')]);
  });
}
