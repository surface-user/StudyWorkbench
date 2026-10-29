import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/editor_tab_bar.dart';
import 'package:study_workbench/workspace_layout.dart';

void main() {
  testWidgets(
    'blank double click creates default page and reduced motion closes immediately',
    (tester) async {
      final layout = WorkspaceLayout.fromJson({
        'tabs': [],
        'closed_tabs': [],
        'active_tab_id': null,
      });
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MediaQuery(
              data: const MediaQueryData(disableAnimations: true),
              child: StatefulBuilder(
                builder: (context, set) => Column(
                  children: [
                    EditorTabBar(
                      layout: layout,
                      onSelect: (id) => set(() => layout.activeId = id),
                      onClose: (id) => set(() => layout.close(id)),
                      onNew: (kind) => set(() => layout.add(kind)),
                      onReopen: () {},
                      onMove: (_, _) {},
                      onMenu: (_, _) {},
                      isDirty: (_) => false,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.tapAt(const Offset(500, 18));
      await tester.pump(const Duration(milliseconds: 50));
      await tester.tapAt(const Offset(500, 18));
      await tester.pump();
      expect(layout.tabs.single.kind, 'welcome');
      await tester.tap(find.byKey(ValueKey('close-tab-${layout.activeId}')));
      await tester.pump();
      await tester.pump();
      expect(layout.tabs, isEmpty);
      expect(find.byKey(const ValueKey('editor-tab-scroll')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pump(const Duration(milliseconds: 400));
    },
  );

  testWidgets(
    'compact tabs animate, scroll active into view, expose menus and resize',
    (tester) async {
      tester.view.physicalSize = const Size(1000, 600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final layout = WorkspaceLayout.fromJson({
        'tabs': [
          {'id': 'a', 'kind': 'question'},
        ],
        'closed_tabs': [],
        'active_tab_id': 'a',
      });
      late StateSetter update;
      String? menu;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, set) {
                update = set;
                return Column(
                  children: [
                    EditorTabBar(
                      layout: layout,
                      onSelect: (id) => set(() => layout.activeId = id),
                      onClose: (id) => set(() => layout.close(id)),
                      onNew: (kind) => set(() => layout.add(kind)),
                      onReopen: () => set(layout.reopen),
                      onMove: (id, target) =>
                          set(() => layout.reorder(id, target)),
                      onMenu: (id, action) => menu = '$id:$action',
                      isDirty: (tab) => tab.id == 'a',
                    ),
                    const Expanded(child: SizedBox()),
                  ],
                );
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.getSize(find.byType(EditorTabBar)).height, 38);
      final first = find.byKey(const ValueKey('select-tab-a'));
      final initial = tester.getRect(first);
      expect(initial.width, inInclusiveRange(112, 220));
      expect(
        tester.getRect(find.byTooltip('新建标签页')).left - initial.right,
        lessThan(2),
      );
      final pointer = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await pointer.addPointer();
      await pointer.moveTo(initial.center);
      await tester.pumpAndSettle();
      expect(
        tester.getRect(first),
        initial,
        reason: 'hover must not change title or close geometry',
      );
      await tester.tap(find.byKey(const ValueKey('close-tab-a')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(
        find.byKey(const ValueKey('select-tab-a')),
        findsOneWidget,
        reason: 'closing appearance remains during contraction',
      );
      await tester.pumpAndSettle();
      expect(first, findsNothing);
      update(() {
        layout.reopen();
        for (var i = 0; i < 7; i++) {
          layout.add('web');
        }
      });
      layout.tabs.last.pageTitle = '很长的网页标题' * 30;
      layout.tabs.last.loading = true;
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump(const Duration(milliseconds: 200));
      final lastId = layout.activeId!;
      final last = find.byKey(ValueKey('select-tab-$lastId'));
      // Opening completion schedules a reveal; advance frames through that reveal.
      for (var i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(tester.getRect(last).right, lessThanOrEqualTo(905));
      expect(tester.getRect(last).left, greaterThanOrEqualTo(0));
      expect(
        tester.getSize(last).width + 2,
        220,
        reason: '220px includes the outer border',
      );
      expect(
        find.descendant(
          of: last,
          matching: find.byType(CircularProgressIndicator),
        ),
        findsOneWidget,
      );
      update(() {
        layout.tabs.last.loading = false;
        layout.tabs.last.error = '离线';
      });
      await tester.pumpAndSettle();
      expect(
        find.descendant(of: last, matching: find.byIcon(Icons.error_outline)),
        findsOneWidget,
      );
      await tester.tap(last, buttons: kSecondaryMouseButton);
      await tester.pumpAndSettle();
      expect(find.text('关闭右侧标签'), findsOneWidget);
      expect(find.text('固定标签'), findsNothing);
      await tester.tap(find.text('关闭其他标签'));
      await tester.pumpAndSettle();
      expect(menu, '$lastId:others');
      for (final width in [640.0, 1200.0, 360.0]) {
        tester.view.physicalSize = Size(width, 600);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(
          tester.getRect(find.byTooltip('新建标签页')).right,
          lessThanOrEqualTo(width),
        );
      }
      await pointer.removePointer();
    },
  );
}
