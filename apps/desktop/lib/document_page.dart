import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_math_fork/flutter_math.dart';
import 'package:markdown/markdown.dart' as md;

import 'backend.dart';
import 'page_activity.dart';
import 'page_host.dart';
import 'question_page.dart';
import 'workspace_layout.dart';
import 'question_file_panel.dart';
import 'learning_marks_dialog.dart';
import 'internal_links.dart';
import 'spreadsheet_view.dart';
import 'document_recovery_dialog.dart';
import 'document_merge_dialog.dart';

class DocumentPage extends StatefulWidget {
  const DocumentPage({
    required this.backend,
    required this.workspaceId,
    required this.tab,
    required this.onChanged,
    this.onActivity,
    this.jumpAnchor,
    this.onNavigate,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final WorkbenchTab tab;
  final VoidCallback onChanged;
  final PageActivityChanged? onActivity;
  final Map<String, dynamic>? jumpAnchor;
  final ValueChanged<Map<String, dynamic>>? onNavigate;
  @override
  State<DocumentPage> createState() => _DocumentPageState();
}

class _DocumentPageState extends State<DocumentPage> {
  final text = TextEditingController();
  late final scroll = ScrollController(
    initialScrollOffset: (widget.tab.documentState['scroll'] as num).toDouble(),
  );
  late final transform = TransformationController(
    Matrix4.diagonal3Values(zoom, zoom, 1),
  );
  Map<String, dynamic>? document;
  Uint8List? image;
  String? hash, error;
  bool busy = false;
  bool mergeOpen = false;
  Map<String, dynamic>? preview;
  Timer? previewTimer;
  int previewGeneration = 0;
  bool requestedPreview = false;
  bool rawText = false;
  int sourceLine = 1;
  Map<String, dynamic>? appliedAnchor;
  Map<String, dynamic>? attemptedAnchor;
  Map<String, dynamic>? attemptedView;
  late bool openedQuestion = widget.tab.documentState['mode'] == 'question';
  int questionGeneration = 0;
  String get prefix =>
      '/api/workspaces/${widget.workspaceId}/nodes/${widget.tab.resourceItemId}';
  int get page => widget.tab.documentState['page'] as int;
  double get zoom => (widget.tab.documentState['zoom'] as num).toDouble();
  bool get editing => widget.tab.documentState['mode'] == 'edit';
  bool get working => document?['working_copy'] == true;
  bool get previewPending => ['queued', 'running'].contains(preview?['status']);
  bool get usingPreview =>
      widget.tab.documentState['representation'] == 'paginated' &&
      preview?['status'] == 'ready';
  int get pageCount =>
      (usingPreview ? preview!['page_count'] : document?['page_count'])
          as int? ??
      1;
  @override
  void initState() {
    super.initState();
    widget.tab.captureView = () => {
      'sha256': hash,
      'state': Map<String, dynamic>.from(widget.tab.documentState),
      'raw_text': rawText,
      'source_line': sourceLine,
      'selection_start': text.selection.start,
      'selection_end': text.selection.end,
      if (usingPreview) 'preview_id': preview!['id'],
      if (usingPreview) 'pdf_sha256': preview!['pdf_sha256'],
    };
    scroll.addListener(() {
      if (!mounted || !scroll.hasClients) return;
      widget.tab.documentState['scroll'] = scroll.offset.clamp(0, 10000000);
      widget.onChanged();
    });
    load();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    widget.onActivity?.call(loading: true);
    try {
      await action();
    } catch (failure) {
      if (mounted) setState(() => error = '文件操作未完成，原件与草稿已保留：$failure');
    } finally {
      if (mounted) {
        setState(() => busy = false);
        widget.onActivity?.call(loading: previewPending, error: error);
        if (document != null &&
            widget.jumpAnchor != null &&
            !identical(widget.jumpAnchor, attemptedAnchor)) {
          scheduleMicrotask(() {
            if (mounted) run(applyAnchor);
          });
        } else if (document != null &&
            widget.tab.pendingView != null &&
            !identical(widget.tab.pendingView, attemptedView)) {
          scheduleMicrotask(() {
            if (mounted) run(restoreView);
          });
        }
      }
    }
  }

  Future<void> load() => run(() async {
    previewTimer?.cancel();
    previewGeneration++;
    final result = Map<String, dynamic>.from(
      await widget.backend.request('GET', '$prefix/document') as Map,
    );
    if (!mounted) return;
    hash = result['sha256'] as String;
    if (widget.tab.draftBaseSha256 == null) {
      text.text = result['text'] as String? ?? '';
    } else {
      text.text = widget.tab.draft;
      if (hash != widget.tab.draftBaseSha256) {
        error = '文件已变化，恢复的草稿保留；保存会进行冲突校验。';
      }
    }
    setState(() {
      document = result;
      questionGeneration++;
      preview = result['preview'] == null
          ? null
          : Map<String, dynamic>.from(result['preview'] as Map);
      image = result['image_base64'] == null
          ? null
          : base64Decode(result['image_base64'] as String);
    });
    if (requestedPreview && preview?['status'] == 'ready') {
      widget.tab.documentState['representation'] = 'paginated';
      requestedPreview = false;
      widget.onChanged();
    }
    if (result['type'] == 'pdf' || usingPreview) {
      await loadPage(page.clamp(1, pageCount));
    }
    schedulePreview();
    await applyAnchor();
  });

  @override
  void didUpdateWidget(covariant DocumentPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.jumpAnchor != oldWidget.jumpAnchor && document != null) {
      run(applyAnchor);
    } else if (widget.tab.pendingView != null &&
        !identical(widget.tab.pendingView, attemptedView) &&
        document != null) {
      run(restoreView);
    }
  }

  Future<void> restoreView() async {
    final view = widget.tab.pendingView;
    if (view == null || identical(view, attemptedView)) return;
    attemptedView = view;
    if (widget.tab.draftBaseSha256 != null) {
      throw StateError('返回来源含未保存草稿，原文与位置保留，请先处理草稿');
    }
    final fresh =
        await widget.backend.request('GET', '$prefix/document') as Map;
    if (!mounted) return;
    if (fresh['sha256'] != view['sha256']) throw StateError('返回来源内容已变化，旧视图未应用');
    Map<String, dynamic>? restoredPreview;
    if (view['preview_id'] != null) {
      restoredPreview = Map<String, dynamic>.from(
        await widget.backend.request(
          'GET',
          '$prefix/previews/${view['preview_id']}',
        ) as Map,
      );
      if (!mounted) return;
      if (restoredPreview['pdf_sha256'] != view['pdf_sha256'] ||
          restoredPreview['source_sha256'] != fresh['source_sha256']) {
        throw StateError('返回来源分页版本已变化，旧视图未应用');
      }
    }
    setState(() {
      document = Map<String, dynamic>.from(fresh);
      hash = fresh['sha256'] as String;
      if (fresh['text'] != null) text.text = fresh['text'] as String;
      widget.tab.documentState.addAll(
        Map<String, dynamic>.from(view['state'] as Map),
      );
      rawText = view['raw_text'] == true;
      sourceLine = view['source_line'] as int;
      if (restoredPreview != null) preview = restoredPreview;
      if (text.text.isNotEmpty) {
        final start = (view['selection_start'] as int).clamp(
          0,
          text.text.length,
        );
        final end = (view['selection_end'] as int).clamp(0, text.text.length);
        text.selection = TextSelection(baseOffset: start, extentOffset: end);
      }
    });
    if (fresh['type'] == 'pdf' || usingPreview) await loadPage(page);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) {
        scroll.jumpTo(
          (widget.tab.documentState['scroll'] as num).toDouble().clamp(
            0,
            scroll.position.maxScrollExtent,
          ),
        );
      }
    });
    widget.onChanged();
  }

  Future<void> applyAnchor() async {
    final point = widget.jumpAnchor;
    if (point == null || identical(point, appliedAnchor)) return;
    attemptedAnchor = point;
    if (point['workspace_id'] != widget.workspaceId ||
        point['resource_item_id'] != widget.tab.resourceItemId) {
      throw StateError('书签不属于当前资料');
    }
    if (widget.tab.draftBaseSha256 != null) {
      throw StateError('当前文件有未保存草稿，保存或放弃后再刷新定位');
    }
    final fresh =
        await widget.backend.request('GET', '$prefix/document') as Map;
    if (!mounted) return;
    void acceptFresh() {
      document = Map<String, dynamic>.from(fresh);
      hash = fresh['sha256'] as String;
      if (fresh['text'] != null) text.text = fresh['text'] as String;
    }

    if (point['kind'] == 'office_pdf_page') {
      final oldPreview = await widget.backend.request(
        'GET',
        '$prefix/previews/${point['preview_id']}',
      ) as Map;
      if (oldPreview['pdf_sha256'] != point['content_sha256'] ||
          fresh['source_sha256'] != point['source_sha256']) {
        throw StateError('派生版本已变化，未跳转旧页码');
      }
      setState(() {
        acceptFresh();
        preview = Map<String, dynamic>.from(oldPreview);
        widget.tab.documentState['representation'] = 'paginated';
        widget.tab.documentState['mode'] = 'read';
      });
      await loadPage(point['page'] as int);
    } else {
      if (fresh['sha256'] != point['content_sha256']) {
        throw StateError('内容已变化，旧位置未自动应用');
      }
      if (point['kind'] == 'pdf_page') {
        setState(() {
          acceptFresh();
          widget.tab.documentState['mode'] = 'read';
        });
        await loadPage(point['page'] as int);
      } else if (point['kind'] == 'text_line') {
        final content = fresh['text'] as String;
        final lines = content.split('\n');
        final line = point['line'] as int;
        if (line < 1 || line > lines.length) throw StateError('原文行已失效');
        final position = lines
            .take(line - 1)
            .fold<int>(0, (sum, s) => sum + s.length + 1);
        setState(() {
          acceptFresh();
          text.text = content;
          rawText = true;
          sourceLine = line;
          widget.tab.documentState['mode'] = 'read';
          text.selection = TextSelection(
            baseOffset: position,
            extentOffset:
                position +
                lines[line - 1].replaceFirst(RegExp(r'\r$'), '').length,
          );
        });
      } else {
        setState(() {
          acceptFresh();
          if (fresh['type'] == 'spreadsheet') {
            widget.tab.documentState['page'] = 1;
            widget.tab.documentState['scroll'] = 0.0;
          }
        });
        if (fresh['type'] == 'spreadsheet' && scroll.hasClients) {
          scroll.jumpTo(0);
        }
      }
    }
    appliedAnchor = point;
    widget.onChanged();
  }

  Future<Map<String, dynamic>> captureCurrent() async {
    if (document == null || busy) throw StateError('资料尚未就绪');
    if (widget.tab.draftBaseSha256 != null) {
      throw StateError('请先保存当前草稿，再记录原文位置');
    }
    final type = document!['type'];
    final Map<String, dynamic> position;
    if (document!['position_kind'] == 'resource') {
      position = {'kind': 'resource'};
    } else if (usingPreview) {
      position = {
        'kind': 'office_pdf_page',
        'page': page,
        'preview_id': preview!['id'],
        'expected_sha256': preview!['pdf_sha256'],
      };
    } else if (type == 'pdf') {
      position = {'kind': 'pdf_page', 'page': page, 'expected_sha256': hash};
    } else if (type == 'text' || type == 'markdown') {
      if (!rawText && !(editing && working)) {
        throw StateError('请先打开原文行并选择要记录的位置；阅读预览不推断行号');
      }
      final selection = text.selection.baseOffset;
      final line = selection < 0
          ? sourceLine
          : '\n'
                    .allMatches(
                      text.text.substring(
                        0,
                        selection.clamp(0, text.text.length),
                      ),
                    )
                    .length +
                1;
      position = {'kind': 'text_line', 'line': line, 'expected_sha256': hash};
    } else {
      position = {'kind': 'resource'};
    }
    return Map<String, dynamic>.from(
      await widget.backend.request('POST', '$prefix/learning-anchor', position)
          as Map,
    );
  }

  Future<void> marks({bool sources = false}) async {
    final target = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => LearningMarksDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        resourceItemId: sources ? null : widget.tab.resourceItemId,
        noteResourceItemId: sources ? widget.tab.resourceItemId : null,
        captureCurrent: sources ? null : captureCurrent,
      ),
    );
    if (mounted && target != null) widget.onNavigate?.call(target);
  }

  Future<void> insertLink() async {
    final link = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => LearningLinkInput(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
      ),
    );
    if (!mounted || link == null) return;
    final label = (link['title'] as String? ?? '学习链接')
        .replaceAll('\\', '\\\\')
        .replaceAll('[', r'\[')
        .replaceAll(']', r'\]')
        .replaceAll('\n', ' ')
        .replaceAll('\r', ' ');
    final selection = text.selection;
    final start = selection.isValid ? selection.start : text.text.length;
    final end = selection.isValid ? selection.end : start;
    final insertion = '[$label](${link['uri']})';
    final updated = text.text.replaceRange(start, end, insertion);
    setState(() {
      text.value = TextEditingValue(
        text: updated,
        selection: TextSelection.collapsed(offset: start + insertion.length),
      );
      change(updated);
    });
  }

  Widget sourceText() => Padding(
    padding: const EdgeInsets.all(12),
    child: Column(
      children: [
        if (sourceLine <= text.text.split('\n').length)
          SelectableText(
            '定位行：${text.text.split('\n')[sourceLine - 1].replaceFirst(RegExp(r'\r$'), '').characters.take(1000)}',
          ),
        Expanded(
          child: TextField(
            key: const ValueKey('source-line-view'),
            controller: text,
            readOnly: true,
            expands: true,
            minLines: null,
            maxLines: null,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              labelText: '原文 · 第$sourceLine行（可选择文字定位）',
            ),
            onTap: () {
              final selection = text.selection.baseOffset;
              if (selection >= 0) {
                setState(
                  () => sourceLine =
                      '\n'
                          .allMatches(
                            text.text.substring(
                              0,
                              selection.clamp(0, text.text.length),
                            ),
                          )
                          .length +
                      1,
                );
              }
            },
          ),
        ),
      ],
    ),
  );

  void schedulePreview() {
    previewTimer?.cancel();
    if (previewPending) {
      previewTimer = Timer(const Duration(milliseconds: 800), pollPreview);
    }
  }

  Future<void> pollPreview() async {
    final generation = previewGeneration;
    final id = preview?['id'];
    if (id == null) return;
    try {
      final value =
          await widget.backend.request('GET', '$prefix/previews/$id') as Map;
      if (!mounted || generation != previewGeneration || preview?['id'] != id) {
        return;
      }
      setState(() => preview = Map<String, dynamic>.from(value));
      if (preview?['status'] == 'ready' && requestedPreview && !busy) {
        await run(() async {
          widget.tab.documentState['representation'] = 'paginated';
          requestedPreview = false;
          widget.onChanged();
          await loadPage(page.clamp(1, pageCount));
        });
      }
      if (mounted) {
        widget.onActivity?.call(
          loading: previewPending,
          error: preview?['status'] == 'failed'
              ? (preview?['error'] as String?)
              : error,
        );
      }
    } catch (failure) {
      if (mounted && generation == previewGeneration) {
        setState(() => error = '转换状态读取失败，可刷新文件重试：$failure');
      }
    }
    if (mounted && generation == previewGeneration) schedulePreview();
  }

  Future<void> startPreview() => run(() async {
    previewTimer?.cancel();
    previewGeneration++;
    final value = await widget.backend.request('POST', '$prefix/previews', {
      'expected_source_sha256': document!['source_sha256'],
    }) as Map;
    if (!mounted) return;
    setState(() => preview = Map<String, dynamic>.from(value));
    requestedPreview = true;
    if (preview?['status'] == 'ready') {
      widget.tab.documentState['representation'] = 'paginated';
      requestedPreview = false;
      widget.onChanged();
      await loadPage(page.clamp(1, pageCount));
    }
    schedulePreview();
  });

  Future<void> openPreview() => run(() async {
    widget.tab.documentState['representation'] = 'paginated';
    widget.onChanged();
    await loadPage(page.clamp(1, pageCount));
  });

  Future<void> cancelPreview() => run(() async {
    final value = await widget.backend.request(
      'POST',
      '$prefix/previews/${preview!['id']}/cancel',
    ) as Map;
    if (!mounted) return;
    setState(() => preview = Map<String, dynamic>.from(value));
    requestedPreview = false;
    schedulePreview();
  });

  Future<void> loadPage(int target) async {
    final result = await widget.backend.request(
      'GET',
      usingPreview
          ? '$prefix/previews/${preview!['id']}/page?page=$target'
          : '$prefix/document-page?page=$target',
    ) as Map;
    if (!mounted) return;
    setState(() {
      image = base64Decode(result['image_base64'] as String);
      widget.tab.documentState['page'] = target;
    });
    widget.onChanged();
  }

  Future<void> edit() => run(() async {
    if (!working) {
      await widget.backend.request('POST', '$prefix/working-copy', {
        'expected_sha256': hash,
      });
      if (!mounted) return;
      document!['working_copy'] = true;
    }
    setState(() => widget.tab.documentState['mode'] = 'edit');
    widget.onChanged();
  });

  Future<void> save() => run(() async {
    final snapshot = text.text;
    final saved = await widget.backend.request('PUT', '$prefix/document', {
      'expected_sha256': widget.tab.draftBaseSha256 ?? hash,
      'text': snapshot,
    }) as Map;
    if (!mounted) return;
    hash = saved['sha256'] as String;
    if (text.text == snapshot) {
      widget.tab.draft = '';
      widget.tab.draftBaseSha256 = null;
    } else {
      widget.tab.draftBaseSha256 = hash;
    }
    document!['external_change'] = false;
    questionGeneration++;
    widget.onChanged();
  });

  Future<void> recovery() async {
    if (busy) return;
    if (widget.tab.draftBaseSha256 != null) {
      setState(() => error = '当前有未保存草稿，请先保存或另行保留后再载入恢复点');
      return;
    }
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => DocumentRecoveryDialog(
        backend: widget.backend,
        prefix: prefix,
        workspacePrefix: widget.onNavigate == null
            ? null
            : '/api/workspaces/${widget.workspaceId}',
      ),
    );
    if (!mounted || result == null) return;
    if (result['copy_node'] != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('恢复副本“${result['copy_node']['name']}”已保存，可从资源目录打开新笔记。'),
        ),
      );
      try {
        widget.onNavigate?.call(
          Map<String, dynamic>.from(result['copy_node'] as Map),
        );
      } catch (failure) {
        setState(() => error = '副本笔记已保存，打开失败：$failure。请从资源目录打开新笔记。');
      }
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('将恢复点放入编辑草稿？'),
        content: const Text('当前文件暂不改变。请核对草稿内容，再点击“保存工作文件”；保存时仍会检查外部修改。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认载入草稿'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true || widget.tab.draftBaseSha256 != null) {
      return;
    }
    setState(() {
      text.text = result['text'] as String;
      widget.tab.draft = text.text;
      widget.tab.draftBaseSha256 = result['current_sha256'] as String;
      widget.tab.documentState['mode'] = 'edit';
      rawText = false;
    });
    widget.onChanged();
  }

  Future<void> merge() async {
    if (busy || mergeOpen || !working || widget.tab.draftBaseSha256 == null) {
      return;
    }
    final owner = widget.tab;
    final sourceBackend = widget.backend;
    final sourcePrefix = prefix;
    final base = owner.draftBaseSha256!;
    final local = text.text;
    setState(() => mergeOpen = true);
    try {
      final result = await showDialog<Map<String, dynamic>>(
        context: context,
        barrierDismissible: false,
        builder: (_) => DocumentMergeDialog(
          backend: sourceBackend,
          prefix: sourcePrefix,
          baseHash: base,
          localText: local,
        ),
      );
      if (!mounted || result == null) return;
      if (widget.tab != owner ||
          widget.backend != sourceBackend ||
          prefix != sourcePrefix ||
          text.text != local ||
          owner.draft != local ||
          owner.draftBaseSha256 != base) {
        setState(() => error = '草稿或资源已变化，合并候选未载入；当前草稿保留。');
        return;
      }
      setState(() {
        text.text = result['text'] as String;
        owner.draft = text.text;
        owner.draftBaseSha256 = result['current_sha256'] as String;
        hash = owner.draftBaseSha256;
        document!['sha256'] = hash;
        owner.documentState['mode'] = 'edit';
        rawText = false;
        error = null;
      });
      widget.onChanged();
    } finally {
      if (mounted) setState(() => mergeOpen = false);
    }
  }

  void change(String value) {
    widget.tab.draft = value;
    widget.tab.draftBaseSha256 ??= hash;
    widget.onChanged();
  }

  @override
  void dispose() {
    widget.tab.captureView = null;
    previewGeneration++;
    previewTimer?.cancel();
    text.dispose();
    scroll.dispose();
    transform.dispose();
    super.dispose();
  }

  Widget picture() => image == null
      ? const Center(child: Text('页图尚未加载，可刷新重试'))
      : InteractiveViewer(
          transformationController: transform,
          minScale: .25,
          maxScale: 4,
          onInteractionEnd: (_) {
            widget.tab.documentState['zoom'] = transform.value
                .getMaxScaleOnAxis()
                .clamp(.25, 4);
            widget.onChanged();
          },
          child: Center(
            child: Image.memory(
              image!,
              gaplessPlayback: true,
              fit: BoxFit.contain,
              semanticLabel: widget.tab.resourceName,
              errorBuilder: (_, error, stack) => const Text('图片无法解码，原件已保留'),
            ),
          ),
        );

  @override
  Widget build(BuildContext context) {
    final value = document;
    final scales = {.25, .5, 1.0, 1.5, 2.0, 3.0, 4.0, zoom}.toList()..sort();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(widget.tab.resourceName ?? '学习资源'),
              TextButton(
                onPressed: busy || document == null ? null : marks,
                child: const Text('书签与备注'),
              ),
              if (value?['type'] == 'markdown')
                TextButton(
                  onPressed: busy ? null : () => marks(sources: true),
                  child: const Text('笔记关联的来源'),
                ),
              if (value?['type'] == 'markdown' || value?['type'] == 'text')
                TextButton(
                  onPressed: busy
                      ? null
                      : () => setState(() => rawText = !rawText),
                  child: Text(rawText ? '返回阅读' : '查看原文行'),
                ),
              OutlinedButton(
                onPressed: busy ? null : load,
                child: const Text('刷新文件'),
              ),
              if (working || (value == null && error != null))
                TextButton(
                  onPressed: busy ? null : recovery,
                  child: const Text('保存恢复点'),
                ),
              if (widget.tab.documentState['mode'] == 'question')
                TextButton(
                  onPressed: () {
                    setState(() => widget.tab.documentState['mode'] = 'read');
                    widget.onChanged();
                  },
                  child: const Text('返回文件阅读'),
                ),
              if (value?['type'] == 'markdown') ...[
                TextButton(
                  onPressed: busy || !editing || !working || rawText
                      ? null
                      : insertLink,
                  child: const Text('插入内部链接'),
                ),
                TextButton(
                  onPressed: busy || widget.tab.draftBaseSha256 != null
                      ? null
                      : () {
                          setState(() {
                            openedQuestion = true;
                            widget.tab.documentState['mode'] = 'question';
                          });
                          widget.onChanged();
                        },
                  child: const Text('检查题目 / 作答'),
                ),
                if (widget.tab.draftBaseSha256 != null)
                  const Text('先保存工作文件，再检查题目版本'),
                OutlinedButton(
                  onPressed: busy ? null : edit,
                  child: Text(working ? '原文编辑' : '创建工作副本并编辑'),
                ),
                TextButton(
                  onPressed: busy
                      ? null
                      : () {
                          setState(
                            () => widget.tab.documentState['mode'] = 'read',
                          );
                          widget.onChanged();
                        },
                  child: const Text('阅读预览'),
                ),
                FilledButton(
                  onPressed:
                      busy || !working || widget.tab.draftBaseSha256 == null
                      ? null
                      : save,
                  child: const Text('保存工作文件'),
                ),
                TextButton(
                  onPressed:
                      busy ||
                          mergeOpen ||
                          !working ||
                          widget.tab.draftBaseSha256 == null
                      ? null
                      : merge,
                  child: const Text('合并修改'),
                ),
                Text(
                  widget.tab.draftBaseSha256 != null
                      ? '文件未保存'
                      : working
                      ? '工作副本 · 原件保留'
                      : '原件只读',
                ),
              ],
              if (['word', 'office'].contains(value?['type'])) ...[
                OutlinedButton(
                  onPressed:
                      busy ||
                          previewPending ||
                          value?['preview_capability']?['available'] != true
                      ? null
                      : startPreview,
                  child: Text(
                    [
                          'failed',
                          'cancelled',
                          'interrupted',
                        ].contains(preview?['status'])
                        ? '重试生成分页预览'
                        : '生成分页预览',
                  ),
                ),
                if (preview?['status'] == 'ready')
                  TextButton(
                    onPressed: busy ? null : openPreview,
                    child: const Text('打开分页预览'),
                  ),
                if (value?['type'] == 'word' && usingPreview)
                  TextButton(
                    onPressed: busy
                        ? null
                        : () {
                            setState(
                              () => widget.tab.documentState['representation'] =
                                  'original',
                            );
                            requestedPreview = false;
                            widget.onChanged();
                          },
                    child: const Text('Word结构预览'),
                  ),
                if (previewPending)
                  TextButton(
                    onPressed: busy || preview?['cancel_requested'] == true
                        ? null
                        : cancelPreview,
                    child: Text(
                      preview?['cancel_requested'] == true ? '已请求取消' : '取消转换',
                    ),
                  ),
              ],
              if (value?['type'] == 'pdf' || usingPreview) ...[
                IconButton(
                  tooltip: '上一页',
                  onPressed: busy || page <= 1
                      ? null
                      : () => run(() => loadPage(page - 1)),
                  icon: const Icon(Icons.chevron_left),
                ),
                Text('第$page页 / $pageCount页'),
                IconButton(
                  tooltip: '下一页',
                  onPressed: busy || page >= pageCount
                      ? null
                      : () => run(() => loadPage(page + 1)),
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
              if (usingPreview || ['pdf', 'image'].contains(value?['type']))
                DropdownButton<double>(
                  value: zoom,
                  items: scales
                      .map(
                        (scale) => DropdownMenuItem(
                          value: scale,
                          child: Text('${(scale * 100).round()}%'),
                        ),
                      )
                      .toList(),
                  onChanged: (scale) {
                    if (scale != null) {
                      setState(() {
                        widget.tab.documentState['zoom'] = scale;
                        transform.value = Matrix4.diagonal3Values(
                          scale,
                          scale,
                          1,
                        );
                      });
                      widget.onChanged();
                    }
                  },
                ),
            ],
          ),
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null)
          Padding(
            padding: const EdgeInsets.all(8),
            child: SelectableText(error!),
          ),
        if (['word', 'office'].contains(value?['type'])) ...[
          if (value?['preview_capability']?['available'] != true)
            Text(
              value?['preview_capability']?['reason'] as String? ??
                  '离线转换组件不可用，原件保留',
            ),
          if (preview != null)
            Text(
              '分页转换：${previewStatus(preview!['status'])}${preview!['error'] == null ? '' : ' · ${preview!['error']}'}',
            ),
          if (previewPending) const Text('关闭标签后转换会在后台继续，可在此取消。'),
          if (usingPreview)
            Text(
              '静态派生PDF · LibreOffice ${preview!['converter_version']} · 原件保留，不保留动画/嵌入视频',
            ),
        ],
        if (value?['external_change'] == true)
          const Text('检测到外部修改；当前显示磁盘内容，旧索引不会自动成为确认答案。'),
        if (value?['type'] == 'text' && value?['position_kind'] == 'resource')
          const Text('UTF-8只读原文 · 资料级书签'),
        if (value != null)
          SelectableText(
            'SHA256：${value['sha256']}',
            style: const TextStyle(fontSize: 11),
          ),
        Expanded(
          child: PageHost(
            activeId:
                widget.tab.documentState['mode'] == 'question' && openedQuestion
                ? 'question'
                : 'document',
            pages: {
              'document': value == null
                  ? const Center(child: Text('文件尚未加载，可刷新重试。'))
                  : usingPreview
                  ? picture()
                  : switch (value['type']) {
                      'pdf' || 'image' => picture(),
                      'spreadsheet' => SpreadsheetView(
                        workbook: value,
                        sheetIndex: page - 1,
                        scrollController: scroll,
                        onSheetChanged: (index) {
                          if (scroll.hasClients) scroll.jumpTo(0);
                          setState(() {
                            widget.tab.documentState['page'] = index + 1;
                            widget.tab.documentState['scroll'] = 0.0;
                          });
                          widget.onChanged();
                        },
                      ),
                      'markdown' =>
                        rawText
                            ? sourceText()
                            : editing && working
                            ? Padding(
                                padding: const EdgeInsets.all(12),
                                child: TextField(
                                  key: const ValueKey('markdown-editor'),
                                  controller: text,
                                  scrollController: scroll,
                                  expands: true,
                                  minLines: null,
                                  maxLines: null,
                                  onChanged: change,
                                  decoration: const InputDecoration(
                                    border: OutlineInputBorder(),
                                    labelText: 'Markdown原文（工作副本）',
                                  ),
                                ),
                              )
                            : text.text.length > 200000
                            ? const Center(
                                child: Text(
                                  'Markdown预览最多200000字符，可切换原文编辑；文件保留。',
                                ),
                              )
                            : Markdown(
                                controller: scroll,
                                data: text.text,
                                selectable: true,
                                inlineSyntaxes: [_MathSyntax()],
                                builders: {'math': _MathBuilder()},
                                imageBuilder: (uri, title, alt) =>
                                    RelativeDocumentImage(
                                      backend: widget.backend,
                                      prefix: prefix,
                                      uri: uri,
                                      alt: alt ?? '相对图片',
                                    ),
                                onTapLink: (label, href, title) {
                                  if (href == null) return;
                                  final scope = InternalLinkScope.maybeOf(
                                    context,
                                  );
                                  if (scope != null) {
                                    scope.follow(href, sourceSha256: hash);
                                  } else {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text('链接导航入口不可用，原文链接保留'),
                                      ),
                                    );
                                  }
                                },
                              ),
                      'text' =>
                        rawText
                            ? sourceText()
                            : SingleChildScrollView(
                                controller: scroll,
                                padding: const EdgeInsets.all(16),
                                child: SelectableText(text.text),
                              ),
                      'word' => SingleChildScrollView(
                        controller: scroll,
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Word结构预览 · 不代表实际分页，原件保持不变'),
                            for (final warning in value['warnings'] as List)
                              Text(warning as String),
                            ContentBlocks(
                              value['blocks'] as List,
                              inlineImages: {
                                for (final asset in value['assets'] as List)
                                  asset['id'] as String: base64Decode(
                                    asset['data'] as String,
                                  ),
                              },
                            ),
                          ],
                        ),
                      ),
                      _ => Center(
                        child: SelectableText(
                          value['message'] as String? ?? '此格式查看器尚未接入，原件保留。',
                        ),
                      ),
                    },
              if (openedQuestion)
                'question': QuestionFilePanel(
                  backend: widget.backend,
                  workspaceId: widget.workspaceId,
                  tab: widget.tab,
                  onChanged: widget.onChanged,
                  generation: questionGeneration,
                ),
            },
          ),
        ),
      ],
    );
  }
}

String previewStatus(dynamic status) => switch (status) {
  'queued' => '排队中',
  'running' => '转换中',
  'ready' => '已就绪',
  'failed' => '失败',
  'cancelled' => '已取消',
  'interrupted' => '上次中断，请显式重试',
  _ => '$status',
};

class RelativeDocumentImage extends StatefulWidget {
  const RelativeDocumentImage({
    required this.backend,
    required this.prefix,
    required this.uri,
    required this.alt,
    super.key,
  });
  final Backend backend;
  final String prefix, alt;
  final Uri uri;
  @override
  State<RelativeDocumentImage> createState() => _RelativeDocumentImageState();
}

class _RelativeDocumentImageState extends State<RelativeDocumentImage> {
  Future<dynamic>? pending;
  bool get allowed =>
      !widget.uri.hasScheme &&
      !widget.uri.hasAuthority &&
      !widget.uri.path.startsWith('/') &&
      !widget.uri.hasQuery &&
      !widget.uri.hasFragment;
  @override
  void initState() {
    super.initState();
    fetch();
  }

  void fetch() {
    pending = allowed
        ? widget.backend.request(
            'GET',
            '${widget.prefix}/relative-image?path=${Uri.encodeQueryComponent(widget.uri.toString())}',
          )
        : null;
  }

  @override
  void didUpdateWidget(covariant RelativeDocumentImage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.uri != widget.uri ||
        oldWidget.prefix != widget.prefix ||
        oldWidget.backend != widget.backend) {
      fetch();
    }
  }

  @override
  Widget build(BuildContext context) => !allowed
      ? Text('已阻止外部或绝对图片：${widget.alt}')
      : FutureBuilder(
          future: pending,
          builder: (_, snapshot) {
            if (snapshot.hasError) {
              return Wrap(
                children: [
                  Text('相对图片无法读取：${widget.alt}'),
                  TextButton(
                    onPressed: () => setState(fetch),
                    child: const Text('重试图片'),
                  ),
                ],
              );
            }
            if (!snapshot.hasData) return Text('加载图片：${widget.alt}');
            return Image.memory(
              base64Decode(snapshot.data['image_base64'] as String),
              semanticLabel: widget.alt,
              errorBuilder: (_, error, stack) => Text('图片无法解码：${widget.alt}'),
            );
          },
        );
}

class _MathSyntax extends md.InlineSyntax {
  _MathSyntax()
    : super(r'\$\$([\s\S]+?)\$\$|\$([^\n$]+?)\$', startCharacter: 36);
  @override
  bool onMatch(md.InlineParser parser, Match match) {
    parser.addNode(md.Element.text('math', match[1] ?? match[2]!));
    return true;
  }
}

class _MathBuilder extends MarkdownElementBuilder {
  @override
  Widget? visitElementAfterWithContext(
    BuildContext context,
    md.Element element,
    TextStyle? preferredStyle,
    TextStyle? parentStyle,
  ) {
    if (element.textContent.length > 8000) return const Text('公式超过预览预算，原文保留');
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Math.tex(
        element.textContent,
        textStyle: preferredStyle,
        onErrorFallback: (_) => Text(element.textContent),
      ),
    );
  }
}
