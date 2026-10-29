import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend.dart';
import 'page_activity.dart';
import 'author_dialog.dart';
import 'note_editor.dart';
import 'question_page.dart';
import 'question_split_dialog.dart';
import 'question_file_panel.dart';

class ImportPage extends StatefulWidget {
  const ImportPage({
    required this.backend,
    required this.workspaceId,
    this.onActivity,
    this.onOpenResource,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final PageActivityChanged? onActivity;
  final ValueChanged<Map<String, dynamic>>? onOpenResource;
  @override
  State<ImportPage> createState() => _ImportPageState();
}

class _ImportPageState extends State<ImportPage> {
  String get scope => '/api/workspaces/${widget.workspaceId}';
  List<dynamic> jobs = [];
  List<dynamic> questions = [];
  List<dynamic> notes = [];
  List<dynamic> markdownQuestions = [];
  bool moreMarkdown = false;
  String markdownSearch = '';
  Map<String, dynamic>? selected;
  bool busy = false;
  bool loading = true;
  String? error;
  String? message;
  bool more = true;
  bool moreQuestions = false;
  bool moreNotes = false;
  int previewIndex = 0;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    widget.onActivity?.call(loading: true);
    try {
      final results = await Future.wait([
        widget.backend.request('GET', '$scope/imports'),
        widget.backend.request('GET', '$scope/questions?limit=100'),
        widget.backend.request('GET', '$scope/notes?limit=100'),
        widget.backend.request(
          'GET',
          '$scope/question-markdown?limit=50&search=${Uri.encodeQueryComponent(markdownSearch)}',
        ),
      ]);
      if (!mounted) return;
      setState(() {
        jobs = results[0] as List;
        questions = results[1] as List;
        notes = results[2] as List;
        markdownQuestions = results[3] as List;
        moreMarkdown = markdownQuestions.length == 50;
        moreQuestions = questions.length == 100;
        moreNotes = notes.length == 100;
        more = jobs.length == 50;
        loading = false;
        error = null;
      });
    } catch (failure) {
      if (mounted) {
        setState(() {
          loading = false;
          error = '资料读取失败：$failure';
        });
      }
    } finally {
      if (mounted) widget.onActivity?.call(loading: false, error: error);
    }
  }

  Future<void> run(Future<void> Function() operation) async {
    if (busy) return;
    widget.onActivity?.call(loading: true);
    setState(() {
      busy = true;
      error = null;
      message = null;
    });
    try {
      await operation();
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    } finally {
      if (mounted) widget.onActivity?.call(loading: false, error: error);
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> choose() => run(() async {
    final path = await const MethodChannel('study/desktop')
        .invokeMethod<String>('chooseImportFile');
    if (path == null || !mounted) return;
    // Only transport user-selected bytes; parsing and persistence belong to Python.
    final file = File(path);
    final size = await file.length();
    if (size == 0 || size > 8 * 1024 * 1024) {
      throw const FormatException('请选择非空且不超过 8 MiB 的文件');
    }
    final bytes = BytesBuilder(copy: false);
    await for (final chunk in file.openRead()) {
      bytes.add(chunk);
      if (bytes.length > 8 * 1024 * 1024) {
        throw const FormatException('文件超过 8 MiB');
      }
    }
    final name = path.split(RegExp(r'[/\\]')).last;
    final job = await widget.backend.uploadImport(
      widget.workspaceId,
      name,
      bytes.takeBytes(),
    ) as Map<String, dynamic>;
    if (!mounted) return;
    setState(() {
      selected = job;
      previewIndex = 0;
      message = job['duplicate'] == true
          ? '检测到相同原件，已打开已有导入记录'
          : '原件已保存，请检查预览后确认';
    });
    await refresh();
  });

  Future<void> confirm() async {
    if (busy) return;
    final job = selected!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认保存此批资料？'),
        content: Text(
          '将“${job['filename']}”的预览内容保存到当前工作空间。导入来源保持未验证，已有题目和标准答案不会覆盖。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认入库'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await run(() async {
      final result = await widget.backend.request(
        'POST',
        '$scope/imports/${job['id']}/confirm',
      ) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        selected = result;
        message = '已保存到当前工作空间';
      });
      await refresh();
    });
  }

  Future<void> openJob(dynamic job) => run(() async {
    final detail = await widget.backend.request(
      'GET',
      '$scope/imports/${job['id']}',
    ) as Map<String, dynamic>;
    if (mounted) {
      setState(() {
        selected = detail;
        previewIndex = 0;
      });
    }
  });

  Future<void> loadMore() => run(() async {
    final next = await widget.backend.request(
      'GET',
      '$scope/imports?offset=${jobs.length}',
    ) as List;
    if (mounted) {
      setState(() {
        jobs.addAll(next);
        more = next.length == 50;
      });
    }
  });

  Future<void> export() => run(() async {
    final path = await const MethodChannel('study/desktop')
        .invokeMethod<String>('chooseExportFile');
    if (path == null) return;
    final bytes = await widget.backend.exportArchive(widget.workspaceId);
    await File(path).writeAsBytes(bytes, flush: true);
    if (mounted) setState(() => message = '资料已导出，包含题目、笔记、原件和校验清单');
  });

  Future<void> author({Map<String, dynamic>? note, bool link = false}) async {
    if (busy) return;
    if (note != null) {
      final saved = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => NoteEditor(
          note: note,
          backend: widget.backend,
          workspaceId: widget.workspaceId,
        ),
      );
      if (saved == true && mounted) {
        await run(() async {
          setState(() => message = '笔记已保存，导入原件保留');
          await refresh();
        });
      }
      return;
    }
    final value = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => AuthorDialog(link: link),
    );
    if (value == null || !mounted) return;
    await run(() async {
      final job = await widget.backend.uploadImport(
        widget.workspaceId,
        link ? value['filename'] as String : '手动录入.json',
        utf8.encode(link ? value['url'] as String : jsonEncode(value)),
      ) as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          selected = job;
          previewIndex = 0;
        });
      }
      await refresh();
    });
  }

  Future<void> retry() => run(() async {
    final job = await widget.backend.request(
      'POST',
      '$scope/imports/${selected!['id']}/retry',
    ) as Map<String, dynamic>;
    if (mounted) {
      setState(() {
        selected = job;
        previewIndex = 0;
      });
    }
    await refresh();
  });

  Future<void> recovery() => run(() async {
    final records =
        await widget.backend.request('GET', '$scope/recovery') as List;
    if (!mounted) return;
    if (records.isEmpty) {
      setState(() => message = '没有发现未登记的原件');
      return;
    }
    // Recover one at a time so the user can assign the original format explicitly.
    final record = records.first;
    var entered = '';
    final filename = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('恢复未登记的原件'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '发现 ${records.length} 个原件。当前文件 ${record['size']} 字节；恢复后仍需检查预览。',
            ),
            TextField(
              onChanged: (value) => entered = value,
              maxLength: 240,
              decoration: const InputDecoration(labelText: '原文件名（包含扩展名）'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('保留原件，稍后处理'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, entered),
            child: const Text('恢复记录'),
          ),
        ],
      ),
    );
    if (filename == null || filename.trim().isEmpty) return;
    final job = await widget.backend.request('POST', '$scope/recovery', {
      'resource_id': record['resource_id'],
      'filename': filename.trim(),
    }) as Map<String, dynamic>;
    if (mounted) {
      setState(() {
        selected = job;
        previewIndex = 0;
      });
    }
    await refresh();
  });

  Future<void> loadLibraryMore({required bool isNotes}) => run(() async {
    final list = isNotes ? notes : questions;
    final collection = isNotes ? 'notes' : 'questions';
    final next = await widget.backend.request(
      'GET',
      '$scope/$collection?offset=${list.length}&limit=100',
    ) as List;
    if (mounted) {
      setState(() {
        list.addAll(next);
        if (isNotes) {
          moreNotes = next.length == 100;
        } else {
          moreQuestions = next.length == 100;
        }
      });
    }
  });

  Future<void> openQuestion(dynamic summary) => run(() async {
    final question = await widget.backend.request(
      'GET',
      '$scope/questions/${summary['id']}',
    ) as Map<String, dynamic>;
    Map<String, dynamic>? passage;
    if (question['passage_id'] != null) {
      passage = await widget.backend.request(
        'GET',
        '$scope/passages/${question['passage_id']}',
      ) as Map<String, dynamic>;
    }
    if (!mounted) return;
    unawaited(
      showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text('${question['subject']} · 题目预览'),
          content: SizedBox(
            width: 720,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (passage != null)
                    ContentBlocks(
                      passage['content'] as List,
                      backend: widget.backend,
                      workspaceId: widget.workspaceId,
                    ),
                  QuestionPreview(
                    question: question,
                    backend: widget.backend,
                    workspaceId: widget.workspaceId,
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭预览'),
            ),
          ],
        ),
      ),
    );
  });

  Future<void> splitQuestions() async {
    if (busy || selected == null) return;
    final saved = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => QuestionSplitDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        job: selected!,
      ),
    );
    if (!mounted) return;
    await run(() async {
      selected = await widget.backend.request(
        'GET',
        '$scope/imports/${selected!['id']}',
      ) as Map<String, dynamic>;
      await refresh();
      if (mounted) {
        setState(
          () => message = saved == true
              ? '已逐题保存为 Markdown；原文档与图片保留'
              : '拆题预览已保留，尚未入库',
        );
      }
    });
  }

  Future<void> openMarkdown(dynamic item) => run(() async {
    final detail = await widget.backend.request(
      'GET',
      '$scope/question-markdown/${item['id']}',
    ) as Map<String, dynamic>;
    if (!mounted) return;
    unawaited(
      showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(detail['title'] as String),
          content: SizedBox(
            width: 780,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('独立 Markdown 题目资料 · 来源未验证 · 未推断标准答案'),
                  ContentBlocks(
                    detail['blocks'] as List,
                    backend: widget.backend,
                    workspaceId: widget.workspaceId,
                  ),
                  ExpansionTile(
                    title: const Text('查看 Markdown 文件内容'),
                    children: [SelectableText(detail['markdown'] as String)],
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () async {
                Navigator.pop(context);
                await run(() async {
                  final node = await convertQuestionFile(
                    this.context,
                    widget.backend,
                    widget.workspaceId,
                    item['id'] as String,
                    legacyMarkdown: true,
                  );
                  if (mounted && node != null) {
                    widget.onOpenResource?.call(node);
                  }
                });
              },
              child: const Text('预览转换为待批改题目文件'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭题目'),
            ),
          ],
        ),
      ),
    );
  });

  String status(dynamic job) => switch (job['status']) {
    'parsing' => '正在解析，请稍后刷新记录',
    'confirmed' => '已入库',
    'failed' => '解析失败，原件保留',
    _ => '待确认',
  };

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.all(24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('导入与资料库', style: Theme.of(context).textTheme.headlineSmall),
        const Text('选择资料 → 检查预览 → 确认入库。原件会保留，未经确认不写入题库或笔记。'),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: busy ? null : choose,
              icon: const Icon(Icons.upload_file),
              label: const Text('选择文件并预览'),
            ),
            OutlinedButton(
              onPressed: busy ? null : author,
              child: const Text('手动录入题目或笔记'),
            ),
            OutlinedButton(
              onPressed: busy ? null : () => author(link: true),
              child: const Text('保存资料链接'),
            ),
            OutlinedButton.icon(
              onPressed: busy ? null : () => run(refresh),
              icon: const Icon(Icons.refresh),
              label: const Text('刷新资料'),
            ),
            OutlinedButton(
              onPressed: busy ? null : export,
              child: const Text('导出资料与原件'),
            ),
            OutlinedButton(
              onPressed: busy ? null : recovery,
              child: const Text('检查中断遗留原件'),
            ),
          ],
        ),
        const Text(
          '支持 Word（DOCX）、PDF（最多20页）、UTF-8 文本、Markdown、HTML、题目 JSON、资料链接和 PNG/JPEG；单文件最多 8 MiB。',
        ),
        if (busy || loading) const LinearProgressIndicator(),
        if (message != null) SelectableText(message!),
        if (error != null)
          SelectableText(
            '操作未完成：$error',
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        if (selected != null) ...[
          const Divider(height: 32),
          Text(
            '${selected!['filename']} · ${status(selected)}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          SelectableText('SHA256：${selected!['sha256']}'),
          Text('解析器：${selected!['parser_version']} · ${selected!['size']} 字节'),
          if (selected!['error'] != null) Text(selected!['error'] as String),
          if (selected!['status'] != 'confirmed' &&
              selected!['status'] != 'parsing')
            TextButton(
              onPressed: busy ? null : retry,
              child: const Text('重新解析原件'),
            ),
          if ((selected!['preview']['question_drafts'] as List? ?? [])
              .isNotEmpty)
            FilledButton(
              onPressed: busy ? null : splitQuestions,
              child: const Text('检查拆题，逐题存为 Markdown'),
            ),
          if ((selected!['preview']['question_drafts'] as List? ?? [])
              .isNotEmpty)
            ExpansionTile(
              title: const Text('查看整份原资料预览'),
              children: [
                _preview(selected!['preview'] as Map<String, dynamic>),
              ],
            ),
          if ((selected!['preview']['question_drafts'] as List? ?? []).isEmpty)
            _preview(selected!['preview'] as Map<String, dynamic>),
          if (selected!['status'] == 'preview')
            FilledButton(
              onPressed: busy ? null : confirm,
              child: Text(
                (selected!['preview']['question_drafts'] as List? ?? []).isEmpty
                    ? '检查完成，确认入库'
                    : '将整篇另存为资料笔记',
              ),
            ),
        ],
        const Divider(height: 32),
        Text('导入记录', style: Theme.of(context).textTheme.titleLarge),
        if (!loading && jobs.isEmpty) const Text('尚无导入记录'),
        for (final job in jobs)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(job['filename'] as String),
            subtitle: Text('${status(job)} · ${job['created_at']}'),
            onTap: busy ? null : () => openJob(job),
            trailing: const Icon(Icons.chevron_right),
          ),
        if (more && !loading)
          TextButton(
            onPressed: busy ? null : loadMore,
            child: const Text('加载更多导入记录'),
          ),
        const Divider(height: 32),
        Text(
          '本地题目知识库（Markdown）',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const Text('由用户文档逐题提取；每题独立，不要求已有标准答案。资料导出包含可独立打开的 MD 与图片。'),
        SizedBox(
          width: 320,
          child: TextField(
            decoration: const InputDecoration(labelText: '按题目标题检索'),
            onChanged: (value) => markdownSearch = value,
            onSubmitted: (_) => run(refresh),
          ),
        ),
        for (final item in markdownQuestions)
          ListTile(
            title: Text(item['title'] as String),
            subtitle: const Text('独立 Markdown · 点击查看原题'),
            onTap: busy ? null : () => openMarkdown(item),
          ),
        if (moreMarkdown)
          TextButton(
            onPressed: busy
                ? null
                : () => run(() async {
                    final next = await widget.backend.request(
                      'GET',
                      '$scope/question-markdown?limit=50&offset=${markdownQuestions.length}&search=${Uri.encodeQueryComponent(markdownSearch)}',
                    ) as List;
                    if (mounted) {
                      setState(() {
                        markdownQuestions.addAll(next);
                        moreMarkdown = next.length == 50;
                      });
                    }
                  }),
            child: const Text('加载更多 Markdown 题目'),
          ),
        const Divider(height: 32),
        Text('结构化练习题（兼容入口）', style: Theme.of(context).textTheme.titleLarge),
        for (final q in questions)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('${q['subject']} · ${q['id']}'),
            trailing: const Icon(Icons.preview_outlined),
            onTap: busy ? null : () => openQuestion(q),
          ),
        if (moreQuestions)
          TextButton(
            onPressed: busy ? null : () => loadLibraryMore(isNotes: false),
            child: const Text('加载更多题目'),
          ),
        const Divider(height: 32),
        Text('资料笔记', style: Theme.of(context).textTheme.titleLarge),
        if (!loading && notes.isEmpty) const Text('尚无已确认的资料笔记'),
        for (final note in notes)
          ExpansionTile(
            key: ValueKey(note['id']),
            title: Text(note['title'] as String),
            children: [
              TextButton(
                onPressed: busy
                    ? null
                    : () => author(note: note as Map<String, dynamic>),
                child: const Text('编辑此笔记'),
              ),
              ContentBlocks(
                note['content'] as List,
                backend: widget.backend,
                workspaceId: widget.workspaceId,
              ),
            ],
          ),
        if (moreNotes)
          TextButton(
            onPressed: busy ? null : () => loadLibraryMore(isNotes: true),
            child: const Text('加载更多笔记'),
          ),
      ],
    ),
  );

  Widget _preview(Map<String, dynamic> preview) {
    if (preview['kind'] == 'questions') {
      final bundle = preview['bundle'] as Map<String, dynamic>;
      final passages = bundle['passages'] as List;
      final questions = bundle['questions'] as List;
      final total = passages.length + questions.length;
      final isPassage = previewIndex < passages.length;
      final record = isPassage
          ? passages[previewIndex]
          : questions[previewIndex - passages.length];
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                '预览 ${previewIndex + 1} / $total（${questions.length} 题，${passages.length} 篇阅读材料）',
              ),
              TextButton(
                onPressed: busy || previewIndex == 0
                    ? null
                    : () => setState(() => previewIndex--),
                child: const Text('上一条'),
              ),
              TextButton(
                onPressed: busy || previewIndex == total - 1
                    ? null
                    : () => setState(() => previewIndex++),
                child: const Text('下一条'),
              ),
            ],
          ),
          if (isPassage) ...[
            Text('共享阅读材料：${record['id']}'),
            ContentBlocks(
              record['content'] as List,
              backend: widget.backend,
              workspaceId: widget.workspaceId,
            ),
          ] else
            QuestionPreview(
              question: record,
              backend: widget.backend,
              workspaceId: widget.workspaceId,
            ),
        ],
      );
    }
    if (preview['blocks'] is List) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final warning in preview['warnings'] as List? ?? [])
            Text('请核对：$warning'),
          ContentBlocks(
            preview['blocks'] as List,
            backend: widget.backend,
            workspaceId: widget.workspaceId,
          ),
        ],
      );
    }
    return const SizedBox.shrink();
  }
}

class QuestionPreview extends StatelessWidget {
  const QuestionPreview({
    required this.question,
    required this.backend,
    required this.workspaceId,
    this.versionId,
    super.key,
  });
  final Map<String, dynamic> question;
  final Backend backend;
  final String workspaceId;
  final String? versionId;
  @override
  Widget build(BuildContext context) {
    final source = question['source'] as Map<String, dynamic>;
    final kind = switch (source['kind']) {
      'ai_generated' => 'AI 生成',
      'official' => '官方来源',
      'manual' => '手动来源',
      _ => '导入来源',
    };
    final verification = switch (source['verification']) {
      'human_verified' => '人工已验证',
      'rejected' => '已拒绝',
      _ => '未验证',
    };
    Widget content(List<dynamic> blocks) => ContentBlocks(
      blocks,
      backend: backend,
      workspaceId: workspaceId,
      versionId: versionId,
    );
    final answer = question['answer'] as Map<String, dynamic>? ?? {};
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${question['subject']} · ${question['id']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text('$kind · $verification · ${source['title']}'),
          if (source['model'] != null) Text('生成模型：${source['model']}'),
          content(question['stem'] as List),
          for (final option in question['options'] as List)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${option['id']}  '),
                Expanded(child: content(option['content'] as List)),
              ],
            ),
          ExpansionTile(
            title: const Text('查看参考答案与解析'),
            children: [
              if (answer['selected'] is List)
                Text('正确选项：${(answer['selected'] as List).join('、')}'),
              if (answer['blanks'] is List)
                for (final blank in answer['blanks'] as List)
                  Text(
                    '填空 ${blank['id']}：${(blank['accepted'] as List).join(' / ')}',
                  ),
              if (answer['rubric'] is String) Text('评分要点：${answer['rubric']}'),
              if (answer['reference'] is List)
                content(answer['reference'] as List),
              if (question['answer'] == null) const Text('未提供标准答案；提交后待人工批改'),
              content(question['explanation'] as List),
            ],
          ),
        ],
      ),
    );
  }
}
