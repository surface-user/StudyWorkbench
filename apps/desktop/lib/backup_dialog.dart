import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend.dart';

class LibraryBackupPlan {
  const LibraryBackupPlan({
    required this.restore,
    required this.zipPath,
    this.target,
  });
  final bool restore;
  final String zipPath;
  final String? target;
}

class LibraryBackupDialog extends StatefulWidget {
  const LibraryBackupDialog({required this.restore, this.backend, super.key});
  final bool restore;
  final Backend? backend;
  @override
  State<LibraryBackupDialog> createState() => _LibraryBackupDialogState();
}

class _LibraryBackupDialogState extends State<LibraryBackupDialog> {
  final zip = TextEditingController(), target = TextEditingController();
  List<Map<String, dynamic>>? spaces;
  bool confirmed = false, busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    if (!widget.restore) load();
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value =
          await widget.backend!.request('GET', '/api/workbench') as Map;
      if (mounted) {
        setState(
          () => spaces = [
            for (final row in [
              ...value['workspaces'] as List,
              ...value['archived_workspaces'] as List,
            ])
              Map<String, dynamic>.from(row as Map),
          ],
        );
      }
    } catch (failure) {
      if (mounted) setState(() => error = '无法确认全部空间范围，请重试：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> pick({bool directory = false}) async {
    setState(() => busy = true);
    try {
      final value = await const MethodChannel('study/desktop')
          .invokeMethod<String>(
            directory
                ? 'chooseDirectory'
                : widget.restore
                ? 'chooseBackupArchive'
                : 'chooseBackupDestination',
          );
      if (mounted && value != null) (directory ? target : zip).text = value;
    } catch (failure) {
      if (mounted) setState(() => error = '选择未完成，可输入绝对路径：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submit() async {
    if (busy || !confirmed || !widget.restore && spaces == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final archive = File(zip.text.trim());
      if (!archive.isAbsolute || archive.path.isEmpty) {
        throw const FormatException('请输入ZIP绝对路径');
      }
      if (widget.restore) {
        if (!await archive.exists()) throw const FormatException('备份ZIP不存在');
        final directory = Directory(target.text.trim());
        if (!directory.isAbsolute || directory.path.isEmpty) {
          throw const FormatException('请输入新空目录的绝对路径');
        }
        if (await directory.exists() &&
            await directory.list().isEmpty == false) {
          throw const FormatException('目标必须是新空目录，不能覆盖已有数据');
        }
      } else {
        if (await archive.exists()) {
          throw const FormatException('请选择新的ZIP文件名，不覆盖已有备份');
        }
        if (!await archive.parent.exists()) {
          throw const FormatException('备份父目录不存在');
        }
      }
      if (mounted) {
        Navigator.pop(
          context,
          LibraryBackupPlan(
            restore: widget.restore,
            zipPath: archive.path,
            target: widget.restore ? target.text.trim() : null,
          ),
        );
      }
    } catch (failure) {
      if (mounted) setState(() => error = '尚未开始操作：$failure');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    zip.dispose();
    target.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: Text(widget.restore ? '从完整学习库备份恢复' : '备份全部学习库'),
      content: SizedBox(
        width: 700,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.restore ? '恢复整个包到新空目录。原学习库保持；校验全部文件、数据库及关系通过后才切换启动配置。' : '范围是全部空间（含归档）、原件/媒体、工作副本、确认版、学习记录和已落盘草稿。备份默认不加密，含私人学习数据，请妥善保管。',
              ),
              const Text(
                '操作会关闭页面并停止本地服务。先保留所有页面草稿，包括未提交作答和未保存正文；不会自动提交答案或替换原文件，草稿保存失败就取消操作。',
              ),
              if (!widget.restore && spaces != null) ...[
                const Text('本次包含的工作空间：'),
                for (final space in spaces!)
                  Text(
                    '• ${space['name']}${space['archived'] == true ? '（已归档）' : ''}',
                  ),
              ],
              if (!widget.restore && spaces == null)
                TextButton(
                  onPressed: busy ? null : load,
                  child: const Text('重试读取全部空间范围'),
                ),
              TextField(
                key: const ValueKey('backup-zip-path'),
                controller: zip,
                enabled: !busy,
                decoration: InputDecoration(
                  labelText: widget.restore
                      ? '备份ZIP绝对路径'
                      : '新备份ZIP绝对路径（数据目录之外）',
                ),
              ),
              TextButton(
                onPressed: busy ? null : pick,
                child: Text(widget.restore ? '选择备份包' : '选择备份保存位置'),
              ),
              if (widget.restore) ...[
                TextField(
                  key: const ValueKey('backup-target-path'),
                  controller: target,
                  enabled: !busy,
                  decoration: const InputDecoration(labelText: '新空数据目录（绝对路径）'),
                ),
                TextButton(
                  onPressed: busy ? null : () => pick(directory: true),
                  child: const Text('选择新空目录'),
                ),
              ],
              CheckboxListTile(
                value: confirmed,
                controlAffinity: ListTileControlAffinity.leading,
                onChanged: busy
                    ? null
                    : (value) => setState(() => confirmed = value == true),
                title: Text(
                  widget.restore
                      ? '确认恢复全部空间到新空目录，原库保留'
                      : '确认备份全部空间（包括归档），已知包未加密',
                ),
              ),
              const Text(
                '预算：100000文件、100GiB总量、单文件8GiB、单条记录64MiB。暂存及校验需要额外空间，失败现场保留，可换新空目录重试。',
              ),
              if (error != null) SelectableText(error!),
              if (busy) const LinearProgressIndicator(),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: busy || !confirmed || !widget.restore && spaces == null
              ? null
              : submit,
          child: const Text('确认并开始离线操作'),
        ),
      ],
    ),
  );
}

String libraryStageLabel(String stage) => switch (stage) {
  'scanning' => '正在检查学习库文件',
  'database-backup' || 'database-check' || 'table-rows' => '正在生成并核验数据快照',
  'packing-file' ||
  'packing-chunk' ||
  'publishing' ||
  'publishing-chunk' => '正在打包并保存学习资料',
  'zip-directory' || 'payload-hashing' || 'hashing' => '正在校验备份字节',
  'restoring-file' || 'restoring-chunk' => '正在恢复到临时目录',
  'restore-validated' || 'promoting-chunk' => '正在校验并写入新数据目录',
  'before-settings' => '核验通过，正在切换数据位置',
  _ => '正在处理学习库，请稍候',
};
