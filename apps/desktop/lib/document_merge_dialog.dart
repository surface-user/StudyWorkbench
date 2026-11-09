import 'dart:convert';

import 'package:flutter/material.dart';

import 'backend.dart';

class DocumentMergeDialog extends StatefulWidget {
  const DocumentMergeDialog({
    required this.backend,
    required this.prefix,
    required this.baseHash,
    required this.localText,
    super.key,
  });
  final Backend backend;
  final String prefix, baseHash, localText;

  @override
  State<DocumentMergeDialog> createState() => _DocumentMergeDialogState();
}

class _DocumentMergeDialogState extends State<DocumentMergeDialog> {
  final rows = <Map<String, dynamic>>[];
  Map<String, dynamic>? selected, result, previewRequest;
  String? error;
  bool busy = false, more = true, original = false, closing = false;
  int offset = 0;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<Map<String, dynamic>> current() async {
    final value = Map<String, dynamic>.from(
      await widget.backend.request('GET', '${widget.prefix}/document') as Map,
    );
    if (value['type'] != 'markdown' || value['working_copy'] != true) {
      throw StateError('当前资源不是可编辑Markdown工作副本，草稿保留');
    }
    return value;
  }

  Future<void> load() async {
    if (busy || closing) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (offset == 0) {
        final fresh = await current();
        if (!mounted || closing) return;
        original = fresh['source_sha256'] == widget.baseHash;
      }
      final page = await widget.backend.request(
        'GET',
        '${widget.prefix}/document-saves?offset=$offset&limit=50',
      ) as List;
      if (!mounted || closing) return;
      setState(() {
        rows.addAll(page.map((row) => Map<String, dynamic>.from(row as Map)));
        offset += page.length;
        more = page.length == 50;
      });
    } catch (failure) {
      if (mounted && !closing) setState(() => error = '基线读取失败：$failure。原草稿保留。');
    } finally {
      if (mounted && !closing) setState(() => busy = false);
    }
  }

  void select(Map<String, dynamic> reference) {
    if (busy || closing) return;
    setState(() {
      selected = reference;
      result = previewRequest = null;
      error = null;
    });
  }

  Map<String, dynamic> checked(dynamic response, Map<String, dynamic> request) {
    final value = Map<String, dynamic>.from(response as Map);
    final candidate = value['text'];
    if (value['base_sha256'] != widget.baseHash ||
        value['current_sha256'] != request['expected_current_sha256'] ||
        value['local_sha256'] is! String ||
        value['conflicted'] is! bool ||
        (value['conflicted'] == true
            ? candidate != null
            : candidate is! String) ||
        (candidate is String && utf8.encode(candidate).length > 1024 * 1024)) {
      throw StateError('合并预览返回不一致或超出预算，草稿保留');
    }
    return value;
  }

  Future<void> preview() async {
    if (busy || closing || selected == null) return;
    setState(() {
      busy = true;
      error = null;
      result = previewRequest = null;
    });
    try {
      final fresh = await current();
      if (!mounted || closing) return;
      final request = <String, dynamic>{
        ...selected!,
        'expected_base_sha256': widget.baseHash,
        'expected_current_sha256': fresh['sha256'] as String,
        'text': widget.localText,
      };
      final value = checked(
        await widget.backend.request(
          'POST',
          '${widget.prefix}/document-merge-preview',
          request,
        ),
        request,
      );
      if (!mounted || closing) return;
      setState(() {
        result = value;
        previewRequest = request;
      });
    } catch (failure) {
      if (mounted && !closing) {
        setState(() => error = '合并预览失败：$failure。原草稿保留，请重新核对。');
      }
    } finally {
      if (mounted && !closing) setState(() => busy = false);
    }
  }

  Future<void> confirm() async {
    if (busy ||
        closing ||
        result?['conflicted'] != false ||
        previewRequest == null) {
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      // Reuse the reviewed request: a fresh current hash would silently accept a stale preview.
      final verified = checked(
        await widget.backend.request(
          'POST',
          '${widget.prefix}/document-merge-preview',
          previewRequest,
        ),
        previewRequest!,
      );
      if (!mounted || closing) return;
      if (verified['conflicted'] != false ||
          verified['text'] != result!['text'] ||
          verified['local_sha256'] != result!['local_sha256']) {
        throw StateError('预览结果已变化，请重新预览');
      }
      closing = true;
      Navigator.pop(context, verified);
    } catch (failure) {
      if (mounted && !closing) {
        setState(() {
          result = previewRequest = null;
          error = '候选未载入：$failure。原草稿保留，必须重新预览。';
        });
      }
    } finally {
      if (mounted && !closing) setState(() => busy = false);
    }
  }

  Widget baseline(String label, Map<String, dynamic> reference, String key) {
    final active =
        selected?['base'] == reference['base'] &&
        selected?['save_id'] == reference['save_id'];
    return ListTile(
      key: ValueKey(key),
      leading: Icon(
        active ? Icons.radio_button_checked : Icons.radio_button_unchecked,
      ),
      title: Text(label),
      onTap: busy ? null : () => select(reference),
    );
  }

  void cancel() {
    if (closing) return;
    closing = true;
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) => PopScope(
    onPopInvokedWithResult: (didPop, _) {
      if (didPop) closing = true;
    },
    child: AlertDialog(
      title: const Text('合并修改预览'),
      content: SizedBox(
        width: 740,
        height: 480,
        child: ListView(
          children: [
            const Text('仅显示与现有草稿基线一致的版本，服务会再次核验。此处不写文件；保存仍需另行点击。'),
            Text(
              '草稿基线：${widget.baseHash}',
              style: const TextStyle(fontSize: 11),
            ),
            if (busy) const LinearProgressIndicator(),
            if (error != null) SelectableText(error!),
            if (original)
              baseline('原件基线', {'base': 'original'}, 'merge-base-original'),
            for (final row in rows) ...[
              if (row['old_sha256'] == widget.baseHash)
                baseline('旧稿基线 · ${row['id']}', {
                  'base': 'before',
                  'save_id': row['id'],
                }, 'merge-base-before-${row['id']}'),
              if (row['new_sha256'] == widget.baseHash)
                baseline('待写稿基线 · ${row['id']}', {
                  'base': 'pending',
                  'save_id': row['id'],
                }, 'merge-base-pending-${row['id']}'),
            ],
            if (!busy &&
                !original &&
                !rows.any(
                  (row) =>
                      row['old_sha256'] == widget.baseHash ||
                      row['new_sha256'] == widget.baseHash,
                ))
              const Text('本页没有与草稿基线一致的版本；不会改用其他基线猜测。'),
            if (more)
              TextButton(
                onPressed: busy ? null : load,
                child: Text(rows.isEmpty ? '重试读取基线' : '加载更多基线记录'),
              ),
            if (result?['conflicted'] == true)
              const Text('修改重叠，无法生成合并候选。原草稿保留；可取消后继续编辑或另行保留。'),
            if (result?['conflicted'] == false) ...[
              Text(
                '当前文件：${result!['current_sha256']}',
                style: const TextStyle(fontSize: 11),
              ),
              Text(
                result!['text'] == '' ? '合并候选为空文本（尚未保存）' : '合并候选（字面预览，尚未保存）',
              ),
              SelectableText(
                result!['text'] as String,
                key: const ValueKey('merge-candidate'),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: cancel, child: const Text('取消合并')),
        OutlinedButton(
          onPressed: busy || selected == null ? null : preview,
          child: const Text('预览合并'),
        ),
        FilledButton(
          onPressed: busy || result?['conflicted'] != false ? null : confirm,
          child: const Text('确认载入合并草稿'),
        ),
      ],
    ),
  );
}
