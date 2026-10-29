import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';
import 'package:study_workbench/learning_record_dialog.dart';

class _Backend implements Backend {
  final writes = <Map<String, dynamic>>[];
  int? rejectStatus;
  @override
  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    if (method == 'GET') {
      if (path.contains('/notes?')) {
        return [
          {'id': 'note-1', 'title': '关联笔记'},
        ];
      }
      return {
        'version_status': 'unknown',
        'events': [],
        'source_resource_item_ids': [],
      };
    }
    writes.add(Map.of(body!));
    if (rejectStatus != null) throw BackendError(rejectStatus!, '明确拒绝');
    throw StateError('response lost');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'unknown version stays explicit and failed event preserves text and retry id',
    (tester) async {
      tester.view.physicalSize = const Size(1200, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final backend = _Backend();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LearningRecordDialog(
              backend: backend,
              scope: '/api/workspaces/default',
              workspaceId: 'default',
              attemptId: 1,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('历史版本未知'), findsOneWidget);
      expect(find.text('查看作答时确认快照'), findsNothing);
      await tester.tap(find.text('选择关联笔记'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const ValueKey('related-note-picker')),
      );
      await tester.tap(find.byKey(const ValueKey('related-note-picker')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('关联笔记').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, '每行一个知识点；留空明确清除记录标签'),
        '积分\n极限',
      );
      await tester.enterText(find.byType(TextField).last, '保留的学习注记');
      await tester.ensureVisible(find.text('追加并关闭'));
      await tester.tap(find.text('追加并关闭'));
      await tester.pumpAndSettle();
      expect(find.textContaining('response lost'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField).last).controller!.text,
        '保留的学习注记',
      );
      await tester.tap(find.text('追加并关闭'));
      await tester.pumpAndSettle();
      expect(backend.writes.length, 2);
      expect(backend.writes[0], backend.writes[1]);
      expect(backend.writes[0]['note_id'], 'note-1');
      expect(backend.writes[0]['knowledge_points'], ['积分', '极限']);
      // A confirmed validation rejection permits correction; a lost response above did not.
      backend.rejectStatus = 422;
      await tester.tap(find.text('追加并关闭'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField).last).enabled,
        true,
      );
      await tester.enterText(find.byType(TextField).last, '修正后注记');
      await tester.tap(find.text('追加并关闭'));
      await tester.pumpAndSettle();
      expect(backend.writes.last['note'], '修正后注记');
    },
  );
}
