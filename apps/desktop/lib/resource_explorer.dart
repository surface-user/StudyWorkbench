import 'dart:async';

import 'package:flutter/material.dart';

import 'backend.dart';
import 'add_resources_dialog.dart';
import 'markdown_note_dialog.dart';
import 'learning_marks_dialog.dart';
import 'media_download_dialog.dart';
export 'add_resources_dialog.dart';

class ResourceExplorer extends StatefulWidget {
  const ResourceExplorer({
    required this.backend,
    required this.workspaceId,
    this.onOpen,
    this.onNodeChanged,
    this.refreshRevision = 0,
    this.onUtility,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final ValueChanged<Map<String, dynamic>>? onOpen, onNodeChanged;
  final int refreshRevision;
  final ValueChanged<String>? onUtility;
  @override
  State<ResourceExplorer> createState() => _ResourceExplorerState();
}

class _ResourceExplorerState extends State<ResourceExplorer> {
  final children = <String?, List<dynamic>>{};
  final expanded = <String?>{null};
  final more = <String?>{};
  final loading = <String?>{};
  int generation = 0;
  String? error;
  String search = '';
  Timer? searchTimer;
  String get prefix => '/api/workspaces/${widget.workspaceId}';

  @override
  void initState() {
    super.initState();
    load(null);
  }

  @override
  void dispose() {
    searchTimer?.cancel();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant ResourceExplorer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshRevision != widget.refreshRevision) {
      generation++;
      loading.clear();
      load(null, reset: true);
    }
  }

  Future<void> load(String? parent, {bool reset = false}) async {
    if (loading.contains(parent)) return;
    final requestedGeneration = generation;
    setState(() {
      loading.add(parent);
      error = null;
    });
    try {
      final offset = reset ? 0 : children[parent]?.length ?? 0;
      final rows = await widget.backend.request(
        'GET',
        '$prefix/nodes?offset=$offset&limit=100${parent == null ? '' : '&parent_id=$parent'}${search.isEmpty ? '' : '&search=${Uri.encodeQueryComponent(search)}'}',
      ) as List;
      if (!mounted || requestedGeneration != generation) return;
      setState(() {
        children[parent] = [...(reset ? [] : children[parent] ?? []), ...rows];
        rows.length == 100 ? more.add(parent) : more.remove(parent);
      });
    } catch (failure) {
      if (mounted && requestedGeneration == generation) {
        setState(() => error = '资源树读取失败：$failure');
      }
    } finally {
      if (mounted && requestedGeneration == generation) {
        setState(() => loading.remove(parent));
      }
    }
  }

  Future<void> reload() {
    generation++;
    children.clear();
    loading.clear();
    more.clear();
    expanded
      ..clear()
      ..add(null);
    return load(null, reset: true);
  }

  Future<void> add(String? parent) async {
    await showDialog<void>(
      context: context,
      builder: (_) => AddResourcesDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        parentId: parent,
        onImported: reload,
        onOpen: widget.onOpen,
        onProcess: widget.onUtility == null
            ? null
            : () => widget.onUtility!('import'),
      ),
    );
    if (mounted) {
      await reload();
    }
  }

  Future<void> newNote(String? parent) async {
    final node = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => MarkdownNoteDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        parentId: parent,
      ),
    );
    if (!mounted) return;
    await reload();
    if (mounted && node != null) widget.onOpen?.call(node);
  }

  Future<void> details(Map<String, dynamic> node) async {
    try {
      node = Map<String, dynamic>.from(
        await widget.backend.request(
          'GET',
          '$prefix/nodes/${node['resource_item_id']}',
        ) as Map,
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('资源详情读取失败：$error')));
      }
      return;
    }
    if (!mounted) return;
    var editedName = node['name'] as String;
    var parent = node['parent_id'] as String?;
    var targetLabel = parent == null ? '工作空间根目录' : '当前文件夹';
    var saving = false;
    String? failure;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: const Text('资源详情与组织'),
            content: SizedBox(
              width: 480,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SelectableText(
                      '资源编号：${node['resource_item_id']}\n状态：${resourceStatus(node['status'])}\n${node['url'] ?? node['sha256'] ?? '逻辑文件夹'}',
                    ),
                    if (node['size'] != null) Text('大小：${node['size']} 字节'),
                    const Text('改名或移动保留资源身份、原件和学习记录。'),
                    TextFormField(
                      initialValue: editedName,
                      onChanged: (value) => editedName = value,
                      decoration: const InputDecoration(labelText: '名称'),
                    ),
                    TextButton(
                      onPressed: saving
                          ? null
                          : () async {
                              final selection =
                                  await showDialog<Map<String, dynamic>>(
                                    context: context,
                                    builder: (_) => _FolderPicker(
                                      backend: widget.backend,
                                      prefix: prefix,
                                      excluded:
                                          node['resource_item_id'] as String,
                                    ),
                                  );
                              if (selection != null && dialogContext.mounted) {
                                update(() {
                                  parent = selection['id'] as String?;
                                  targetLabel = selection['name'] as String;
                                });
                              }
                            },
                      child: Text('移动到：$targetLabel'),
                    ),
                    if (failure != null) SelectableText(failure!),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('关闭'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        update(() {
                          saving = true;
                          failure = null;
                        });
                        try {
                          final saved = await widget.backend.request(
                            'PATCH',
                            '$prefix/nodes/${node['resource_item_id']}',
                            {'name': editedName, 'parent_id': parent},
                          );
                          if (mounted) {
                            widget.onNodeChanged?.call(
                              Map<String, dynamic>.from(saved as Map),
                            );
                          }
                          if (dialogContext.mounted) {
                            Navigator.pop(dialogContext);
                          }
                        } catch (error) {
                          update(() => failure = '未保存：$error');
                        } finally {
                          if (dialogContext.mounted) {
                            update(() => saving = false);
                          }
                        }
                      },
                child: Text(saving ? '保存中…' : '保存名称与位置'),
              ),
            ],
          ),
        ),
      ),
    );
    if (mounted) {
      await reload();
    }
  }

  Future<void> remove(Map<String, dynamic> node) async {
    var saving = false;
    String? failure;
    final removed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) => PopScope(
          canPop: !saving,
          child: AlertDialog(
            title: Text('删除“${node['name']}”？'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  node['kind'] == 'folder'
                      ? '将从工作区资源树删除此文件夹及其中全部资料。'
                      : '将从工作区资源树删除此资料。',
                ),
                const Text('原文件、编辑副本和学习记录保留；已打开的标签及草稿保留。此操作不释放磁盘空间。'),
                if (failure != null) Text(failure!),
              ],
            ),
            actions: [
              TextButton(
                onPressed: saving
                    ? null
                    : () => Navigator.pop(dialogContext, false),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        update(() {
                          saving = true;
                          failure = null;
                        });
                        try {
                          await widget.backend.request(
                            'DELETE',
                            '$prefix/nodes/${node['resource_item_id']}',
                          );
                          if (dialogContext.mounted) {
                            Navigator.pop(dialogContext, true);
                          }
                        } catch (error) {
                          if (dialogContext.mounted) {
                            update(() => failure = '未删除：$error');
                          }
                        } finally {
                          if (dialogContext.mounted) {
                            update(() => saving = false);
                          }
                        }
                      },
                child: Text(saving ? '删除中…' : '确认删除'),
              ),
            ],
          ),
        ),
      ),
    );
    if (removed == true && mounted) await reload();
  }

  List<Widget> rows(String? parent, int depth) => [
    for (final raw in children[parent] ?? []) ...[
      ListTile(
        key: ValueKey('node-${raw['resource_item_id']}'),
        dense: true,
        contentPadding: EdgeInsets.only(
          left: (depth.clamp(0, 4) * 10).toDouble(),
        ),
        minLeadingWidth: 18,
        horizontalTitleGap: 4,
        leading: Icon(
          raw['kind'] == 'folder'
              ? (expanded.contains(raw['resource_item_id'])
                    ? Icons.folder_open
                    : Icons.folder_outlined)
              : raw['kind'] == 'link'
              ? Icons.link
              : raw['kind'] == 'media'
              ? Icons.play_circle_outline
              : Icons.insert_drive_file_outlined,
          size: 18,
        ),
        title: Text(
          raw['name'] as String,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: raw['status'] == 'ready'
            ? null
            : Text(resourceStatus(raw['status'])),
        trailing: PopupMenuButton<String>(
          tooltip: '资源操作',
          onSelected: (action) => switch (action) {
            'add' => add(raw['resource_item_id'] as String),
            'note' => newNote(raw['resource_item_id'] as String),
            'delete' => remove(Map<String, dynamic>.from(raw)),
            _ => details(Map<String, dynamic>.from(raw)),
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'details', child: Text('详情 / 改名 / 移动')),
            if (raw['kind'] == 'folder')
              const PopupMenuItem(value: 'add', child: Text('添加到此文件夹')),
            if (raw['kind'] == 'folder')
              const PopupMenuItem(value: 'note', child: Text('在此新建笔记')),
            const PopupMenuItem(value: 'delete', child: Text('删除')),
          ],
        ),
        onTap: () {
          final id = raw['resource_item_id'] as String;
          if (raw['kind'] != 'folder') {
            if (widget.onOpen != null) {
              widget.onOpen!(Map<String, dynamic>.from(raw));
            } else {
              details(Map<String, dynamic>.from(raw));
            }
            return;
          }
          setState(
            () =>
                expanded.contains(id) ? expanded.remove(id) : expanded.add(id),
          );
          if (expanded.contains(id) && !children.containsKey(id)) load(id);
        },
      ),
      if (raw['kind'] == 'folder' && expanded.contains(raw['resource_item_id']))
        ...rows(raw['resource_item_id'] as String, depth + 1),
    ],
    if (loading.contains(parent)) const LinearProgressIndicator(),
    if (more.contains(parent))
      TextButton(
        onPressed: loading.contains(parent) ? null : () => load(parent),
        child: const Text('加载更多资源'),
      ),
  ];

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Row(
        children: [
          const Expanded(
            child: Text(
              '资源管理器',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
          if (widget.onUtility != null)
            PopupMenuButton<String>(
              tooltip: '资源视图与处理',
              onSelected: widget.onUtility,
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'import', child: Text('资料处理与导出')),
                PopupMenuItem(value: 'player', child: Text('媒体视图')),
              ],
            ),
          IconButton(
            tooltip: '刷新资源树',
            onPressed: reload,
            icon: const Icon(Icons.refresh, size: 18),
          ),
          IconButton(
            tooltip: '书签与备注',
            icon: const Icon(Icons.bookmarks_outlined, size: 18),
            onPressed: () async {
              final node = await showDialog<Map<String, dynamic>>(
                context: context,
                barrierDismissible: false,
                builder: (_) => LearningMarksDialog(
                  backend: widget.backend,
                  workspaceId: widget.workspaceId,
                ),
              );
              if (mounted && node != null) widget.onOpen?.call(node);
            },
          ),
        ],
      ),
      FilledButton.tonalIcon(
        onPressed: () => add(null),
        icon: const Icon(Icons.add),
        label: const Text('添加资源'),
      ),
      TextButton.icon(
        onPressed: () => newNote(null),
        icon: const Icon(Icons.note_add_outlined),
        label: const Text('新建笔记'),
      ),
      TextButton.icon(
        onPressed: () async {
          final node = await showDialog<Map<String, dynamic>>(
            context: context,
            builder: (_) => MediaDownloadDialog(
              backend: widget.backend,
              workspaceId: widget.workspaceId,
            ),
          );
          if (!mounted) return;
          await reload();
          if (mounted && node != null) widget.onOpen?.call(node);
        },
        icon: const Icon(Icons.download_outlined),
        label: const Text('下载媒体'),
      ),
      TextField(
        key: const ValueKey('resource-search'),
        decoration: const InputDecoration(
          hintText: '搜索资源',
          prefixIcon: Icon(Icons.search, size: 18),
          isDense: true,
        ),
        maxLength: 200,
        buildCounter: (
          _, {
          required currentLength,
          required isFocused,
          maxLength,
        }) => null,
        onChanged: (value) {
          searchTimer?.cancel();
          searchTimer = Timer(const Duration(milliseconds: 250), () {
            search = value.trim();
            reload();
          });
        },
      ),
      if (children[null]?.isEmpty ?? false) const Text('添加文件、文件夹或链接。原目录保持不变。'),
      ...rows(null, 0),
      if (error != null) SelectableText(error!),
    ],
  );
}

String resourceStatus(dynamic value) => switch (value) {
  'removed' => '已从工作区删除，文件和记录保留',
  'ready' => '可用',
  'missing' => '文件缺失，关系已保留',
  'conflict' => '文件冲突或不可读取',
  'queued' => '排队中',
  'running' => '复制中',
  'copying' => '正在复制文件',
  'completed' => '已完成',
  'partial' => '部分成功',
  'cancelled' => '已取消',
  'interrupted' => '上次中断，请重新选择来源',
  'failed' => '失败',
  'added' => '已添加',
  'renamed' => '重名已编号',
  'duplicate' => '相同原件，独立资源',
  _ => '$value',
};

class _FolderPicker extends StatefulWidget {
  const _FolderPicker({
    required this.backend,
    required this.prefix,
    required this.excluded,
  });
  final Backend backend;
  final String prefix, excluded;
  @override
  State<_FolderPicker> createState() => _FolderPickerState();
}

class _FolderPickerState extends State<_FolderPicker> {
  final trail = <Map<String, dynamic>>[
    {'id': null, 'name': '工作空间根目录'},
  ];
  List<dynamic> rows = [];
  int offset = 0;
  bool busy = true, more = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load({bool reset = true}) async {
    setState(() {
      busy = true;
      error = null;
    });
    if (reset) {
      rows = [];
      offset = 0;
    }
    try {
      final parent = trail.last['id'];
      final page = await widget.backend.request(
        'GET',
        '${widget.prefix}/nodes?offset=$offset&limit=100${parent == null ? '' : '&parent_id=$parent'}',
      ) as List;
      if (mounted) {
        setState(() {
          offset += page.length;
          more = page.length == 100;
          rows.addAll(
            page.where(
              (n) =>
                  n['kind'] == 'folder' &&
                  n['resource_item_id'] != widget.excluded,
            ),
          );
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('目标：${trail.last['name']}'),
    content: SizedBox(
      width: 420,
      height: 300,
      child: ListView(
        children: [
          if (trail.length > 1)
            TextButton(
              onPressed: busy
                  ? null
                  : () {
                      trail.removeLast();
                      load();
                    },
              child: const Text('上一级'),
            ),
          if (busy) const LinearProgressIndicator(),
          for (final row in rows)
            ListTile(
              title: Text(row['name'] as String),
              leading: const Icon(Icons.folder_outlined),
              onTap: busy
                  ? null
                  : () {
                      trail.add({
                        'id': row['resource_item_id'],
                        'name': row['name'],
                      });
                      load();
                    },
            ),
          if (more)
            TextButton(
              onPressed: busy ? null : () => load(reset: false),
              child: const Text('更多文件夹'),
            ),
          if (error != null) SelectableText(error!),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('取消'),
      ),
      FilledButton(
        onPressed: busy || error != null
            ? null
            : () => Navigator.pop(context, trail.last),
        child: const Text('选择此位置'),
      ),
    ],
  );
}
