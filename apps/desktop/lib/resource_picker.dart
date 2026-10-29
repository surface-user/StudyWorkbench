import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend.dart';

class ResourcePicker extends StatefulWidget {
  const ResourcePicker({
    required this.backend,
    required this.workspaceId,
    required this.imagesOnly,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final bool imagesOnly;
  @override
  State<ResourcePicker> createState() => _ResourcePickerState();
}

class _ResourcePickerState extends State<ResourcePicker> {
  final resources = <dynamic>[];
  int offset = 0;
  bool busy = false, more = true;
  String? error;
  bool supported(dynamic resource) => widget.imagesOnly
      ? ['image/png', 'image/jpeg'].contains(resource['mime'])
      : [
          'image/png',
          'image/jpeg',
          'text/plain',
          'application/json',
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ].contains(resource['mime']);
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final rows = await widget.backend.request(
        'GET',
        '/api/workspaces/${widget.workspaceId}/resources?offset=$offset&limit=50',
      ) as List;
      if (mounted) {
        setState(() {
          offset += rows.length;
          more = rows.length == 50;
          resources.addAll(rows.where(supported));
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = '资源读取失败：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> upload() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final path = await const MethodChannel('study/desktop')
          .invokeMethod<String>('chooseImportFile');
      if (path == null) return;
      final file = File(path);
      if (await file.length() > 8 * 1024 * 1024) {
        throw const FormatException('附件最多8MiB');
      }
      final bytes = BytesBuilder(copy: false);
      await for (final chunk in file.openRead()) {
        bytes.add(chunk);
        if (bytes.length > 8 * 1024 * 1024) {
          throw const FormatException('附件最多8MiB');
        }
      }
      final name = path.split(RegExp(r'[/\\]')).last;
      final job = await widget.backend.uploadImport(
        widget.workspaceId,
        name,
        bytes.takeBytes(),
      ) as Map<String, dynamic>;
      final resource = {
        'id': job['resource_id'],
        'filename': name,
        'mime': job['mime'],
      };
      if (job['status'] == 'failed' || !supported(resource)) {
        throw const FormatException('此文件不能用于当前附件，原件已保留');
      }
      if (mounted) Navigator.pop(context, resource);
    } catch (failure) {
      if (mounted) setState(() => error = '附件未选入：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: Text(widget.imagesOnly ? '选择图片' : '选择附件'),
      content: SizedBox(
        width: 600,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('仅选择当前工作空间资源。选择后仍需确认保存笔记；原文件不会替换或删除。'),
              OutlinedButton(
                onPressed: busy ? null : upload,
                child: const Text('从文件添加新资源'),
              ),
              for (final resource in resources)
                ListTile(
                  title: Text(resource['filename'] as String),
                  subtitle: Text(resource['mime'] as String),
                  onTap: busy ? null : () => Navigator.pop(context, resource),
                ),
              if (!busy && resources.isEmpty) const Text('尚无匹配资源，可添加文件或加载下一页'),
              if (busy) const LinearProgressIndicator(),
              if (more)
                TextButton(
                  onPressed: busy ? null : load,
                  child: const Text('加载更多资源'),
                ),
              if (error != null) SelectableText(error!),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('取消选择'),
        ),
      ],
    ),
  );
}
