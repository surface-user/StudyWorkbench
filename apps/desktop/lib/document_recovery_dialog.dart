import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';

class DocumentRecoveryDialog extends StatefulWidget {
  const DocumentRecoveryDialog({
    required this.backend,
    required this.prefix,
    this.workspacePrefix,
    super.key,
  });
  final Backend backend;
  final String prefix;
  final String? workspacePrefix;

  @override
  State<DocumentRecoveryDialog> createState() => _DocumentRecoveryDialogState();
}

class _DocumentRecoveryDialogState extends State<DocumentRecoveryDialog> {
  final rows = <Map<String, dynamic>>[];
  Map<String, dynamic>? selected;
  String? error;
  bool busy = false, more = true;
  int offset = 0;
  final copyName = TextEditingController(text: '恢复的笔记.md');
  Map<String, dynamic>? copyRequest, copySource;
  bool copying = false;

  @override
  void dispose() {
    copyName.dispose();
    super.dispose();
  }

  Future<void> copyNote() async {
    if (busy || selected == null || widget.workspacePrefix == null) return;
    setState(() {
      busy = true;
      copying = true;
      error = null;
    });
    try {
      if (copyRequest == null) {
        if (copyName.text.trim().isEmpty) throw StateError('请填写新笔记名称');
        if (!copyName.text.trim().toLowerCase().endsWith('.md')) {
          throw StateError('新笔记名称必须以.md结尾');
        }
        final verified = await widget.backend.request(
          'GET',
          '${widget.prefix}/document-saves/${Uri.encodeComponent(selected!['id'] as String)}?version=${selected!['version']}',
        ) as Map;
        if (!mounted) return;
        if (verified['sha256'] != selected!['sha256'] ||
            verified['text'] != selected!['text']) {
          throw StateError('恢复点已变化，请重新选择并核对');
        }
        copySource = Map<String, dynamic>.from(selected!);
        copyRequest = {
          'request_id': List.generate(
            16,
            (_) =>
                Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
          ).join(),
          'name': copyName.text.trim(),
          'parent_id': null,
        };
      }
      final node = await widget.backend.request(
        'POST',
        '${widget.workspacePrefix}/markdown-notes',
        copyRequest,
      ) as Map;
      if (!mounted) return;
      if (node['status'] != 'ready') throw StateError('副本笔记未就绪或已被移除，记录保留');
      final target =
          '${widget.workspacePrefix}/nodes/${Uri.encodeComponent(node['resource_item_id'] as String)}/document';
      final current = await widget.backend.request('GET', target) as Map;
      if (!mounted) return;
      if (current['type'] != 'markdown' || current['working_copy'] != true) {
        throw StateError('副本不是可保存的Markdown工作文件');
      }
      if (current['sha256'] != copySource!['sha256'] ||
          current['text'] != copySource!['text']) {
        if (current['sha256'] != node['sha256']) {
          throw StateError('新笔记已被修改，拒绝覆盖；请从资源目录核对该笔记');
        }
        final saved = await widget.backend.request('PUT', target, {
          'expected_sha256': node['sha256'],
          'text': copySource!['text'],
        }) as Map;
        if (saved['sha256'] != copySource!['sha256']) {
          throw StateError('副本保存结果尚未核实，请重试对账');
        }
      }
      if (mounted) {
        Navigator.pop(context, {'copy_node': Map<String, dynamic>.from(node)});
      }
    } catch (failure) {
      if (mounted) {
        setState(
          () => error = '副本创建或保存未确认：$failure。原文件、恢复点和已创建笔记保留；重试使用原请求，不重复建笔记。',
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          copying = false;
        });
      }
    }
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final page = await widget.backend.request(
        'GET',
        '${widget.prefix}/document-saves?offset=$offset&limit=50',
      ) as List;
      if (!mounted) return;
      setState(() {
        rows.addAll(page.map((row) => Map<String, dynamic>.from(row as Map)));
        offset += page.length;
        more = page.length == 50;
      });
    } catch (failure) {
      if (mounted) setState(() => error = '恢复记录读取失败：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> preview(Map<String, dynamic> row, String version) async {
    if (busy || copyRequest != null) return;
    setState(() {
      busy = true;
      error = null;
      selected = null;
    });
    try {
      final result = await widget.backend.request(
        'GET',
        '${widget.prefix}/document-saves/${Uri.encodeComponent(row['id'] as String)}?version=$version',
      ) as Map;
      if (mounted) setState(() => selected = Map<String, dynamic>.from(result));
    } catch (failure) {
      if (mounted) {
        setState(
          () => error = '恢复点不可读取或校验未通过：$failure。待写稿在保存成功后可能已移入当前文件；不会用其他内容替代。',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String status(String? value) => switch (value) {
    'prepared' => '待重启对账',
    'committed' => '已保存',
    'interrupted' => '保存中断',
    'conflict' => '保存冲突',
    _ => '未知状态',
  };

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !copying,
    child: AlertDialog(
      title: const Text('保存恢复点'),
      content: SizedBox(
        width: 740,
        height: 480,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('只读查看保留的旧稿或待写稿。载入后仍需另行保存；原件和恢复点保留。记录按标识排序。'),
            if (busy) const LinearProgressIndicator(),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (!busy && rows.isEmpty && !more) const Text('尚无保存恢复记录'),
            Expanded(
              child: ListView(
                children: [
                  for (final row in rows)
                    ListTile(
                      title: Text(status(row['status'] as String?)),
                      subtitle: Text(row['id'] as String),
                      trailing: Wrap(
                        children: [
                          TextButton(
                            onPressed: busy || copyRequest != null
                                ? null
                                : () => preview(row, 'before'),
                            child: const Text('查看旧稿'),
                          ),
                          TextButton(
                            onPressed: busy || copyRequest != null
                                ? null
                                : () => preview(row, 'pending'),
                            child: const Text('查看待写稿'),
                          ),
                        ],
                      ),
                    ),
                  if (more)
                    TextButton(
                      onPressed: busy ? null : load,
                      child: Text(rows.isEmpty ? '重试读取记录' : '加载更多记录'),
                    ),
                ],
              ),
            ),
            if (selected != null) ...[
              Text(
                selected!['version'] == 'before' ? '旧稿内容（字面预览）' : '待写稿内容（字面预览）',
              ),
              if (selected!['unavailable_reason'] != null)
                Text(selected!['unavailable_reason'] as String),
              Expanded(
                flex: 2,
                child: SingleChildScrollView(
                  child: SelectableText(selected!['text'] as String),
                ),
              ),
              if (widget.workspacePrefix != null) ...[
                TextField(
                  controller: copyName,
                  enabled: !busy && copyRequest == null,
                  decoration: const InputDecoration(labelText: '副本名称（.md）'),
                ),
                const Text('另存会新建独立笔记，不修复原路径；失败重试沿用原名称和内容。'),
              ],
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: copying ? null : () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
        FilledButton(
          onPressed:
              busy || copyRequest != null || selected?['current_sha256'] == null
              ? null
              : () => Navigator.pop(context, selected),
          child: const Text('载入编辑草稿'),
        ),
        if (widget.workspacePrefix != null)
          FilledButton(
            onPressed: busy || selected == null ? null : copyNote,
            child: Text(copyRequest == null ? '确认另存为新笔记' : '重试另存并对账'),
          ),
      ],
    ),
  );
}
