import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';

class MediaSitePreviewDialog extends StatefulWidget {
  const MediaSitePreviewDialog({
    required this.backend,
    required this.workspaceId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;

  @override
  State<MediaSitePreviewDialog> createState() => _MediaSitePreviewDialogState();
}

class _MediaSitePreviewDialogState extends State<MediaSitePreviewDialog> {
  final url = TextEditingController();
  bool rights = false, busy = false;
  int generation = 0;
  int? pollingGeneration;
  String? identifier, requestId, requestKey, selected, error;
  Map<String, dynamic>? preview;
  Timer? timer;

  String get prefix =>
      '/api/workspaces/${widget.workspaceId}/media-site-previews';

  Future<void> cancelRemote(
    Backend backend,
    String endpoint,
    String? id,
  ) async {
    if (id == null) return;
    try {
      await backend.request('POST', '$endpoint/$id/cancel', {});
    } catch (_) {
      // The fixed worker also has a deadline; a failed cancel never starts a download.
    }
  }

  void cancel({bool changed = false}) {
    final old = identifier;
    generation++;
    timer?.cancel();
    setState(() {
      busy = false;
      identifier = requestId = requestKey = selected = error = null;
      preview = null;
      if (changed) rights = false;
    });
    unawaited(cancelRemote(widget.backend, prefix, old));
  }

  @override
  void didUpdateWidget(covariant MediaSitePreviewDialog oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.backend == widget.backend &&
        oldWidget.workspaceId == widget.workspaceId) {
      return;
    }
    final old = identifier;
    generation++;
    timer?.cancel();
    busy = rights = false;
    identifier = requestId = requestKey = selected = error = null;
    preview = null;
    url.clear();
    unawaited(
      cancelRemote(
        oldWidget.backend,
        '/api/workspaces/${oldWidget.workspaceId}/media-site-previews',
        old,
      ),
    );
  }

  @override
  void dispose() {
    generation++;
    timer?.cancel();
    unawaited(cancelRemote(widget.backend, prefix, identifier));
    url.dispose();
    super.dispose();
  }

  Future<void> start() async {
    if (!rights || busy || url.text.trim().isEmpty) return;
    final old = identifier;
    final backend = widget.backend;
    final endpoint = prefix;
    if (old != null) {
      unawaited(cancelRemote(backend, endpoint, old));
      requestId = null;
    }
    final key = url.text.trim();
    if (requestId == null || requestKey != key) {
      requestKey = key;
      requestId = List.generate(
        24,
        (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join();
    }
    final run = ++generation;
    setState(() {
      busy = true;
      error = selected = identifier = null;
      preview = null;
    });
    try {
      final response = await backend.request('POST', endpoint, {
        'url': key,
        'request_id': requestId,
        'rights_confirmed': true,
      }) as Map;
      final id = response['id'] as String;
      if (!mounted || run != generation) {
        await cancelRemote(backend, endpoint, id);
        return;
      }
      identifier = id;
      apply(response, run);
      if (busy) {
        timer = Timer.periodic(
          const Duration(milliseconds: 300),
          (_) => poll(id, run),
        );
      }
    } catch (_) {
      if (mounted && run == generation) {
        setState(() {
          busy = false;
          error = '预览暂不可用，请检查链接后重试';
        });
      }
    }
  }

  Future<void> poll(String id, int run) async {
    if (!mounted || run != generation || pollingGeneration == run) return;
    pollingGeneration = run;
    final backend = widget.backend;
    final endpoint = prefix;
    try {
      final response = await backend.request('GET', '$endpoint/$id') as Map;
      if (mounted && run == generation) apply(response, run);
    } catch (_) {
      if (mounted && run == generation) {
        timer?.cancel();
        setState(() {
          busy = false;
          error = '预览状态暂不可用，请重新预览';
        });
        unawaited(cancelRemote(backend, endpoint, id));
      }
    } finally {
      if (pollingGeneration == run) pollingGeneration = null;
    }
  }

  void apply(Map response, int run) {
    if (!mounted || run != generation || response['status'] == 'running') {
      return;
    }
    timer?.cancel();
    setState(() {
      busy = false;
      if (response['status'] == 'ready') {
        preview = Map<String, dynamic>.from(response['result'] as Map);
      } else {
        requestId = null;
        error = response['error'] as String? ?? '预览已取消，请重新预览';
      }
    });
  }

  String formatLabel(Map item) {
    final kind = switch (item['delivery']) {
      'dash_video' => '视频轨',
      'dash_audio' => '音轨',
      'segments' => '多段',
      _ => '单文件',
    };
    final resolution = item['height'] == null ? '' : '${item['height']}p · ';
    return '$resolution$kind · ${item['container'] ?? '容器未知'}';
  }

  @override
  Widget build(BuildContext context) {
    final formats = preview?['formats'] as List? ?? const [];
    final chosen = formats.cast<Map>().where(
      (item) => item['format_id'] == selected,
    );
    final item = chosen.isEmpty ? null : chosen.first;
    return AlertDialog(
      title: const Text('预览B站视频格式'),
      content: SizedBox(
        width: 650,
        height: MediaQuery.sizeOf(context).height * .6,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('支持普通单视频和短链。先查看视频返回的格式；此处暂不提供下载。'),
              TextField(
                controller: url,
                enabled: !busy,
                maxLength: 8192,
                decoration: const InputDecoration(
                  labelText: 'B站视频链接',
                  counterText: '',
                ),
                onChanged: (_) => cancel(changed: true),
              ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('我有权获取此视频'),
                value: rights,
                onChanged: busy
                    ? null
                    : (value) {
                        if (value != true) cancel();
                        setState(() => rights = value == true);
                      },
              ),
              Wrap(
                spacing: 12,
                children: [
                  FilledButton(
                    onPressed: busy || !rights ? null : start,
                    child: Text(preview == null ? '预览格式' : '重新预览'),
                  ),
                  if (busy)
                    TextButton(onPressed: cancel, child: const Text('取消预览')),
                ],
              ),
              if (busy) const Text('正在获取格式…'),
              if (error != null) Text(error!),
              if (preview != null) ...[
                const SizedBox(height: 12),
                Text(preview!['title'] as String),
                Text(
                  'B站 · ${preview!['duration_seconds']} 秒 · ${formats.length} 个返回格式',
                ),
                DropdownButtonFormField<String>(
                  key: ValueKey(identifier),
                  initialValue: selected,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: '选择格式查看'),
                  items: formats
                      .cast<Map>()
                      .map(
                        (entry) => DropdownMenuItem(
                          value: entry['format_id'] as String,
                          child: Text(
                            formatLabel(entry),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (value) => setState(() => selected = value),
                ),
                if (item != null) ...[
                  Text('编码：${item['codecs'] ?? '未知'}'),
                  Text(
                    item['size_bytes'] == null
                        ? '大小未知'
                        : '接口声明大小：${((item['size_bytes'] as num) / (1024 * 1024)).toStringAsFixed(1)} MiB',
                  ),
                  Text(item['limitation'] as String),
                ],
                const Text('仅列出本次返回的格式，元数据不证明实际解码能力。过期或重新打开后请重新预览。'),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ],
    );
  }
}
