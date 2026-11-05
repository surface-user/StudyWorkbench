import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/learning_search_dialog.dart';

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

Map<String, dynamic> row(String id, {String kind = 'file_note'}) => {
  'kind': kind,
  'id': id,
  'title': id,
  'snippet': '<script>纯文本拥塞</script>',
  'uri':
      'studyworkbench://v1/workspaces/default/${kind == 'file_note'
          ? 'nodes'
          : kind == 'mark'
          ? 'marks'
          : 'notes'}/$id',
  if (kind == 'file_note') 'content_sha256': 'a' * 64,
  if (kind != 'file_note') 'revision': 'rev1',
};
Map<String, dynamic> page(
  List<Map<String, dynamic>> rows, {
  int offset = 0,
  bool more = false,
  bool truncated = false,
}) => {
  'items': rows,
  'offset': offset,
  'total': 3,
  'has_more': more,
  'truncated': truncated,
  'reasons': truncated ? ['达到预算，结果不完整'] : [],
  'scanned': {'file_note': 2, 'legacy_note': 1, 'mark': 0, 'bytes': 80},
};

Future<void> show(
  WidgetTester tester,
  Backend backend, {
  ValueChanged<String>? opened,
}) async {
  tester.view.physicalSize = const Size(1400, 1100);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () async {
              final result = await showDialog<String>(
                context: context,
                barrierDismissible: false,
                builder: (_) => LearningSearchDialog(
                  backend: backend,
                  workspaceId: 'default',
                ),
              );
              if (result != null) opened?.call(result);
            },
            child: const Text('打开搜索'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('打开搜索'));
  await tester.pumpAndSettle();
}

Future<void> search(WidgetTester tester, [String query = '拥塞']) async {
  await tester.enterText(
    find.byKey(const ValueKey('learning-search-query')),
    query,
  );
  await tester.tap(find.text('搜索 / 刷新'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'bounded results show truncation and plain snippets; next page deduplicates stable IDs',
    (tester) async {
      final seen = <String>[];
      final backend = _Backend((method, path, body) async {
        expect(method, 'GET');
        seen.add(path);
        return path.contains('offset=0')
            ? page([row('one')], more: true, truncated: true)
            : page([row('one'), row('two')], offset: 1);
      });
      await show(tester, backend);
      await search(tester, '拥塞%_');
      expect(Uri.parse(seen.first).queryParameters['q'], '拥塞%_');
      expect(find.textContaining('范围不完整'), findsOneWidget);
      expect(find.text('<script>纯文本拥塞</script>'), findsOneWidget);
      await tester.tap(find.text('加载更多结果'));
      await tester.pumpAndSettle();
      expect(seen.last, contains('offset=1'));
      expect(find.text('MD文件 · one'), findsOneWidget);
      expect(find.text('MD文件 · two'), findsOneWidget);
    },
  );

  testWidgets(
    'blank query is rejected locally and failures preserve old results and query',
    (tester) async {
      var requests = 0, fail = false;
      final backend = _Backend((method, path, body) async {
        requests++;
        if (fail) throw StateError('断连');
        return page([row('saved')]);
      });
      await show(tester, backend);
      await search(tester, '   ');
      expect(requests, 0);
      await search(tester);
      fail = true;
      await tester.tap(find.text('搜索 / 刷新'));
      await tester.pumpAndSettle();
      expect(find.text('MD文件 · saved'), findsOneWidget);
      expect(find.textContaining('原查询和结果保留'), findsOneWidget);
      expect(
        tester
            .widget<TextField>(
              find.byKey(const ValueKey('learning-search-query')),
            )
            .controller!
            .text,
        '拥塞',
      );
    },
  );

  testWidgets(
    'changed file result refuses stale jump and keeps search available',
    (tester) async {
      String? opened;
      final backend = _Backend((method, path, body) async {
        if (path.contains('/learning-search?')) return page([row('file')]);
        if (path.endsWith('/internal-links/resolve')) {
          return {'status': 'valid'};
        }
        return {'sha256': 'b' * 64};
      });
      await show(tester, backend, opened: (uri) => opened = uri);
      await search(tester);
      await tester.tap(find.text('MD文件 · file'));
      await tester.pumpAndSettle();
      expect(opened, isNull);
      expect(find.textContaining('正文已变化'), findsOneWidget);
      expect(find.text('MD文件 · file'), findsOneWidget);
    },
  );

  testWidgets(
    'current file and legacy revision are checked before returning URI',
    (tester) async {
      for (final kind in ['file_note', 'legacy_note']) {
        String? opened;
        final value = row(kind, kind: kind);
        final backend = _Backend((method, path, body) async {
          if (path.contains('/learning-search?')) return page([value]);
          if (path.endsWith('/internal-links/resolve')) {
            return {
              'status': 'valid',
              'note': {'revision': 'rev1'},
            };
          }
          return {'sha256': 'a' * 64};
        });
        await show(tester, backend, opened: (uri) => opened = uri);
        await search(tester);
        await tester.tap(
          find.text('${kind == 'file_note' ? 'MD文件' : '旧笔记'} · $kind'),
        );
        await tester.pumpAndSettle();
        expect(opened, value['uri']);
        await tester.pumpWidget(const SizedBox());
        await tester.pumpAndSettle();
      }
    },
  );

  testWidgets(
    'changed legacy note revision keeps result and explains refresh',
    (tester) async {
      final backend = _Backend(
        (method, path, body) async => path.contains('/learning-search?')
            ? page([row('old', kind: 'legacy_note')])
            : {
                'status': 'valid',
                'note': {'revision': 'rev2'},
              },
      );
      await show(tester, backend);
      await search(tester);
      await tester.tap(find.text('旧笔记 · old'));
      await tester.pumpAndSettle();
      expect(find.textContaining('旧笔记已变化'), findsOneWidget);
    },
  );

  testWidgets(
    'invalid-source bookmark opens retained remark without claiming a jump',
    (tester) async {
      final backend = _Backend((method, path, body) async {
        if (path.contains('/learning-search?')) {
          return page([row('mark', kind: 'mark')]);
        }
        if (path.contains('/learning-marks?')) return [];
        return {
          'id': 'mark',
          'title': '拥塞疑问',
          'note': '保留的备注',
          'revision': 1,
          'targets': [],
          'target_details': [],
          'resource_item_id': 'source',
          'anchor': {'version': 1, 'kind': 'text_line', 'line': 2},
          'location': {'status': 'removed', 'message': '来源已移除，备注保留'},
        };
      });
      await show(tester, backend);
      await search(tester);
      await tester.tap(find.text('书签/备注 · mark'));
      await tester.pumpAndSettle();
      expect(find.text('来源已移除，备注保留'), findsOneWidget);
      expect(find.widgetWithText(TextField, '保留的备注'), findsOneWidget);
      await tester.tap(find.text('返回来源位置'));
      await tester.pumpAndSettle();
      expect(find.textContaining('操作未完成'), findsOneWidget);
      expect(find.text('书签与备注'), findsOneWidget);
    },
  );
}
