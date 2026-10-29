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
import 'package:study_workbench/media_page.dart';
import 'package:study_workbench/resource_page.dart';
import 'package:study_workbench/web_page.dart';
import 'package:study_workbench/webview_lifecycle.dart';
import 'package:study_workbench/workspace_layout.dart';
import 'package:study_workbench/workspace_shell.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'resource identity tabs retain native instances and legacy state',
    (tester) async {
      const evidence = String.fromEnvironment('STUDY_EVIDENCE_DIR');
      const sample = String.fromEnvironment('STUDY_MEDIA');
      expect(Backend.testData, isNotEmpty);
      final capture = GlobalKey();
      Future<void> until(bool Function() condition) async {
        for (var i = 0; i < 200; i++) {
          await tester.pump(const Duration(milliseconds: 100));
          if (condition()) return;
        }
        fail('Resource tabs did not reach expected state');
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
      final unknown = {
        'id': 'future',
        'kind': 'future',
        'draft': {'future-format': '未知草稿'},
        'state': {'draft': '未来草稿', 'version': 5},
      };
      final legacy = {
        'version': 1,
        'tabs': [
          {'id': 'legacy-question', 'kind': 'question', 'draft': '旧作答草稿'},
          unknown,
        ],
        'closed_tabs': [
          {
            'id': 'closed-web',
            'kind': 'web',
            'url': 'https://example.org/closed',
          },
        ],
        'active_tab_id': 'legacy-question',
      };
      await tester.runAsync(
        () => backend.request('PUT', '$prefix/layout', legacy),
      );
      shell.layouts['default'] = WorkspaceLayout.fromJson(legacy);
      await tester.pump(const Duration(milliseconds: 300));
      Map<String, dynamic>? node;
      Map<String, dynamic>? link;
      Map<String, dynamic>? media;
      await tester.runAsync(() async {
        final source = File('${Backend.testData}-source/资料.md');
        await source.parent.create(recursive: true);
        await source.writeAsString('# 中文资料\n保留原件和稳定身份。');
        final job = await backend.request('POST', '$prefix/resource-add-jobs', {
          'source_path': source.path,
        });
        for (var i = 0; i < 100; i++) {
          final state = await backend.request(
            'GET',
            '$prefix/resource-add-jobs/${job['id']}',
          );
          if (!['queued', 'running'].contains(state['status'])) {
            expect(state['status'], 'completed');
            break;
          }
          await Future<void>.delayed(const Duration(milliseconds: 50));
        }
        await backend.uploadMedia('default', File(sample), (_) {});
        link = Map<String, dynamic>.from(
          await backend.request('POST', '$prefix/nodes', {
            'name': '参考网页',
            'kind': 'link',
            'url': 'https://example.com',
          }),
        );
        final nodes = await backend.request('GET', '$prefix/nodes') as List;
        node = Map<String, dynamic>.from(
          nodes.firstWhere((n) => n['kind'] == 'resource'),
        );
        media = Map<String, dynamic>.from(
          nodes.firstWhere((n) => n['kind'] == 'media'),
        );
      });
      await tester.tap(find.byTooltip('刷新资源树'));
      await until(
        () => find
            .byKey(ValueKey('node-${node!['resource_item_id']}'))
            .evaluate()
            .isNotEmpty,
      );
      await tester.ensureVisible(
        find.byKey(ValueKey('node-${node!['resource_item_id']}')),
      );
      await tester.tap(
        find.byKey(ValueKey('node-${node!['resource_item_id']}')),
      );
      await until(() => find.textContaining('SHA256：').evaluate().isNotEmpty);
      final documentId = shell.layouts['default']!.activeId!;
      final documentState = tester.state(find.byType(ResourcePage));
      await tester.tap(
        find.byKey(ValueKey('node-${node!['resource_item_id']}')),
      );
      await tester.pump(const Duration(milliseconds: 200));
      expect(shell.layouts['default']!.tabs, hasLength(3));
      expect(tester.state(find.byType(ResourcePage)), same(documentState));

      // Same display name, different stable identity must remain two documents.
      final missing = {
        'resource_item_id': 'f' * 32,
        'name': node!['name'],
        'kind': 'resource',
      };
      shell.openResource(missing);
      await until(() => find.textContaining('标签与草稿已保留').evaluate().isNotEmpty);
      expect(shell.layouts['default']!.tabs, hasLength(4));
      await tester.runAsync(() async {
        node = Map<String, dynamic>.from(
          await backend.request(
            'PATCH',
            '$prefix/nodes/${node!['resource_item_id']}',
            {'name': '已改名.md', 'parent_id': null},
          ),
        );
      });
      shell.openResource(node!);
      await tester.pump(const Duration(milliseconds: 200));
      expect(shell.layouts['default']!.activeId, documentId);
      expect(tester.state(find.byType(ResourcePage)), same(documentState));

      shell.openResource(media!);
      await until(
        () =>
            find.byType(MediaPage).evaluate().isNotEmpty &&
            find.byType(WebPage).evaluate().isNotEmpty,
      );
      final mediaTab = shell.layouts['default']!.activeId!;
      final dynamic nativePlayer = tester.state(find.byType(WebPage));
      await until(() => nativePlayer.controller != null);
      var decoded = false;
      for (var i = 0; i < 100; i++) {
        decoded =
            await nativePlayer.controller.evaluateJavascript(
              source: 'document.querySelector("video")?.readyState >= 1',
            ) ==
            true;
        if (decoded) break;
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(decoded, true);
      await nativePlayer.controller.evaluateJavascript(
        source: 'document.querySelector("video").pause();document.querySelector("video").currentTime=2;document.querySelector("video").playbackRate=1.5;',
      );
      shell.openResource(link!);
      await until(() => find.byType(WebPage).evaluate().isNotEmpty);
      final dynamic browser = tester.state(find.byType(WebPage));
      await until(() => browser.controller != null);
      await tester.pump(const Duration(seconds: 2));
      await browser.controller.evaluateJavascript(
        source: 'window.resourceTabMarker="retained";',
      );
      shell.openResource(node!);
      await tester.pump(const Duration(milliseconds: 250));
      shell.openResource(link!);
      await tester.pump(const Duration(milliseconds: 250));
      expect(tester.state(find.byType(WebPage)), same(browser));
      expect(
        await browser.controller.evaluateJavascript(
          source: 'window.resourceTabMarker',
        ),
        'retained',
      );
      shell.openResource(media!);
      await tester.pump(const Duration(milliseconds: 250));
      expect(tester.state(find.byType(WebPage)), same(nativePlayer));
      expect(
        await nativePlayer.controller.evaluateJavascript(
          source: 'document.querySelector("video").currentTime',
        ) as num,
        closeTo(2, .3),
      );
      expect(
        await nativePlayer.controller.evaluateJavascript(
          source: 'document.querySelector("video").playbackRate',
        ),
        1.5,
      );
      await shell.flush();
      final saved = await tester.runAsync(
        () => backend.request('GET', '$prefix/layout'),
      );
      expect(saved['version'], 2);
      expect(saved['tabs'][0]['draft'], '旧作答草稿');
      expect(saved['tabs'][1], unknown);
      expect(saved['closed_tabs'][0]['url'], 'https://example.org/closed');
      expect(jsonEncode(saved).contains('?cap='), false);
      expect(jsonEncode(saved).contains(backend.token), false);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyW);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pump(const Duration(milliseconds: 300));
      expect(nativePlayer.mounted, false);
      await tester.tap(find.byTooltip('重新打开关闭的标签页'));
      await until(() => find.byType(MediaPage).evaluate().isNotEmpty);
      expect(shell.layouts['default']!.activeId, mediaTab);
      await tester.pump(const Duration(seconds: 1));
      shell.openResource(node!);
      await tester.pump(const Duration(milliseconds: 300));
      final boundary =
          capture.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final screenshot = await boundary.toImage(pixelRatio: 1);
      final bytes = await screenshot.toByteData(format: ui.ImageByteFormat.png);
      await File('$evidence/resource-tabs-windows.png')
          .writeAsBytes(bytes!.buffer.asUint8List());
      screenshot.dispose();
      await File('$evidence/resource-tabs-native.json').writeAsString(
        jsonEncode({
          'layout_version': 2,
          'legacy_and_unknown_retained': true,
          'duplicate_activated': true,
          'rename_instance_retained': true,
          'missing_placeholder': true,
          'web_document_retained': true,
          'media_position_speed_retained': true,
          'closed_player_disposed': true,
          'reopen_same_tab_id': true,
          'capability_and_token_not_persisted': true,
        }),
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
      await drainWebEnvironments();
    },
  );
}
