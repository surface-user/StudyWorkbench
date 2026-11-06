import 'dart:math';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'backend.dart';

final _editors = <Future<void> Function()>{};

Future<void> flushAnalysisDraftEditors() async {
  for (final save in List.of(_editors)) {
    await save();
  }
}

Future<Map<String, dynamic>?> showAnalysisReviews(
  BuildContext context,
  Backend backend,
  String scope,
) async {
  return await showDialog<Map<String, dynamic>>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _ReviewList(backend: backend, scope: scope),
  );
}

class _ReviewList extends StatefulWidget {
  const _ReviewList({required this.backend, required this.scope});
  final Backend backend;
  final String scope;
  @override
  State<_ReviewList> createState() => _ReviewListState();
}

class _ReviewListState extends State<_ReviewList> {
  final rows = <Map>[];
  bool busy = false, more = true;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.backend.request(
        'GET',
        '${widget.scope}/analysis-drafts?offset=${rows.length}&limit=50',
      ) as List;
      if (mounted) {
        setState(() {
          rows.addAll(result.cast<Map>());
          more = result.length == 50;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('分析候选审核（未接入模型）'),
    content: SizedBox(
      width: 680,
      height: 420,
      child: ListView(
        children: [
          const Text('外部候选均未经验证。采用只新建独立笔记，不改标准答案、作答或评分。已保存候选在授权撤销后仍保留。'),
          if (error != null) SelectableText(error!),
          for (final row in rows)
            ListTile(
              title: Text('${row['content']['title']}'),
              subtitle: Text('${row['status']} · 修订 ${row['revision']} · 未验证'),
              onTap: busy
                  ? null
                  : () async {
                      final note = await showDialog<Map<String, dynamic>>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => AnalysisReviewDialog(
                          backend: widget.backend,
                          scope: widget.scope,
                          draft: row,
                        ),
                      );
                      if (!mounted) return;
                      if (note != null) {
                        if (context.mounted) Navigator.pop(context, note);
                        return;
                      }
                      rows.clear();
                      more = true;
                      await load();
                    },
            ),
          if (more)
            TextButton(
              onPressed: busy ? null : load,
              child: Text(busy ? '读取中…' : '加载候选'),
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
  );
}

class AnalysisReviewDialog extends StatefulWidget {
  const AnalysisReviewDialog({
    required this.backend,
    required this.scope,
    this.draft,
    this.authorization,
    this.grantId,
    super.key,
  });
  final Backend backend;
  final String scope;
  final Map? draft, authorization;
  final String? grantId;
  @override
  State<AnalysisReviewDialog> createState() => _AnalysisReviewDialogState();
}

class _AnalysisReviewDialogState extends State<AnalysisReviewDialog> {
  final title = TextEditingController(),
      body = TextEditingController(),
      source = TextEditingController();
  final name = TextEditingController(text: '分析候选.md');
  final requestId = List.generate(
    16,
    (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
  Map? row;
  Future<void>? saving;
  Map<String, dynamic>? pendingCreate, pendingAdoption;
  bool busy = false, confirmed = false, showContext = false;
  String? error;
  late final Future<void> Function() flusher;
  bool get editable =>
      (row == null || row!['status'] == 'pending') && pendingAdoption == null;
  bool get dirty => row == null
      ? [title.text, body.text, source.text].any((v) => v.isNotEmpty)
      : title.text != row!['content']['title'] ||
            body.text != row!['content']['body'] ||
            source.text != row!['content']['source_label'];
  String get endpoint => '${widget.scope}/analysis-drafts';
  Map<String, dynamic> get guard => {
    'expected_revision': row!['revision'],
    'expected_payload_sha256': row!['payload_sha256'],
  };
  @override
  void initState() {
    super.initState();
    row = widget.draft;
    if (row != null) {
      title.text = row!['content']['title'];
      body.text = row!['content']['body'];
      source.text = row!['content']['source_label'];
      if ((row!['adoption'] as Map).isNotEmpty) {
        name.text = row!['adoption']['name'] as String;
      }
    }
    for (final field in [title, body, source]) {
      field.addListener(changed);
    }
    flusher = flush;
    _editors.add(flusher);
  }

  void changed() {
    if (mounted) {
      setState(() {
        confirmed = false;
      });
    }
  }

  @override
  void dispose() {
    _editors.remove(flusher);
    for (final field in [title, body, source, name]) {
      field.dispose();
    }
    super.dispose();
  }

  Future<void> flush() async {
    if (busy && saving == null) throw StateError('候选审核操作尚未结束，请稍后重试');
    if (saving != null) await saving;
    if (!dirty && pendingCreate == null) return;
    if (!editable) throw StateError('候选状态变化，请保留文字并重新核对');
    final operation = save();
    saving = operation;
    try {
      await operation;
    } finally {
      saving = null;
    }
  }

  Future<void> save() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final text = {
        'title': title.text,
        'body': body.text,
        'source_label': source.text,
      };
      dynamic result;
      if (row == null) {
        pendingCreate ??= {
          ...text,
          'grant_id': widget.grantId,
          'context_sha256': widget.authorization!['context_sha256'],
          'request_id': requestId,
        };
        result = await widget.backend.request('POST', endpoint, pendingCreate);
      } else {
        result = await widget.backend.request(
          'PATCH',
          '$endpoint/${row!['id']}',
          {...text, ...guard},
        );
      }
      if (mounted) {
        setState(() {
          row = result as Map;
          pendingCreate = null;
          confirmed = false;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '保存未确认，文字保留：$failure');
      rethrow;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    try {
      await action();
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    }
  }

  Future<void> close() async {
    await flush();
    if (mounted) Navigator.pop(context);
  }

  Future<void> adopt() async {
    if (!confirmed || dirty || row == null) return;
    pendingAdoption ??= (row!['adoption'] as Map).isNotEmpty
        ? Map<String, dynamic>.from(row!['adoption'] as Map)
        : {
            ...guard,
            'name': name.text,
            'request_id': 'review_$requestId',
            'confirm': true,
          };
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.backend.request(
        'POST',
        '$endpoint/${row!['id']}/adopt',
        pendingAdoption,
      ) as Map;
      if (mounted) {
        setState(() {
          row = result;
          confirmed = false;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '采用未确认，可重试原请求；草稿与已建笔记保留：$failure');
      rethrow;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> openNote() async {
    await flush();
    setState(() => busy = true);
    try {
      final node = Map<String, dynamic>.from(
        await widget.backend.request(
          'GET',
          '${widget.scope}/nodes/${row!['result']['resource_item_id']}',
        ) as Map,
      );
      if (node['status'] != 'ready' || node['removed_at'] != null) {
        throw StateError('笔记已移除或原件变化，请在资源管理器核对');
      }
      if (mounted) Navigator.pop(context, node);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy && !dirty && pendingCreate == null,
    child: AlertDialog(
      title: const Text('审核外部候选（未经验证）'),
      content: SizedBox(
        width: 680,
        height: 440,
        child: ListView(
          children: [
            const Text('本应用未调用模型。候选来源说明为自填；任何内容只作为文字保存。采用仍标为未验证，仅新建根目录笔记。'),
            if (row == null)
              Text('本地授权范围：${widget.authorization?['scope']}；保存时重新核对授权及上下文。'),
            if (widget.authorization != null) ...[
              TextButton(
                onPressed: () => setState(() => showContext = !showContext),
                child: Text(showContext ? '收起授权上下文' : '查看授权上下文'),
              ),
              if (showContext)
                SelectableText(
                  const JsonEncoder.withIndent('  ')
                      .convert(widget.authorization),
                ),
            ],
            if (row != null)
              Text(
                '状态：${row!['status']} · 修订 ${row!['revision']}；撤销授权不会删除已保存草稿。',
              ),
            if (busy) const LinearProgressIndicator(),
            if (error != null)
              SelectableText(error!, key: const ValueKey('review-error')),
            TextField(
              controller: title,
              enabled: !busy && editable && pendingCreate == null,
              maxLength: 200,
              decoration: const InputDecoration(labelText: '候选标题'),
            ),
            TextField(
              controller: source,
              enabled: !busy && editable && pendingCreate == null,
              maxLength: 200,
              decoration: const InputDecoration(labelText: '来源说明（自填）'),
            ),
            TextField(
              controller: body,
              enabled: !busy && editable && pendingCreate == null,
              maxLength: 16000,
              minLines: 5,
              maxLines: 12,
              decoration: const InputDecoration(labelText: '候选正文'),
            ),
            if (row != null) ...[
              for (final reference in row!['content']['references'] as List)
                Text(
                  '作答 #${reference['attempt_id']} · ${reference['question_id']} · 确认版 ${reference['question_version_id'] ?? '历史未知'}',
                ),
              if (row!['status'] == 'pending' ||
                  row!['status'] == 'failed') ...[
                TextField(
                  controller: name,
                  enabled:
                      !busy &&
                      pendingAdoption == null &&
                      (row!['adoption'] as Map).isEmpty,
                  decoration: const InputDecoration(labelText: '新笔记文件名'),
                ),
                CheckboxListTile(
                  value: confirmed,
                  onChanged: busy || dirty
                      ? null
                      : (v) => setState(() => confirmed = v == true),
                  title: const Text('我已核对当前内容，同意保存为未经验证的独立笔记'),
                ),
                if ((row!['adoption'] as Map).isNotEmpty)
                  const Text('已有采用收据；重试使用原文件名和原请求，不覆盖其他编辑。'),
              ],
              if (row!['result']['resource_item_id'] != null)
                const Text('已建独立笔记；内容仍未经验证。'),
              if (row!['error'] != null) SelectableText('${row!['error']}'),
            ],
          ],
        ),
      ),
      actions: [
        if (row?['result']['resource_item_id'] != null)
          TextButton(
            onPressed: busy ? null : () => run(openNote),
            child: const Text('打开已建笔记'),
          ),
        if (row != null)
          TextButton(
            onPressed: busy
                ? null
                : () => run(() async {
                    setState(() => busy = true);
                    try {
                      final history = await widget.backend.request(
                        'GET',
                        '$endpoint/${row!['id']}/revisions?limit=50',
                      ) as List;
                      if (!context.mounted) return;
                      await showDialog<void>(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('最近50条审核修订（旧记录保留）'),
                          content: SizedBox(
                            width: 600,
                            height: 400,
                            child: ListView(
                              children: [
                                for (final item in history)
                                  SelectableText(
                                    const JsonEncoder.withIndent('  ')
                                        .convert(item),
                                  ),
                              ],
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('关闭'),
                            ),
                          ],
                        ),
                      );
                    } finally {
                      if (mounted) setState(() => busy = false);
                    }
                  }),
            child: const Text('审核修订'),
          ),
        if (editable)
          TextButton(
            onPressed: busy ? null : () => run(flush),
            child: const Text('保存草稿'),
          ),
        if (row != null && ['pending', 'failed'].contains(row!['status']))
          TextButton(
            onPressed: busy || dirty || pendingAdoption != null
                ? null
                : () => run(() async {
                    setState(() => busy = true);
                    try {
                      final result = await widget.backend.request(
                        'POST',
                        '$endpoint/${row!['id']}/reject',
                        {...guard, 'reason': '人工拒绝'},
                      );
                      if (mounted) setState(() => row = result as Map);
                    } finally {
                      if (mounted) setState(() => busy = false);
                    }
                  }),
            child: const Text('拒绝并保留记录'),
          ),
        if (row != null && ['pending', 'failed'].contains(row!['status']))
          FilledButton(
            onPressed: busy || dirty || !confirmed ? null : () => run(adopt),
            child: const Text('确认采用为笔记'),
          ),
        TextButton(
          onPressed: busy ? null : () => run(close),
          child: const Text('保存并关闭'),
        ),
        if (dirty)
          TextButton(
            onPressed: busy
                ? null
                : () async {
                    final discard = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('放弃尚未保存的文字？'),
                        content: Text(
                          pendingCreate == null
                              ? '仅放弃本窗口未保存的编辑。'
                              : '创建结果尚未确认；可能已保存的候选仍保留，请到候选列表核对。此操作只关闭本窗口文字。',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(context, false),
                            child: const Text('保留编辑'),
                          ),
                          TextButton(
                            onPressed: () => Navigator.pop(context, true),
                            child: const Text('确认放弃'),
                          ),
                        ],
                      ),
                    );
                    if (discard == true && context.mounted) {
                      Navigator.pop(context);
                    }
                  },
            child: const Text('放弃未保存编辑'),
          ),
      ],
    ),
  );
}
