import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/question_page.dart';

const _question = {
  'id': 'demo-integral',
  'subject': '数学演示',
  'stem': [
    {'type': 'text', 'text': '选择演示答案'},
  ],
  'options': [
    {
      'id': 'a',
      'content': [
        {'type': 'text', 'text': '演示选项'},
      ],
    },
  ],
};

class _Backend implements Backend {
  _Backend(this.handle);
  final Future<dynamic> Function(
    String method,
    String path,
    Map<String, dynamic>? body,
  )
  handle;
  final calls = <String>[];

  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) {
    calls.add('$method $path');
    return handle(method, path, body);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> _show(WidgetTester tester, Backend backend) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: QuestionPage(backend: backend)),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('question load can retry without submitting an attempt', (
    tester,
  ) async {
    var loads = 0;
    final backend = _Backend((method, path, body) async {
      expect(method, 'GET');
      expect(path, '/api/workspaces/default/questions/demo');
      if (++loads == 1) throw const HttpException('请求失败 500');
      return _question;
    });
    await _show(tester, backend);
    expect(find.textContaining('题目加载失败'), findsOneWidget);
    await tester.tap(find.text('重新加载题目'));
    await tester.pumpAndSettle();
    expect(find.text('选择演示答案'), findsOneWidget);
    expect(find.textContaining('题目加载失败'), findsNothing);
    expect(backend.calls, [
      'GET /api/workspaces/default/questions/demo',
      'GET /api/workspaces/default/questions/demo',
    ]);
    expect(tester.takeException(), isNull);
  });

  for (final pending in [false, true]) {
    testWidgets('saved answer survives history failure (pending=$pending)', (
      tester,
    ) async {
      final backend = _Backend((method, path, body) async {
        if (path == '/api/workspaces/default/questions/demo') return _question;
        if (method == 'POST') {
          final submission = body!;
          expect(
            submission['question_id'],
            pending ? 'demo-proof' : 'demo-integral',
          );
          expect(
            submission['response'],
            pending
                ? {'text': '解题过程'}
                : {
                    'selected': ['a'],
                  },
          );
          return {
            'id': 1,
            'status': pending ? 'pending_review' : 'graded',
            'score': pending ? null : 1.0,
          };
        }
        throw const HttpException('请求失败 500');
      });
      await _show(tester, backend);
      if (pending) {
        await tester.enterText(find.byType(TextField), '解题过程');
      }
      await tester.tap(find.text(pending ? '提交主观作答' : '选择答案  '));
      await tester.pumpAndSettle();
      expect(
        find.textContaining(pending ? '已保存，待人工批改' : '已保存，得分 1.0'),
        findsOneWidget,
      );
      expect(find.textContaining('请勿重复提交'), findsOneWidget);
      expect(find.textContaining('未能确认'), findsNothing);
      expect(
        backend.calls.where(
          (call) => call == 'POST /api/workspaces/default/attempts',
        ),
        hasLength(1),
      );
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('uncertain save is not retried and does not claim success', (
    tester,
  ) async {
    final backend = _Backend((method, path, body) async {
      if (path == '/api/workspaces/default/questions/demo') return _question;
      throw TimeoutException('响应超时');
    });
    await _show(tester, backend);
    await tester.tap(find.text('选择答案  '));
    await tester.pumpAndSettle();
    expect(find.textContaining('未能确认作答是否保存'), findsOneWidget);
    expect(find.textContaining('已保存'), findsNothing);
    expect(backend.calls, [
      'GET /api/workspaces/default/questions/demo',
      'POST /api/workspaces/default/attempts',
    ]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('confirmed save shows score before history finishes', (
    tester,
  ) async {
    final history = Completer<List<dynamic>>();
    final backend = _Backend((method, path, body) async {
      if (path == '/api/workspaces/default/questions/demo') return _question;
      if (method == 'POST') {
        return {'id': 1, 'status': 'graded', 'score': 1.0};
      }
      return history.future;
    });
    await _show(tester, backend);
    await tester.tap(find.text('选择答案  '));
    await tester.pumpAndSettle();
    expect(find.text('已保存，得分 1.0'), findsOneWidget);
    expect(
      tester.widget<OutlinedButton>(find.byType(OutlinedButton)).onPressed,
      isNull,
    );
    history.complete([
      {'id': 1},
    ]);
    await tester.pumpAndSettle();
    expect(find.text('已保存，得分 1.0 · 共 1 次作答'), findsOneWidget);
    expect(
      tester.widget<OutlinedButton>(find.byType(OutlinedButton)).onPressed,
      isNotNull,
    );
    expect(
      backend.calls.where(
        (call) => call == 'POST /api/workspaces/default/attempts',
      ),
      hasLength(1),
    );
    expect(tester.takeException(), isNull);
  });
}
