import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';
import 'import_page.dart';
import 'question_page.dart';

class LearningRecordDialog extends StatefulWidget {
  const LearningRecordDialog({
    required this.backend,
    required this.scope,
    required this.workspaceId,
    required this.attemptId,
    this.onOpenResource,
    super.key,
  });
  final Backend backend;
  final String scope, workspaceId;
  final int attemptId;
  final ValueChanged<Map<String, dynamic>>? onOpenResource;
  @override
  State<LearningRecordDialog> createState() => _LearningRecordDialogState();
}

class _LearningRecordDialogState extends State<LearningRecordDialog> {
  final note = TextEditingController();
  final errorType = TextEditingController();
  final points = TextEditingController();
  bool correctPoints = false, moreNotes = true;
  String? noteId;
  List notes = [];
  Map? linkedNote;
  String? rating;
  Map? record, version;
  List events = [];
  String? error;
  String kind = 'annotation';
  bool busy = false;
  Map<String, dynamic>? pending;
  final requestId = List.generate(
    24,
    (_) => Random.secure().nextInt(16).toRadixString(16),
  ).join();
  String get endpoint => '${widget.scope}/attempts/${widget.attemptId}';
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    note.dispose();
    errorType.dispose();
    points.dispose();
    super.dispose();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> load() => run(() async {
    final data = await widget.backend.request('GET', '$endpoint/record') as Map;
    if (mounted) {
      setState(() {
        record = data;
        events = List.of(data['events'] as List);
      });
    }
  });
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('学习记录与作答时版本'),
    content: SizedBox(
      width: 700,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (busy) const LinearProgressIndicator(),
            if (error != null) SelectableText(error!),
            Text(
              record?['version_status'] == 'known'
                  ? '当时知识点：${record!['knowledge_points']}'
                  : '历史版本未知，不使用当前题目补造历史',
            ),
            if (record != null)
              Text(
                '记录知识点：${record!['effective_knowledge_points'] ?? '未知'} · 已记录复习 ${record!['reviewed_count'] ?? 0} 次',
              ),
            for (final related in record?['related_notes'] as List? ?? [])
              TextButton(
                onPressed: busy || related['available'] != true
                    ? null
                    : () => run(() async {
                        final data = await widget.backend.request(
                          'GET',
                          '$endpoint/notes/${related['id']}',
                        ) as Map;
                        if (mounted) setState(() => linkedNote = data);
                      }),
                child: Text('相关笔记：${related['title']}'),
              ),
            if (linkedNote != null) ...[
              Text(linkedNote!['title'] as String),
              ContentBlocks(
                linkedNote!['content'] as List,
                backend: widget.backend,
                workspaceId: widget.workspaceId,
              ),
            ],
            if (record?['question_version_id'] != null)
              TextButton(
                onPressed: busy
                    ? null
                    : () => run(() async {
                        final data = await widget.backend.request(
                          'GET',
                          '${widget.scope}/question-versions/${record!['question_version_id']}',
                        ) as Map;
                        if (mounted) setState(() => version = data);
                      }),
                child: const Text('查看作答时确认快照'),
              ),
            for (final id in [
              if (record?['resource_item_id'] != null)
                record!['resource_item_id'],
              ...?record?['source_resource_item_ids'] as List?,
            ])
              TextButton(
                onPressed: busy || widget.onOpenResource == null
                    ? null
                    : () => run(() async {
                        final node = await widget.backend.request(
                          'GET',
                          '${widget.scope}/nodes/$id',
                        ) as Map<String, dynamic>;
                        widget.onOpenResource!(node);
                      }),
                child: Text(
                  id == record?['resource_item_id'] ? '打开当前题目文件' : '打开来源资源',
                ),
              ),
            if (record != null && record!['resource_item_id'] == null)
              const Text('当前题目文件未关联或已缺失，历史记录保留。'),
            if (version?['passage'] != null)
              ContentBlocks(
                version!['passage']['content'] as List,
                backend: widget.backend,
                workspaceId: widget.workspaceId,
                versionId: version!['id'] as String,
              ),
            if (version != null)
              QuestionPreview(
                question: Map<String, dynamic>.from(
                  version!['question'] as Map,
                ),
                backend: widget.backend,
                workspaceId: widget.workspaceId,
                versionId: version!['id'] as String,
              ),
            for (final event in events)
              Text(
                '${event['created_at']} · ${event['kind'] == 'reviewed' ? '复习记录' : '注记'} · ${event['note']}\n错误类型：${event['error_type'] ?? '未填写'} · 自评：${const {'again': '需要重学', 'hard': '困难', 'good': '基本理解', 'easy': '熟练'}[event['self_rating']] ?? '未填写'}${event['knowledge_points'] == null ? '' : '\n知识点修订：${event['knowledge_points']}'}',
              ),
            if (record?['next_before_id'] != null)
              TextButton(
                onPressed: busy
                    ? null
                    : () => run(() async {
                        final page = await widget.backend.request(
                          'GET',
                          '$endpoint/record?before_id=${record!['next_before_id']}',
                        ) as Map;
                        if (mounted) {
                          setState(() {
                            record = page;
                            events.addAll(page['events'] as List);
                          });
                        }
                      }),
                child: const Text('加载更早注记'),
              ),
            const Text('追加记录保留历史，不修改标准答案、分数或正确连击。'),
            CheckboxListTile(
              value: correctPoints,
              title: const Text('修订此记录的知识点（不改题目或当时快照）'),
              onChanged: busy || pending != null
                  ? null
                  : (v) => setState(() => correctPoints = v!),
            ),
            if (correctPoints)
              TextField(
                controller: points,
                enabled: !busy && pending == null,
                maxLength: 50000,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: '每行一个知识点；留空明确清除记录标签',
                ),
              ),
            if (moreNotes)
              TextButton(
                onPressed: busy || pending != null
                    ? null
                    : () => run(() async {
                        final page = await widget.backend.request(
                          'GET',
                          '${widget.scope}/notes?offset=${notes.length}&limit=50',
                        ) as List;
                        if (mounted) {
                          setState(() {
                            notes.addAll(page);
                            moreNotes = page.length == 50;
                          });
                        }
                      }),
                child: Text(notes.isEmpty ? '选择关联笔记' : '加载更多笔记'),
              ),
            if (notes.isNotEmpty)
              DropdownButton<String>(
                key: const ValueKey('related-note-picker'),
                value: noteId,
                hint: const Text('关联笔记（可选）'),
                isExpanded: true,
                items: [
                  const DropdownMenuItem<String>(
                    value: null,
                    child: Text('不关联笔记'),
                  ),
                  for (final item in notes)
                    DropdownMenuItem(
                      value: item['id'] as String,
                      child: Text(
                        item['title'] as String,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: busy || pending != null
                    ? null
                    : (s) => setState(() => noteId = s),
              ),
            DropdownButton<String>(
              value: kind,
              items: const [
                DropdownMenuItem(value: 'annotation', child: Text('学习注记')),
                DropdownMenuItem(value: 'reviewed', child: Text('复习记录')),
              ],
              onChanged: busy || pending != null
                  ? null
                  : (s) => setState(() => kind = s!),
            ),
            TextField(
              controller: errorType,
              enabled: !busy && pending == null,
              maxLength: 100,
              decoration: const InputDecoration(labelText: '错误类型（可选）'),
            ),
            DropdownButton<String>(
              value: rating,
              hint: const Text('自评（可选）'),
              items: [
                for (final entry in const {
                  'again': '需要重学',
                  'hard': '困难',
                  'good': '基本理解',
                  'easy': '熟练',
                }.entries)
                  DropdownMenuItem(value: entry.key, child: Text(entry.value)),
              ],
              onChanged: busy || pending != null
                  ? null
                  : (s) => setState(() => rating = s),
            ),
            TextField(
              controller: note,
              enabled: !busy && pending == null,
              maxLength: 4000,
              maxLines: 3,
              decoration: const InputDecoration(labelText: '注记或复习说明'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () => run(() async {
                      if (note.text.trim().isEmpty) throw StateError('请填写说明');
                      pending ??= {
                        'request_id': requestId,
                        'kind': kind,
                        'note': note.text,
                        if (errorType.text.trim().isNotEmpty)
                          'error_type': errorType.text.trim(),
                        if (rating != null) 'self_rating': rating,
                        if (noteId != null) 'note_id': noteId,
                        if (correctPoints)
                          'knowledge_points': points.text
                              .split('\n')
                              .map((p) => p.trim())
                              .where((p) => p.isNotEmpty)
                              .toList(),
                      };
                      try {
                        await widget.backend.request(
                          'POST',
                          '$endpoint/events',
                          pending,
                        );
                      } on BackendError catch (failure) {
                        // These responses reject before inserting; unknown outcomes keep the original request.
                        if ({404, 413, 422}.contains(failure.statusCode)) {
                          pending = null;
                        }
                        rethrow;
                      }
                      if (context.mounted) Navigator.pop(context);
                    }),
              child: const Text('追加并关闭'),
            ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('关闭'),
      ),
    ],
  );
}
