import 'package:flutter/material.dart';

import 'backend.dart';

class DocumentRecoveryDialog extends StatefulWidget {
  const DocumentRecoveryDialog({
    required this.backend,
    required this.prefix,
    super.key,
  });
  final Backend backend;
  final String prefix;

  @override
  State<DocumentRecoveryDialog> createState() => _DocumentRecoveryDialogState();
}

class _DocumentRecoveryDialogState extends State<DocumentRecoveryDialog> {
  final rows = <Map<String, dynamic>>[];
  Map<String, dynamic>? selected;
  String? error;
  bool busy = false, more = true;
  int offset = 0;

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
    if (busy) return;
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
  Widget build(BuildContext context) => AlertDialog(
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
                          onPressed: busy ? null : () => preview(row, 'before'),
                          child: const Text('查看旧稿'),
                        ),
                        TextButton(
                          onPressed: busy
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
          ],
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('关闭'),
      ),
      FilledButton(
        onPressed: busy || selected?['current_sha256'] == null
            ? null
            : () => Navigator.pop(context, selected),
        child: const Text('载入编辑草稿'),
      ),
    ],
  );
}
