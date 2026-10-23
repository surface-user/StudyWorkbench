import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/question_page.dart';
import 'package:study_workbench/url_policy.dart';

void main() {
  test('external navigation rejects local and unsafe schemes', () {
    for (final value in [
      'http://example.com',
      'https://127.0.0.1',
      'https://[::1]',
      'file:///C:/secret',
      'javascript:alert(1)',
      'https://localhost',
      'https://x.local',
      'https://user:pass@example.com',
      'https://example.com:8000',
      'https://2130706433',
    ]) {
      expect(publicHttpsUrl(value), false, reason: value);
    }
    expect(publicHttpsUrl('https://example.com/path'), true);
    expect(publicHttpsUrl('https://chat.deepseek.com'), true);
  });
  testWidgets('rich blocks render actual math and preserve unknown blocks', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ContentBlocks([
            {'type': 'text', 'text': '演示公式'},
            {'type': 'latex', 'tex': r'\int_0^1 x^2\,dx'},
            {'type': 'future-block'},
          ]),
        ),
      ),
    );
    expect(find.text('演示公式'), findsOneWidget);
    expect(find.byType(Math), findsOneWidget);
    expect(find.textContaining('尚未支持'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
