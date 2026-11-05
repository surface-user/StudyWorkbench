import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';
import 'agent_access_dialog.dart';
import 'analysis_review_dialog.dart';
import 'learning_record_dialog.dart';
import 'page_activity.dart';
import 'import_page.dart';
import 'question_page.dart';
import 'question_file_panel.dart';

class StudyPage extends StatefulWidget {
  const StudyPage({
    required this.backend,
    required this.workspaceId,
    this.onActivity,
    this.onOpenResource,
    this.historyRevision = 0,
    super.key,
  });
  final Backend backend;
  final int historyRevision;
  final String workspaceId;
  final PageActivityChanged? onActivity;
  final ValueChanged<Map<String, dynamic>>? onOpenResource;
  @override
  State<StudyPage> createState() => _StudyPageState();
}

class _StudyPageState extends State<StudyPage> {
  final historyKey = GlobalKey();
  final historyController = ExpansibleController();
  @override
  void dispose() {
    historyController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant StudyPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.historyRevision != widget.historyRevision) revealHistory();
  }

  void revealHistory() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || historyKey.currentContext == null) return;
      historyController.expand();
      Scrollable.ensureVisible(
        historyKey.currentContext!,
        duration: const Duration(milliseconds: 200),
      );
    });
  }

  String get scope => '/api/workspaces/${widget.workspaceId}';
  List<dynamic> rows = [], history = [], tasks = [];
  Map<String, dynamic>? stats, question, passage;
  String mode = 'due', knowledge = '';
  String? subject, kind, error;
  bool busy = false, more = false, moreHistory = false;
  @override
  void initState() {
    super.initState();
    refresh();
    if (widget.historyRevision > 0) revealHistory();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    widget.onActivity?.call(loading: true);
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    } finally {
      if (mounted) widget.onActivity?.call(loading: false, error: error);
      if (mounted) setState(() => busy = false);
    }
  }

  String get filters => Uri(
    queryParameters: {
      'mode': mode,
      'subject': ?subject,
      'kind': ?kind,
      if (knowledge.trim().isNotEmpty) 'knowledge_point': knowledge.trim(),
    },
  ).query;
  Future<void> fetch() async {
    final results = await Future.wait([
      widget.backend.request('GET', '$scope/study?$filters'),
      widget.backend.request('GET', '$scope/statistics'),
      widget.backend.request('GET', '$scope/attempt-history?limit=50'),
      widget.backend.request('GET', '$scope/study-tasks'),
    ]);
    if (mounted) {
      setState(() {
        rows = results[0] as List;
        stats = results[1] as Map<String, dynamic>;
        history = results[2] as List;
        moreHistory = history.length == 50;
        tasks = results[3] as List;
        more = rows.length == 50;
      });
    }
  }

  Future<void> refresh() => run(fetch);
  Future<void> loadHistory() => run(() async {
    final page = history;
    final next = await widget.backend.request(
      'GET',
      '$scope/attempt-history?limit=50&before_id=${page.last['id']}',
    ) as List;
    if (mounted && identical(history, page)) {
      setState(() {
        history.addAll(next);
        moreHistory = next.length == 50;
      });
    }
  });
  Future<void> open(String id) => run(() async {
    final q = await widget.backend.request(
      'GET',
      '$scope/questions/${Uri.encodeComponent(id)}',
    ) as Map<String, dynamic>;
    final version = q['confirmed_version_id'] == null
        ? null
        : await widget.backend.request(
            'GET',
            '$scope/question-versions/${q['confirmed_version_id']}',
          ) as Map;
    final p = version != null
        ? version['passage'] as Map<String, dynamic>?
        : q['passage_id'] == null
        ? null
        : await widget.backend.request(
            'GET',
            '$scope/passages/${q['passage_id']}',
          ) as Map<String, dynamic>;
    if (mounted) {
      setState(() {
        question = q;
        passage = p;
      });
    }
  });
  Future<void> plan() => run(() async {
    await widget.backend.request('POST', '$scope/study-tasks', {
      'title': '${DateTime.now().toIso8601String().substring(0, 10)} 每日练习',
      'count': 10,
      'mode': mode,
      if (subject != null) 'subject': subject,
      if (kind != null) 'kind': kind,
      if (knowledge.trim().isNotEmpty) 'knowledge_point': knowledge.trim(),
    });
    await fetch();
  });
  Future<void> review(Map<String, dynamic> attempt) async {
    if (busy) return;
    var score = '', feedback = '';
    final form = GlobalKey<FormState>();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('人工批改 / 修订评分'),
        content: SizedBox(
          width: 480,
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('追加评分修订，保留原始作答和既有评分。'),
                TextFormField(
                  decoration: const InputDecoration(labelText: '得分比例（0 至 1）'),
                  onChanged: (s) => score = s,
                  validator: (s) {
                    final n = double.tryParse(s ?? '');
                    return n == null || !n.isFinite || n < 0 || n > 1
                        ? '请输入 0 至 1 的数字'
                        : null;
                  },
                ),
                TextFormField(
                  decoration: const InputDecoration(labelText: '批改说明'),
                  minLines: 2,
                  maxLines: 4,
                  onChanged: (s) => feedback = s,
                  validator: (s) =>
                      s == null || s.trim().isEmpty ? '请填写说明' : null,
                ),
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
            onPressed: () {
              if (form.currentState!.validate()) {
                Navigator.pop(context, {
                  'score': double.parse(score),
                  'feedback': feedback,
                  'confirm': true,
                });
              }
            },
            child: const Text('确认追加评分'),
          ),
        ],
      ),
    );
    if (result == null || !mounted) return;
    await run(() async {
      await widget.backend.request(
        'POST',
        '$scope/attempts/${attempt['id']}/reviews',
        result,
      );
      await fetch();
    });
  }

  String writtenResponse(Map<String, dynamic> response) {
    if (response['text'] is String) return response['text'] as String;
    if (response['selected'] is List) {
      return '已选选项：${(response['selected'] as List).join('、')}';
    }
    if (response['blanks'] is Map) {
      return (response['blanks'] as Map).entries
          .map((e) => '${e.key}：${e.value}')
          .join('\n');
    }
    return '不支持此作答格式，原始记录保留';
  }

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.all(24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('题库与学习计划', style: Theme.of(context).textTheme.headlineSmall),
        const Text('支持 408、数学一、英语一、政治等自建题库；可从资源管理器的资料处理中录入或确认题目。'),
        if (stats != null)
          Text(
            '题目 ${stats!['questions']} · 作答 ${stats!['attempts']} · 到期 ${stats!['due']} · 错题 ${stats!['wrong']} · 掌握 ${stats!['mastered']} · 待批改 ${stats!['pending_review']}',
          ),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            DropdownButton<String>(
              value: mode,
              items: [
                for (final e in const {
                  'due': '到期复习与新题',
                  'wrong': '错题本',
                  'all': '全部题库',
                }.entries)
                  DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: busy
                  ? null
                  : (s) {
                      setState(() => mode = s!);
                      refresh();
                    },
            ),
            DropdownButton<String>(
              value: subject,
              hint: const Text('全部科目'),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('全部科目'),
                ),
                for (final s in stats?['subjects'] as List? ?? [])
                  DropdownMenuItem(value: s as String, child: Text(s)),
              ],
              onChanged: busy
                  ? null
                  : (s) {
                      setState(() => subject = s);
                      refresh();
                    },
            ),
            DropdownButton<String>(
              value: kind,
              hint: const Text('全部题型'),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('全部题型'),
                ),
                for (final e in const {
                  'single_choice': '单选',
                  'multiple_choice': '多选',
                  'fill_blank': '填空',
                  'calculation': '计算',
                  'proof': '证明',
                  'subjective': '主观',
                  'reading_question': '阅读',
                }.entries)
                  DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: busy
                  ? null
                  : (s) {
                      setState(() => kind = s);
                      refresh();
                    },
            ),
            SizedBox(
              width: 220,
              child: TextField(
                decoration: const InputDecoration(labelText: '知识点（精确名称）'),
                onChanged: (s) => knowledge = s,
                onSubmitted: (_) => refresh(),
              ),
            ),
            OutlinedButton(
              onPressed: busy ? null : refresh,
              child: const Text('筛选 / 刷新'),
            ),
            FilledButton(
              onPressed: busy ? null : plan,
              child: const Text('生成每日十题任务'),
            ),
          ],
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) SelectableText('操作未完成：$error'),
        if (question != null) ...[
          const Divider(),
          OutlinedButton(
            onPressed: busy
                ? null
                : () => run(() async {
                    final node = await convertQuestionFile(
                      context,
                      widget.backend,
                      widget.workspaceId,
                      question!['id'] as String,
                    );
                    if (mounted && node != null) {
                      widget.onOpenResource?.call(node);
                    }
                  }),
            child: const Text('预览转换 / 打开题目文件'),
          ),
          if (passage != null)
            ContentBlocks(
              passage!['content'] as List,
              backend: widget.backend,
              workspaceId: widget.workspaceId,
              versionId: question!['confirmed_version_id'] as String?,
            ),
          QuestionPreview(
            question: question!,
            backend: widget.backend,
            workspaceId: widget.workspaceId,
            versionId: question!['confirmed_version_id'] as String?,
          ),
          StudyAnswer(
            key: ValueKey((
              question!['id'],
              question!['confirmed_version_id'] ?? question!['revision'],
            )),
            question: question!,
            backend: widget.backend,
            workspaceId: widget.workspaceId,
            scope: scope,
            onSaved: fetch,
          ),
          const Divider(),
        ],
        for (final r in rows)
          ListTile(
            title: Text('${r['subject']} · ${r['id']}'),
            subtitle: Text(
              '${(r['knowledge_points'] as List).join('、')} · ${r['pending_review'] == true
                  ? '待批改'
                  : r['mastered'] == true
                  ? '已掌握'
                  : r['wrong'] == true
                  ? '需巩固'
                  : '学习中'} · 作答 ${r['attempt_count']} 次',
            ),
            trailing: const Icon(Icons.edit_note),
            onTap: busy ? null : () => open(r['id'] as String),
          ),
        if (!busy && rows.isEmpty) const Text('没有符合条件的题目；到期复习会跳过未到期的掌握题和待批改题。'),
        if (more)
          TextButton(
            onPressed: busy
                ? null
                : () => run(() async {
                    final next = await widget.backend.request(
                      'GET',
                      '$scope/study?$filters&offset=${rows.length}',
                    ) as List;
                    if (mounted) {
                      setState(() {
                        rows.addAll(next);
                        more = next.length == 50;
                      });
                    }
                  }),
            child: const Text('加载更多题目'),
          ),
        ExpansionTile(
          title: const Text('每日任务'),
          children: [
            for (final t in tasks)
              ExpansionTile(
                title: Text(
                  '${t['title']} · ${(t['completed_question_ids'] as List).length}/${(t['question_ids'] as List).length}',
                ),
                children: [
                  for (final id in t['question_ids'] as List)
                    ListTile(
                      title: Text(id as String),
                      onTap: busy ? null : () => open(id),
                    ),
                ],
              ),
          ],
        ),
        ExpansionTile(
          title: const Text('知识点统计'),
          children: [
            for (final p in stats?['knowledge_points'] as List? ?? [])
              ListTile(
                title: Text('${p['subject']} · ${p['name']}'),
                subtitle: Text(
                  '题目 ${p['questions']} · 掌握 ${p['mastered']} · 错题 ${p['wrong']}',
                ),
              ),
          ],
        ),
        ExpansionTile(
          key: historyKey,
          controller: historyController,
          title: Text('作答历史与待批改（已加载 ${history.length} 条）'),
          children: [
            TextButton(
              onPressed: busy || history.isEmpty
                  ? null
                  : () async {
                      final note = await showDialog<Map<String, dynamic>>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => AgentAccessDialog(
                          backend: widget.backend,
                          scope: scope,
                          attempts: List.of(history),
                        ),
                      );
                      if (mounted && note != null) {
                        widget.onOpenResource?.call(note);
                      }
                    },
              child: const Text('选择记录 / 本地授权'),
            ),
            TextButton(
              onPressed: busy
                  ? null
                  : () async {
                      final note = await showAnalysisReviews(
                        context,
                        widget.backend,
                        scope,
                      );
                      if (mounted && note != null) {
                        widget.onOpenResource?.call(note);
                      }
                    },
              child: const Text('分析候选 / 独立审核'),
            ),
            for (final a in history)
              ExpansionTile(
                title: Text(
                  '${a['question_id']} · ${a['status'] == 'pending_review' ? '待人工批改' : '得分 ${a['score']}'}',
                ),
                subtitle: Text(a['created_at'] as String),
                children: [
                  SelectableText(
                    writtenResponse(a['response'] as Map<String, dynamic>),
                  ),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => showDialog<void>(
                            context: context,
                            builder: (context) => LearningRecordDialog(
                              backend: widget.backend,
                              scope: scope,
                              workspaceId: widget.workspaceId,
                              attemptId: a['id'] as int,
                              onOpenResource: widget.onOpenResource,
                            ),
                          ),
                    child: const Text('学习记录 / 历史快照'),
                  ),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => open(a['question_id'] as String),
                    child: const Text('打开此题'),
                  ),
                  for (final r in a['reviews'] as List? ?? [])
                    Text('评分修订：${r['score']} · ${r['feedback']}'),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => review(a as Map<String, dynamic>),
                    child: const Text('人工批改 / 修订评分'),
                  ),
                ],
              ),
            if (moreHistory)
              TextButton(
                onPressed: busy ? null : loadHistory,
                child: const Text('加载更早作答'),
              ),
          ],
        ),
      ],
    ),
  );
}

class StudyAnswer extends StatefulWidget {
  const StudyAnswer({
    required this.question,
    required this.backend,
    required this.scope,
    required this.workspaceId,
    required this.onSaved,
    this.initialDraft = '',
    this.onDraftChanged,
    super.key,
  });
  final Map<String, dynamic> question;
  final Backend backend;
  final String scope, workspaceId;
  final Future<void> Function() onSaved;
  final String initialDraft;
  final ValueChanged<String>? onDraftChanged;
  @override
  State<StudyAnswer> createState() => _StudyAnswerState();
}

class _StudyAnswerState extends State<StudyAnswer> {
  final selected = <String>{};
  final blanks = <String, String>{};
  String text = '', message = '';
  String? lastPayload, requestId;
  bool busy = false;
  bool saved = false;
  bool draftConflict = false;
  late final TextEditingController written;
  final blankControllers = <String, TextEditingController>{};
  String get kind =>
      (widget.question['kind'] == 'reading_question'
              ? widget.question['response_kind']
              : widget.question['kind'])
          as String;
  Map<String, dynamic> response() => switch (kind) {
    'single_choice' ||
    'multiple_choice' => {'selected': selected.toList()..sort()},
    'fill_blank' => {'blanks': blanks},
    _ => {'text': text},
  };
  @override
  void initState() {
    super.initState();
    if (widget.initialDraft.isNotEmpty) {
      try {
        final value = jsonDecode(widget.initialDraft) as Map;
        if (value['question_id'] != widget.question['id'] ||
            value['version_id'] != widget.question['confirmed_version_id']) {
          throw const FormatException('草稿属于另一确认版');
        }
        selected.addAll((value['selected'] as List).cast<String>());
        blanks.addAll(Map<String, String>.from(value['blanks'] as Map));
        text = value['text'] as String;
        requestId = value['request_id'] as String?;
        if (requestId != null &&
            !RegExp(r'^[A-Za-z0-9_-]{16,80}$').hasMatch(requestId!)) {
          throw const FormatException('草稿提交编号无效');
        }
        lastPayload = requestId == null ? null : jsonEncode(response());
      } catch (_) {
        draftConflict = true;
        message = '旧版或无法识别的作答草稿已保留。核对后可明确放弃旧草稿，再开始本版作答。';
      }
    }
    written = TextEditingController(text: text);
  }

  void persistDraft() {
    if (draftConflict) return;
    final payload = jsonEncode(response());
    if (lastPayload != null && lastPayload != payload) {
      requestId = null;
      lastPayload = null;
    }
    widget.onDraftChanged?.call(
      selected.isEmpty &&
              blanks.values.every((v) => v.isEmpty) &&
              text.isEmpty &&
              requestId == null
          ? ''
          : jsonEncode({
              'question_id': widget.question['id'],
              'version_id': widget.question['confirmed_version_id'],
              'selected': selected.toList(),
              'blanks': blanks,
              'text': text,
              'request_id': requestId,
            }),
    );
  }

  @override
  void dispose() {
    written.dispose();
    for (final controller in blankControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    final q = widget.question;
    final kind = q['kind'] == 'reading_question'
        ? q['response_kind']
        : q['kind'];
    final response = switch (kind) {
      'single_choice' ||
      'multiple_choice' => {'selected': selected.toList()..sort()},
      'fill_blank' => {'blanks': blanks},
      _ => {'text': text},
    };
    final payload = jsonEncode(response);
    if (lastPayload != payload || requestId == null) {
      requestId =
          'study_${DateTime.now().microsecondsSinceEpoch}_${Random.secure().nextInt(1 << 32)}';
      lastPayload = payload;
    }
    persistDraft();
    setState(() {
      busy = true;
      message = '';
    });
    try {
      final result = await widget.backend.request(
        'POST',
        '${widget.scope}/attempts',
        {
          'question_id': q['id'],
          'question_revision': q['revision'],
          if (q['confirmed_version_id'] != null)
            'question_version_id': q['confirmed_version_id'],
          'request_id': requestId,
          'response': response,
        },
      );
      if (!mounted) return;
      widget.onDraftChanged?.call('');
      setState(() {
        saved = true;
        message = result['status'] == 'pending_review'
            ? '作答已保存，待人工批改'
            : '作答已保存，得分 ${result['score']}';
      });
      try {
        await widget.onSaved();
      } catch (_) {
        if (mounted) setState(() => message += '；统计刷新失败，可稍后刷新');
      }
    } catch (failure) {
      if (mounted) {
        setState(() => message = '未确认保存结果，可核对历史或用同一答案重试（不会重复保存）：$failure');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.question;
    final kind = q['kind'] == 'reading_question'
        ? q['response_kind']
        : q['kind'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (kind == 'single_choice' || kind == 'multiple_choice')
          for (final option in q['options'] as List)
            CheckboxListTile(
              title: ContentBlocks(
                option['content'] as List,
                backend: widget.backend,
                workspaceId: widget.workspaceId,
                versionId: q['confirmed_version_id'] as String?,
              ),
              value: selected.contains(option['id']),
              onChanged: busy || draftConflict
                  ? null
                  : (value) => setState(() {
                      if (kind == 'single_choice') selected.clear();
                      if (value == true) {
                        selected.add(option['id'] as String);
                      } else {
                        selected.remove(option['id']);
                      }
                      persistDraft();
                    }),
            )
        else if (kind == 'fill_blank')
          for (final blank
              in (q['answer']?['blanks'] as List? ??
                  (q['blank_ids'] as List? ?? [])
                      .map((id) => {'id': id})
                      .toList()))
            TextField(
              enabled: !busy && !draftConflict,
              controller: blankControllers.putIfAbsent(
                blank['id'] as String,
                () => TextEditingController(text: blanks[blank['id']] ?? ''),
              ),
              decoration: InputDecoration(labelText: '填空 ${blank['id']}'),
              onChanged: (s) {
                blanks[blank['id'] as String] = s;
                persistDraft();
              },
            )
        else
          TextField(
            enabled: !busy && !draftConflict,
            controller: written,
            minLines: 3,
            maxLines: 8,
            maxLength: 16000,
            decoration: const InputDecoration(labelText: '解题过程 / 主观作答（默认待批改）'),
            onChanged: (s) {
              text = s;
              persistDraft();
            },
          ),
        FilledButton(
          onPressed: busy || saved || draftConflict ? null : submit,
          child: const Text('保存本次作答'),
        ),
        if (saved)
          TextButton(
            onPressed: busy
                ? null
                : () => setState(() {
                    saved = false;
                    requestId = null;
                    lastPayload = null;
                    message = '';
                    persistDraft();
                  }),
            child: const Text('开始新一次作答'),
          ),
        if (message.isNotEmpty) SelectableText(message),
        if (draftConflict) ...[
          SelectableText(widget.initialDraft),
          TextButton(
            onPressed: () => setState(() {
              draftConflict = false;
              selected.clear();
              blanks.clear();
              text = '';
              requestId = null;
              lastPayload = null;
              written.clear();
              for (final controller in blankControllers.values) {
                controller.clear();
              }
              message = '';
              persistDraft();
            }),
            child: const Text('放弃旧版作答草稿'),
          ),
        ],
      ],
    );
  }
}
