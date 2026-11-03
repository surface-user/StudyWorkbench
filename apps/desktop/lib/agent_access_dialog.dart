import 'package:flutter/material.dart';

import 'backend.dart';

class AgentAccessDialog extends StatefulWidget {
  const AgentAccessDialog({
    required this.backend,
    required this.scope,
    required this.attempts,
    super.key,
  });
  final Backend backend;
  final String scope;
  final List attempts;

  @override
  State<AgentAccessDialog> createState() => _AgentAccessDialogState();
}

class _AgentAccessDialogState extends State<AgentAccessDialog> {
  final selected = <int>{};
  String? grantId, error;
  List? summaries;
  bool busy = false;
  String get endpoint => '${widget.scope}/agent-grants';

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

  Future<void> revoke() async {
    try {
      await widget.backend.request('DELETE', '$endpoint/$grantId');
    } on BackendError catch (failure) {
      if (failure.statusCode != 404) {
        rethrow;
      }
    }
    if (mounted) {
      setState(() {
        grantId = null;
        summaries = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy && grantId == null,
    child: AlertDialog(
      title: const Text('授权读取作答摘要'),
      content: SizedBox(
        width: 640,
        height: 420,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('选择本次允许读取的记录（最多100条）。用途：作答分析；有效期5分钟。仅本机读取，不发送远端。'),
            const Text(
              '当前尚未接入模型；摘要包含题目/版本编号、原始评分和时间，不含答案正文或后续人工评分，不能代替完整学情分析。',
            ),
            if (busy) const LinearProgressIndicator(),
            if (error != null) Text(error!, key: const ValueKey('grant-error')),
            if (grantId != null) const Text('授权已创建；关闭前可撤销，后端重启或到期后失效。'),
            Expanded(
              child: ListView(
                children: [
                  if (grantId == null)
                    for (final attempt in widget.attempts)
                      CheckboxListTile(
                        title: Text(
                          '记录 #${attempt['id']} · ${attempt['question_id']}',
                        ),
                        value: selected.contains(attempt['id']),
                        onChanged:
                            busy ||
                                (!selected.contains(attempt['id']) &&
                                    selected.length >= 100)
                            ? null
                            : (value) => setState(() {
                                if (value == true) {
                                  selected.add(attempt['id'] as int);
                                } else {
                                  selected.remove(attempt['id']);
                                }
                              }),
                      ),
                  for (final summary in summaries ?? [])
                    ListTile(
                      title: Text(
                        '记录 #${summary['id']} · ${summary['question_id']}',
                      ),
                      subtitle: Text(
                        '原始评分：${summary['status']} / ${summary['score'] ?? '待批改'} · ${summary['created_at']}',
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
      actions: [
        if (grantId == null)
          FilledButton(
            onPressed: busy || selected.isEmpty
                ? null
                : () => run(() async {
                    final result = await widget.backend.request(
                      'POST',
                      endpoint,
                      {
                        'attempt_ids': selected.toList(),
                        'purpose': 'analyze_attempts',
                        'expires_in_seconds': 300,
                        'confirm': true,
                      },
                    ) as Map;
                    if (mounted) {
                      setState(() => grantId = result['id'] as String);
                    }
                  }),
            child: const Text('确认授权所选记录'),
          ),
        if (grantId != null) ...[
          TextButton(
            onPressed: busy
                ? null
                : () => run(() async {
                    try {
                      final result = await widget.backend.request(
                        'POST',
                        '$endpoint/$grantId/read-attempts',
                      ) as Map;
                      if (mounted) {
                        setState(() => summaries = result['attempts'] as List);
                      }
                    } on BackendError catch (failure) {
                      if (failure.statusCode == 404 && mounted) {
                        setState(() {
                          grantId = null;
                          summaries = null;
                        });
                      }
                      rethrow;
                    }
                  }),
            child: const Text('读取授权摘要'),
          ),
          TextButton(
            onPressed: busy ? null : () => run(revoke),
            child: const Text('撤销授权'),
          ),
        ],
        TextButton(
          onPressed: busy
              ? null
              : () => run(() async {
                  if (grantId != null) await revoke();
                  if (context.mounted) Navigator.pop(context);
                }),
          child: Text(grantId == null ? '关闭' : '撤销并关闭'),
        ),
      ],
    ),
  );
}
