import 'package:flutter/material.dart';

import 'backend.dart';
import 'learning_marks_dialog.dart';

class LearningSearchDialog extends StatefulWidget {
  const LearningSearchDialog({
    required this.backend,
    required this.workspaceId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  @override
  State<LearningSearchDialog> createState() => _LearningSearchDialogState();
}

class _LearningSearchDialogState extends State<LearningSearchDialog> {
  final query = TextEditingController();
  final rows = <Map<String, dynamic>>[];
  Map<String, dynamic>? result;
  String? error, searched;
  int offset = 0;
  bool busy = false;
  String get scope => '/api/workspaces/${widget.workspaceId}';

  Future<void> search({bool more = false}) async {
    if (busy) return;
    final current = more ? searched! : query.text;
    if (current.trim().isEmpty || current.length > 200) {
      setState(() => error = '请输入1–200字符的非空搜索词');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final page = Map<String, dynamic>.from(
        await widget.backend.request(
          'GET',
          '$scope/learning-search?q=${Uri.encodeQueryComponent(current)}&offset=${more ? offset : 0}&limit=50',
        ) as Map,
      );
      if (!mounted) return;
      setState(() {
        if (!more) rows.clear();
        final incoming = (page['items'] as List).map(
          (v) => Map<String, dynamic>.from(v as Map),
        );
        for (final row in incoming) {
          final index = rows.indexWhere(
            (old) => old['kind'] == row['kind'] && old['id'] == row['id'],
          );
          if (index < 0) {
            rows.add(row);
          } else {
            rows[index] = row;
          }
        }
        result = page;
        searched = current;
        offset = (page['offset'] as int) + (page['items'] as List).length;
      });
    } catch (failure) {
      if (mounted) setState(() => error = '搜索未完成，原查询和结果保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> open(Map<String, dynamic> row) async {
    if (busy) return;
    if (row['kind'] == 'mark') {
      final node = await showDialog<Map<String, dynamic>>(
        context: context,
        barrierDismissible: false,
        builder: (_) => LearningMarksDialog(
          backend: widget.backend,
          workspaceId: widget.workspaceId,
          initialMarkId: row['id'] as String,
        ),
      );
      if (mounted && node != null) Navigator.pop(context, row['uri'] as String);
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final resolved = await widget.backend.request(
        'POST',
        '$scope/internal-links/resolve',
        {'uri': row['uri']},
      ) as Map;
      if (resolved['status'] != 'valid') {
        throw StateError(resolved['message'] as String? ?? '目标不可用');
      }
      if (row['kind'] == 'file_note') {
        final doc = await widget.backend.request(
          'GET',
          '$scope/nodes/${row['id']}/document',
        ) as Map;
        if (doc['sha256'] != row['content_sha256']) {
          throw StateError('笔记正文已变化，请刷新搜索后再打开');
        }
      } else if ((resolved['note'] as Map)['revision'] != row['revision']) {
        throw StateError('旧笔记已变化，请刷新搜索后再打开');
      }
      if (mounted) Navigator.pop(context, row['uri'] as String);
    } catch (failure) {
      if (mounted) setState(() => error = '结果未打开，记录保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('查找学习记录'),
      content: SizedBox(
        width: 800,
        height: 560,
        child: Column(
          children: [
            const Text('搜索MD笔记文件当前正文、旧富内容笔记和书签备注；不含TXT全文或OCR。'),
            TextField(
              key: const ValueKey('learning-search-query'),
              controller: query,
              enabled: !busy,
              maxLength: 200,
              decoration: const InputDecoration(labelText: '搜索词'),
              onSubmitted: (_) => search(),
            ),
            TextButton(
              onPressed: busy ? null : search,
              child: const Text('搜索 / 刷新'),
            ),
            if (busy) const LinearProgressIndicator(),
            if (error != null) SelectableText(error!),
            if (result != null) ...[
              Text('结果对应搜索词：$searched'),
              Text('本次扫描匹配${result!['total']}条；翻页期间内容可能变化，可刷新。'),
              if (result!['truncated'] == true)
                SelectableText(
                  '范围不完整：${(result!['reasons'] as List).join('；')}',
                ),
              Text('已扫描：${result!['scanned']}'),
            ],
            Expanded(
              child: ListView(
                children: [
                  for (final row in rows)
                    ListTile(
                      title: Text(
                        '${switch (row['kind']) {
                          'file_note' => 'MD文件',
                          'legacy_note' => '旧笔记',
                          _ => '书签/备注',
                        }} · ${row['title']}',
                      ),
                      subtitle: Text(row['snippet'] as String),
                      onTap: busy ? null : () => open(row),
                    ),
                  if (result != null && rows.isEmpty)
                    Text(
                      result!['truncated'] == true
                          ? '已扫描范围内无匹配，不代表全库无结果。'
                          : '当前搜索范围内无匹配。',
                    ),
                  if (result?['has_more'] == true)
                    TextButton(
                      onPressed: busy ? null : () => search(more: true),
                      child: const Text('加载更多结果'),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ],
    ),
  );
}
