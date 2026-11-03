import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/agent_access_dialog.dart';
import 'package:study_workbench/backend.dart';

class _Backend implements Backend {
  final calls = <String>[];
  Map? body;
  bool failRevoke = false, expired = false;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? data,
  ]) async {
    calls.add('$method $path');
    if (method == 'DELETE') {
      if (failRevoke) throw BackendError(500, '撤销失败');
      return {'revoked': true};
    }
    if (path.endsWith('/read-attempts')) {
      if (expired) throw BackendError(404, '授权已过期');
      return {
        'attempts': [
          {
            'id': 7,
            'question_id': 'q7',
            'score': 1,
            'status': 'graded',
            'created_at': '2026-11-03',
          },
        ],
      };
    }
    body = data;
    return {'id': 'grant'};
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> _open(WidgetTester tester, _Backend backend) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () => showDialog<void>(
              context: context,
              barrierDismissible: false,
              builder: (_) => AgentAccessDialog(
                backend: backend,
                scope: '/api/workspaces/math',
                attempts: [
                  for (final i in [7, 8]) {'id': i, 'question_id': 'q$i'},
                ],
              ),
            ),
            child: const Text('打开'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('打开'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'cancel does not grant; explicit scope, read and revoke failure retry',
    (tester) async {
      final backend = _Backend();
      await _open(tester, backend);
      await tester.tap(find.text('关闭'));
      await tester.pumpAndSettle();
      expect(backend.calls, isEmpty);
      await tester.tap(find.text('打开'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('记录 #7 · q7'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认授权所选记录'));
      await tester.pumpAndSettle();
      expect(backend.body, {
        'attempt_ids': [7],
        'purpose': 'analyze_attempts',
        'expires_in_seconds': 300,
        'confirm': true,
      });
      expect(backend.calls.length, 1);
      await tester.tap(find.text('读取授权摘要'));
      await tester.pumpAndSettle();
      expect(find.textContaining('原始评分：graded'), findsOneWidget);
      backend.failRevoke = true;
      await tester.tap(find.text('撤销并关闭'));
      await tester.pumpAndSettle();
      expect(find.byType(AgentAccessDialog), findsOneWidget);
      expect(find.textContaining('撤销失败'), findsOneWidget);
      backend.failRevoke = false;
      await tester.tap(find.text('撤销并关闭'));
      await tester.pumpAndSettle();
      expect(find.byType(AgentAccessDialog), findsNothing);
      expect(
        backend.calls.last,
        'DELETE /api/workspaces/math/agent-grants/grant',
      );
    },
  );

  testWidgets(
    'expired grant clears summaries and allows a new explicit grant',
    (tester) async {
      final backend = _Backend();
      await _open(tester, backend);
      await tester.tap(find.text('记录 #8 · q8'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认授权所选记录'));
      await tester.pumpAndSettle();
      backend.expired = true;
      await tester.tap(find.text('读取授权摘要'));
      await tester.pumpAndSettle();
      expect(find.text('确认授权所选记录'), findsOneWidget);
      expect(find.textContaining('授权已过期'), findsOneWidget);
      expect(backend.body!['attempt_ids'], [8]);
    },
  );
}
