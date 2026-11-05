import 'dart:convert';

import 'package:flutter/material.dart';

import 'backend.dart';
import 'internal_links.dart';
import 'question_contract.dart';
import 'question_page.dart';
import 'resource_picker.dart';

class NoteEditor extends StatefulWidget {
  const NoteEditor({
    required this.note,
    required this.backend,
    required this.workspaceId,
    super.key,
  });
  final Map<String, dynamic> note;
  final Backend backend;
  final String workspaceId;
  @override
  State<NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends State<NoteEditor> {
  final form = GlobalKey<FormState>();
  late String title = widget.note['title'] as String;
  // Keep every field, including optional fields the user does not edit.
  late final List<dynamic> blocks =
      jsonDecode(jsonEncode(widget.note['content'])) as List;
  bool busy = false, preview = false;
  String? error;

  Future<void> pickResource({required bool image, Map? replacement}) async {
    if (busy) return;
    final resource = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ResourcePicker(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        imagesOnly: image,
      ),
    );
    if (resource == null || !mounted) return;
    setState(() {
      final block =
          replacement ??
          <String, dynamic>{'type': image ? 'image' : 'attachment'};
      block['attachment_id'] = resource['id'];
      block[image ? 'alt' : 'label'] = (resource['filename'] as String)
          .characters
          .take(500)
          .toString();
      if (replacement == null) blocks.add(block);
    });
  }

  Future<void> save() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final contract = await QuestionContract.load(bundle: false);
      contract.validateContent(blocks);
      await widget.backend.request(
        'PUT',
        '/api/workspaces/${widget.workspaceId}/notes/${widget.note['id']}',
        {
          'expected_revision': widget.note['revision'],
          'title': title.trim(),
          'content': blocks,
        },
      );
      if (mounted) Navigator.pop(context, true);
    } catch (failure) {
      if (mounted) setState(() => error = '未确认保存结果，草稿保留在此窗口：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget field(
    Map block,
    String key,
    String label, {
    int length = 500,
    bool optional = false,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextFormField(
      key: ValueKey(
        '${identityHashCode(block)}-${block['attachment_id'] ?? ''}-$key',
      ),
      initialValue: block[key] as String? ?? '',
      enabled: !busy,
      minLines: 1,
      maxLines: 5,
      maxLength: length,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      onChanged: (value) => setState(() {
        if (optional && value.isEmpty) {
          block.remove(key);
        } else {
          block[key] = value;
        }
      }),
      validator: (value) => !optional && (value == null || value.trim().isEmpty)
          ? '请填写$label'
          : null,
    ),
  );

  Widget inline(Map block) => switch (block['type']) {
    'text' => field(block, 'text', '文字内容', length: 20000),
    'latex' => Column(
      children: [
        field(block, 'tex', '公式内容', length: 8000),
        CheckboxListTile(
          title: const Text('公式独占一行'),
          value: block['display'] == true,
          onChanged: busy
              ? null
              : (value) => setState(() => block['display'] = value!),
        ),
      ],
    ),
    'image' || 'chart' => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        field(block, 'alt', block['type'] == 'image' ? '图片说明' : '图表说明'),
        if (block['type'] == 'image')
          field(block, 'caption', '图片标题（可选）', optional: true),
        if (block['type'] == 'image')
          TextButton(
            onPressed: busy
                ? null
                : () => pickResource(image: true, replacement: block),
            child: const Text('更换此图片'),
          ),
        const Text('仅修改说明不会替换文件；更换图片后旧资源仍保留。'),
      ],
    ),
    'attachment' => Column(
      children: [
        field(block, 'label', '附件名称'),
        TextButton(
          onPressed: busy
              ? null
              : () => pickResource(image: false, replacement: block),
          child: const Text('更换此附件'),
        ),
      ],
    ),
    _ => const Text('此内容暂不支持编辑，原始数据保留。'),
  };

  Widget table(Map block) {
    final headers = block['headers'] as List;
    final rows = block['rows'] as List;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final (rowIndex, row) in [headers, ...rows].indexed)
          ExpansionTile(
            key: ValueKey('${identityHashCode(block)}-row-$rowIndex'),
            title: Text(rowIndex == 0 ? '表头' : '表格第 $rowIndex 行'),
            children: [
              for (final (column, cell) in (row as List).indexed)
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('第 ${column + 1} 列'),
                      for (final value in cell as List) inline(value as Map),
                    ],
                  ),
                ),
            ],
          ),
        Wrap(
          spacing: 8,
          children: [
            TextButton(
              onPressed: busy || rows.length <= 1
                  ? null
                  : () => setState(() => rows.removeLast()),
              child: const Text('从草稿移除末行'),
            ),
            TextButton(
              onPressed: busy || headers.length <= 1
                  ? null
                  : () => setState(() {
                      for (final row in [headers, ...rows]) {
                        (row as List).removeLast();
                      }
                    }),
              child: const Text('从草稿移除末列'),
            ),
            TextButton(
              onPressed: busy || rows.length >= 100
                  ? null
                  : () => setState(
                      () => rows.add([
                        for (var i = 0; i < headers.length; i++)
                          [
                            {'type': 'text', 'text': '新单元格'},
                          ],
                      ]),
                    ),
              child: const Text('添加一行'),
            ),
            TextButton(
              onPressed: busy || headers.length >= 20
                  ? null
                  : () => setState(() {
                      for (final row in [headers, ...rows]) {
                        (row as List).add([
                          {'type': 'text', 'text': '新单元格'},
                        ]);
                      }
                    }),
              child: const Text('添加一列'),
            ),
          ],
        ),
      ],
    );
  }

  void add(Map<String, dynamic> block) => setState(() {
    blocks.add(block);
    preview = false;
  });

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('编辑富内容笔记'),
      content: SizedBox(
        width: 760,
        child: SingleChildScrollView(
          child: Form(
            key: form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  initialValue: title,
                  enabled: !busy,
                  maxLength: 240,
                  decoration: const InputDecoration(labelText: '笔记标题'),
                  onChanged: (value) => title = value,
                  validator: (value) =>
                      value == null || value.trim().isEmpty ? '请填写标题' : null,
                ),
                const Text('原件保留。确认保存后更新笔记；取消不修改资料。'),
                for (final (index, block) in blocks.indexed)
                  Card(
                    key: ObjectKey(block),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text('内容段 ${index + 1}'),
                              IconButton(
                                tooltip: '上移内容段',
                                onPressed: busy || index == 0
                                    ? null
                                    : () => setState(() {
                                        blocks.insert(
                                          index - 1,
                                          blocks.removeAt(index),
                                        );
                                      }),
                                icon: const Icon(Icons.arrow_upward),
                              ),
                              IconButton(
                                tooltip: '下移内容段',
                                onPressed: busy || index == blocks.length - 1
                                    ? null
                                    : () => setState(() {
                                        blocks.insert(
                                          index + 1,
                                          blocks.removeAt(index),
                                        );
                                      }),
                                icon: const Icon(Icons.arrow_downward),
                              ),
                              IconButton(
                                tooltip: '从草稿移除此段',
                                onPressed: busy || blocks.length == 1
                                    ? null
                                    : () => setState(
                                        () => blocks.removeAt(index),
                                      ),
                                icon: const Icon(Icons.remove_circle_outline),
                              ),
                            ],
                          ),
                          if (block['type'] == 'table')
                            table(block as Map)
                          else
                            inline(block as Map),
                        ],
                      ),
                    ),
                  ),
                if (blocks.length < 200)
                  Wrap(
                    spacing: 8,
                    children: [
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => pickResource(image: true),
                        child: const Text('添加图片'),
                      ),
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => pickResource(image: false),
                        child: const Text('添加附件'),
                      ),
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => add({'type': 'text', 'text': ''}),
                        child: const Text('添加文字'),
                      ),
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => add({
                                'type': 'latex',
                                'tex': '',
                                'display': true,
                              }),
                        child: const Text('添加公式'),
                      ),
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => add({
                                'type': 'table',
                                'headers': [
                                  [
                                    {'type': 'text', 'text': '表头'},
                                  ],
                                ],
                                'rows': [
                                  [
                                    [
                                      {'type': 'text', 'text': '单元格'},
                                    ],
                                  ],
                                ],
                              }),
                        child: const Text('添加表格'),
                      ),
                    ],
                  ),
                TextButton(
                  onPressed: busy
                      ? null
                      : () => setState(() => preview = !preview),
                  child: Text(preview ? '收起草稿预览' : '预览当前草稿'),
                ),
                if (preview)
                  ContentBlocks(
                    blocks,
                    backend: widget.backend,
                    workspaceId: widget.workspaceId,
                  ),
                if (busy) const LinearProgressIndicator(),
                if (error != null)
                  SelectableText(
                    error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => copyLearningLink(
            context,
            LearningLink(
              widget.workspaceId,
              'notes',
              widget.note['id'] as String,
            ),
          ),
          child: const Text('复制笔记链接'),
        ),
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context, false),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: busy ? null : save,
          child: const Text('确认保存笔记'),
        ),
      ],
    ),
  );
}
