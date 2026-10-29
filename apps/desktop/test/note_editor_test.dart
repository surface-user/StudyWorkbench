import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/note_editor.dart';
import 'package:study_workbench/question_contract.dart';

class _Backend implements Backend {
  bool fail = false;
  Completer<void>? pending;
  final started = Completer<void>();
  final bodies = <Map<String, dynamic>>[];
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    if (method == 'GET' && path.startsWith('/api/workspaces/math/resources?')) {
      return [
        {
          'id': 'new-image',
          'filename': '新图片.png',
          'mime': 'image/png',
          'size': 100,
        },
      ];
    }
    expect(method, 'PUT');
    expect(path, '/api/workspaces/math/notes/note');
    bodies.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
    if (!started.isCompleted) started.complete();
    if (pending != null) await pending!.future;
    if (fail) throw StateError('409 笔记已更新');
    return {};
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> note() => {
  'id': 'note',
  'title': '混合笔记',
  'revision': 'a' * 64,
  'content': [
    {'type': 'text', 'text': '原文'},
    {'type': 'latex', 'tex': 'x^2', 'display': true},
    {
      'type': 'image',
      'attachment_id': 'image',
      'alt': '图片说明',
      'caption': '原图标题',
    },
    {
      'type': 'chart',
      'attachment_id': 'chart',
      'alt': '图表说明',
      'data_attachment_id': 'data',
    },
    {'type': 'attachment', 'attachment_id': 'document', 'label': '原附件'},
    {
      'type': 'table',
      'headers': [
        [
          {'type': 'text', 'text': '列名'},
        ],
      ],
      'rows': [
        [
          [
            {'type': 'text', 'text': '旧单元格'},
            {'type': 'latex', 'tex': 'y'},
          ],
        ],
      ],
    },
  ],
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  Future<void> open(
    WidgetTester tester,
    _Backend backend,
    Map<String, dynamic> value,
  ) async {
    tester.view.physicalSize = const Size(1200, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              child: const Text('编辑'),
              onPressed: () => showDialog<bool>(
                context: context,
                barrierDismissible: false,
                builder: (_) => NoteEditor(
                  note: value,
                  backend: backend,
                  workspaceId: 'math',
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('编辑'));
    await tester.pumpAndSettle();
  }

  Finder field(String label) => find.byWidgetPredicate(
    (w) => w is TextField && w.decoration?.labelText == label,
  );

  Future<void> save(WidgetTester tester) async {
    final action = tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, '确认保存笔记'))
        .onPressed;
    await tester.runAsync(() async => await (action as dynamic)());
    await tester.pumpAndSettle();
  }

  testWidgets(
    'selecting a replacement updates only the reference and retains the old note',
    (tester) async {
      final backend = _Backend();
      final original = note()
        ..['content'] = [
          {
            'type': 'image',
            'attachment_id': 'old-image',
            'alt': '旧图',
            'caption': '保留标题',
          },
        ];
      await open(tester, backend, original);
      await tester.ensureVisible(find.text('更换此图片'));
      await tester.tap(find.text('更换此图片'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('新图片.png'));
      await tester.pumpAndSettle();
      expect(find.text('新图片.png'), findsOneWidget);
      expect(backend.bodies, isEmpty);
      await save(tester);
      expect(backend.bodies.single['content'], [
        {
          'type': 'image',
          'attachment_id': 'new-image',
          'alt': '新图片.png',
          'caption': '保留标题',
        },
      ]);
      expect(original['content'][0]['attachment_id'], 'old-image');
    },
  );

  testWidgets(
    'mixed note edits preserve all resource and inline table fields',
    (tester) async {
      final backend = _Backend();
      final original = note();
      final before = jsonEncode(original);
      await open(tester, backend, original);
      await tester.enterText(field('文字内容').first, '改过的正文');
      await tester.ensureVisible(field('图片标题（可选）'));
      await tester.enterText(field('图片标题（可选）'), '新图片标题');
      await tester.ensureVisible(find.text('表格第 1 行'));
      await tester.tap(find.text('表格第 1 行'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(field('文字内容').last);
      await tester.enterText(field('文字内容').last, '新单元格');
      await save(tester);
      expect(backend.bodies, hasLength(1));
      final saved = backend.bodies.single;
      expect(saved['expected_revision'], original['revision']);
      final expected = note()['content'] as List;
      expected[0]['text'] = '改过的正文';
      expected[2]['caption'] = '新图片标题';
      expected[5]['rows'][0][0][0]['text'] = '新单元格';
      expect(saved['content'], expected);
      expect(jsonEncode(original), before);
      expect(find.text('编辑富内容笔记'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'conflict retains the draft and cancel leaves original untouched',
    (tester) async {
      final backend = _Backend()..fail = true;
      final original = note()
        ..['content'] = [
          {'type': 'text', 'text': '原文'},
        ];
      await open(tester, backend, original);
      await tester.enterText(field('文字内容'), '保留我的草稿');
      await save(tester);
      expect(find.textContaining('草稿保留'), findsOneWidget);
      expect(find.text('保留我的草稿'), findsOneWidget);
      expect(backend.bodies, hasLength(1));
      expect(original['content'][0]['text'], '原文');
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(backend.bodies, hasLength(1));
    },
  );

  testWidgets(
    'reorder keeps edited text with its block; forbidden formula cannot save',
    (tester) async {
      final backend = _Backend();
      final original = note()
        ..['content'] = [
          {'type': 'text', 'text': '第一段'},
          {'type': 'latex', 'tex': 'x'},
        ];
      await open(tester, backend, original);
      await tester.enterText(field('文字内容'), '已编辑第一段');
      await tester.tap(find.byTooltip('下移内容段').first);
      await tester.pumpAndSettle();
      expect(find.text('已编辑第一段'), findsOneWidget);
      await tester.enterText(field('公式内容'), r'\input{secret}');
      await save(tester);
      expect(backend.bodies, isEmpty);
      expect(find.textContaining('公式含不允许'), findsOneWidget);
      await tester.enterText(field('公式内容'), 'z^2');
      await save(tester);
      expect(backend.bodies.single['content'], [
        {'type': 'latex', 'tex': 'z^2'},
        {'type': 'text', 'text': '已编辑第一段'},
      ]);
    },
  );

  test(
    'content contract rejects unknown blocks and nonrectangular tables',
    () async {
      final contract = await QuestionContract.load(bundle: false);
      expect(
        () => contract.validateContent(note()['content'] as List),
        returnsNormally,
      );
      expect(
        () => contract.validateContent([
          {'type': 'future', 'payload': 'keep'},
        ]),
        throwsFormatException,
      );
      final table = note()['content'].last as Map;
      table['rows'][0].add([
        {'type': 'text', 'text': 'extra'},
      ]);
      expect(() => contract.validateContent([table]), throwsFormatException);
    },
  );

  testWidgets(
    'save in flight disables duplicate writes and closing the dialog',
    (tester) async {
      final backend = (await tester.runAsync(
        () async => _Backend()..pending = Completer<void>(),
      ))!;
      final original = note()
        ..['content'] = [
          {'type': 'text', 'text': '正文'},
        ];
      await open(tester, backend, original);
      final action = tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '确认保存笔记'))
          .onPressed;
      late Future<void> saving;
      await tester.runAsync(() async {
        saving = (action as dynamic)() as Future<void>;
        await backend.started.future;
      });
      await tester.pump();
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, '确认保存笔记'))
            .onPressed,
        isNull,
      );
      expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '取消'))
            .onPressed,
        isNull,
      );
      final context = tester.element(find.text('编辑富内容笔记'));
      await Navigator.of(context).maybePop();
      await tester.pump();
      expect(find.text('编辑富内容笔记'), findsOneWidget);
      expect(backend.bodies, hasLength(1));
      await tester.runAsync(() async {
        backend.pending!.complete();
        await saving;
      });
      await tester.pumpAndSettle();
      expect(find.text('编辑富内容笔记'), findsNothing);
    },
  );

  testWidgets(
    'new table rows and columns stay rectangular; cancel writes nothing',
    (tester) async {
      final backend = _Backend();
      final original = note()
        ..['content'] = [
          {'type': 'text', 'text': '正文'},
        ];
      final before = jsonEncode(original);
      await open(tester, backend, original);
      await tester.tap(find.text('添加表格'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('添加一列'));
      await tester.tap(find.text('添加一列'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('添加一行'));
      await tester.pumpAndSettle();
      await save(tester);
      final table = backend.bodies.single['content'][1];
      expect(table['headers'], hasLength(2));
      expect(table['rows'], hasLength(2));
      expect(
        (table['rows'] as List).every((row) => (row as List).length == 2),
        isTrue,
      );
      expect(jsonEncode(original), before);
      backend.bodies.clear();
      await tester.tap(find.text('编辑'));
      await tester.pumpAndSettle();
      await tester.enterText(field('文字内容'), '取消这个草稿');
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(backend.bodies, isEmpty);
      expect(jsonEncode(original), before);
    },
  );
}
