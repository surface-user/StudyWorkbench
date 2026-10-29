import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/study_page.dart';

class _Backend implements Backend {
  int writes = 0;
  final bodies = <Map<String, dynamic>>[];
  bool failFirst = false;
  bool pagedHistory = false, failHistory = false;
  final historyPaths = <String>[];
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    if (path.contains('/study?')) {
      return [
        {
          'id': 'q',
          'subject': '数学',
          'kind': 'multiple_choice',
          'knowledge_points': ['集合'],
          'pending_review': false,
          'mastered': false,
          'wrong': false,
          'attempt_count': 0,
        },
      ];
    }
    if (path.endsWith('/statistics')) {
      return {
        'questions': 1,
        'attempts': writes,
        'due': 1,
        'wrong': 0,
        'mastered': 0,
        'pending_review': 0,
        'subjects': ['数学'],
        'knowledge_points': [],
      };
    }
    if (method == 'GET' && path.contains('/attempt-history?')) {
      historyPaths.add(path);
      if (!pagedHistory) return [];
      if (path.contains('before_id=')) {
        if (failHistory) throw StateError('历史读取失败');
        return [attempt(1)];
      }
      return [for (var i = 51; i >= 2; i--) attempt(i)];
    }
    if (path.endsWith('/study-tasks')) {
      return [];
    }
    if (path.endsWith('/questions/q')) {
      return {
        'schema_version': 1,
        'id': 'q',
        'revision': 1,
        'subject': '数学',
        'kind': 'multiple_choice',
        'stem': [
          {'type': 'text', 'text': '请选择两个正确项'},
        ],
        'options': [
          for (final id in ['甲', '乙'])
            {
              'id': id,
              'content': [
                {'type': 'text', 'text': '选项$id'},
              ],
            },
        ],
        'answer': {
          'selected': ['甲', '乙'],
        },
        'explanation': [
          {'type': 'text', 'text': '解析'},
        ],
        'knowledge_points': ['集合'],
        'source': {
          'kind': 'imported',
          'verification': 'unverified',
          'title': '自编样例',
        },
      };
    }
    if (method == 'POST' && path.endsWith('/attempts')) {
      bodies.add(Map<String, dynamic>.from(body!));
      if (failFirst && bodies.length == 1) throw StateError('response lost');
      writes++;
      return {'id': 1, 'status': 'graded', 'score': 1.0};
    }
    throw StateError(path);
  }

  Map<String, dynamic> attempt(int id) => {
    'id': id,
    'question_id': '历史$id',
    'response': {'text': '作答$id'},
    'status': 'pending_review',
    'score': null,
    'created_at': '2026-10-25T00:00:00+00:00',
    'reviews': [],
  };

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'history loads older pages and retains loaded records on failure',
    (tester) async {
      final backend = _Backend()
        ..pagedHistory = true
        ..failHistory = true;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StudyPage(backend: backend, workspaceId: 'math'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        backend.historyPaths.single,
        endsWith('/attempt-history?limit=50'),
      );
      final heading = find.text('作答历史与待批改（已加载 50 条）');
      await tester.ensureVisible(heading);
      await tester.tap(heading);
      await tester.pumpAndSettle();
      final older = find.text('加载更早作答');
      await tester.ensureVisible(older);
      await tester.tap(older);
      await tester.pumpAndSettle();
      expect(heading, findsOneWidget);
      expect(find.text('历史51 · 待人工批改'), findsOneWidget);
      expect(backend.historyPaths.last, endsWith('limit=50&before_id=2'));
      backend.failHistory = false;
      await tester.ensureVisible(older);
      await tester.tap(older);
      await tester.pumpAndSettle();
      expect(find.text('作答历史与待批改（已加载 51 条）'), findsOneWidget);
      expect(find.text('历史1 · 待人工批改'), findsOneWidget);
      expect(older, findsNothing);
      expect(backend.historyPaths.length, 3);
    },
  );

  Future<void> open(WidgetTester tester, _Backend backend) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StudyPage(backend: backend, workspaceId: 'math'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('数学 · q'));
    await tester.pumpAndSettle();
    final checkboxes = find.byType(CheckboxListTile);
    for (var i = 0; i < 2; i++) {
      await tester.ensureVisible(checkboxes.at(i));
      await tester.tap(checkboxes.at(i));
      await tester.pump();
    }
  }

  testWidgets(
    'multi-select submits once and an intentional new attempt has a fresh id',
    (tester) async {
      final backend = _Backend();
      await open(tester, backend);
      await tester.ensureVisible(find.text('保存本次作答'));
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(backend.writes, 1);
      expect(backend.bodies[0]['response'], {
        'selected': ['乙', '甲'],
      });
      expect(find.text('作答已保存，得分 1.0'), findsOneWidget);
      await tester.ensureVisible(find.text('开始新一次作答'));
      await tester.tap(find.text('开始新一次作答'));
      await tester.pump();
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(backend.writes, 2);
      expect(
        backend.bodies[1]['request_id'],
        isNot(backend.bodies[0]['request_id']),
      );
    },
  );
  testWidgets(
    'uncertain response retries the same submission key without losing selection',
    (tester) async {
      final backend = _Backend()..failFirst = true;
      await open(tester, backend);
      await tester.ensureVisible(find.text('保存本次作答'));
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(find.textContaining('未确认保存结果'), findsOneWidget);
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(backend.bodies.length, 2);
      expect(backend.bodies[1]['request_id'], backend.bodies[0]['request_id']);
      expect(backend.writes, 1);
    },
  );
}
