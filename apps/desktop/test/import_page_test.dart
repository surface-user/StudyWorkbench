import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/import_page.dart';
import 'package:study_workbench/question_contract.dart';
import 'package:study_workbench/question_page.dart';

class _Backend implements Backend {
  _Backend({
    this.failConfirm = false,
    this.failedJob = false,
    this.questionJob = false,
    this.richNote = false,
    this.splitJob = false,
  });
  final bool failConfirm;
  final bool failedJob;
  final bool questionJob;
  final bool richNote;
  final bool splitJob;
  bool mdSaved = false;
  Map<String, dynamic>? edited;
  final edits = <Map<String, dynamic>>[];
  int writes = 0;
  bool saved = false;
  final paths = <String>[];
  Map<String, dynamic> get job => {
    'id': 'job',
    'filename': '中文资料.md',
    'resource_id': 'original',
    'status': failedJob
        ? 'failed'
        : saved || mdSaved
        ? 'confirmed'
        : 'preview',
    'sha256': 'abc',
    'size': 32,
    'parser_version': 'builtin-1',
    'created_at': '2026-10-24T00:00:00Z',
    'draft_revision': 'a' * 64,
    'question_markdown': ['独立题目正文\n'],
    'error': failedJob ? '解析失败；原件保留' : null,
    'preview': failedJob
        ? <String, dynamic>{}
        : questionJob
        ? {
            'kind': 'questions',
            'bundle': {
              'passages': [],
              'questions': [
                for (final id in ['第一题', '第二题'])
                  {
                    'id': id,
                    'subject': '数学',
                    'source': {
                      'kind': 'imported',
                      'verification': 'unverified',
                      'title': '资料来源',
                    },
                    'stem': [
                      {'type': 'text', 'text': id},
                    ],
                    'options': [],
                    'answer': {'rubric': '评分要点'},
                    'explanation': [
                      {'type': 'text', 'text': '解析内容'},
                    ],
                  },
              ],
            },
          }
        : {
            'kind': 'note',
            'title': '中文资料.md',
            'blocks': [
              {'type': 'text', 'text': '需要确认的中文笔记'},
            ],
            if (splitJob)
              'question_drafts': [
                {
                  'title': '1. 原题',
                  'blocks': [
                    {'type': 'text', 'text': '独立题目正文'},
                  ],
                },
              ],
          },
  };
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    paths.add(path);
    expect(path, startsWith('/api/workspaces/math/'));
    if (method == 'POST' && path.endsWith('/question-markdown')) {
      expect(body!['selected'], [0]);
      mdSaved = true;
      return [];
    }
    if (method == 'PUT' && path.endsWith('/notes/note')) {
      edits.add(body!);
      edited = {
        'id': 'note',
        'title': body['title'],
        'content': body['content'],
        'revision': 'b' * 64,
      };
      return edited;
    }
    if (path.endsWith('/confirm')) {
      writes++;
      if (failConfirm) throw StateError('网络中断，请核实导入记录');
      saved = true;
      return job;
    }
    if (path.contains('/resources?')) {
      return [
        {'id': 'original', 'filename': '原件.md', 'mime': 'text/markdown'},
      ];
    }
    if (path.endsWith('/analyze')) return job;
    if (path.endsWith('/imports')) return [job];
    if (path.endsWith('/imports/job')) return job;
    if (path.contains('/questions?')) return [];
    if (path.contains('/question-markdown?')) {
      return mdSaved
          ? [
              {'id': 'md', 'title': '1. 原题'},
            ]
          : [];
    }
    if (path.endsWith('/question-markdown/md')) {
      return {
        'id': 'md',
        'title': '1. 原题',
        'markdown': '独立题目正文\n',
        'blocks': [
          {'type': 'text', 'text': '独立题目正文'},
        ],
      };
    }
    if (path.contains('/notes?')) {
      if (richNote) {
        return [
          edited ??
              {
                'id': 'note',
                'title': '富笔记',
                'revision': 'a' * 64,
                'content': [
                  {'type': 'text', 'text': '文字段'},
                  {'type': 'latex', 'tex': 'x^2'},
                ],
              },
        ];
      }
      return saved
          ? [
              {'id': 'note', 'title': '已保存资料', 'content': []},
            ]
          : [];
    }
    throw StateError('Unexpected $method $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> showPage(WidgetTester tester, Backend backend) async {
  tester.view.physicalSize = const Size(1200, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: ImportPage(backend: backend, workspaceId: 'math'),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'closing split preview refreshes persisted preview without confirming a question',
    (tester) async {
      final backend = _Backend(splitJob: true);
      await showPage(tester, backend);
      await tester.tap(find.text('中文资料.md'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('检查拆题，逐题存为 Markdown'));
      await tester.tap(find.text('检查拆题，逐题存为 Markdown'));
      await tester.pumpAndSettle();
      final before = backend.paths
          .where((path) => path.endsWith('/imports/job'))
          .length;
      await tester.tap(find.text('暂不入库'));
      await tester.pumpAndSettle();
      expect(
        backend.paths.where((path) => path.endsWith('/imports/job')).length,
        before + 1,
      );
      expect(backend.mdSaved, isFalse);
      expect(backend.writes, 0);
      expect(find.text('拆题预览已保留，尚未入库'), findsOneWidget);
    },
  );
  testWidgets(
    'document split entry confirms independent MD and opens its library item',
    (tester) async {
      final backend = _Backend(splitJob: true);
      await showPage(tester, backend);
      await tester.tap(find.text('中文资料.md'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('检查拆题，逐题存为 Markdown'));
      await tester.tap(find.text('检查拆题，逐题存为 Markdown'));
      await tester.pumpAndSettle();
      expect(backend.mdSaved, isFalse);
      expect(find.text('独立题目正文'), findsOneWidget);
      await tester.tap(find.text('确认逐题保存为 Markdown'));
      await tester.pumpAndSettle();
      expect(backend.mdSaved, isTrue);
      expect(backend.saved, isFalse);
      await tester.ensureVisible(find.text('1. 原题'));
      await tester.tap(find.text('1. 原题'));
      await tester.pumpAndSettle();
      expect(find.text('独立题目正文'), findsOneWidget);
      expect(find.text('独立 Markdown 题目资料 · 来源未验证 · 未推断标准答案'), findsOneWidget);
    },
  );
  testWidgets('library opens rich editor and refreshes saved content', (
    tester,
  ) async {
    await tester.runAsync(() => QuestionContract.load(bundle: false));
    final backend = _Backend(richNote: true);
    await showPage(tester, backend);
    await tester.ensureVisible(find.text('富笔记'));
    await tester.tap(find.text('富笔记'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('编辑此笔记'));
    await tester.tap(find.text('编辑此笔记'));
    await tester.pumpAndSettle();
    expect(find.text('编辑富内容笔记'), findsOneWidget);
    final text = find.byWidgetPredicate(
      (w) => w is TextField && w.decoration?.labelText == '文字内容',
    );
    await tester.enterText(text, '编辑后的正文');
    final action = tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, '确认保存笔记'))
        .onPressed;
    await tester.runAsync(() async => await (action as dynamic)());
    await tester.pumpAndSettle();
    expect(backend.edits, hasLength(1));
    expect(backend.edits.single['content'], [
      {'type': 'text', 'text': '编辑后的正文'},
      {'type': 'latex', 'tex': 'x^2'},
    ]);
    expect(find.text('笔记已保存，导入原件保留'), findsOneWidget);
    expect(find.text('编辑富内容笔记'), findsNothing);
  });
  testWidgets(
    'bundle preview pages through every question without expanding all records',
    (tester) async {
      final backend = _Backend(questionJob: true);
      await showPage(tester, backend);
      await tester.tap(find.text('中文资料.md'));
      await tester.pumpAndSettle();
      expect(find.text('第一题'), findsOneWidget);
      expect(find.text('第二题'), findsNothing);
      await tester.tap(find.text('下一条'));
      await tester.pumpAndSettle();
      expect(find.text('第二题'), findsOneWidget);
      expect(find.text('第一题'), findsNothing);
      await tester.tap(find.text('上一条'));
      await tester.pumpAndSettle();
      expect(find.text('第一题'), findsOneWidget);
      expect(backend.writes, 0);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'preview and cancelled confirmation do not write; explicit confirmation refreshes library',
    (tester) async {
      final backend = _Backend();
      await showPage(tester, backend);
      await tester.tap(find.text('中文资料.md'));
      await tester.pumpAndSettle();
      expect(find.text('需要确认的中文笔记'), findsOneWidget);
      expect(backend.writes, 0);
      await tester.tap(find.text('检查完成，确认入库'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(backend.writes, 0);
      await tester.tap(find.text('检查完成，确认入库'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认入库'));
      await tester.pumpAndSettle();
      expect(backend.writes, 1);
      expect(find.text('已保存到当前工作空间'), findsOneWidget);
      expect(find.text('检查完成，确认入库'), findsNothing);
      expect(find.text('已保存资料'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'failed confirm keeps preview and reports uncertainty without automatic replay',
    (tester) async {
      final backend = _Backend(failConfirm: true);
      await showPage(tester, backend);
      await tester.tap(find.text('中文资料.md'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('检查完成，确认入库'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('确认入库'));
      await tester.pumpAndSettle();
      expect(backend.writes, 1);
      expect(find.textContaining('网络中断'), findsOneWidget);
      expect(find.text('需要确认的中文笔记'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('failed parser keeps history and never offers confirmation', (
    tester,
  ) async {
    final backend = _Backend(failedJob: true);
    await showPage(tester, backend);
    await tester.tap(find.text('中文资料.md'));
    await tester.pumpAndSettle();
    expect(find.text('解析失败；原件保留'), findsOneWidget);
    expect(find.text('检查完成，确认入库'), findsNothing);
    expect(backend.writes, 0);
  });

  testWidgets(
    'cancel resource selection does not analyze; explicit selection reuses original',
    (tester) async {
      final backend = _Backend();
      await showPage(tester, backend);
      await tester.tap(find.text('选择已有资源并预览'));
      await tester.pumpAndSettle();
      expect(find.text('从文件添加新资源'), findsNothing);
      await tester.tap(find.text('取消选择'));
      await tester.pumpAndSettle();
      expect(backend.paths.where((p) => p.endsWith('/analyze')), isEmpty);
      await tester.tap(find.text('选择已有资源并预览'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('原件.md'));
      await tester.pumpAndSettle();
      expect(
        backend.paths.where((p) => p.endsWith('/resources/original/analyze')),
        hasLength(1),
      );
      expect(find.text('需要确认的中文笔记'), findsOneWidget);
      expect(backend.writes, 0);
    },
  );

  testWidgets(
    'tables contain native cells and scroll horizontally in a narrow view',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 240,
              child: ContentBlocks([
                {
                  'type': 'table',
                  'headers': [
                    [
                      {'type': 'text', 'text': '知识点'},
                    ],
                    [
                      {'type': 'text', 'text': '说明'},
                    ],
                  ],
                  'rows': [
                    [
                      [
                        {'type': 'text', 'text': '极限'},
                      ],
                      [
                        {'type': 'latex', 'tex': r'x^2'},
                      ],
                    ],
                  ],
                },
              ]),
            ),
          ),
        ),
      );
      expect(find.byType(Table), findsOneWidget);
      expect(find.text('知识点'), findsOneWidget);
      expect(find.text('极限'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
