import 'package:flutter/material.dart';

import 'backend.dart';
import 'import_page.dart';
import 'question_page.dart';
import 'study_page.dart';
import 'workspace_layout.dart';

Future<Map<String, dynamic>?> convertQuestionFile(
  BuildContext context,
  Backend backend,
  String workspace,
  String id, {
  bool legacyMarkdown = false,
}) async {
  final scope = '/api/workspaces/$workspace';
  final endpoint =
      '$scope/${legacyMarkdown ? 'question-markdown' : 'questions'}/${Uri.encodeComponent(id)}';
  final preview = await backend.request('GET', '$endpoint/file-preview') as Map;
  if (!context.mounted) return null;
  if (preview['status'] == 'mapped') {
    return Map<String, dynamic>.from(
      await backend.request(
        'GET',
        '$scope/nodes/${preview['resource_item_id']}',
      ) as Map,
    );
  }
  final confirm = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('预览题目文件转换'),
      content: SizedBox(
        width: 760,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(preview['warning'] as String),
              if (legacyMarkdown)
                const Text('此入口将资料明确转为无标准答案的主观题草稿，不自动推断实际题型或答案。'),
              QuestionPreview(
                question: Map<String, dynamic>.from(preview['question'] as Map),
                backend: backend,
                workspaceId: workspace,
              ),
              ExpansionTile(
                title: const Text('查看将创建的 Markdown'),
                children: [SelectableText(preview['markdown'] as String)],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('取消转换'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('创建题目编辑文件'),
        ),
      ],
    ),
  );
  if (confirm != true) return null;
  return Map<String, dynamic>.from(
    await backend.request('POST', '$endpoint/file', {
      'expected_source_sha256': preview['source_sha256'],
      'expected_preview_sha256': preview['preview_sha256'],
      'confirm': true,
    }) as Map,
  );
}

class QuestionFilePanel extends StatefulWidget {
  const QuestionFilePanel({
    required this.backend,
    required this.workspaceId,
    required this.tab,
    required this.onChanged,
    required this.generation,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final WorkbenchTab tab;
  final VoidCallback onChanged;
  final int generation;
  @override
  State<QuestionFilePanel> createState() => _QuestionFilePanelState();
}

class _QuestionFilePanelState extends State<QuestionFilePanel> {
  Map<String, dynamic>? data;
  bool busy = false, useConfirmed = false;
  String? error;
  String get scope => '/api/workspaces/${widget.workspaceId}';
  String get endpoint =>
      '$scope/nodes/${widget.tab.resourceItemId}/question-file';
  @override
  void initState() {
    super.initState();
    refresh();
  }

  @override
  void didUpdateWidget(covariant QuestionFilePanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.generation != widget.generation) refresh();
  }

  Future<void> refresh() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = Map<String, dynamic>.from(
        await widget.backend.request('GET', endpoint) as Map,
      );
      if (!mounted) return;
      setState(() {
        data = result;
        useConfirmed = [
          'confirmed',
          'invalid_current',
        ].contains(result['status']);
      });
    } catch (failure) {
      if (mounted) setState(() => error = '当前文件未通过题目检查，原文与旧确认版保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> confirm() async {
    final current = data;
    if (busy || current == null || error != null) return;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('发布此题的确认版本？'),
        content: const Text(
          '将保存此刻的题目、共享材料与附件快照，后续作答按该版本判分。已有作答与旧分数保留；缺标准答案的题目待人工批改。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('继续检查'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认题目版本'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.backend.request('POST', '$endpoint/confirm', {
        'expected_sha256': current['sha256'],
        'expected_version_id': current['confirmed_version_id'],
        'confirm': true,
      });
    } catch (failure) {
      if (mounted) setState(() => error = '题目版本未确认，草稿与原件保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
    if (mounted && error == null) await refresh();
  }

  @override
  Widget build(BuildContext context) {
    final current = data;
    final version = useConfirmed ? (current?['confirmed'] as Map?) : null;
    final question = (version?['question'] ?? current?['question']) as Map?;
    final passage =
        (version != null ? version['passage'] : current?['passage']) as Map?;
    final versionId = version?['id'] as String?;
    final title = version != null
        ? version['title'] ?? version['question']['source']['title']
        : current?['title'];
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                onPressed: busy ? null : refresh,
                child: const Text('重新检查题目文件'),
              ),
              if (current?['status'] == 'unconfirmed')
                FilledButton(
                  onPressed: busy || error != null ? null : confirm,
                  child: const Text('检查后确认题目版本'),
                ),
              if (current?['confirmed'] != null)
                TextButton(
                  onPressed: () => setState(() => useConfirmed = !useConfirmed),
                  child: Text(useConfirmed ? '查看当前文件预览' : '查看已确认版并作答'),
                ),
            ],
          ),
          if (busy) const LinearProgressIndicator(),
          if (error != null) SelectableText(error!),
          if (current != null) ...[
            if (title is String)
              Text(title, style: Theme.of(context).textTheme.titleLarge),
            Text(
              versionId == null
                  ? '文件内容尚未确认，不能提交此预览的作答'
                  : '正在使用已确认第${version!['revision']}版 · 当前文件改动不会自动修改答案',
            ),
            for (final warning in current['warnings'] as List? ?? [])
              Text(warning as String),
          ],
          if (passage != null)
            ContentBlocks(
              passage['content'] as List,
              backend: widget.backend,
              workspaceId: widget.workspaceId,
              versionId: versionId,
            ),
          if (question != null)
            QuestionPreview(
              question: Map<String, dynamic>.from(question),
              backend: widget.backend,
              workspaceId: widget.workspaceId,
              versionId: versionId,
            ),
          if (versionId != null)
            StudyAnswer(
              key: ValueKey(versionId),
              question: {
                ...Map<String, dynamic>.from(question!),
                'confirmed_version_id': versionId,
              },
              backend: widget.backend,
              workspaceId: widget.workspaceId,
              scope: scope,
              initialDraft: widget.tab.questionDraft,
              onDraftChanged: (value) {
                widget.tab.questionDraft = value;
                widget.onChanged();
              },
              onSaved: () async {},
            ),
        ],
      ),
    );
  }
}
