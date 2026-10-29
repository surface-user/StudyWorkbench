import 'dart:typed_data';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

import 'backend.dart';
import 'page_activity.dart';

class ContentBlocks extends StatelessWidget {
  const ContentBlocks(
    this.blocks, {
    this.backend,
    this.workspaceId = 'default',
    this.inlineImages = const {},
    this.versionId,
    super.key,
  });
  final List<dynamic> blocks;
  final Backend? backend;
  final String workspaceId;
  final Map<String, Uint8List> inlineImages;
  final String? versionId;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: blocks
        .map<Widget>(
          (block) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: switch (block['type']) {
              'text' => Text(block['text'] as String),
              'latex' => SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Math.tex(
                  block['tex'] as String,
                  textStyle: const TextStyle(fontSize: 24),
                ),
              ),
              'table' => SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Table(
                  defaultColumnWidth: const FixedColumnWidth(200),
                  border: TableBorder.all(
                    color: Theme.of(context).dividerColor,
                  ),
                  children: [
                    for (final row in [
                      block['headers'],
                      ...block['rows'] as List,
                    ])
                      TableRow(
                        children: [
                          for (final cell in row as List)
                            Padding(
                              padding: const EdgeInsets.all(8),
                              child: ContentBlocks(
                                cell as List,
                                backend: backend,
                                workspaceId: workspaceId,
                                inlineImages: inlineImages,
                                versionId: versionId,
                              ),
                            ),
                        ],
                      ),
                  ],
                ),
              ),
              'image' || 'chart' =>
                inlineImages.containsKey(block['attachment_id'])
                    ? Image.memory(
                        inlineImages[block['attachment_id']]!,
                        semanticLabel: block['alt'] as String,
                        cacheWidth: 1600,
                        errorBuilder: (_, error, stack) =>
                            const Text('预览图片无法解码'),
                      )
                    : backend == null
                    ? Text(block['alt'] as String)
                    : _ResourceImage(
                        backend: backend!,
                        workspaceId: workspaceId,
                        resourceId: block['attachment_id'] as String,
                        alt: block['alt'] as String,
                        caption: block['caption'] as String?,
                        versionId: versionId,
                      ),
              'attachment' => Text('附件：${block['label']}（原件已保留）'),
              _ => const Text('此内容块尚未支持（已保留原数据）'),
            },
          ),
        )
        .toList(),
  );
}

class _ResourceImage extends StatefulWidget {
  const _ResourceImage({
    required this.backend,
    required this.workspaceId,
    required this.resourceId,
    required this.alt,
    this.caption,
    this.versionId,
  });
  final Backend backend;
  final String workspaceId;
  final String resourceId;
  final String alt;
  final String? caption;
  final String? versionId;
  @override
  State<_ResourceImage> createState() => _ResourceImageState();
}

class _ResourceImageState extends State<_ResourceImage> {
  late var bytes = load();
  Future<Uint8List> load() async {
    if (widget.versionId == null) {
      return widget.backend.resourceBytes(
        widget.workspaceId,
        widget.resourceId,
      );
    }
    final result = await widget.backend.request(
      'GET',
      '/api/workspaces/${widget.workspaceId}/question-versions/${widget.versionId}/assets/${widget.resourceId}',
    ) as Map;
    return base64Decode(result['image_base64'] as String);
  }

  @override
  void didUpdateWidget(covariant _ResourceImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.backend != widget.backend ||
        oldWidget.workspaceId != widget.workspaceId ||
        oldWidget.resourceId != widget.resourceId ||
        oldWidget.versionId != widget.versionId) {
      bytes = load();
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder(
    future: bytes,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text('图片无法读取：${widget.alt}'),
            TextButton(
              onPressed: () => setState(() => bytes = load()),
              child: const Text('重新加载图片'),
            ),
          ],
        );
      }
      if (!snapshot.hasData) return Text('正在加载图片：${widget.alt}');
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Image.memory(
            snapshot.data!,
            semanticLabel: widget.alt,
            fit: BoxFit.contain,
            cacheWidth: 1600,
            errorBuilder: (_, error, stack) => Text('图片无法解码：${widget.alt}'),
          ),
          if (widget.caption != null) Text(widget.caption!),
        ],
      );
    },
  );
}

class QuestionPage extends StatefulWidget {
  const QuestionPage({
    required this.backend,
    this.workspaceId = 'default',
    this.initialDraft = '',
    this.onDraftChanged,
    this.onActivity,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final String initialDraft;
  final ValueChanged<String>? onDraftChanged;
  final PageActivityChanged? onActivity;
  @override
  State<QuestionPage> createState() => _QuestionPageState();
}

class _QuestionPageState extends State<QuestionPage> {
  String? confirmedVersionId;
  int? confirmedRevision;
  late Future<dynamic> question = loadQuestion();
  Future<dynamic> loadQuestion() async {
    widget.onActivity?.call(loading: true);
    try {
      final value = await widget.backend.request(
        'GET',
        '$scope/questions/demo',
      );
      confirmedVersionId = value['confirmed_version_id'] as String?;
      confirmedRevision = value['revision'] as int?;
      if (mounted) widget.onActivity?.call(loading: false);
      return value;
    } catch (failure) {
      if (mounted) widget.onActivity?.call(loading: false, error: '$failure');
      rethrow;
    }
  }

  String get scope => '/api/workspaces/${widget.workspaceId}';
  late final written = TextEditingController(text: widget.initialDraft);
  String? result;
  bool busy = false;
  void reloadQuestion() {
    setState(() {
      question = loadQuestion();
    });
  }

  Future<void> submit(String id, Map<String, dynamic> response) async {
    if (busy) return;
    setState(() {
      busy = true;
      result = null;
    });
    try {
      final answer = await widget.backend.request('POST', '$scope/attempts', {
        'question_id': id,
        'response': response,
        if (confirmedVersionId != null) ...{
          'question_version_id': confirmedVersionId,
          'question_revision': confirmedRevision,
        },
      });
      final saved = answer['status'] == 'pending_review'
          ? '已保存，待人工批改'
          : '已保存，得分 ${answer['score']}';
      if (mounted) setState(() => result = saved);
      // History is a separate read; its failure must not invite another write.
      try {
        final history =
            await widget.backend.request('GET', '$scope/attempts') as List;
        if (mounted) {
          setState(() => result = '$saved · 共 ${history.length} 次作答');
        }
      } catch (_) {
        if (mounted) {
          setState(() => result = '$saved · 作答次数暂时无法读取，请勿重复提交');
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => result = '未能确认作答是否保存，请勿连续重试；需核实保存状态：$e');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    written.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
    future: question,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('题目加载失败：${snapshot.error}'),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: reloadQuestion,
                  icon: const Icon(Icons.refresh),
                  label: const Text('重新加载题目'),
                ),
              ],
            ),
          ),
        );
      }
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final q = snapshot.data as Map<String, dynamic>;
      return SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              q['subject'] as String,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const Text('人工演示题 · 非真题 · 未验证'),
            ContentBlocks(
              q['stem'] as List,
              backend: widget.backend,
              workspaceId: widget.workspaceId,
            ),
            for (final option in q['options'] as List)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => submit(q['id'] as String, {
                          'selected': [option['id']],
                        }),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('选择答案  '),
                      ContentBlocks(
                        option['content'] as List,
                        backend: widget.backend,
                        workspaceId: widget.workspaceId,
                      ),
                    ],
                  ),
                ),
              ),
            const Divider(height: 36),
            const Text('主观题验证：说明计算过程（默认待批改）'),
            const SizedBox(height: 12),
            TextField(
              controller: written,
              onChanged: widget.onDraftChanged,
              maxLength: 16000,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: '输入解题过程',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: busy
                  ? null
                  : () => submit('demo-proof', {'text': written.text}),
              child: const Text('提交主观作答'),
            ),
            if (result != null)
              Padding(padding: const EdgeInsets.all(12), child: Text(result!)),
          ],
        ),
      );
    },
  );
}
