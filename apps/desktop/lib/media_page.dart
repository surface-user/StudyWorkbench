import 'package:flutter/material.dart';

import 'backend.dart';
import 'add_resources_dialog.dart';
import 'page_activity.dart';
import 'web_page.dart';
import 'learning_marks_dialog.dart';

class MediaPage extends StatefulWidget {
  const MediaPage({
    required this.backend,
    required this.workspaceId,
    required this.profile,
    this.onActivity,
    this.mediaId,
    this.onResourcesChanged,
    this.resourceItemId,
    this.sourceSha256,
    this.jumpAnchor,
    this.onNavigate,
    super.key,
  });
  final Backend backend;
  final String workspaceId, profile;
  final PageActivityChanged? onActivity;
  final String? mediaId;
  final VoidCallback? onResourcesChanged;
  final String? resourceItemId, sourceSha256;
  final Map<String, dynamic>? jumpAnchor;
  final ValueChanged<Map<String, dynamic>>? onNavigate;
  @override
  State<MediaPage> createState() => _MediaPageState();
}

class _MediaPageState extends State<MediaPage> {
  List<dynamic> entries = [];
  bool busy = false, more = false;
  double? progress;
  String? error, playerUrl;
  String? openedMedia;
  PlayerCommands? playerCommands;
  Map<String, dynamic>? appliedAnchor;
  Map<String, dynamic>? attemptedAnchor;
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
    if (oldWidget.jumpAnchor != widget.jumpAnchor && playerCommands != null) {
      run(applyAnchor);
    }
  }

  Future<void> applyAnchor() async {
    final point = widget.jumpAnchor;
    if (point == null || identical(appliedAnchor, point)) {
      return;
    }
    attemptedAnchor = point;
    if (point['kind'] != 'media_time') return;
    if (point['workspace_id'] != widget.workspaceId ||
        point['resource_item_id'] != widget.resourceItemId ||
        point['content_sha256'] != widget.sourceSha256) {
      throw StateError('媒体书签的资源或版本不匹配');
    }
    final verified = await widget.backend.request(
      'POST',
      '$scope/nodes/${widget.resourceItemId}/learning-anchor',
      {
        'kind': 'media_time',
        'position_ms': point['position_ms'],
        'expected_sha256': point['content_sha256'],
      },
    ) as Map;
    if (playerCommands == null ||
        !await playerCommands!.seekToMs(verified['position_ms'] as int)) {
      throw StateError('播放器尚不能跳转，请重新打开媒体');
    }
    appliedAnchor = point;
  }

  Future<void> marks() async {
    final target = await showDialog<Map<String, dynamic>>(
      context: context,
      barrierDismissible: false,
      builder: (_) => LearningMarksDialog(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        resourceItemId: widget.resourceItemId,
        captureCurrent: () async {
          final milliseconds = await playerCommands?.readPositionMs();
          if (milliseconds == null) {
            throw StateError('请等待本地媒体加载后再记录时间点；也可标记整份资料');
          }
          return Map<String, dynamic>.from(
            await widget.backend.request(
              'POST',
              '$scope/nodes/${widget.resourceItemId}/learning-anchor',
              {
                'kind': 'media_time',
                'position_ms': milliseconds,
                'expected_sha256': widget.sourceSha256,
              },
            ) as Map,
          );
        },
      ),
    );
    if (mounted && target != null) widget.onNavigate?.call(target);
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
        if (playerCommands != null &&
            widget.jumpAnchor != null &&
            !identical(widget.jumpAnchor, attemptedAnchor)) {
          Future.microtask(() {
            if (mounted) run(applyAnchor);
          });
        }
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
        playerCommands = null;
        appliedAnchor = null;
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
            if (widget.resourceItemId != null)
              TextButton(
                onPressed: busy ? null : marks,
                child: const Text('书签与备注'),
              ),
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
                onPlayerReady: (commands) {
                  playerCommands = commands;
                  run(applyAnchor);
                },
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
