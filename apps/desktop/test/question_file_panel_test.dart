import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_page.dart';
import 'package:study_workbench/question_file_panel.dart';
import 'package:study_workbench/study_page.dart';
import 'package:study_workbench/workspace_layout.dart';

class _Backend implements Backend {
  _Backend(this.handle);
  final Future<dynamic> Function(String, String, Map<String, dynamic>?) handle;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) => handle(method, path, body);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> question() => {
  'id': 'file-question',
  'schema_version': 1,
  'revision': 1,
  'kind': 'subjective',
  'subject': '未分类',
  'stem': [
    {'type': 'text', 'text': '请说明过程'},
  ],
  'options': <dynamic>[],
  'answer': null,
  'explanation': [
    {'type': 'text', 'text': '未提供解析'},
  ],
  'blank_ids': <dynamic>[],
  'knowledge_points': <dynamic>[],
  'source': {'kind': 'imported', 'title': '自编样例', 'verification': 'unverified'},
};

Future<void> show(WidgetTester tester, Widget child) async {
  tester.view.physicalSize = const Size(1300, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'unreadable current Markdown still opens its retained confirmed snapshot',
    (tester) async {
      final versionId = 'b' * 32;
      final tab = WorkbenchTab(
        id: 'doc',
        kind: 'resource',
        resourceItemId: 'a' * 32,
        viewKind: 'document',
        documentState: {'mode': 'question'},
      );
      final backend = _Backend((method, path, body) async {
        if (path.endsWith('/document')) {
          throw StateError('current file missing');
        }
        return {
          'status': 'invalid_current',
          'sha256': null,
          'question': question(),
          'passage': null,
          'warnings': ['当前文件不可读，上次确认版保留'],
          'confirmed_version_id': versionId,
          'confirmed': {
            'id': versionId,
            'revision': 1,
            'question': question(),
            'passage': null,
          },
        };
      });
      await show(
        tester,
        DocumentPage(
          backend: backend,
          workspaceId: 'default',
          tab: tab,
          onChanged: () {},
        ),
      );
      expect(find.text('保存本次作答'), findsOneWidget);
      expect(find.text('检查后确认题目版本'), findsNothing);
      expect(find.textContaining('上次确认版保留'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'file preview cannot submit until explicit confirmation; null answers stay pending',
    (tester) async {
      var confirmed = false, attempts = 0;
      final tab = WorkbenchTab(
        id: 'doc',
        kind: 'resource',
        resourceItemId: 'a' * 32,
        viewKind: 'document',
      );
      final versionId = 'b' * 32;
      final backend = _Backend((method, path, body) async {
        if (method == 'GET') {
          return {
            'status': confirmed ? 'confirmed' : 'unconfirmed',
            'sha256': 'c' * 64,
            'question': question(),
            'passage': null,
            'warnings': <dynamic>[],
            'confirmed_version_id': confirmed ? versionId : null,
            'confirmed': confirmed
                ? {
                    'id': versionId,
                    'revision': 1,
                    'question': question(),
                    'passage': null,
                  }
                : null,
          };
        }
        if (path.endsWith('/confirm')) {
          expect(body, {
            'expected_sha256': 'c' * 64,
            'expected_version_id': null,
            'confirm': true,
          });
          confirmed = true;
          return {'id': versionId};
        }
        expect(body!['question_version_id'], versionId);
        expect(body['response'], {'text': '保留过程'});
        attempts++;
        return {'id': attempts, 'status': 'pending_review', 'score': null};
      });
      await show(
        tester,
        QuestionFilePanel(
          backend: backend,
          workspaceId: 'default',
          tab: tab,
          onChanged: () {},
          generation: 0,
        ),
      );
      expect(find.text('保存本次作答'), findsNothing);
      expect(attempts, 0);
      await tester.tap(find.text('检查后确认题目版本'));
      await tester.pumpAndSettle();
      expect(confirmed, false);
      await tester.tap(find.text('确认题目版本'));
      await tester.pumpAndSettle();
      expect(confirmed, true);
      await tester.enterText(find.byType(TextField), '保留过程');
      expect(jsonDecode(tab.questionDraft)['text'], '保留过程');
      await tester.ensureVisible(find.text('保存本次作答'));
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(attempts, 1);
      expect(tab.questionDraft, '');
      expect(find.textContaining('待人工批改'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('failed confirmation preserves file and answer drafts', (
    tester,
  ) async {
    final tab = WorkbenchTab(
      id: 'doc',
      kind: 'resource',
      resourceItemId: 'a' * 32,
      viewKind: 'document',
      draft: 'MD编辑草稿',
      draftBaseSha256: 'a' * 64,
      questionDraft: '待保留的作答草稿',
    );
    final backend = _Backend((method, path, body) async {
      if (method == 'GET') {
        return {
          'status': 'unconfirmed',
          'sha256': 'c' * 64,
          'question': question(),
          'passage': null,
          'warnings': [],
          'confirmed_version_id': null,
          'confirmed': null,
        };
      }
      throw StateError('409 文件已变化');
    });
    await show(
      tester,
      QuestionFilePanel(
        backend: backend,
        workspaceId: 'default',
        tab: tab,
        onChanged: () {},
        generation: 0,
      ),
    );
    await tester.tap(find.text('检查后确认题目版本'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认题目版本'));
    await tester.pumpAndSettle();
    expect(find.textContaining('409'), findsOneWidget);
    expect(tab.questionDraft, '待保留的作答草稿');
    expect(tab.draft, 'MD编辑草稿');
    expect(find.text('保存本次作答'), findsNothing);
  });

  testWidgets(
    'submission retry restores its request id across closing and reopening',
    (tester) async {
      var draft = '', failFirst = true;
      final requests = <Map<String, dynamic>>[];
      final q = {...question(), 'confirmed_version_id': 'b' * 32};
      final backend = _Backend((method, path, body) async {
        requests.add(Map<String, dynamic>.from(body!));
        if (failFirst) throw StateError('lost response');
        return {'id': 1, 'status': 'pending_review', 'score': null};
      });
      Widget answer() => SingleChildScrollView(
        child: StudyAnswer(
          question: q,
          backend: backend,
          workspaceId: 'default',
          scope: '/api/workspaces/default',
          initialDraft: draft,
          onDraftChanged: (value) => draft = value,
          onSaved: () async {},
        ),
      );
      await show(tester, answer());
      await tester.enterText(find.byType(TextField), '重试过程');
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(jsonDecode(draft)['request_id'], requests.first['request_id']);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      failFirst = false;
      await show(tester, answer());
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '重试过程',
      );
      await tester.tap(find.text('保存本次作答'));
      await tester.pumpAndSettle();
      expect(requests.length, 2);
      expect(requests.first, requests.last);
      expect(draft, '');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'new confirmed version never silently submits an old-version draft',
    (tester) async {
      final old = jsonEncode({
        'question_id': 'file-question',
        'version_id': 'a' * 32,
        'selected': [],
        'blanks': {},
        'text': '旧过程',
        'request_id': null,
      });
      var draft = old;
      final backend = _Backend(
        (method, path, body) async => fail('Must not submit old-version input'),
      );
      await show(
        tester,
        SingleChildScrollView(
          child: StudyAnswer(
            question: {...question(), 'confirmed_version_id': 'b' * 32},
            backend: backend,
            workspaceId: 'default',
            scope: '/api/workspaces/default',
            initialDraft: draft,
            onDraftChanged: (value) => draft = value,
            onSaved: () async {},
          ),
        ),
      );
      expect(draft, old);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '保存本次作答'))
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('放弃旧版作答草稿'));
      await tester.pumpAndSettle();
      expect(draft, '');
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '保存本次作答'))
            .onPressed,
        isNotNull,
      );
    },
  );
}
