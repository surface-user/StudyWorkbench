import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';

/// The request survives retries in this window; server receipts allow recovery after restart.
class MarkdownNoteDialog extends StatefulWidget {
  const MarkdownNoteDialog({
    required this.backend,
    required this.workspaceId,
    this.parentId,
    this.fromResource = false,
    this.sourceResourceItemId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final String? parentId;
  final bool fromResource;
  final String? sourceResourceItemId;

  @override
  State<MarkdownNoteDialog> createState() => _MarkdownNoteDialogState();
}

class _MarkdownNoteDialogState extends State<MarkdownNoteDialog> {
  final name = TextEditingController(text: '新笔记.md');
  static String newRequestId() => List.generate(
    16,
    (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
  String requestId = newRequestId();
  Map<String, dynamic>? pending;
  Map<String, dynamic>? pendingNote, pendingSourceLink;
  bool busy = false;
  String? error;
  List<dynamic>? choices;
  bool recovering = false, more = false;
  int offset = 0;
  String get prefix => '/api/workspaces/${widget.workspaceId}';

  @override
  void dispose() {
    name.dispose();
    super.dispose();
  }

  Future<void> create([Map<String, dynamic>? request]) async {
    if (busy) return;
    if (request == null && pending == null && name.text.trim().isEmpty) {
      setState(() => error = '请填写笔记名称');
      return;
    }
    pending =
        request ??
        pending ??
        {
          'request_id': requestId,
          'parent_id': widget.parentId,
          'name': name.text.trim(),
        };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (pendingNote != null) {
        await finish(pendingNote!);
        return;
      }
      final result = Map<String, dynamic>.from(
        await widget.backend.request('POST', '$prefix/markdown-notes', pending)
            as Map,
      );
      if (result['status'] != 'ready') {
        throw StateError('笔记已移除或尚未就绪，创建请求与文件保留');
      }
      await finish({...result, 'open_in_edit': true});
    } catch (failure) {
      if (mounted) {
        setState(
          () => error = pendingNote == null
              ? '未确认创建结果：$failure。可重试原请求；关闭后可从“恢复创建”查找。'
              : '笔记已保存，来源关联未确认：$failure。可重试关联；关闭后笔记仍保留。',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> finish(Map<String, dynamic> node) async {
    pendingNote = node;
    final source = widget.sourceResourceItemId;
    if (source != null) {
      if (pendingSourceLink == null) {
        final existing = await widget.backend.request(
          'GET',
          '$prefix/learning-marks?resource_item_id=${Uri.encodeQueryComponent(source)}&note_resource_item_id=${Uri.encodeQueryComponent(node['resource_item_id'] as String)}&limit=1',
        ) as List;
        if (existing.isNotEmpty) {
          if (mounted) Navigator.pop(context, node);
          return;
        }
        final anchor = await widget.backend.request(
          'POST',
          '$prefix/nodes/$source/learning-anchor',
          {'kind': 'resource'},
        );
        pendingSourceLink = {
          'request_id': '${requestId}_source',
          'anchor': anchor,
          'title': node['name'],
          'note': '',
          'targets': [
            {'kind': 'file_note', 'id': node['resource_item_id']},
          ],
        };
      }
      final linked = await widget.backend.request(
        'POST',
        '$prefix/learning-marks',
        pendingSourceLink,
      ) as Map;
      if (linked['removed_at'] != null ||
          !(linked['targets'] as List).any(
            (target) =>
                target['kind'] == 'file_note' &&
                target['id'] == node['resource_item_id'],
          )) {
        throw StateError('来源关联已被移除或修改，笔记保留；请核对书签列表');
      }
    }
    if (mounted) Navigator.pop(context, node);
  }

  Future<void> loadChoices({required bool recovery, bool reset = true}) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
      recovering = recovery;
    });
    if (reset) {
      choices = [];
      offset = 0;
    }
    try {
      final rows = await widget.backend.request(
        'GET',
        recovery
            ? '$prefix/markdown-notes/requests?offset=$offset&limit=50'
            : '$prefix/markdown-notes?offset=$offset&limit=50',
      ) as List;
      if (mounted) {
        setState(() {
          choices!.addAll(
            rows.where((row) => recovery || row['kind'] == 'resource'),
          );
          offset += rows.length;
          more = rows.length == 50;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '笔记列表读取失败：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> select(Map<String, dynamic> row) async {
    if (busy) return;
    if (recovering && row['status'] != 'ready') {
      await create({
        'request_id': row['request_id'],
        'parent_id': row['requested_parent_id'],
        'name': row['requested_name'],
      });
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final current = await widget.backend.request(
        'GET',
        '$prefix/nodes/${row['resource_item_id']}',
      ) as Map;
      if (current['status'] != 'ready') throw StateError('笔记已移除或不可读取');
      final doc = await widget.backend.request(
        'GET',
        '$prefix/nodes/${row['resource_item_id']}/document',
      ) as Map;
      if (doc['type'] != 'markdown') throw StateError('此文件不是Markdown笔记，请另选');
      if (mounted) {
        await finish({
          ...row,
          ...Map<String, dynamic>.from(current),
          'open_in_edit': doc['working_copy'] == true,
        });
      }
    } catch (failure) {
      if (mounted) {
        setState(
          () => error = pendingNote == null
              ? '笔记未打开，记录保留：$failure'
              : '笔记已保存，来源关联未确认：$failure。可重试关联。',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: Text(widget.fromResource ? '记笔记' : '新建笔记'),
      content: SizedBox(
        width: 500,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: name,
                enabled: !busy && pending == null && pendingNote == null,
                maxLength: 200,
                decoration: const InputDecoration(labelText: '笔记名称（.md）'),
              ),
              if (widget.fromResource)
                Text(
                  widget.sourceResourceItemId == null
                      ? '可新建或打开已有Markdown笔记；关联来源请使用书签与备注。'
                      : '新建或选择笔记后会关联这份资料；页码或时间点请使用书签与备注。',
                ),
              Wrap(
                children: [
                  TextButton(
                    onPressed: busy || pendingNote != null
                        ? null
                        : () => loadChoices(recovery: false),
                    child: const Text('选择已有Markdown笔记'),
                  ),
                  TextButton(
                    onPressed: busy || pendingNote != null
                        ? null
                        : () => loadChoices(recovery: true),
                    child: const Text('恢复创建'),
                  ),
                ],
              ),
              if (choices != null) ...[
                Text(recovering ? '创建记录（按编号排序，已移除笔记不能恢复）' : '当前空间的Markdown文件'),
                for (final raw in choices!)
                  ListTile(
                    title: Text(
                      (raw['name'] ?? raw['requested_name']) as String,
                    ),
                    subtitle: recovering
                        ? Text('${raw['status']} · ${raw['request_id']}')
                        : null,
                    enabled:
                        !busy &&
                        pendingNote == null &&
                        raw['status'] != 'removed',
                    onTap: () => select(Map<String, dynamic>.from(raw as Map)),
                  ),
                if (choices!.isEmpty) const Text('暂无记录'),
                if (more)
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => loadChoices(recovery: recovering, reset: false),
                    child: const Text('加载更多笔记'),
                  ),
              ],
              if (pending != null)
                SelectableText('创建请求：${pending!['request_id']}'),
              if (error != null) SelectableText(error!),
              if (busy) const LinearProgressIndicator(),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
        if (pending != null || pendingNote != null)
          TextButton(
            onPressed: busy
                ? null
                : () => setState(() {
                    pending = null;
                    pendingNote = null;
                    pendingSourceLink = null;
                    requestId = newRequestId();
                    error = null;
                  }),
            child: const Text('修改名称后另建'),
          ),
        FilledButton(
          onPressed: busy ? null : () => create(),
          child: Text(
            pendingNote != null
                ? '重试保存来源关联'
                : pending == null
                ? '创建并编辑'
                : '重试原请求',
          ),
        ),
      ],
    ),
  );
}
