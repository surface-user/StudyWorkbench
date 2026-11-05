import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class StartupFailure extends StatelessWidget {
  const StartupFailure({
    super.key,
    required this.details,
    required this.onRetry,
    this.onChooseData,
    this.onUseDefault,
    this.onRestoreBackup,
  });

  final String details;
  final VoidCallback onRetry;
  final VoidCallback? onChooseData;
  final VoidCallback? onUseDefault;
  final VoidCallback? onRestoreBackup;

  @override
  Widget build(BuildContext context) => Center(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '本地服务未能启动',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 12),
                const Text(
                  '请确认程序所在目录包含 backend 文件夹，且个人数据目录可以写入。'
                  '权限被拒绝时可使用默认数据位置；原目录和学习数据均保留。'
                  '处理后可点击重试；若仍失败，请复制错误详情用于排查。',
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    if (onRestoreBackup != null)
                      OutlinedButton.icon(
                        onPressed: onRestoreBackup,
                        icon: const Icon(Icons.restore),
                        label: const Text('从完整学习库备份恢复'),
                      ),
                    if (onUseDefault != null)
                      FilledButton(
                        onPressed: onUseDefault,
                        child: const Text('使用默认数据位置'),
                      ),
                    FilledButton.icon(
                      onPressed: onRetry,
                      icon: const Icon(Icons.refresh),
                      label: const Text('重新启动本地服务'),
                    ),
                    if (onChooseData != null)
                      OutlinedButton.icon(
                        onPressed: onChooseData,
                        icon: const Icon(Icons.folder_open),
                        label: const Text('重新选择数据位置'),
                      ),
                    OutlinedButton.icon(
                      onPressed: () async {
                        try {
                          await Clipboard.setData(ClipboardData(text: details));
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('错误详情已复制，包含本机路径')),
                          );
                        } catch (_) {
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('复制失败，请在详情中选择文字复制')),
                          );
                        }
                      },
                      icon: const Icon(Icons.copy_outlined),
                      label: const Text('复制错误详情'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('错误详情（含本机路径）'),
                  children: [
                    Align(
                      alignment: Alignment.centerLeft,
                      child: SelectableText(details),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
