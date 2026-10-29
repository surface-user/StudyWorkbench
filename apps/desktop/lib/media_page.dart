import 'package:flutter/material.dart';

import 'backend.dart';
import 'add_resources_dialog.dart';
import 'page_activity.dart';
import 'web_page.dart';

class MediaPage extends StatefulWidget {
  const MediaPage({
    required this.backend,
    required this.workspaceId,
    required this.profile,
    this.onActivity,
    this.mediaId,
    this.onResourcesChanged,
    super.key,
  });
  final Backend backend;
  final String workspaceId, profile;
  final PageActivityChanged? onActivity;
  final String? mediaId;
  final VoidCallback? onResourcesChanged;
  @override
  State<MediaPage> createState() => _MediaPageState();
}

class _MediaPageState extends State<MediaPage> {
  List<dynamic> entries = [];
  bool busy = false, more = false;
  double? progress;
  String? error, playerUrl;
  String? openedMedia;
  String get scope => '/api/workspaces/${widget.workspaceId}';
  @override
  void initState() {
    super.initState();
    run(widget.mediaId == null ? load : () => openPlayer(widget.mediaId!));
  }

  Future<void> refreshSession() => run(
    widget.mediaId != null || openedMedia != null
        ? () => openPlayer(widget.mediaId ?? openedMedia!)
        : load,
  );

  @override
  void didUpdateWidget(covariant MediaPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.backend != widget.backend && !busy) refreshSession();
  }

  Future<void> load() async {
    final rows =
        await widget.backend.request('GET', '$scope/media?limit=50') as List;
    if (mounted) {
      setState(() {
        entries = rows;
        more = rows.length == 50;
      });
    }
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    final backendAtStart = widget.backend;
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
      if (mounted) {
        setState(() {
          busy = false;
          progress = null;
        });
        if (backendAtStart != widget.backend) refreshSession();
      }
    }
  }

  Future<void> import() async {
    await showDialog<void>(
      context: context,
      builder: (_) => AddResourcesDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        onImported: widget.onResourcesChanged,
      ),
    );
    if (mounted) await run(load);
  }

  Future<void> open(dynamic entry) =>
      run(() => openPlayer(entry['id'] as String));
  Future<void> openPlayer(String id) async {
    final value = await widget.backend.request(
      'GET',
      '$scope/media/$id/player',
    ) as Map<String, dynamic>;
    final uri = Uri.parse(value['url'] as String);
    if (uri.scheme != 'http' ||
        uri.host != '127.0.0.1' ||
        uri.port != widget.backend.port ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch(id) ||
        uri.path != '/media/library/$id/player') {
      throw const FormatException('本地播放器地址无效');
    }
    if (mounted) {
      setState(() {
        playerUrl = uri.toString();
        openedMedia = id;
      });
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            if (widget.mediaId != null)
              OutlinedButton(
                onPressed: busy
                    ? null
                    : () => run(() => openPlayer(widget.mediaId!)),
                child: const Text('重新打开媒体'),
              ),
            if (widget.mediaId == null) ...[
              Text('媒体库', style: Theme.of(context).textTheme.titleLarge),
              FilledButton(
                onPressed: busy ? null : import,
                child: const Text('添加资源'),
              ),
              OutlinedButton(
                onPressed: busy ? null : () => run(load),
                child: const Text('刷新媒体库'),
              ),
              if (playerUrl != null)
                TextButton(
                  onPressed: busy
                      ? null
                      : () => setState(() {
                          playerUrl = null;
                          openedMedia = null;
                        }),
                  child: const Text('返回媒体列表'),
                ),
              const Text('支持MP4/WebM/M4A，最多512MiB。入库不代表编码可播放；普通播放不依赖模型。'),
            ],
          ],
        ),
      ),
      if (busy) LinearProgressIndicator(value: progress),
      if (progress != null)
        Text('正在传送本地文件 ${(progress! * 100).toStringAsFixed(0)}%；完成后仍需等待保存确认'),
      if (error != null) SelectableText('操作未完成：$error'),
      Expanded(
        child: playerUrl != null
            ? WebPage(
                key: ValueKey(playerUrl),
                profile: widget.profile,
                playerUrl: playerUrl,
                onActivity: widget.onActivity,
              )
            : widget.mediaId != null
            ? const Center(child: Text('媒体尚未加载，可重试打开。'))
            : ListView(
                children: [
                  for (final entry in entries)
                    ListTile(
                      title: Text(entry['title'] as String),
                      subtitle: Text(
                        entry['status'] == 'ready'
                            ? '${entry['size']} 字节 · 支持续播/倍速/WebVTT字幕'
                            : '导入未完成，已接收部分保留，请重新选择原文件',
                      ),
                      onTap: busy || entry['status'] != 'ready'
                          ? null
                          : () => open(entry),
                    ),
                  if (!busy && entries.isEmpty)
                    const ListTile(title: Text('尚无媒体，请选择本人有权使用的本地文件')),
                  if (more)
                    TextButton(
                      onPressed: busy
                          ? null
                          : () => run(() async {
                              final next = await widget.backend.request(
                                'GET',
                                '$scope/media?limit=50&offset=${entries.length}',
                              ) as List;
                              if (mounted) {
                                setState(() {
                                  entries.addAll(next);
                                  more = next.length == 50;
                                });
                              }
                            }),
                      child: const Text('加载更多媒体'),
                    ),
                ],
              ),
      ),
    ],
  );
}
