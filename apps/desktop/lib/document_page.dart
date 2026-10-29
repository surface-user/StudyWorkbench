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

class DocumentPage extends StatefulWidget {
  const DocumentPage({
    required this.backend,
    required this.workspaceId,
    required this.tab,
    required this.onChanged,
    this.onActivity,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final WorkbenchTab tab;
  final VoidCallback onChanged;
  final PageActivityChanged? onActivity;
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
  Map<String, dynamic>? preview;
  Timer? previewTimer;
  int previewGeneration = 0;
  bool requestedPreview = false;
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
  });

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

  void change(String value) {
    widget.tab.draft = value;
    widget.tab.draftBaseSha256 ??= hash;
    widget.onChanged();
  }

  @override
  void dispose() {
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
              OutlinedButton(
                onPressed: busy ? null : load,
                child: const Text('刷新文件'),
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
                      'markdown' =>
                        editing && working
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
                                onTapLink: (label, href, title) =>
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(
                                        content: Text('链接地址：$href（可保存为独立网页资源）'),
                                      ),
                                    ),
                              ),
                      'text' => SingleChildScrollView(
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
