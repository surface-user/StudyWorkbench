import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lightweight_liquid_glass/lightweight_liquid_glass.dart';

import 'backend.dart';
import 'internal_links.dart';
import 'editor_tab_bar.dart';
import 'page_host.dart';
import 'import_page.dart';
import 'media_page.dart';
import 'question_page.dart';
import 'resource_explorer.dart';
import 'resource_page.dart';
import 'study_page.dart';
import 'web_page.dart';
import 'workspace_layout.dart';

class WorkspaceShell extends StatefulWidget {
  const WorkspaceShell({
    required this.backend,
    required this.playerHtml,
    this.onSettings,
    this.backendAvailable = true,
    super.key,
  });
  final Backend backend;
  final String playerHtml;
  final VoidCallback? onSettings;
  final bool backendAvailable;
  @override
  State<WorkspaceShell> createState() => WorkspaceShellState();
}

class WorkspaceShellState extends State<WorkspaceShell> {
  List<dynamic> spaces = [];
  List<dynamic> archived = [];
  String? activeSpace;
  final layouts = <String, WorkspaceLayout>{};
  final dirty = <String>{};
  final savedDrafts = <String, String>{};
  final resourceRevisions = <String, int>{};
  final closingTabs = <String>{};
  int historyRevision = 0;
  Timer? saveTimer;
  Future<void> saveQueue = Future.value();
  bool loading = true;
  bool busy = false;
  String? error;
  String? saveError;
  Map<ShortcutActivator, VoidCallback> tabBindings = {};

  @override
  void initState() {
    super.initState();
    FocusManager.instance.addEarlyKeyEventHandler(_earlyShortcut);
    _load();
  }

  KeyEventResult _earlyShortcut(KeyEvent event) {
    if (!mounted || ModalRoute.of(context)?.isCurrent != true) {
      return KeyEventResult.ignored;
    }
    for (final entry in tabBindings.entries) {
      if (entry.key.accepts(event, HardwareKeyboard.instance)) {
        entry.value();
        return KeyEventResult.handled;
      }
    }
    return KeyEventResult.ignored;
  }

  Future<void> _load() async {
    try {
      final state = await widget.backend.request('GET', '/api/workbench');
      final id = state['active_workspace_id'] as String;
      final layout =
          layouts[id] ??
          WorkspaceLayout.fromJson(
            await widget.backend.request('GET', '/api/workspaces/$id/layout'),
          );
      if (!mounted) return;
      setState(() {
        spaces = state['workspaces'] as List;
        archived = state['archived_workspaces'] as List;
        activeSpace = id;
        final activeIds = spaces.map((space) => space['id']).toSet();
        layouts.removeWhere((key, _) => !activeIds.contains(key));
        layouts[id] = layout;
        for (final tab in [...layout.tabs, ...layout.closed]) {
          savedDrafts.putIfAbsent(tab.id, () => tab.draft);
        }
        loading = false;
        error = null;
      });
    } catch (failure) {
      if (mounted) {
        setState(() {
          error = '$failure';
          loading = false;
        });
      }
    }
  }

  void _changed(String id) {
    setState(() {
      dirty.add(id);
      saveError = null;
    });
    saveTimer?.cancel();
    saveTimer = Timer(const Duration(milliseconds: 350), () {
      flush().catchError((Object failure) {
        if (mounted) setState(() => saveError = '$failure');
      });
    });
  }

  /// Serial writes prevent an older draft/layout response from winning a race.
  Future<void> flush() {
    saveTimer?.cancel();
    Future<void> drain() async {
      while (dirty.isNotEmpty) {
        final id = dirty.first;
        final snapshot = jsonEncode(layouts[id]!.toJson());
        await widget.backend.request(
          'PUT',
          '/api/workspaces/$id/layout',
          jsonDecode(snapshot),
        );
        final saved = jsonDecode(snapshot) as Map<String, dynamic>;
        for (final tab in [...saved['tabs'], ...saved['closed_tabs']]) {
          if (tab['kind'] == 'question') {
            savedDrafts[tab['id'] as String] = tab['draft'] as String? ?? '';
          }
        }
        if (jsonEncode(layouts[id]!.toJson()) == snapshot) dirty.remove(id);
      }
      if (mounted) setState(() => saveError = null);
    }

    final result = saveQueue.then((_) => drain(), onError: (_) => drain());
    saveQueue = result;
    return result;
  }

  Future<void> _run(Future<void> Function() operation) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await flush();
      if (!mounted) return;
      await operation();
    } catch (failure) {
      if (mounted) {
        setState(() => saveError = '$failure');
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('操作未完成：$failure')));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _select(String id) => _run(() async {
    final layout =
        layouts[id] ??
        WorkspaceLayout.fromJson(
          await widget.backend.request('GET', '/api/workspaces/$id/layout'),
        );
    await widget.backend.request('PUT', '/api/active-workspace', {
      'workspace_id': id,
    });
    if (mounted) {
      setState(() {
        layouts[id] = layout;
        for (final tab in [...layout.tabs, ...layout.closed]) {
          savedDrafts.putIfAbsent(tab.id, () => tab.draft);
        }
        activeSpace = id;
      });
    }
  });

  Future<String?> _nameDialog(String? initial) => showDialog<String>(
    context: context,
    builder: (_) => _WorkspaceNameDialog(initial: initial),
  );

  Future<void> _create() async {
    final name = await _nameDialog(null);
    if (name == null || !mounted) return;
    await _run(() async {
      await widget.backend.request('POST', '/api/workspaces', {'name': name});
      await _load();
    });
  }

  Future<void> _spaceAction(Map<String, dynamic> space, String action) async {
    final id = space['id'] as String;
    if (action == 'rename') {
      final name = await _nameDialog(space['name'] as String);
      if (name == null || !mounted) return;
      await _run(() async {
        await widget.backend.request('PATCH', '/api/workspaces/$id', {
          'name': name,
        });
        await _load();
      });
    } else {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text('移除“${space['name']}”？'),
          content: const Text('工作空间将从侧栏移除。题目、作答和页面数据会保留，可从“已移除工作空间”恢复。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('确认移除并保留数据'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      await _run(() async {
        await widget.backend.request('DELETE', '/api/workspaces/$id', {
          'confirm_name': space['name'],
        });
        await _load();
      });
    }
  }

  Future<void> _restore() async {
    final id = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('恢复已移除工作空间'),
        children: [
          for (final space in archived)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(context, space['id'] as String),
              child: Text(space['name'] as String),
            ),
        ],
      ),
    );
    if (id == null || !mounted) return;
    await _run(() async {
      await widget.backend.request('POST', '/api/workspaces/$id/restore');
      await _load();
    });
  }

  void _tabAction(void Function(WorkspaceLayout) action) {
    if (busy || activeSpace == null) return;
    try {
      action(layouts[activeSpace]!);
      _changed(activeSpace!);
    } catch (failure) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$failure')));
    }
  }

  void openResource(Map<String, dynamic> node) =>
      _tabAction((layout) => layout.openResource(node));

  void _createdResource(String space, Map<String, dynamic> node) {
    layouts[space]!.openResource(node);
    resourceRevisions[space] = (resourceRevisions[space] ?? 0) + 1;
    _changed(space);
  }

  void _nodeChanged(Map<String, dynamic> node) {
    final layout = layouts[activeSpace];
    if (layout == null) return;
    for (final tab in [...layout.tabs, ...layout.closed]) {
      if (tab.resourceItemId == node['resource_item_id']) {
        tab.resourceName = node['name'] as String;
      }
    }
    _changed(activeSpace!);
  }

  bool _isDirty(WorkbenchTab tab) =>
      tab.draftBaseSha256 != null ||
      tab.questionDraft.isNotEmpty ||
      tab.kind == 'question' && tab.draft != (savedDrafts[tab.id] ?? '');

  Future<void> _closeTabs(List<String> ids) async {
    final space = activeSpace;
    final layout = layouts[space];
    if (space == null || layout == null || busy || closingTabs.isNotEmpty) {
      return;
    }
    closingTabs.addAll(ids);
    try {
      for (final id in ids) {
        final tab = layout.tabs.where((t) => t.id == id).firstOrNull;
        if (tab == null) continue;
        if (_isDirty(tab)) {
          final fileDraft = tab.draftBaseSha256 != null;
          final decision = await showDialog<String>(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(
                fileDraft ? '保存“${tab.title}”的文件？' : '保存“${tab.title}”的草稿？',
              ),
              content: Text(
                fileDraft
                    ? 'Markdown内容尚未写入工作文件。保存失败或冲突时保留标签及草稿；作答草稿单独保留，不会自动提交。'
                    : '作答草稿尚未保存到本地。保存草稿不会提交作答或改变评分。',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('取消关闭'),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(context, 'discard'),
                  child: const Text('放弃更改'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, 'save'),
                  child: Text(fileDraft ? '保存文件并关闭' : '保存草稿并关闭'),
                ),
              ],
            ),
          );
          if (!mounted || decision == null) return;
          if (decision == 'save') {
            try {
              if (fileDraft) {
                await widget.backend.request(
                  'PUT',
                  '/api/workspaces/$space/nodes/${tab.resourceItemId}/document',
                  {'expected_sha256': tab.draftBaseSha256, 'text': tab.draft},
                );
                tab.draft = '';
                tab.draftBaseSha256 = null;
              }
              await flush();
            } catch (failure) {
              if (mounted) setState(() => saveError = '$failure');
              return;
            }
          } else {
            tab.questionDraft = '';
            tab.draft = fileDraft ? '' : savedDrafts[id] ?? '';
            if (fileDraft) tab.draftBaseSha256 = null;
          }
        }
        if (!mounted) return;
        // Capture the original workspace: a pending dialog must never close another space's tab.
        layout.close(id);
        _changed(space);
      }
    } finally {
      closingTabs.clear();
    }
  }

  void _tabMenu(String id, String action) {
    final layout = layouts[activeSpace];
    if (layout == null) return;
    final index = layout.tabs.indexWhere((t) => t.id == id);
    if (action == 'copy') {
      if (index >= 0 && layout.tabs[index].url != null) {
        Clipboard.setData(ClipboardData(text: layout.tabs[index].url!));
      }
      return;
    }
    final ids = switch (action) {
      'close' => [id],
      'others' =>
        layout.tabs.where((t) => t.id != id).map((t) => t.id).toList(),
      'right' =>
        index < 0
            ? <String>[]
            : layout.tabs.skip(index + 1).map((t) => t.id).toList(),
      'all' => layout.tabs.map((t) => t.id).toList(),
      _ => <String>[],
    };
    unawaited(_closeTabs(ids));
  }

  void _activity(
    String space,
    WorkbenchTab tab, {
    required bool loading,
    String? error,
    String? title,
  }) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || layouts[space]?.tabs.contains(tab) != true) return;
      if (tab.loading == loading &&
          tab.error == error &&
          (title == null || title == tab.pageTitle)) {
        return;
      }
      setState(() {
        tab.loading = loading;
        tab.error = error;
        if (title != null && title.trim().isNotEmpty) {
          tab.pageTitle = title.trim().substring(
            0,
            title.trim().length.clamp(0, 512),
          );
        }
      });
    });
    WidgetsBinding.instance.ensureVisualUpdate();
  }

  @override
  void dispose() {
    FocusManager.instance.removeEarlyKeyEventHandler(_earlyShortcut);
    saveTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final layout = layouts[activeSpace];
    tabBindings = {
      for (var i = 0; i < 9; i++)
        SingleActivator(
          [
            LogicalKeyboardKey.digit1,
            LogicalKeyboardKey.digit2,
            LogicalKeyboardKey.digit3,
            LogicalKeyboardKey.digit4,
            LogicalKeyboardKey.digit5,
            LogicalKeyboardKey.digit6,
            LogicalKeyboardKey.digit7,
            LogicalKeyboardKey.digit8,
            LogicalKeyboardKey.digit9,
          ][i],
          control: true,
        ): () => _tabAction((l) {
          if (l.tabs.isNotEmpty && (i == 8 || i < l.tabs.length)) {
            l.activeId = l.tabs[i == 8 ? l.tabs.length - 1 : i].id;
          }
        }),
      const SingleActivator(LogicalKeyboardKey.keyT, control: true): () =>
          _tabAction((l) => l.add('welcome')),
      const SingleActivator(LogicalKeyboardKey.keyW, control: true): () =>
          unawaited(
            _closeTabs([if (layout?.activeId != null) layout!.activeId!]),
          ),
      const SingleActivator(
        LogicalKeyboardKey.keyT,
        control: true,
        shift: true,
      ): () =>
          _tabAction((l) => l.reopen()),
      const SingleActivator(LogicalKeyboardKey.tab, control: true): () =>
          _tabAction((l) => l.cycle(1)),
      const SingleActivator(
        LogicalKeyboardKey.tab,
        control: true,
        shift: true,
      ): () =>
          _tabAction((l) => l.cycle(-1)),
    };
    return CallbackShortcuts(
      bindings: tabBindings,
      child: Focus(
        autofocus: true,
        child: GlassBackdrop(
          child: Row(
            children: [
              GlassSurface(
                width: 244,
                margin: const EdgeInsets.all(12),
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: ListView(
                        children: [
                          const Text(
                            'StudyWorkbench',
                            style: TextStyle(
                              fontSize: 21,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const Text('个人学习与资料工作台'),
                          const Divider(height: 28),
                          const Text('工作空间'),
                          Column(
                            children: [
                              for (final raw in spaces)
                                Builder(
                                  builder: (context) {
                                    final space = raw as Map<String, dynamic>;
                                    return ListTile(
                                      key: ValueKey('workspace-${space['id']}'),
                                      selected: space['id'] == activeSpace,
                                      contentPadding: EdgeInsets.zero,
                                      minLeadingWidth: 24,
                                      horizontalTitleGap: 8,
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      leading: const Icon(
                                        Icons.folder_outlined,
                                      ),
                                      title: Text(
                                        space['name'] as String,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      onTap: busy
                                          ? null
                                          : () =>
                                                _select(space['id'] as String),
                                      trailing: PopupMenuButton<String>(
                                        tooltip: '工作空间操作',
                                        enabled: !busy,
                                        onSelected: (action) =>
                                            _spaceAction(space, action),
                                        itemBuilder: (_) => [
                                          const PopupMenuItem(
                                            value: 'rename',
                                            child: Text('重命名'),
                                          ),
                                          PopupMenuItem(
                                            value: 'remove',
                                            enabled: spaces.length > 1,
                                            child: const Text('移除并保留数据'),
                                          ),
                                        ],
                                      ),
                                    );
                                  },
                                ),
                            ],
                          ),
                          FilledButton.tonalIcon(
                            onPressed: busy || loading ? null : _create,
                            icon: const Icon(Icons.add),
                            label: const Text('新建工作空间'),
                          ),
                          const SizedBox(height: 12),
                          if (activeSpace != null)
                            ResourceExplorer(
                              key: ValueKey('explorer-$activeSpace'),
                              backend: widget.backend,
                              workspaceId: activeSpace!,
                              refreshRevision:
                                  resourceRevisions[activeSpace] ?? 0,
                              onOpen: openResource,
                              onNodeChanged: _nodeChanged,
                              onUtility: (kind) =>
                                  _tabAction((l) => l.openSingleton(kind)),
                            ),
                          const Divider(),
                          const Text('学习'),
                          TextButton.icon(
                            onPressed: busy || layout == null
                                ? null
                                : () => _tabAction(
                                    (l) => l.openSingleton('study'),
                                  ),
                            icon: const Icon(Icons.school_outlined, size: 18),
                            label: const Text('学习计划'),
                          ),
                          TextButton.icon(
                            onPressed: busy || layout == null
                                ? null
                                : () {
                                    _tabAction((l) => l.openSingleton('study'));
                                    setState(() => historyRevision++);
                                  },
                            icon: const Icon(Icons.history, size: 18),
                            label: const Text('学习记录与错题'),
                          ),
                          if (archived.isNotEmpty)
                            TextButton.icon(
                              onPressed: busy ? null : _restore,
                              icon: const Icon(Icons.restore),
                              label: const Text('已移除工作空间'),
                            ),
                        ],
                      ),
                    ),
                    const Divider(),
                    TextButton.icon(
                      onPressed: busy ? null : widget.onSettings,
                      icon: const Icon(Icons.settings_outlined),
                      label: const Text('数据与存储设置'),
                    ),
                    Text(
                      widget.backendAvailable ? '本地后端已连接' : '本地后端已停止',
                      style: const TextStyle(fontSize: 12),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      saveError != null
                          ? '有更改未保存'
                          : dirty.isNotEmpty
                          ? '正在保存页面…'
                          : '页面已保存',
                      style: TextStyle(
                        fontSize: 12,
                        color: saveError != null
                            ? Theme.of(context).colorScheme.error
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Column(
                  children: [
                    if (busy) const LinearProgressIndicator(),
                    if (saveError != null)
                      MaterialBanner(
                        content: Text('保存或操作失败：$saveError'),
                        actions: [
                          TextButton(
                            onPressed: busy ? null : () => _run(() async {}),
                            child: const Text('重试保存'),
                          ),
                        ],
                      ),
                    if (layout != null)
                      EditorTabBar(
                        key: ValueKey('tab-bar-$activeSpace'),
                        layout: layout,
                        enabled: !busy,
                        isDirty: _isDirty,
                        onSelect: (id) => _tabAction((l) => l.activeId = id),
                        onClose: (id) => unawaited(_closeTabs([id])),
                        onNew: (kind) => _tabAction((l) => l.add(kind)),
                        onReopen: () => _tabAction((l) => l.reopen()),
                        onMove: (id, target) =>
                            _tabAction((l) => l.reorder(id, target)),
                        onMenu: _tabMenu,
                      ),
                    Expanded(
                      child: loading
                          ? const Center(child: CircularProgressIndicator())
                          : error != null
                          ? Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text('工作台加载失败：$error'),
                                  TextButton(
                                    onPressed: _load,
                                    child: const Text('重新加载工作台'),
                                  ),
                                ],
                              ),
                            )
                          : Material(
                              color: Theme.of(context).colorScheme.surface,
                              child: PageHost(
                                activeId: activeSpace,
                                pages: {
                                  for (final entry in layouts.entries)
                                    entry.key: _WorkspacePages(
                                      key: ValueKey(entry.key),
                                      workspaceId: entry.key,
                                      layout: entry.value,
                                      backend: widget.backend,
                                      historyRevision: historyRevision,
                                      onResourcesChanged: () => setState(
                                        () => resourceRevisions[entry.key] =
                                            (resourceRevisions[entry.key] ??
                                                0) +
                                            1,
                                      ),
                                      playerHtml: widget.playerHtml,
                                      onChanged: () => _changed(entry.key),
                                      onOpenResource: (node) =>
                                          _createdResource(entry.key, node),
                                      onActivity:
                                          (
                                            tab, {
                                            required loading,
                                            error,
                                            title,
                                          }) => _activity(
                                            entry.key,
                                            tab,
                                            loading: loading,
                                            error: error,
                                            title: title,
                                          ),
                                    ),
                                },
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WorkspacePages extends StatefulWidget {
  const _WorkspacePages({
    required this.workspaceId,
    required this.layout,
    required this.backend,
    required this.playerHtml,
    required this.onChanged,
    required this.onOpenResource,
    required this.onActivity,
    required this.historyRevision,
    required this.onResourcesChanged,
    super.key,
  });
  final String workspaceId;
  final int historyRevision;
  final VoidCallback onResourcesChanged;
  final WorkspaceLayout layout;
  final Backend backend;
  final String playerHtml;
  final VoidCallback onChanged;
  final ValueChanged<Map<String, dynamic>> onOpenResource;
  final void Function(
    WorkbenchTab, {
    required bool loading,
    String? error,
    String? title,
  })
  onActivity;
  @override
  State<_WorkspacePages> createState() => _WorkspacePagesState();
}

class _WorkspacePagesState extends State<_WorkspacePages> {
  final visited = <String>{};
  void _openResource(Map<String, dynamic> node) {
    try {
      widget.onOpenResource(node);
    } catch (failure) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$failure')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = widget.layout.tabs;
    final active = widget.layout.activeId;
    visited.removeWhere((id) => !tabs.any((tab) => tab.id == id));
    if (active != null) visited.add(active);
    return InternalLinkHost(
      backend: widget.backend,
      workspaceId: widget.workspaceId,
      layout: widget.layout,
      onChanged: widget.onChanged,
      child: tabs.isEmpty
          ? const Center(child: Text('此工作空间尚未打开页面。请从左侧添加文件、文件夹或链接。'))
          : PageHost(
              activeId: active,
              pages: {
                for (final tab in tabs)
                  tab.id: !visited.contains(tab.id)
                      ? const SizedBox()
                      : switch (tab.kind) {
                          'welcome' => Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text('欢迎使用 StudyWorkbench'),
                                const Text('从左侧资源管理器添加文件、文件夹、媒体或网页链接。'),
                                FilledButton.tonal(
                                  onPressed: () => showDialog<void>(
                                    context: context,
                                    builder: (_) => AddResourcesDialog(
                                      backend: widget.backend,
                                      workspaceId: widget.workspaceId,
                                      onImported: widget.onResourcesChanged,
                                      onOpen: _openResource,
                                      onProcess: () {
                                        widget.layout.openSingleton('import');
                                        widget.onChanged();
                                      },
                                    ),
                                  ),
                                  child: const Text('添加资源'),
                                ),
                              ],
                            ),
                          ),
                          'resource' => ResourcePage(
                            backend: widget.backend,
                            workspaceId: widget.workspaceId,
                            tab: tab,
                            onOpenNote: _openResource,
                            onChanged: widget.onChanged,
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                          ),
                          'study' => StudyPage(
                            historyRevision: widget.historyRevision,
                            backend: widget.backend,
                            workspaceId: widget.workspaceId,
                            onOpenResource: _openResource,
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                          ),
                          'import' => ImportPage(
                            onResourcesChanged: widget.onResourcesChanged,
                            backend: widget.backend,
                            workspaceId: widget.workspaceId,
                            onOpenResource: _openResource,
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                          ),
                          'question' => QuestionPage(
                            backend: widget.backend,
                            workspaceId: widget.workspaceId,
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                            initialDraft: tab.draft,
                            onDraftChanged: (value) {
                              tab.draft = value;
                              widget.onChanged();
                            },
                          ),
                          'web' => WebPage(
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                            profile:
                                '${widget.backend.dataDir}/workspaces/${widget.workspaceId}/web/${tab.id}',
                            initialUrl: tab.url,
                            onUrlChanged: (value) {
                              if (tab.url != value) {
                                tab.url = value;
                                widget.onChanged();
                              }
                            },
                          ),
                          'player' => MediaPage(
                            onResourcesChanged: widget.onResourcesChanged,
                            backend: widget.backend,
                            workspaceId: widget.workspaceId,
                            onActivity: ({required loading, error, title}) =>
                                widget.onActivity(
                                  tab,
                                  loading: loading,
                                  error: error,
                                  title: title,
                                ),
                            profile:
                                '${widget.backend.dataDir}/workspaces/${widget.workspaceId}/player/${tab.id}',
                          ),
                          _ => const Center(child: Text('此标签类型尚未支持，原始状态保留')),
                        },
              },
            ),
    );
  }
}

class _WorkspaceNameDialog extends StatefulWidget {
  const _WorkspaceNameDialog({this.initial});
  final String? initial;
  @override
  State<_WorkspaceNameDialog> createState() => _WorkspaceNameDialogState();
}

class _WorkspaceNameDialogState extends State<_WorkspaceNameDialog> {
  late final text = TextEditingController(text: widget.initial ?? '');
  void submit() {
    if (text.text.trim().isNotEmpty) {
      Navigator.pop(context, text.text.trim());
    }
  }

  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.initial == null ? '创建工作空间' : '重命名工作空间'),
    content: TextField(
      key: const ValueKey('workspace-name'),
      controller: text,
      autofocus: true,
      maxLength: 80,
      decoration: const InputDecoration(labelText: '工作空间名称'),
      onSubmitted: (_) => submit(),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('取消'),
      ),
      FilledButton(
        onPressed: submit,
        child: Text(widget.initial == null ? '创建' : '保存名称'),
      ),
    ],
  );
}
