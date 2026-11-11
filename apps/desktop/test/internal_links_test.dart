import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/document_page.dart';
import 'package:study_workbench/internal_links.dart';
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

String link(String id, {String kind = 'nodes', String workspace = 'default'}) =>
    LearningLink(workspace, kind, id).uri;
Map<String, dynamic> node(String id) => {
  'resource_item_id': id,
  'name': '$id.md',
  'kind': 'resource',
  'status': 'ready',
};
Map<String, dynamic> resolved(String id, {String status = 'valid'}) => {
  'status': status,
  'message': status == 'valid' ? '有效' : '来源已移除',
  'resource': node(id),
};
WorkbenchTab tab(String id) => WorkbenchTab(
  id: id,
  kind: 'resource',
  resourceItemId: id,
  viewKind: 'document',
  resourceName: '$id.md',
);

WorkspaceLayout makeLayout(List<WorkbenchTab> tabs, String active) {
  final value = WorkspaceLayout.fromJson({
    'tabs': [],
    'closed_tabs': [],
    'active_tab_id': active,
    'version': 2,
  });
  value.tabs.addAll(tabs);
  return value;
}

void main() {
  for (final changed in [false, true]) {
    testWidgets(
      'TXT search reaches the source line with final version check: changed=$changed',
      (tester) async {
        tester.view.physicalSize = const Size(1500, 1200);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final layout = makeLayout([], '');
        var documentReads = 0;
        final point = {
          'version': 1,
          'kind': 'text_line',
          'workspace_id': 'default',
          'resource_item_id': 'txt',
          'content_sha256': 'a' * 64,
          'line': 2,
          'line_sha256': 'c' * 64,
        };
        final backend = _Backend((method, path, body) async {
          if (path.contains('/learning-search?')) {
            return {
              'items': [
                {
                  'kind': 'text_resource',
                  'id': 'txt',
                  'title': '课程.txt',
                  'snippet': '第二行关键字',
                  'uri': link('txt'),
                  'content_sha256': 'a' * 64,
                  'anchor': point,
                },
              ],
              'offset': 0,
              'total': 1,
              'has_more': false,
              'truncated': false,
              'scanned': {'text_resource': 1},
            };
          }
          if (path.endsWith('/internal-links/resolve')) return resolved('txt');
          if (path.endsWith('/document')) {
            documentReads++;
            return {
              'type': 'text',
              'text': '首行\r\n第二行关键字\r\n末行',
              'sha256': (changed && documentReads > 1 ? 'b' : 'a') * 64,
              'working_copy': false,
            };
          }
          throw StateError('$method $path');
        });
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: StatefulBuilder(
                builder: (context, set) => InternalLinkHost(
                  backend: backend,
                  workspaceId: 'default',
                  layout: layout,
                  onChanged: () => set(() {}),
                  child: layout.tabs.isEmpty
                      ? const Text('资料区域')
                      : DocumentPage(
                          backend: backend,
                          workspaceId: 'default',
                          tab: layout.tabs.single,
                          jumpAnchor: layout.tabs.single.pendingAnchor,
                          onChanged: () {},
                        ),
                ),
              ),
            ),
          ),
        );
        await tester.tap(find.text('查找学习记录'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.byKey(const ValueKey('learning-search-query')),
          '关键字',
        );
        await tester.tap(find.text('搜索 / 刷新'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('TXT资料 · 课程.txt'));
        await tester.pumpAndSettle();
        expect(layout.tabs.single.resourceItemId, 'txt');
        expect(documentReads, greaterThanOrEqualTo(3));
        if (changed) {
          expect(find.textContaining('内容已变化，旧位置未自动应用'), findsOneWidget);
          expect(find.text('定位行：第二行关键字'), findsNothing);
        } else {
          expect(
            find.byKey(const ValueKey('source-line-view')),
            findsOneWidget,
          );
          expect(find.text('定位行：第二行关键字'), findsOneWidget);
          expect(layout.tabs.single.captureView!()['source_line'], 2);
        }
        await tester.pumpWidget(const SizedBox());
      },
    );
  }
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'strict links retain legacy IDs and reject dangerous or ambiguous input',
    () {
      expect(
        LearningLink.parse(link('old.note-1_%32', kind: 'notes')).id,
        'old.note-1_2',
      );
      for (final value in [
        'https://example.com',
        'file:///D:/data',
        'javascript:x',
        link('../x'),
        link('%252f'),
        link('%2f'),
        link('%5c'),
        link('%0a'),
        link('%FF'),
        link('%xx'),
        link('..'),
        link(''),
        '${link('x')}?token=x',
        '${link('x')}#x',
        '${link('x')}/',
        '${link('x')}\n',
        link('x', workspace: '..'),
        'studyworkbench://v1:80/workspaces/default/nodes/x',
        link('x').replaceFirst('v1', 'v2'),
        link('x' * 2049),
      ]) {
        expect(
          () => LearningLink.parse(value),
          throwsFormatException,
          reason: value,
        );
      }
    },
  );

  test('history bounds identities and small view data to fifty entries', () {
    final history = LearningLinkHistory();
    for (var i = 0; i < 70; i++) {
      history.add(history.back, LinkVisit(link('n$i')));
    }
    expect(history.back.length, 50);
    expect(history.back.first.uri, link('n20'));
  });

  testWidgets('clipboard contains canonical identity only', (tester) async {
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String;
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => copyLearningLink(
                context,
                LearningLink.parse(link('old%32', kind: 'marks')),
              ),
              child: const Text('复制'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('复制'));
    await tester.pump();
    expect(copied, link('old2', kind: 'marks'));
    expect(copied, isNot(contains('token')));
  });

  testWidgets(
    'failed validation retains input; cross-space input never sends a request',
    (tester) async {
      var requests = 0;
      final backend = _Backend((method, path, body) async {
        requests++;
        return resolved('x', status: 'removed');
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LearningLinkInput(backend: backend, workspaceId: 'default'),
          ),
        ),
      );
      final input = find.byKey(const ValueKey('internal-link-input'));
      await tester.enterText(input, link('x', workspace: 'other'));
      await tester.tap(find.text('确认链接'));
      await tester.pumpAndSettle();
      expect(requests, 0);
      expect(find.textContaining('请先切换'), findsOneWidget);
      await tester.enterText(input, link('x'));
      await tester.tap(find.text('确认链接'));
      await tester.pumpAndSettle();
      expect(requests, 1);
      expect(find.textContaining('来源已移除'), findsOneWidget);
      expect(tester.widget<TextField>(input).controller!.text, link('x'));
    },
  );

  testWidgets(
    'follow/back/forward re-resolve exact mark and failures keep history',
    (tester) async {
      final layout = makeLayout([tab('source')], 'source');
      final seen = <String>[];
      var removed = false;
      final backend = _Backend((method, path, body) async {
        expect(method, 'POST');
        expect(path, '/api/workspaces/default/internal-links/resolve');
        final uri = body!['uri'] as String;
        seen.add(uri);
        final id = LearningLink.parse(uri).id;
        return {
          ...resolved(
            id == 'bookmark' ? 'target' : id,
            status: removed ? 'removed' : 'valid',
          ),
          if (id == 'bookmark') 'anchor': {'kind': 'text_line', 'line': 2},
        };
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, refresh) => InternalLinkHost(
                backend: backend,
                workspaceId: 'default',
                layout: layout,
                onChanged: () => refresh(() {}),
                child: Builder(
                  builder: (context) => TextButton(
                    onPressed: () =>
                        InternalLinkScope.maybeOf(context)!
                            .follow(link('bookmark', kind: 'marks')),
                    child: const Text('跟随'),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('跟随'));
      await tester.pumpAndSettle();
      expect(layout.activeId, isNot('source'));
      expect(layout.tabs.last.pendingAnchor!['line'], 2);
      removed = true;
      await tester.tap(find.byTooltip('返回链接来源'));
      await tester.pumpAndSettle();
      expect(find.textContaining('返回未完成'), findsOneWidget);
      removed = false;
      await tester.tap(find.byTooltip('返回链接来源'));
      await tester.pumpAndSettle();
      expect(layout.activeId, 'source');
      await tester.tap(find.byTooltip('前进链接'));
      await tester.pumpAndSettle();
      expect(seen.last, link('bookmark', kind: 'marks'));
      expect(layout.tabs.last.pendingAnchor!['line'], 2);
    },
  );

  testWidgets('failed target open preserves draft and does not add history', (
    tester,
  ) async {
    final dirty = tab('target')
      ..draft = '未保存的笔记'
      ..draftBaseSha256 = 'a' * 64;
    final layout = makeLayout([tab('source'), dirty], 'source');
    final backend = _Backend(
      (m, p, b) async => {
        ...resolved('target'),
        'anchor': {'kind': 'text_line', 'line': 2},
      },
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: InternalLinkHost(
            backend: backend,
            workspaceId: 'default',
            layout: layout,
            onChanged: () {},
            child: Builder(
              builder: (context) => TextButton(
                onPressed: () =>
                    InternalLinkScope.maybeOf(context)!
                        .follow(link('m', kind: 'marks')),
                child: const Text('跳转'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('跳转'));
    await tester.pumpAndSettle();
    expect(dirty.draft, '未保存的笔记');
    expect(layout.activeId, 'source');
    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.arrow_back))
          .onPressed,
      isNull,
    );
    expect(find.textContaining('目标含未保存草稿'), findsOneWidget);
  });

  testWidgets(
    'Markdown preview follows only an explicit click and passes displayed version',
    (tester) async {
      final current = tab('source');
      String? opened, version;
      var requests = 0;
      final backend = _Backend((method, path, body) async {
        requests++;
        return {
          'type': 'markdown',
          'text': '[教材](${link('m', kind: 'marks')})',
          'sha256': 'a' * 64,
          'working_copy': true,
        };
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InternalLinkScope(
              follow: (uri, {sourceSha256}) async {
                opened = uri;
                version = sourceSha256;
              },
              child: DocumentPage(
                backend: backend,
                workspaceId: 'default',
                tab: current,
                onChanged: () {},
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(opened, isNull);
      expect(requests, 1);
      await tester.tap(find.text('教材'));
      await tester.pumpAndSettle();
      expect(opened, link('m', kind: 'marks'));
      expect(version, 'a' * 64);
      expect(current.draftBaseSha256, isNull);
    },
  );

  testWidgets(
    'return restores text view only for matching bytes and preserves base on mismatch',
    (tester) async {
      final current = tab('source');
      var changed = false;
      final backend = _Backend(
        (method, path, body) async => {
          'type': 'markdown',
          'text': changed ? 'changed' : 'first\nsecond',
          'sha256': (changed ? 'b' : 'a') * 64,
          'working_copy': true,
        },
      );
      late StateSetter refresh;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, set) {
                refresh = set;
                return DocumentPage(
                  backend: backend,
                  workspaceId: 'default',
                  tab: current,
                  onChanged: () {},
                );
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final original = current.captureView!();
      expect(original.toString(), isNot(contains('first')));
      refresh(
        () => current.pendingView = {
          ...original,
          'raw_text': true,
          'source_line': 2,
          'selection_start': 6,
          'selection_end': 12,
        },
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('source-line-view')), findsOneWidget);
      expect(find.text('定位行：second'), findsOneWidget);
      changed = true;
      refresh(() => current.pendingView = Map.of(original));
      await tester.pumpAndSettle();
      expect(find.textContaining('返回来源内容已变化'), findsOneWidget);
      expect(current.captureView!()['sha256'], 'a' * 64);
      expect(find.text('定位行：second'), findsOneWidget);
    },
  );

  testWidgets('Markdown insertion uses checked URI and ordinary save draft', (
    tester,
  ) async {
    final current = tab('source')..documentState['mode'] = 'edit';
    final backend = _Backend((method, path, body) async {
      if (path.endsWith('/document') && method == 'GET') {
        return {
          'type': 'markdown',
          'text': '# 笔记\n',
          'sha256': 'a' * 64,
          'working_copy': true,
        };
      }
      if (path.endsWith('/internal-links/resolve')) {
        return {...resolved('target'), 'title': '教材[页]'};
      }
      throw StateError('$method $path');
    });
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DocumentPage(
            backend: backend,
            workspaceId: 'default',
            tab: current,
            onChanged: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('插入内部链接'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('internal-link-input')),
      link('target', kind: 'marks'),
    );
    await tester.tap(find.text('确认链接'));
    await tester.pumpAndSettle();
    expect(
      current.draft,
      contains('[教材\\[页\\]](${link('target', kind: 'marks')})'),
    );
    expect(current.draftBaseSha256, 'a' * 64);
    expect(find.byKey(const ValueKey('markdown-editor')), findsOneWidget);
  });
}
