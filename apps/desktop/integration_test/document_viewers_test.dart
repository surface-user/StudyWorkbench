import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/main.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Windows Markdown workfiles, PDF pages, image and Word structure', (
    tester,
  ) async {
    const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
    const root = String.fromEnvironment('STUDY_ROOT');
    expect(Backend.testData, isNotEmpty);
    final capture = GlobalKey();
    Future<void> until(bool Function() condition) async {
      for (var i = 0; i < 300; i++) {
        await tester.pump(const Duration(milliseconds: 100));
        if (condition()) return;
      }
      fail(
        'Document viewer did not reach expected state: ${find.byType(Text).evaluate().map((e) => (e.widget as Text).data).join(" | ")}',
      );
    }

    Future<void> close() async {
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyW);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pump(const Duration(milliseconds: 300));
    }

    await tester.pumpWidget(
      RepaintBoundary(key: capture, child: const StudyApp()),
    );
    await until(
      () =>
          find.byType(WorkspaceShell).evaluate().isNotEmpty &&
          find.text('添加资源').evaluate().isNotEmpty,
    );
    final shell = tester.state<WorkspaceShellState>(
      find.byType(WorkspaceShell),
    );
    final backend = shell.widget.backend;
    const prefix = '/api/workspaces/default';
    final source = Directory('${Backend.testData}-source/文件查看');
    late Map<String, dynamic> markdown, pdf, picture, word;
    const raw = r'''# 中文学习资料
**公式和图片** $x^2+1$

![本地图片](图示.png)
![网络图片](https://example.com/private.png)
''';
    await tester.runAsync(() async {
      await source.create(recursive: true);
      await File('${source.path}/笔记.md').writeAsString(raw);
      await File('${source.path}/图示.png').writeAsBytes(
        base64Decode(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        ),
      );
      await File('$root/contracts/samples/original-study.pdf')
          .copy('${source.path}/讲义.pdf');
      await File('$root/contracts/samples/original-study.docx')
          .copy('${source.path}/资料.docx');
      final started = await backend.request(
        'POST',
        '$prefix/resource-add-jobs',
        {'source_path': source.path},
      );
      for (var i = 0; i < 100; i++) {
        final job = await backend.request(
          'GET',
          '$prefix/resource-add-jobs/${started['id']}',
        );
        if (!['queued', 'running'].contains(job['status'])) {
          expect(job['status'], 'completed');
          break;
        }
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
      final folder = (await backend.request('GET', '$prefix/nodes') as List)
          .firstWhere((n) => n['kind'] == 'folder');
      final nodes = await backend.request(
        'GET',
        '$prefix/nodes?parent_id=${folder['resource_item_id']}',
      ) as List;
      markdown = Map<String, dynamic>.from(
        nodes.firstWhere((n) => n['name'] == '笔记.md'),
      );
      pdf = Map<String, dynamic>.from(
        nodes.firstWhere((n) => n['name'] == '讲义.pdf'),
      );
      picture = Map<String, dynamic>.from(
        nodes.firstWhere((n) => n['name'] == '图示.png'),
      );
      word = Map<String, dynamic>.from(
        nodes.firstWhere((n) => n['name'] == '资料.docx'),
      );
    });
    shell.openResource(markdown);
    await until(() => find.textContaining('已阻止外部或绝对图片').evaluate().isNotEmpty);
    await tester.tap(find.text('创建工作副本并编辑'));
    await until(
      () => find.byKey(const ValueKey('markdown-editor')).evaluate().isNotEmpty,
    );
    await tester.enterText(
      find.byKey(const ValueKey('markdown-editor')),
      '# 已编辑工作副本\n中文内容',
    );
    await shell.flush();
    shell.openResource(pdf);
    await until(
      () =>
          find.text('第1页 / 2页').evaluate().isNotEmpty &&
          find.byType(Image).evaluate().isNotEmpty,
    );
    await tester.tap(find.byTooltip('下一页'));
    await until(() => find.text('第2页 / 2页').evaluate().isNotEmpty);
    await tester.tap(find.byType(DropdownButton<double>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('150%').last);
    await tester.pumpAndSettle();
    final pdfTab = shell.layouts['default']!.tabs.last;
    expect(pdfTab.documentState['zoom'], 1.5);
    shell.openResource(markdown);
    await tester.pump(const Duration(milliseconds: 300));
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('markdown-editor')))
          .controller!
          .text,
      '# 已编辑工作副本\n中文内容',
    );
    await close();
    expect(find.text('保存文件并关闭'), findsOneWidget);
    await tester.tap(find.text('取消关闭'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存工作文件'));
    await until(
      () =>
          find.text('文件未保存').evaluate().isEmpty &&
          !shell.layouts['default']!.tabs.first.loading,
    );
    final saved = await tester.runAsync(
      () => backend.request(
        'GET',
        '$prefix/nodes/${markdown['resource_item_id']}/document',
      ),
    );
    expect(saved['text'], '# 已编辑工作副本\n中文内容');
    expect(saved['working_copy'], true);
    expect(await File('${source.path}/笔记.md').readAsString(), raw);
    await tester.tap(find.byKey(const ValueKey('markdown-editor')));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.enterText(
      find.byKey(const ValueKey('markdown-editor')),
      '冲突草稿',
    );
    await tester.pump(const Duration(milliseconds: 200));
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('markdown-editor')))
          .controller!
          .text,
      '冲突草稿',
    );
    expect(shell.layouts['default']!.tabs.first.draft, '冲突草稿');
    expect(shell.layouts['default']!.tabs.first.draftBaseSha256, isNotNull);
    await tester.runAsync(() async {
      final working = Directory(
        '${Backend.testData}/workspaces/default/working/${markdown['resource_item_id']}',
      );
      final file =
          await working
                  .list(recursive: true)
                  .where(
                    (entry) =>
                        entry is File && entry.path.endsWith('current.md'),
                  )
                  .first
              as File;
      await file.writeAsString('外部修改');
    });
    await tester.tap(find.text('保存工作文件'));
    await until(() => find.textContaining('409').evaluate().isNotEmpty);
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('markdown-editor')))
          .controller!
          .text,
      '冲突草稿',
    );
    expect(shell.layouts['default']!.tabs.first.draftBaseSha256, isNotNull);
    expect(shell.busy, false);
    expect(shell.closingTabs, isEmpty);
    expect(ModalRoute.of(shell.context)?.isCurrent, true);
    await close();
    await until(() => find.text('放弃更改').evaluate().isNotEmpty);
    await tester.tap(find.text('放弃更改'));
    await tester.pumpAndSettle();
    shell.openResource(markdown);
    await until(
      () => find.byKey(const ValueKey('markdown-editor')).evaluate().isNotEmpty,
    );
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('markdown-editor')))
          .controller!
          .text,
      '外部修改',
    );
    shell.openResource(picture);
    await until(
      () =>
          find.byType(InteractiveViewer).evaluate().isNotEmpty &&
          find.byType(Image).evaluate().isNotEmpty,
    );
    shell.openResource(word);
    await until(() => find.textContaining('Word结构预览').evaluate().isNotEmpty);
    expect(find.textContaining('中文题干'), findsWidgets);
    shell.openResource(pdf);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('第2页 / 2页'), findsOneWidget);
    expect(
      tester
          .widget<DropdownButton<double>>(find.byType(DropdownButton<double>))
          .value,
      1.5,
    );
    await shell.flush();
    final persisted = await tester.runAsync(
      () => backend.request('GET', '$prefix/layout'),
    );
    expect(
      (persisted['tabs'] as List).firstWhere(
        (t) => t['resource_item_id'] == pdf['resource_item_id'],
      )['document_state']['page'],
      2,
    );
    await tester.tap(find.byTooltip('刷新资源树'));
    await until(() => find.text('文件查看').evaluate().isNotEmpty);
    await tester.ensureVisible(find.text('文件查看'));
    await tester.tap(find.text('文件查看'));
    await until(
      () => find
          .byKey(ValueKey('node-${markdown['resource_item_id']}'))
          .evaluate()
          .isNotEmpty,
    );
    await tester.pump(const Duration(milliseconds: 400));
    final boundary =
        capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final screenshot = await boundary.toImage(pixelRatio: 1);
    final bytes = await screenshot.toByteData(format: ui.ImageByteFormat.png);
    await File('$evidence/document-viewers-windows.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    screenshot.dispose();
    await File('$evidence/document-viewers-native.json').writeAsString(
      jsonEncode({
        'markdown_saved_workcopy': true,
        'source_unchanged': true,
        'dirty_close_confirmed': true,
        'conflict_draft_retained': true,
        'external_content_retained': true,
        'pdf_page_zoom_retained': true,
        'relative_image_scoped': true,
        'remote_image_blocked': true,
        'image_viewed': true,
        'word_structure_viewed': true,
      }),
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
  });
}
