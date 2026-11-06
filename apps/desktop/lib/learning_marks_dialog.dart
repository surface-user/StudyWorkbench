import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';
import 'internal_links.dart';
import 'markdown_note_dialog.dart';
import 'note_editor.dart';

typedef CaptureLearningAnchor = Future<Map<String, dynamic>> Function();

String learningPosition(dynamic anchor) {
  if (anchor is! Map || anchor['version'] != 1) return '不支持的位置（原始记录保留）';
  return switch (anchor['kind']) {
    'pdf_page' || 'office_pdf_page' => '第${anchor['page']}页',
    'text_line' => '原文第${anchor['line']}行',
    'media_time' when anchor['position_ms'] is num =>
      '${((anchor['position_ms'] as num) / 1000).toStringAsFixed(3)}秒',
    'resource' => '整份资料',
    _ => '不支持的位置（原始记录保留）',
  };
}

class LearningMarksDialog extends StatefulWidget {
  const LearningMarksDialog({
    required this.backend,
    required this.workspaceId,
    this.resourceItemId,
    this.noteResourceItemId,
    this.captureCurrent,
    this.initialMarkId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final String? resourceItemId, noteResourceItemId;
  final String? initialMarkId;
  final CaptureLearningAnchor? captureCurrent;
  @override
  State<LearningMarksDialog> createState() => _LearningMarksDialogState();
}

class _LearningMarksDialogState extends State<LearningMarksDialog> {
  final title = TextEditingController(), note = TextEditingController();
  List<dynamic> rows = [];
  Map<String, dynamic>? current, draftAnchor, pendingCreate;
  List<Map<String, dynamic>>? pendingTargets;
  bool busy = false, dirty = false, more = false;
  String? error;
  int offset = 0;
  String requestId = '';
  String get scope => '/api/workspaces/${widget.workspaceId}';
  String get url => '$scope/learning-marks';
  String get filter => widget.noteResourceItemId != null
      ? '&note_resource_item_id=${Uri.encodeQueryComponent(widget.noteResourceItemId!)}'
      : widget.resourceItemId == null
      ? ''
      : '&resource_item_id=${Uri.encodeQueryComponent(widget.resourceItemId!)}';

  @override
  void initState() {
    super.initState();
    run(() => load()).then((_) {
      if (mounted && widget.initialMarkId != null) {
        select(widget.initialMarkId!);
      }
    });
  }

  @override
  void dispose() {
    title.dispose();
    note.dispose();
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
      if (mounted) setState(() => error = '操作未完成，记录和当前草稿保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> load({bool reset = true}) async {
    final page = await widget.backend.request(
      'GET',
      '$url?offset=${reset ? 0 : offset}&limit=50$filter',
    ) as List;
    if (mounted) {
      setState(() {
        rows = [...(reset ? [] : rows), ...page];
        offset = reset ? page.length : offset + page.length;
        more = page.length == 50;
      });
    }
  }

  Future<bool> discard() async {
    if (!dirty && pendingTargets == null) return true;
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('放弃当前未保存的书签草稿？'),
            content: const Text('已保存记录保留。创建结果未确认时，请在列表核对后再另建。'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('继续编辑'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('放弃草稿'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> select(String id) async {
    if (!await discard() || !mounted) return;
    await run(() async {
      final item = Map<String, dynamic>.from(
        await widget.backend.request('GET', '$url/$id') as Map,
      );
      if (mounted) {
        setState(() {
          current = item;
          title.text = item['title'] as String;
          note.text = item['note'] as String;
          draftAnchor = null;
          pendingCreate = null;
          pendingTargets = null;
          dirty = false;
        });
      }
    });
  }

  Future<void> start(bool positional) async {
    if (!await discard() || !mounted) return;
    await run(() async {
      final point = positional
          ? await widget.captureCurrent!()
          : Map<String, dynamic>.from(
              await widget.backend.request(
                'POST',
                '$scope/nodes/${widget.resourceItemId}/learning-anchor',
                {'kind': 'resource'},
              ) as Map,
            );
      if (mounted) {
        setState(() {
          current = null;
          pendingCreate = null;
          pendingTargets = null;
          draftAnchor = point;
          title.text = '新书签';
          note.clear();
          dirty = true;
          final random = Random.secure();
          requestId = List.generate(
            16,
            (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
          ).join();
        });
      }
    });
  }

  Future<void> save() => run(() async {
    if (title.text.trim().isEmpty) throw StateError('请填写书签名称');
    Map<String, dynamic> result;
    if (current == null) {
      pendingCreate ??= {
        'request_id': requestId,
        'anchor': draftAnchor,
        'title': title.text,
        'note': note.text,
      };
      result = Map<String, dynamic>.from(
        await widget.backend.request('POST', url, pendingCreate) as Map,
      );
    } else {
      result = Map<String, dynamic>.from(
        await widget.backend.request('PATCH', '$url/${current!['id']}', {
          'expected_revision': current!['revision'],
          'title': title.text,
          'note': note.text,
          if (draftAnchor != null) 'anchor': draftAnchor,
        }) as Map,
      );
    }
    if (!mounted) return;
    setState(() {
      current = result;
      title.text = result['title'] as String;
      note.text = result['note'] as String;
      dirty = false;
      pendingCreate = null;
      draftAnchor = null;
    });
    final detail =
        await widget.backend.request('GET', '$url/${result['id']}') as Map;
    if (mounted) setState(() => current = Map<String, dynamic>.from(detail));
    await load();
  });

  Future<void> saveTargets(List<Map<String, dynamic>> targets) => run(() async {
    pendingTargets = targets;
    final saved = await widget.backend.request(
      'PUT',
      '$url/${current!['id']}/notes',
      {'expected_revision': current!['revision'], 'targets': targets},
    ) as Map;
    if (mounted) {
      setState(() {
        current = Map<String, dynamic>.from(saved);
        pendingTargets = null;
      });
    }
    final detail =
        await widget.backend.request('GET', '$url/${saved['id']}') as Map;
    if (mounted) setState(() => current = Map<String, dynamic>.from(detail));
  });

  Future<void> attach(bool legacy) async {
    final chosen = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => legacy
          ? _LegacyNotes(backend: widget.backend, scope: scope)
          : MarkdownNoteDialog(
              backend: widget.backend,
              workspaceId: widget.workspaceId,
            ),
    );
    if (!mounted || chosen == null) return;
    final target = {
      'kind': legacy ? 'legacy_note' : 'file_note',
      'id': chosen[legacy ? 'id' : 'resource_item_id'],
    };
    final targets = (current!['targets'] as List)
        .map((t) => Map<String, dynamic>.from(t as Map))
        .toList();
    if (!targets.any(
      (t) => t['kind'] == target['kind'] && t['id'] == target['id'],
    )) {
      targets.add(target);
    }
    await saveTargets(targets);
  }

  Future<void> jump() => run(() async {
    // A fresh resolve prevents a stale list or editor from silently returning to changed content.
    final detail =
        await widget.backend.request('GET', '$url/${current!['id']}') as Map;
    if (!mounted) return;
    setState(() => current = Map<String, dynamic>.from(detail));
    final location = detail['location'] as Map;
    if (detail['removed_at'] != null) throw StateError('书签已移除，备注和历史保留');
    if (location['status'] != 'valid') {
      throw StateError(location['message'] ?? '书签已移除');
    }
    Navigator.pop(context, {
      ...Map<String, dynamic>.from(location['resource'] as Map),
      'learning_anchor': Map<String, dynamic>.from(location['anchor'] as Map),
    });
  });

  Future<void> openNote(Map target) => run(() async {
    final value = Map<String, dynamic>.from(
      await widget.backend.request(
        'GET',
        '$url/${current!['id']}/notes/${target['kind']}/${Uri.encodeComponent(target['id'] as String)}',
      ) as Map,
    );
    if (!mounted) return;
    if (target['kind'] == 'file_note') {
      Navigator.pop(context, value);
    } else {
      await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => NoteEditor(
          note: value,
          backend: widget.backend,
          workspaceId: widget.workspaceId,
        ),
      );
    }
  });

  Future<void> remove() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('移除此书签？'),
        content: const Text('备注和旧修订保留，原资料及关联笔记不删除。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认移除'),
          ),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    await run(() async {
      await widget.backend.request('DELETE', '$url/${current!['id']}', {
        'expected_revision': current!['revision'],
      });
      if (mounted) {
        setState(() {
          current = null;
          draftAnchor = null;
          dirty = false;
        });
      }
      await load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final location = current?['location'] as Map?;
    final point = draftAnchor ?? current?['anchor'];
    return PopScope(
      canPop: !busy && !dirty && pendingTargets == null,
      child: AlertDialog(
        title: Text(widget.noteResourceItemId == null ? '书签与备注' : '笔记关联的来源'),
        content: SizedBox(
          width: 760,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  children: [
                    if (widget.resourceItemId != null)
                      TextButton(
                        onPressed: busy ? null : () => start(false),
                        child: const Text('标记整份资料'),
                      ),
                    if (widget.captureCurrent != null)
                      TextButton(
                        onPressed: busy ? null : () => start(true),
                        child: const Text('记录当前位置'),
                      ),
                    TextButton(
                      onPressed: busy ? null : () => run(() => load()),
                      child: const Text('刷新书签列表'),
                    ),
                  ],
                ),
                for (final row in rows)
                  ListTile(
                    dense: true,
                    title: Text(row['title'] as String),
                    subtitle: Text(
                      '${learningPosition(row['anchor'])} · 点击核对位置',
                    ),
                    enabled: !busy,
                    onTap: () => select(row['id'] as String),
                  ),
                if (rows.isEmpty && !busy) const Text('暂无书签，可在阅读资料时添加。'),
                if (more)
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => run(() => load(reset: false)),
                    child: const Text('加载更多书签'),
                  ),
                if (point != null) ...[
                  const Divider(),
                  Text(learningPosition(point)),
                  if (location != null)
                    Text(location['message'] as String? ?? '位置待核对'),
                  TextField(
                    controller: title,
                    enabled: !busy && pendingCreate == null,
                    maxLength: 240,
                    decoration: const InputDecoration(labelText: '书签名称'),
                    onChanged: (_) => setState(() => dirty = true),
                  ),
                  TextField(
                    controller: note,
                    enabled: !busy && pendingCreate == null,
                    maxLength: 4000,
                    minLines: 2,
                    maxLines: 6,
                    decoration: const InputDecoration(labelText: '备注'),
                    onChanged: (_) => setState(() => dirty = true),
                  ),
                  Wrap(
                    children: [
                      FilledButton(
                        onPressed: busy || !dirty ? null : save,
                        child: Text(pendingCreate == null ? '保存书签' : '重试原创建请求'),
                      ),
                      if (current != null) ...[
                        TextButton(
                          onPressed: busy || dirty
                              ? null
                              : () => copyLearningLink(
                                  context,
                                  LearningLink(
                                    widget.workspaceId,
                                    'marks',
                                    current!['id'] as String,
                                  ),
                                ),
                          child: const Text('复制书签链接'),
                        ),
                        TextButton(
                          onPressed: busy || dirty ? null : jump,
                          child: const Text('返回来源位置'),
                        ),
                        if (widget.captureCurrent != null &&
                            current!['resource_item_id'] ==
                                widget.resourceItemId)
                          TextButton(
                            onPressed: busy || pendingCreate != null
                                ? null
                                : () => run(() async {
                                    final next = await widget.captureCurrent!();
                                    if (mounted) {
                                      setState(() {
                                        draftAnchor = next;
                                        dirty = true;
                                      });
                                    }
                                  }),
                            child: const Text('重新关联当前阅读位置'),
                          ),
                        TextButton(
                          onPressed: busy || dirty ? null : remove,
                          child: const Text('移除书签'),
                        ),
                      ],
                    ],
                  ),
                  if (current != null) ...[
                    const Text('关联笔记（先保存书签；创建笔记成功但关联失败时，笔记仍保留）'),
                    for (final raw in current!['target_details'] as List? ?? [])
                      ListTile(
                        title: Text(raw['title'] as String),
                        subtitle: Text(
                          raw['status'] == 'ready' ? '已关联' : '笔记已移除或缺失',
                        ),
                        onTap: busy || dirty
                            ? null
                            : () => openNote(raw as Map),
                        trailing: IconButton(
                          tooltip: '解除笔记关联',
                          onPressed: busy || dirty
                              ? null
                              : () => saveTargets(
                                  (current!['targets'] as List)
                                      .where(
                                        (t) =>
                                            t['kind'] != raw['kind'] ||
                                            t['id'] != raw['id'],
                                      )
                                      .map(
                                        (t) =>
                                            Map<String, dynamic>.from(t as Map),
                                      )
                                      .toList(),
                                ),
                          icon: const Icon(Icons.link_off),
                        ),
                      ),
                    Wrap(
                      children: [
                        TextButton(
                          onPressed: busy || dirty ? null : () => attach(false),
                          child: const Text('新建或关联Markdown笔记'),
                        ),
                        TextButton(
                          onPressed: busy || dirty ? null : () => attach(true),
                          child: const Text('关联旧富内容笔记'),
                        ),
                        if (pendingTargets != null)
                          TextButton(
                            onPressed: busy
                                ? null
                                : () => saveTargets(pendingTargets!),
                            child: const Text('重试保存笔记关联'),
                          ),
                      ],
                    ),
                  ],
                ],
                if (error != null) SelectableText(error!),
                if (busy) const LinearProgressIndicator(),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: busy
                ? null
                : () async {
                    if (await discard() && context.mounted) {
                      Navigator.pop(context);
                    }
                  },
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }
}

class _LegacyNotes extends StatefulWidget {
  const _LegacyNotes({required this.backend, required this.scope});
  final Backend backend;
  final String scope;
  @override
  State<_LegacyNotes> createState() => _LegacyNotesState();
}

class _LegacyNotesState extends State<_LegacyNotes> {
  List<dynamic> rows = [];
  bool busy = false, more = false;
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
      final page = await widget.backend.request(
        'GET',
        '${widget.scope}/notes?offset=${rows.length}&limit=20',
      ) as List;
      if (mounted) {
        setState(() {
          rows.addAll(page);
          more = page.length == 20;
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
    title: const Text('选择旧富内容笔记'),
    content: SizedBox(
      width: 450,
      height: 300,
      child: ListView(
        children: [
          for (final row in rows)
            ListTile(
              title: Text(row['title'] as String),
              onTap: () =>
                  Navigator.pop(context, Map<String, dynamic>.from(row as Map)),
            ),
          if (error != null) Text(error!),
          if (busy) const LinearProgressIndicator(),
          if (more || error != null)
            TextButton(
              onPressed: busy ? null : load,
              child: const Text('加载笔记'),
            ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('取消'),
      ),
    ],
  );
}
