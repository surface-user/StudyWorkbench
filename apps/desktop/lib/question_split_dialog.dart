import 'package:flutter/material.dart';

import 'dart:typed_data';

import 'backend.dart';
import 'question_page.dart';

class QuestionSplitDialog extends StatefulWidget {
  const QuestionSplitDialog({
    required this.backend,
    required this.workspaceId,
    required this.job,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final Map<String, dynamic> job;
  @override
  State<QuestionSplitDialog> createState() => _QuestionSplitDialogState();
}

class _QuestionSplitDialogState extends State<QuestionSplitDialog> {
  late Map<String, dynamic> job = widget.job;
  List get drafts => job['preview']['question_drafts'] as List;
  late final selected = {for (var i = 0; i < drafts.length; i++) i};
  int index = 0;
  bool busy = false;
  String? error;

  String blockLabel(dynamic block) => switch (block['type']) {
    'text' =>
      '文字：${(block['text'] as String).replaceAll('\n', ' ').characters.take(45)}',
    'latex' => '公式：${block['tex']}',
    'image' => '图片：${block['alt']}',
    _ => '内容：${block['type']}',
  };

  Future<void> edit(
    String action, [
    Map<String, dynamic> values = const {},
  ]) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final updated = await widget.backend.request(
        'POST',
        '/api/workspaces/${widget.workspaceId}/imports/${job['id']}/question-drafts/edit',
        {
          'expected_revision': job['draft_revision'],
          'action': action,
          'index': index,
          ...values,
        },
      ) as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          job = updated;
          if (index >= drafts.length) index = drafts.length - 1;
          selected
            ..clear()
            ..addAll(List.generate(drafts.length, (i) => i));
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '预览修改未完成，旧内容保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> split() async {
    final regions = drafts[index]['regions'] as List? ?? [];
    final blocks = drafts[index]['blocks'] as List;
    var position = 0, offset = '';
    var title = '拆分出的题目';
    double? cut = regions.isEmpty
        ? null
        : ((regions[0]['box'][1] as num) + (regions[0]['box'][3] as num)) / 2;
    Future<Uint8List>? pageImage;
    if (regions.isNotEmpty) {
      final pages = (job['preview']['blocks'] as List)
          .where((b) => b['type'] == 'image')
          .toList();
      pageImage = widget.backend.resourceBytes(
        widget.workspaceId,
        pages[(regions[0]['page'] as int) - 1]['attachment_id'] as String,
      );
    }
    final value = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, rebuild) => AlertDialog(
          title: const Text('调整分割位置'),
          content: SizedBox(
            width: 600,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    decoration: const InputDecoration(labelText: '新题目标题'),
                    onChanged: (value) => title = value,
                  ),
                  DropdownButtonFormField<int>(
                    initialValue: position,
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: regions.isEmpty ? '在此内容段之前分割' : '选择分割所在页',
                    ),
                    items: [
                      for (
                        var i = 0;
                        i < (regions.isEmpty ? blocks.length : regions.length);
                        i++
                      )
                        DropdownMenuItem(
                          value: i,
                          child: Text(
                            regions.isEmpty
                                ? blockLabel(blocks[i])
                                : '第${regions[i]['page']}页题目区域',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: (value) => rebuild(() {
                      position = value!;
                      if (regions.isNotEmpty) {
                        cut =
                            ((regions[position]['box'][1] as num) +
                                (regions[position]['box'][3] as num)) /
                            2;
                        final pages = (job['preview']['blocks'] as List)
                            .where((b) => b['type'] == 'image')
                            .toList();
                        pageImage = widget.backend.resourceBytes(
                          widget.workspaceId,
                          pages[(regions[position]['page'] as int) -
                                  1]['attachment_id']
                              as String,
                        );
                      }
                    }),
                  ),
                  if (regions.isEmpty)
                    TextField(
                      decoration: InputDecoration(
                        labelText: '段内字符位置（留空则从该段开头分割）',
                        errorText:
                            offset.isNotEmpty &&
                                (int.tryParse(offset) == null ||
                                    int.parse(offset) < 0)
                            ? '请输入非负整数'
                            : null,
                      ),
                      onChanged: (value) => rebuild(() => offset = value),
                    ),
                  if (regions.isNotEmpty) ...[
                    const Text('移动红线选择页内分界。原件不变，拆分后以精确裁图为准。'),
                    FutureBuilder<Uint8List>(
                      future: pageImage,
                      builder: (context, snapshot) => snapshot.hasData
                          ? SizedBox(
                              width: 400,
                              child: Stack(
                                children: [
                                  Image.memory(snapshot.data!, width: 400),
                                  Positioned.fill(
                                    child: Align(
                                      alignment: Alignment(0, cut! * 2 - 1),
                                      child: Container(
                                        height: 2,
                                        color: Colors.red,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            )
                          : Text(
                              snapshot.hasError
                                  ? '页图读取失败：${snapshot.error}'
                                  : '正在读取原页图',
                            ),
                    ),
                    Text('分割线：距页面顶部 ${(cut! * 100).toStringAsFixed(1)}%'),
                    Slider(
                      value: cut!,
                      min: (regions[position]['box'][1] as num).toDouble(),
                      max: (regions[position]['box'][3] as num).toDouble(),
                      onChanged: (value) => rebuild(() => cut = value),
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed:
                  regions.isEmpty &&
                          offset.isNotEmpty &&
                          (int.tryParse(offset) == null ||
                              int.parse(offset) < 0) ||
                      regions.isNotEmpty &&
                          (cut! <= (regions[position]['box'][1] as num) ||
                              cut! >= (regions[position]['box'][3] as num))
                  ? null
                  : () => Navigator.pop(context, {
                      'position': position,
                      'title': title,
                      if (regions.isEmpty)
                        'text_offset': int.tryParse(offset) ?? 0,
                      'cut': ?cut,
                    }),
              child: const Text('保存分割预览'),
            ),
          ],
        ),
      ),
    );
    if (value != null && mounted) {
      await edit(regions.isEmpty ? 'split_block' : 'split_region', value);
    }
  }

  Future<void> share() async {
    final source = job['preview']['blocks'] as List;
    final chosen = <int>{};
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, rebuild) => AlertDialog(
          title: const Text('为勾选的题目附上共享材料'),
          content: SizedBox(
            width: 600,
            child: SingleChildScrollView(
              child: Column(
                children: [
                  Text('选取原资料中的内容段，附到当前勾选的 ${selected.length} 道题。'),
                  for (var i = 0; i < source.length; i++)
                    CheckboxListTile(
                      title: Text(blockLabel(source[i])),
                      value: chosen.contains(i),
                      onChanged: (value) => rebuild(() {
                        if (value == true) {
                          chosen.add(i);
                        } else {
                          chosen.remove(i);
                        }
                      }),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: chosen.isEmpty
                  ? null
                  : () => Navigator.pop(context, true),
              child: const Text('附加材料到预览'),
            ),
          ],
        ),
      ),
    );
    if (accepted == true && mounted) {
      await edit('share', {
        'targets': selected.toList()..sort(),
        'source_blocks': chosen.toList()..sort(),
      });
    }
  }

  Future<void> save() async {
    if (busy || selected.isEmpty) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.backend.request(
        'POST',
        '/api/workspaces/${widget.workspaceId}/imports/${job['id']}/question-markdown',
        {
          'expected_revision': job['draft_revision'],
          'selected': selected.toList()..sort(),
          'confirm': true,
        },
      );
      if (mounted) Navigator.pop(context, true);
    } catch (failure) {
      if (mounted) setState(() => error = '保存未完成，请保留预览并核对记录：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('逐题裁切与 Markdown 预览'),
      content: SizedBox(
        width: 800,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('每个候选将独立保存为 question.md，图片使用相对路径。没有答案也可入库，不自动补答案。'),
              for (final warning in job['preview']['warnings'] as List? ?? [])
                Text('请核对：$warning'),
              Wrap(
                spacing: 12,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    '候选 ${index + 1} / ${drafts.length} · 已选 ${selected.length} 题',
                  ),
                  TextButton(
                    onPressed: busy || index == 0
                        ? null
                        : () => setState(() => index--),
                    child: const Text('上一题'),
                  ),
                  TextButton(
                    onPressed: busy || index == drafts.length - 1
                        ? null
                        : () => setState(() => index++),
                    child: const Text('下一题'),
                  ),
                ],
              ),
              CheckboxListTile(
                title: Text(drafts[index]['title'] as String),
                subtitle: const Text('边界不正确的候选可取消选择；原文档始终保留。'),
                value: selected.contains(index),
                onChanged: busy
                    ? null
                    : (value) => setState(() {
                        if (value == true) {
                          selected.add(index);
                        } else {
                          selected.remove(index);
                        }
                      }),
              ),
              if (job['status'] != 'confirmed')
                Wrap(
                  spacing: 8,
                  children: [
                    OutlinedButton(
                      onPressed: busy || index + 1 >= drafts.length
                          ? null
                          : () => edit('merge_next'),
                      child: const Text('与下一题合并'),
                    ),
                    OutlinedButton(
                      onPressed: busy ? null : split,
                      child: const Text('调整位置并拆分'),
                    ),
                    OutlinedButton(
                      onPressed: busy || selected.isEmpty ? null : share,
                      child: const Text('附加共享材料'),
                    ),
                  ],
                ),
              for (final material
                  in drafts[index]['shared_materials'] as List? ?? []) ...[
                const Text('共享材料'),
                ContentBlocks(
                  material['blocks'] as List,
                  backend: widget.backend,
                  workspaceId: widget.workspaceId,
                ),
              ],
              ContentBlocks(
                drafts[index]['blocks'] as List,
                backend: widget.backend,
                workspaceId: widget.workspaceId,
              ),
              ExpansionTile(
                title: const Text('查看 Markdown 源文'),
                children: [
                  SelectableText(
                    (job['question_markdown'] as List)[index] as String,
                  ),
                ],
              ),
              if (busy) const LinearProgressIndicator(),
              if (error != null) SelectableText(error!),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context, false),
          child: const Text('暂不入库'),
        ),
        FilledButton(
          onPressed: busy || selected.isEmpty ? null : save,
          child: const Text('确认逐题保存为 Markdown'),
        ),
      ],
    ),
  );
}
