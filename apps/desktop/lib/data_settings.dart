import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class DataSettings extends StatefulWidget {
  const DataSettings({
    required this.initial,
    required this.firstRun,
    super.key,
  });
  final String initial;
  final bool firstRun;
  @override
  State<DataSettings> createState() => _DataSettingsState();
}

class _DataSettingsState extends State<DataSettings> {
  late final path = TextEditingController(text: widget.initial);
  String? error;
  bool selecting = false;
  @override
  void dispose() {
    path.dispose();
    super.dispose();
  }

  Future<void> choose() async {
    setState(() => selecting = true);
    try {
      final value = await const MethodChannel('study/desktop')
          .invokeMethod<String>('chooseDirectory');
      if (value != null && mounted) path.text = value;
    } catch (failure) {
      if (mounted) setState(() => error = '无法选择文件夹，可直接输入绝对路径：$failure');
    } finally {
      if (mounted) setState(() => selecting = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.firstRun ? '选择学习数据位置' : '数据与存储设置'),
    content: SizedBox(
      width: 580,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.firstRun
                ? '学习记录、原文件与页面状态保存在此目录。检测到旧 M0 数据时默认继续使用，可在设置中迁移。'
                : '当前数据目录：${widget.initial}\n迁移将关闭全部页面，复制并校验学习数据后重新打开。原目录始终保留，不覆盖非空目标文件夹。',
          ),
          const SizedBox(height: 16),
          TextField(
            key: const ValueKey('data-directory'),
            controller: path,
            decoration: InputDecoration(
              labelText: widget.firstRun ? '数据文件夹（绝对路径）' : '新的空数据文件夹（绝对路径）',
            ),
          ),
          TextButton.icon(
            onPressed: selecting ? null : choose,
            icon: const Icon(Icons.folder_open),
            label: const Text('选择文件夹'),
          ),
          if (error != null)
            Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ],
      ),
    ),
    actions: [
      if (!widget.firstRun)
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
      FilledButton(
        onPressed: selecting
            ? null
            : () {
                if (path.text.trim().isEmpty) {
                  setState(() => error = '请选择或输入数据文件夹');
                  return;
                }
                Navigator.pop(context, path.text.trim());
              },
        child: Text(widget.firstRun ? '使用此位置并启动' : '确认迁移并重启工作台'),
      ),
    ],
  );
}

Future<String?> showDataSettings(
  BuildContext context, {
  required String initial,
  required bool firstRun,
}) => showDialog<String>(
  context: context,
  barrierDismissible: !firstRun,
  builder: (_) => DataSettings(initial: initial, firstRun: firstRun),
);
