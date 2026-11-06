import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend.dart';
import 'learning_search_dialog.dart';
import 'note_editor.dart';
import 'url_policy.dart';
import 'web_page.dart';
import 'workspace_layout.dart';

class LearningLink {
  const LearningLink(this.workspace, this.kind, this.id);
  final String workspace, kind, id;
  static final _id = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$');
  static LearningLink parse(String value) {
    if (value.length > 2048 || value.codeUnits.any((c) => c < 33 || c == 127)) {
      throw const FormatException('内部链接格式无效');
    }
    final match = RegExp(
      r'^studyworkbench://v1/workspaces/([^/?#]+)/(nodes|marks|notes)/([^/?#]+)$',
    ).firstMatch(value);
    if (match == null || match.end != value.length) {
      throw const FormatException('仅支持内部链接v1，无参数或额外路径');
    }
    final String workspace, id;
    try {
      workspace = Uri.decodeComponent(match[1]!);
      id = Uri.decodeComponent(match[3]!);
    } on ArgumentError {
      throw const FormatException('内部链接编码无效');
    }
    if ([
      workspace,
      id,
    ].any((p) => _id.stringMatch(p) != p || p == '.' || p == '..')) {
      throw const FormatException('内部链接标识无效');
    }
    return LearningLink(workspace, match[2]!, id);
  }

  String get uri => 'studyworkbench://v1/workspaces/$workspace/$kind/$id';
}

Future<void> copyLearningLink(BuildContext context, LearningLink link) async {
  await Clipboard.setData(ClipboardData(text: link.uri));
  if (context.mounted) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('内部链接已复制')));
  }
}

typedef FollowLearningLink = Future<void> Function(
  String uri, {
  String? sourceSha256,
});

class InternalLinkScope extends InheritedWidget {
  const InternalLinkScope({
    required this.follow,
    required super.child,
    super.key,
  });
  final FollowLearningLink follow;
  static InternalLinkScope? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<InternalLinkScope>();
  @override
  bool updateShouldNotify(InternalLinkScope oldWidget) =>
      follow != oldWidget.follow;
}

class LinkVisit {
  LinkVisit(this.uri, {this.view});
  final String uri;
  final Map<String, dynamic>? view;
}

/// Only identities and small view state; drafts and bearer/capability URLs never enter history.
class LearningLinkHistory {
  final back = <LinkVisit>[], forward = <LinkVisit>[];
  void add(List<LinkVisit> stack, LinkVisit point) {
    stack.add(point);
    if (stack.length > 50) stack.removeAt(0);
  }
}

class InternalLinkHost extends StatefulWidget {
  const InternalLinkHost({
    required this.backend,
    required this.workspaceId,
    required this.layout,
    required this.onChanged,
    required this.child,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final WorkspaceLayout layout;
  final VoidCallback onChanged;
  final Widget child;
  @override
  State<InternalLinkHost> createState() => _InternalLinkHostState();
}

class _InternalLinkHostState extends State<InternalLinkHost> {
  final history = LearningLinkHistory();
  LinkVisit? currentVisit;
  String? currentTabId;
  bool busy = false;
  String? error;
  LinkVisit? snapshot({String? sha256}) {
    final tab = widget.layout.tabs
        .where((t) => t.id == widget.layout.activeId)
        .firstOrNull;
    if (tab?.resourceItemId == null) return null;
    final useCurrent =
        currentTabId == tab!.id &&
        currentVisit != null &&
        (sha256 == null ||
            LearningLink.parse(currentVisit!.uri).kind != 'notes');
    return LinkVisit(
      useCurrent
          ? currentVisit!.uri
          : LearningLink(widget.workspaceId, 'nodes', tab.resourceItemId!).uri,
      view: tab.captureView?.call(),
    );
  }

  Future<void> open(LinkVisit point) async {
    final link = LearningLink.parse(point.uri);
    if (link.workspace != widget.workspaceId) {
      throw const FormatException('链接属于其他工作空间，请先切换空间');
    }
    final result = Map<String, dynamic>.from(
      await widget.backend.request(
        'POST',
        '/api/workspaces/${widget.workspaceId}/internal-links/resolve',
        {'uri': link.uri},
      ) as Map,
    );
    if (!mounted) return;
    if (result['status'] != 'valid') {
      throw StateError(result['message'] as String? ?? '链接暂不可用');
    }
    if (link.kind == 'notes') {
      await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => NoteEditor(
          note: Map<String, dynamic>.from(result['note'] as Map),
          backend: widget.backend,
          workspaceId: widget.workspaceId,
        ),
      );
      currentVisit = point;
      currentTabId = widget.layout.activeId;
      return;
    }
    final node = Map<String, dynamic>.from(result['resource'] as Map);
    final existing = [
      ...widget.layout.tabs,
      ...widget.layout.closed,
    ].where((t) => t.resourceItemId == node['resource_item_id']).firstOrNull;
    if (result['anchor'] != null) {
      if (existing?.draftBaseSha256 != null ||
          existing?.questionDraft.isNotEmpty == true) {
        throw StateError('目标含未保存草稿，请先保存后定位；当前草稿保留');
      }
      node['learning_anchor'] = Map<String, dynamic>.from(
        result['anchor'] as Map,
      );
    }
    if (point.view != null) {
      if (existing?.draftBaseSha256 != null ||
          existing?.questionDraft.isNotEmpty == true) {
        throw StateError('来源含未保存草稿，请先处理；返回记录仍保留');
      }
      final doc = await widget.backend.request(
        'GET',
        '/api/workspaces/${widget.workspaceId}/nodes/${node['resource_item_id']}/document',
      ) as Map;
      if (!mounted) return;
      if (doc['sha256'] != point.view!['sha256']) {
        throw StateError('返回来源内容已变化，保留记录，请重新打开核对');
      }
    }
    widget.layout.openResource(node);
    if (point.view != null) {
      final tab = widget.layout.tabs.firstWhere(
        (t) => t.id == widget.layout.activeId,
      );
      tab.pendingView = point.view;
    }
    widget.onChanged();
    currentVisit = point;
    currentTabId = widget.layout.activeId;
  }

  Future<void> follow(String uri, {String? sourceSha256}) async {
    if (busy) return;
    if (publicHttpsUrl(uri)) {
      await showDialog<void>(
        context: context,
        builder: (_) => Dialog(
          child: SizedBox(
            width: 1000,
            height: 700,
            child: Column(
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('关闭网页'),
                  ),
                ),
                Expanded(
                  child: WebPage(
                    profile:
                        '${widget.backend.dataDir}/workspaces/${widget.workspaceId}/link-web',
                    initialUrl: uri,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final source = snapshot(sha256: sourceSha256);
      await open(LinkVisit(uri));
      if (!mounted) return;
      if (source != null) history.add(history.back, source);
      history.forward.clear();
    } catch (failure) {
      if (mounted) error = '链接未打开：$failure';
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> travel(bool backwards) async {
    final from = backwards ? history.back : history.forward;
    final to = backwards ? history.forward : history.back;
    if (busy || from.isEmpty) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final source = snapshot();
      await open(from.last);
      if (!mounted) return;
      from.removeLast();
      if (source != null) history.add(to, source);
    } catch (failure) {
      if (mounted) error = '返回未完成，记录仍保留：$failure';
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> prompt() async {
    final value = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => LearningLinkInput(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
      ),
    );
    if (mounted && value != null) await follow(value['uri'] as String);
  }

  @override
  Widget build(BuildContext context) => InternalLinkScope(
    follow: follow,
    child: Column(
      children: [
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            IconButton(
              tooltip: '返回链接来源',
              onPressed: busy || history.back.isEmpty
                  ? null
                  : () => travel(true),
              icon: const Icon(Icons.arrow_back),
            ),
            IconButton(
              tooltip: '前进链接',
              onPressed: busy || history.forward.isEmpty
                  ? null
                  : () => travel(false),
              icon: const Icon(Icons.arrow_forward),
            ),
            TextButton(
              onPressed: busy ? null : prompt,
              child: const Text('打开内部链接'),
            ),
            TextButton(
              onPressed: busy
                  ? null
                  : () async {
                      final uri = await showDialog<String>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => LearningSearchDialog(
                          backend: widget.backend,
                          workspaceId: widget.workspaceId,
                        ),
                      );
                      if (mounted && uri != null) await follow(uri);
                    },
              child: const Text('查找学习记录'),
            ),
            TextButton(
              onPressed: snapshot() == null
                  ? null
                  : () => copyLearningLink(
                      context,
                      LearningLink.parse(snapshot()!.uri),
                    ),
              child: const Text('复制当前链接'),
            ),
            if (busy)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(),
              ),
          ],
        ),
        if (error != null) SelectableText(error!),
        Expanded(child: widget.child),
      ],
    ),
  );
}

class LearningLinkInput extends StatefulWidget {
  const LearningLinkInput({
    required this.backend,
    required this.workspaceId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  @override
  State<LearningLinkInput> createState() => _LearningLinkInputState();
}

class _LearningLinkInputState extends State<LearningLinkInput> {
  final text = TextEditingController();
  bool busy = false;
  String? error;
  Future<void> confirm() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final link = LearningLink.parse(text.text);
      if (link.workspace != widget.workspaceId) {
        throw const FormatException('请先切换到链接所属工作空间');
      }
      final result = await widget.backend.request(
        'POST',
        '/api/workspaces/${widget.workspaceId}/internal-links/resolve',
        {'uri': link.uri},
      ) as Map;
      if (result['status'] != 'valid') {
        throw StateError(result['message'] as String? ?? '链接不可用');
      }
      if (!mounted) return;
      Navigator.pop(context, <String, dynamic>{
        'uri': link.uri,
        'title':
            result['title'] ??
            (result['resource'] as Map?)?['name'] ??
            (result['note'] as Map?)?['title'] ??
            '学习链接',
      });
    } catch (failure) {
      if (mounted) setState(() => error = '链接未确认，输入保留：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('选择内部链接'),
      content: SizedBox(
        width: 600,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              key: const ValueKey('internal-link-input'),
              controller: text,
              enabled: !busy,
              maxLength: 2048,
              decoration: const InputDecoration(
                labelText: '粘贴studyworkbench链接',
              ),
            ),
            if (error != null) SelectableText(error!),
            if (busy) const LinearProgressIndicator(),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: busy ? null : confirm,
          child: const Text('确认链接'),
        ),
      ],
    ),
  );
}
