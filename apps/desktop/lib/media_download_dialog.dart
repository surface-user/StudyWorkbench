import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import 'backend.dart';

class MediaDownloadDialog extends StatefulWidget {
  const MediaDownloadDialog({
    required this.backend,
    required this.workspaceId,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  @override
  State<MediaDownloadDialog> createState() => _MediaDownloadDialogState();
}

class _MediaDownloadDialogState extends State<MediaDownloadDialog> {
  final url = TextEditingController(), name = TextEditingController();
  List<dynamic> rows = [];
  bool rights = false, busy = false, loading = false;
  String? error, requestId, requestKey;
  Timer? timer;
  String get prefix => '/api/workspaces/${widget.workspaceId}/media-downloads';
  @override
  void initState() {
    super.initState();
    refresh();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => refresh());
  }

  @override
  void dispose() {
    timer?.cancel();
    url.dispose();
    name.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    if (loading || busy) return;
    loading = true;
    try {
      final result = await widget.backend.request('GET', '$prefix?limit=100');
      if (mounted) setState(() => rows = result as List);
    } catch (_) {
      if (mounted) setState(() => error = '下载列表暂不可用，已显示记录保留，可刷新重试');
    } finally {
      loading = false;
    }
  }

  Future<void> action(Future<void> Function() operation) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await operation();
    } catch (failure) {
      if (mounted) setState(() => error = '操作未完成，下载记录与已存部分保留：$failure');
    } finally {
      if (mounted) {
        setState(() => busy = false);
        await refresh();
      }
    }
  }

  Future<void> create() async {
    if (!rights || url.text.trim().isEmpty || name.text.trim().isEmpty) {
      setState(() => error = '请输入直链、带后缀文件名，并确认下载权利');
      return;
    }
    final key = jsonEncode([url.text.trim(), name.text.trim()]);
    if (requestKey != key) {
      requestKey = key;
      requestId = List.generate(
        24,
        (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join();
    }
    await action(() async {
      await widget.backend.request('POST', prefix, {
        'url': url.text.trim(),
        'name': name.text.trim(),
        'request_id': requestId,
        'rights_confirmed': true,
      });
    });
  }

  Future<void> open(Map row) async {
    await action(() async {
      final id = row['result']['resource_item_id'];
      final node = await widget.backend.request(
        'GET',
        '/api/workspaces/${widget.workspaceId}/nodes/$id',
      );
      if ((node as Map)['removed_at'] != null) {
        throw StateError('来源已从资源树移除，下载文件与记录仍保留');
      }
      if (mounted) {
        Navigator.pop(context, Map<String, dynamic>.from(node));
      }
    });
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: const Text('下载媒体'),
      content: SizedBox(
        width: 850,
        height: MediaQuery.sizeOf(context).height * .65,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    '仅下载有权获取的 HTTPS 媒体直链，保存到当前空间根目录。支持 MP4/WebM/M4A 原始文件，最多512MiB；不支持站点解析、登录、DRM或转码。',
                  ),
                  TextField(
                    controller: url,
                    maxLength: 8192,
                    decoration: const InputDecoration(
                      labelText: 'HTTPS媒体直链',
                      counterText: '',
                    ),
                  ),
                  TextField(
                    controller: name,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: '文件名（含 .mp4 / .webm / .m4a）',
                      counterText: '',
                    ),
                  ),
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    value: rights,
                    title: const Text('我有权下载此媒体文件'),
                    onChanged: busy
                        ? null
                        : (value) => setState(() => rights = value == true),
                  ),
                  const Text(
                    '下载地址可能包含临时签名，会保存在本地任务及未加密整库备份中。关闭窗口继续下载；退出应用后须手动恢复。',
                    style: TextStyle(fontSize: 12),
                  ),
                  Row(
                    children: [
                      FilledButton(
                        onPressed: busy || !rights ? null : create,
                        child: const Text('加入下载队列'),
                      ),
                      TextButton(
                        onPressed: busy ? null : refresh,
                        child: const Text('刷新列表'),
                      ),
                    ],
                  ),
                  const Text(
                    '优先显示进行中的任务，列表最多100条；更早记录仍保留在本地库。',
                    style: TextStyle(fontSize: 12),
                  ),
                  if (error != null) Text(error!),
                  if (rows.isEmpty) const Center(child: Text('暂无下载任务')),
                ],
              ),
            ),
            if (rows.isNotEmpty)
              SliverList.builder(
                itemCount: rows.length,
                itemBuilder: (context, index) {
                  final row = rows[index] as Map;
                  final status = row['status'] as String;
                  final progress = row['progress'] as Map;
                  final labels = {
                    'queued': '排队中',
                    'running': '下载中',
                    'paused': '已暂停',
                    'interrupted': '上次中断',
                    'failed': '未完成',
                    'ready': '已入库',
                  };
                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${row['name']} · ${labels[status] ?? status}'),
                          Text(
                            '${row['source_host']} · ${progress['received'] ?? 0} / ${progress['total'] ?? '未知总量'} 字节',
                          ),
                          if (row['error'] != null)
                            Text(row['error'] as String),
                          Wrap(
                            children: [
                              if (['queued', 'running'].contains(status))
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => action(() async {
                                          await widget.backend.request(
                                            'POST',
                                            '$prefix/${row['id']}/pause',
                                            {},
                                          );
                                        }),
                                  child: const Text('暂停'),
                                ),
                              if ([
                                'paused',
                                'interrupted',
                                'failed',
                              ].contains(status)) ...[
                                if (row['can_resume'] == true)
                                  TextButton(
                                    onPressed: busy
                                        ? null
                                        : () => action(() async {
                                            await widget.backend.request(
                                              'POST',
                                              '$prefix/${row['id']}/retry',
                                              {'mode': 'resume'},
                                            );
                                          }),
                                    child: const Text('断点重试'),
                                  ),
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => action(() async {
                                          await widget.backend.request(
                                            'POST',
                                            '$prefix/${row['id']}/retry',
                                            {'mode': 'restart'},
                                          );
                                        }),
                                  child: const Text('保留旧部分，重新开始'),
                                ),
                              ],
                              if (status == 'ready')
                                TextButton(
                                  onPressed: busy ? null : () => open(row),
                                  child: const Text('打开媒体'),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('关闭'),
        ),
      ],
    ),
  );
}
