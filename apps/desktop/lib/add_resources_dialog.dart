import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend.dart';
import 'resource_explorer.dart' show resourceStatus;

class AddResourcesDialog extends StatefulWidget {
  const AddResourcesDialog({
    required this.backend,
    required this.workspaceId,
    this.parentId,
    this.onImported,
    this.onOpen,
    this.onProcess,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final String? parentId;
  final VoidCallback? onImported, onProcess;
  final ValueChanged<Map<String, dynamic>>? onOpen;
  @override
  State<AddResourcesDialog> createState() => _AddResourcesDialogState();
}

class _AddResourcesDialogState extends State<AddResourcesDialog>
    with WidgetsBindingObserver {
  static const channel = MethodChannel('study/desktop');
  final dropKey = GlobalKey(), viewportKey = GlobalKey();
  final name = TextEditingController(), url = TextEditingController();
  final pending = <Map<String, dynamic>>[];
  List<dynamic> jobs = [];
  bool busy = false, importing = false, hovering = false, stop = false;
  String? error, notice, activeJob;
  Rect? lastBounds;
  int jobOffset = 0;
  Timer? timer;
  Future<void> staging = Future.value();
  String get prefix => '/api/workspaces/${widget.workspaceId}';
  String pathKey(String path) => path.replaceAll('\\', '/').toLowerCase();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    channel.setMethodCallHandler((call) async {
      if (!mounted) return;
      switch (call.method) {
        case 'resourceDrag':
          setState(() => hovering = call.arguments == true);
        case 'resourceDrop':
          await stage((call.arguments as List).cast<String>());
        case 'resourceDropError':
          setState(() => error = '${call.arguments}');
      }
    });
    refresh();
    Future<void>.delayed(const Duration(milliseconds: 350), () {
      if (mounted) updateBounds();
    });
  }

  @override
  void didChangeMetrics() => updateBounds();

  void updateBounds() {
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final box = dropKey.currentContext?.findRenderObject() as RenderBox?;
      final ratio = View.of(context).devicePixelRatio;
      final viewport =
          viewportKey.currentContext?.findRenderObject() as RenderBox?;
      var bounds = busy || box == null
          ? Rect.zero
          : (box.localToGlobal(Offset.zero) * ratio) & (box.size * ratio);
      if (viewport != null) {
        bounds = bounds.intersect(
          (viewport.localToGlobal(Offset.zero) * ratio) &
              (viewport.size * ratio),
        );
      }
      if (lastBounds == bounds) return;
      lastBounds = bounds;
      try {
        await channel.invokeMethod<void>(
          'setResourceDropBounds',
          bounds.isEmpty
              ? null
              : [bounds.left, bounds.top, bounds.right, bounds.bottom],
        );
      } on MissingPluginException {
        // Widget tests have no native window.
      } catch (failure) {
        if (mounted) setState(() => error = '拖放不可用：$failure；可使用添加文件');
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    channel.setMethodCallHandler(null);
    unawaited(
      channel.invokeMethod<void>('setResourceDropBounds').catchError((_) {}),
    );
    name.dispose();
    url.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    timer?.cancel();
    try {
      final rows = await widget.backend.request(
        'GET',
        '$prefix/resource-add-jobs${jobOffset == 0 ? '' : '?offset=$jobOffset'}',
      ) as List;
      if (!mounted) return;
      setState(() => jobs = rows);
      if (rows.any((j) => ['queued', 'running'].contains(j['status']))) {
        timer = Timer(const Duration(milliseconds: 800), refresh);
      }
    } catch (failure) {
      if (mounted) setState(() => error = '任务读取失败：$failure');
    }
  }

  Future<void> run(Future<void> Function() operation) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await operation();
    } catch (failure) {
      if (mounted) setState(() => error = '添加未完成：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> stage(List<String> paths) => staging = staging.then((_) async {
    if (!mounted) return;
    if (busy) {
      setState(() => error = '当前操作尚未完成，请稍后重新添加文件');
      return;
    }
    await run(() async {
      final known = pending
          .map((r) => pathKey(r['source_path'] as String))
          .toSet();
      final unique = paths.where((p) => known.add(pathKey(p))).toList();
      if (unique.length + pending.length > 1000) {
        throw const FormatException('待导入列表最多1000项');
      }
      final rows = unique.isEmpty
          ? <dynamic>[]
          : await widget.backend.request(
              'POST',
              '$prefix/resource-inspections',
              {'source_paths': unique},
            ) as List;
      if (!mounted) return;
      setState(() {
        notice = paths.length > unique.length
            ? '已跳过 ${paths.length - unique.length} 个重复选择的路径'
            : null;
        for (final raw in rows) {
          final row = Map<String, dynamic>.from(raw as Map);
          final key = pathKey(row['source_path'] as String);
          if (!pending.any((p) => pathKey(p['source_path'] as String) == key)) {
            pending.add({...row, 'state': 'pending'});
          }
        }
      });
    });
  });

  Future<void> choose(bool folder) async {
    try {
      final paths = folder
          ? [await channel.invokeMethod<String>('chooseResourceDirectory')]
                .whereType<String>()
                .toList()
          : await channel.invokeListMethod<String>('chooseResourceFiles') ?? [];
      if (mounted && paths.isNotEmpty) await stage(paths);
    } catch (failure) {
      if (mounted) setState(() => error = '文件选择失败：$failure');
    }
  }

  Future<void> confirm() => run(() async {
    importing = true;
    stop = false;
    try {
      for (final row in pending.where((r) => r['state'] != 'success')) {
        if (stop || !mounted) break;
        try {
          if (row['job_id'] == null) {
            final checked = await widget.backend.request(
              'POST',
              '$prefix/resource-inspections',
              {
                'source_paths': [row['source_path']],
              },
            ) as List;
            if (stop || !mounted) break;
            row.addAll(Map<String, dynamic>.from(checked.single as Map));
            if (row['error'] != null) throw FormatException('${row['error']}');
            final job = await widget.backend.request(
              'POST',
              '$prefix/resource-add-jobs',
              {'source_path': row['source_path'], 'parent_id': widget.parentId},
            ) as Map;
            row['job_id'] = job['id'];
          }
          activeJob = row['job_id'] as String;
          if (stop) await cancelCopy();
          row['state'] = 'importing';
          while (mounted) {
            final job = await widget.backend.request(
              'GET',
              '$prefix/resource-add-jobs/$activeJob',
            ) as Map;
            if (!mounted) break;
            setState(() {
              row['results'] = job['results'];
              row['error'] = job['error'];
            });
            if (!['queued', 'running'].contains(job['status'])) {
              row['state'] = job['status'] == 'completed'
                  ? 'success'
                  : 'failed';
              row.remove('job_id');
              widget.onImported?.call();
              break;
            }
            await Future<void>.delayed(const Duration(milliseconds: 300));
          }
        } catch (failure) {
          if (mounted) {
            setState(() {
              row['state'] = 'failed';
              row['error'] = '$failure';
            });
          }
        } finally {
          activeJob = null;
        }
      }
    } finally {
      importing = false;
      if (mounted) await refresh();
    }
  });

  Future<void> cancelCopy() async {
    setState(() => stop = true);
    try {
      if (activeJob != null) {
        await widget.backend.request(
          'POST',
          '$prefix/resource-add-jobs/$activeJob/cancel',
        );
      }
    } catch (failure) {
      if (mounted) setState(() => error = '取消未确认：$failure；已完成部分保留');
    }
  }

  Future<void> create(String kind) => run(() async {
    await widget.backend.request('POST', '$prefix/nodes', {
      'parent_id': widget.parentId,
      'name': name.text,
      'kind': kind,
      if (kind == 'link') 'url': url.text,
    });
    widget.onImported?.call();
    if (mounted) {
      setState(() {
        notice = '已保存${kind == 'link' ? '网页链接' : '文件夹'}';
        name.clear();
        url.clear();
      });
    }
  });

  Widget resultRow(dynamic result) => ListTile(
    dense: true,
    title: Text(result['stored_name'] as String? ?? result['name'] as String),
    subtitle: Text(
      '${resourceStatus(result['status'])}${result['error'] == null ? '' : '：${result['error']}'}',
    ),
    trailing:
        result['resource_item_id'] != null &&
            widget.onOpen != null &&
            result['status'] != 'failed'
        ? TextButton(
            onPressed: busy
                ? null
                : () async {
                    try {
                      final node = await widget.backend.request(
                        'GET',
                        '$prefix/nodes/${result['resource_item_id']}',
                      ) as Map;
                      if (mounted && node['kind'] != 'folder') {
                        Navigator.pop(context);
                        widget.onOpen!(Map<String, dynamic>.from(node));
                      }
                    } catch (failure) {
                      if (mounted) setState(() => error = '打开失败：$failure');
                    }
                  },
            child: const Text('打开'),
          )
        : null,
  );

  String sizeLabel(dynamic size) => size == null
      ? '大小将在复制时检查'
      : size < 1024
      ? '$size B'
      : size < 1024 * 1024
      ? '${(size / 1024).toStringAsFixed(1)} KB'
      : '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';

  @override
  Widget build(BuildContext context) {
    updateBounds();
    final colors = Theme.of(context).colorScheme;
    final success = pending.where((r) => r['state'] == 'success').length;
    return PopScope(
      canPop: !busy,
      child: AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.add_circle_outline),
            const SizedBox(width: 10),
            const Expanded(child: Text('添加资源')),
            IconButton(
              tooltip: '关闭添加资源',
              onPressed: busy ? null : () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        content: SizedBox(
          key: viewportKey,
          width: 680,
          height: MediaQuery.sizeOf(context).height * .68,
          child: NotificationListener<ScrollNotification>(
            onNotification: (_) {
              updateBounds();
              return false;
            },
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('将学习资料、视频、笔记或其他文件添加到当前工作空间。'),
                  const SizedBox(height: 18),
                  AnimatedContainer(
                    key: dropKey,
                    duration: const Duration(milliseconds: 120),
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: hovering
                          ? colors.primaryContainer
                          : colors.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: hovering
                            ? colors.primary
                            : colors.outlineVariant,
                        width: 2,
                      ),
                    ),
                    child: Column(
                      children: [
                        Icon(
                          Icons.file_copy_outlined,
                          size: 36,
                          color: colors.primary,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          hovering ? '松开鼠标，添加文件' : '拖动文件到这里',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          '支持多个文件，可一次添加不同类型的资源',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: busy ? null : () => choose(false),
                          child: const Text('添加文件'),
                        ),
                        const SizedBox(height: 8),
                        const Text('也可以直接选择电脑中的文件'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '待导入资源（${pending.length}）',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      ),
                      TextButton(
                        onPressed: busy || pending.isEmpty
                            ? null
                            : () => setState(pending.clear),
                        child: const Text('清空列表'),
                      ),
                    ],
                  ),
                  if (pending.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(12),
                      child: Text('选择文件后可检查类型、大小和支持状态，再确认导入。'),
                    ),
                  for (final row in pending) ...[
                    Card.outlined(
                      child: Column(
                        children: [
                          ListTile(
                            leading: Icon(
                              row['kind'] == 'folder'
                                  ? Icons.folder_outlined
                                  : row['kind'] == 'media'
                                  ? Icons.play_circle_outline
                                  : Icons.description_outlined,
                            ),
                            title: Text(
                              row['name'] as String,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              '${row['type']} · ${sizeLabel(row['size'])}\n${row['error'] ?? row['warning'] ?? '已识别，可保存'}',
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  switch (row['state']) {
                                    'success' => '已导入',
                                    'failed' => '未完成',
                                    'importing' => '复制中',
                                    _ => row['error'] != null ? '不可导入' : '已识别',
                                  },
                                  style: TextStyle(
                                    color: row['error'] == null
                                        ? colors.primary
                                        : colors.error,
                                  ),
                                ),
                                IconButton(
                                  tooltip: '移除 ${row['name']}',
                                  onPressed: busy
                                      ? null
                                      : () =>
                                            setState(() => pending.remove(row)),
                                  icon: const Icon(Icons.close, size: 18),
                                ),
                              ],
                            ),
                          ),
                          if (row['results'] != null)
                            ExpansionTile(
                              title: const Text('导入结果'),
                              children: [
                                for (final result in row['results'] as List)
                                  resultRow(result),
                              ],
                            ),
                        ],
                      ),
                    ),
                  ],
                  if (pending.any(
                    (r) => r['kind'] == 'folder' && r['state'] == 'failed',
                  ))
                    const Text('文件夹重试会创建新的编号副本；先检查已完成部分，避免重复。'),
                  if (notice != null) Text(notice!),
                  if (error != null)
                    SelectableText(
                      error!,
                      style: TextStyle(color: colors.error),
                    ),
                  if (busy) const LinearProgressIndicator(),
                  if (!busy && success > 0 && widget.onProcess != null)
                    TextButton(
                      onPressed: () {
                        Navigator.pop(context);
                        widget.onProcess!();
                      },
                      child: const Text('继续提取题目 / 资料处理'),
                    ),
                  ExpansionTile(
                    title: const Text('文件夹与网页链接'),
                    children: [
                      OutlinedButton(
                        onPressed: busy ? null : () => choose(true),
                        child: const Text('复制导入文件夹'),
                      ),
                      const Text(
                        '受管复制：保留原目录与层级，不自动提取题目。最多1000节点、32层、合计1GiB；普通文件128MiB，MP4/WebM/M4A媒体512MiB。重名自动编号，原件不覆盖。',
                      ),
                      TextField(
                        controller: name,
                        decoration: const InputDecoration(
                          labelText: '新文件夹 / 链接名称',
                        ),
                      ),
                      TextField(
                        controller: url,
                        decoration: const InputDecoration(
                          labelText: '网页 HTTPS 地址',
                        ),
                      ),
                      Wrap(
                        spacing: 12,
                        children: [
                          TextButton(
                            onPressed: busy ? null : () => create('folder'),
                            child: const Text('新建文件夹'),
                          ),
                          TextButton(
                            onPressed: busy ? null : () => create('link'),
                            child: const Text('保存网页链接'),
                          ),
                        ],
                      ),
                      const Text('视频下载尚未实现；视频分享地址可保存为网页链接。'),
                    ],
                  ),
                  ExpansionTile(
                    title: const Text('后台添加任务'),
                    children: [
                      TextButton(
                        onPressed: busy ? null : refresh,
                        child: const Text('刷新添加任务'),
                      ),
                      for (final job in jobs)
                        ExpansionTile(
                          key: ValueKey('add-job-${job['id']}'),
                          title: Text(
                            '${resourceStatus(job['status'])} · ${(job['results'] as List).length} 项',
                          ),
                          subtitle: job['error'] == null
                              ? null
                              : Text(job['error'] as String),
                          children: [
                            if (['queued', 'running'].contains(job['status']))
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => run(() async {
                                        await widget.backend.request(
                                          'POST',
                                          '$prefix/resource-add-jobs/${job['id']}/cancel',
                                        );
                                        await refresh();
                                      }),
                                child: Text(
                                  job['cancel_requested'] == true
                                      ? '已请求取消'
                                      : '取消复制',
                                ),
                              ),
                            for (final result in job['results'] as List)
                              resultRow(result),
                          ],
                        ),
                      if (jobs.length == 20)
                        TextButton(
                          onPressed: busy
                              ? null
                              : () {
                                  jobOffset += 20;
                                  refresh();
                                },
                          child: const Text('更早的添加任务'),
                        ),
                      if (jobOffset > 0)
                        TextButton(
                          onPressed: busy
                              ? null
                              : () {
                                  jobOffset -= 20;
                                  refresh();
                                },
                          child: const Text('较新的添加任务'),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
        actions: [
          Text(
            '已选择 ${pending.length} 项${success > 0 ? ' · 已导入 $success 项' : ''}',
          ),
          if (importing)
            TextButton(
              onPressed: stop ? null : cancelCopy,
              child: Text(stop ? '正在停止…' : '停止导入'),
            ),
          TextButton(
            onPressed: busy ? null : () => Navigator.pop(context),
            child: Text(success > 0 ? '完成' : '取消'),
          ),
          FilledButton(
            onPressed: busy || pending.isEmpty || success == pending.length
                ? null
                : confirm,
            child: Text(
              pending.any((r) => r['state'] == 'failed') ? '重试未完成项' : '确认导入',
            ),
          ),
        ],
      ),
    );
  }
}
