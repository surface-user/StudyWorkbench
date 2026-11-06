import 'dart:async';

import 'dart:ui' show AppExitResponse;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:lightweight_liquid_glass/lightweight_liquid_glass.dart';

import 'backend.dart';
import 'analysis_review_dialog.dart';
import 'backup_dialog.dart';
import 'data_settings.dart';
import 'startup_failure.dart';
import 'webview_lifecycle.dart';
import 'workspace_shell.dart';

void main() => runApp(const StudyApp());

class StudyApp extends StatelessWidget {
  const StudyApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'StudyWorkbench · M1',
    debugShowCheckedModeBanner: false,
    locale: const Locale('zh', 'CN'),
    supportedLocales: const [Locale('zh', 'CN')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    theme: ThemeData(
      colorSchemeSeed: const Color(0xff426da9),
      fontFamily: 'Microsoft YaHei',
      extensions: const [LiquidGlassThemeData()],
    ),
    home: const Workbench(),
  );
}

class Workbench extends StatefulWidget {
  const Workbench({super.key});
  @override
  State<Workbench> createState() => _WorkbenchState();
}

class _WorkbenchState extends State<Workbench> with WidgetsBindingObserver {
  Backend? backend;
  String? error;
  String? playerHtml;
  bool starting = false;
  bool migrating = false;
  bool closing = false;
  bool recovering = false;
  String? connectionError;
  OfflineLibraryOperation? libraryWorker;
  String libraryProgress = '';
  final shellKey = GlobalKey<WorkspaceShellState>();
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
  }

  Future<void> _start({
    String? dataDir,
    Map<String, Map<String, dynamic>>? recoveredLayouts,
  }) async {
    if (starting || !mounted) return;
    setState(() {
      starting = true;
      error = null;
    });
    Backend? service;
    try {
      final data =
          dataDir ??
          await Backend.configuredData() ??
          await Backend.defaultData;
      if (!mounted) return;
      service = await Backend.start(dataDir: data);
      if (recoveredLayouts != null) {
        for (final entry in recoveredLayouts.entries) {
          await service.request(
            'PUT',
            '/api/workspaces/${entry.key}/layout',
            entry.value,
          );
        }
      }
      final html = await service.player();
      if (!mounted) {
        service.close();
        return;
      }
      setState(() {
        backend = service;
        playerHtml = html;
        connectionError = null;
      });
      final startedService = service;
      unawaited(
        service.process.exitCode.then((code) {
          if (mounted && identical(backend, startedService) && !closing) {
            setState(() => connectionError = '本地后端已停止（退出码 $code），当前页面草稿仍保留。');
          }
        }),
      );
    } catch (e) {
      service?.close();
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => starting = false);
    }
  }

  Map<String, Map<String, dynamic>>? recoveryLayouts;
  String? recoveryDataDir;
  Future<void> _recover() async {
    if (starting || migrating || recovering) return;
    recovering = true;
    recoveryLayouts ??= shellKey.currentState?.layouts.map(
      (id, layout) => MapEntry(id, layout.toJson()),
    );
    final service = backend;
    recoveryDataDir ??= service?.dataDir;
    setState(() => backend = null);
    await WidgetsBinding.instance.endOfFrame;
    try {
      await drainWebEnvironments();
      service?.close();
      await _start(dataDir: recoveryDataDir, recoveredLayouts: recoveryLayouts);
      if (backend != null) {
        recoveryLayouts = null;
        recoveryDataDir = null;
      }
    } catch (failure) {
      if (mounted) setState(() => error = '页面释放失败，草稿仍保留，可重试：$failure');
    } finally {
      if (mounted) setState(() => recovering = false);
    }
  }

  Future<void> _chooseData() async {
    if (starting || migrating || recovering || recoveryLayouts != null) return;
    final initial = await Backend.defaultData;
    if (!mounted) return;
    final data = await showDataSettings(
      context,
      initial: initial,
      firstRun: true,
    );
    if (data != null && mounted) await _start(dataDir: data);
  }

  Future<void> _useDefault() async {
    try {
      final data = await Backend.defaultData;
      if (mounted) await _start(dataDir: data);
    } catch (failure) {
      if (mounted) setState(() => error = '$failure');
    }
  }

  Future<void> _settings() async {
    if (starting || migrating || recovering) return;
    final action = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('数据与学习库'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(context, 'move'),
            child: const Text('迁移数据位置'),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(context, 'backup'),
            child: const Text('备份全部学习库'),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(context, 'restore'),
            child: const Text('从完整备份恢复到新空目录'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    if (action == 'move') {
      await _migrateSettings();
    }
    if (action == 'backup') {
      await _library(restore: false);
    }
    if (action == 'restore') {
      await _library(restore: true);
    }
  }

  Future<void> _library({required bool restore}) async {
    if (starting || migrating || recovering || recoveryLayouts != null) return;
    final service = backend;
    if (!restore && service == null) return;
    final plan = await showDialog<LibraryBackupPlan>(
      context: context,
      barrierDismissible: false,
      builder: (_) => LibraryBackupDialog(restore: restore, backend: service),
    );
    if (plan == null || !mounted) return;
    String? config;
    String? priorConfigData;
    var activated = false;
    var activationUncertain = false;
    try {
      config = Backend.testData.isEmpty
          ? await Backend.settingsPath
          : '${Backend.testData}.settings.json';
      if (restore) {
        priorConfigData = await Backend.configuredData(configPath: config);
      }
      await flushAnalysisDraftEditors();
      await shellKey.currentState?.flush();
      if (!mounted) return;
      setState(() {
        migrating = true;
        backend = null;
        error = null;
        libraryProgress = '正在保存页面并停止本地服务';
      });
      await WidgetsBinding.instance.endOfFrame;
      try {
        await drainWebEnvironments();
      } finally {
        await service?.shutdown();
      }
      if (!mounted) return;
      libraryWorker = await Backend.libraryOperation(
        restore: restore,
        dataDir: restore ? plan.target! : service!.dataDir,
        zipPath: plan.zipPath,
        configPath: !restore && service?.startupWarning != null ? null : config,
        onStage: (stage) {
          if (mounted) {
            setState(() => libraryProgress = libraryStageLabel(stage));
          }
        },
      );
      if (mounted) setState(() {});
      final result = await libraryWorker!.done;
      libraryWorker = null;
      if (!mounted) return;
      if (restore &&
          (result['data_activated'] != true ||
              !await Backend.sameDataDirectory(
                result['data_dir'] as String?,
                plan.target,
              ))) {
        throw StateError('恢复结果与所选目录不符，先保留现场核对启动配置');
      }
      activated = restore;
      await _start(dataDir: restore ? plan.target : service!.dataDir);
      if (backend == null) throw StateError('文件已处理，但本地服务尚未重新启动：$error');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${restore ? '完整备份已恢复到新目录，原库保留' : '全部学习库备份完成'}${result['cleanup_pending'] == true ? '；已完成校验，暂存副本清理待处理' : ''}',
            ),
            duration: const Duration(seconds: 10),
          ),
        );
      }
    } catch (failure) {
      if (migrating && restore && config != null && !activated) {
        try {
          final current = await Backend.configuredData(configPath: config);
          activated = await Backend.sameDataDirectory(current, plan.target);
          activationUncertain =
              !activated &&
              current != priorConfigData &&
              !await Backend.sameDataDirectory(current, priorConfigData);
        } catch (_) {
          activationUncertain = true;
        }
      }
      if (migrating &&
          backend == null &&
          service != null &&
          !activated &&
          !activationUncertain) {
        await _start(dataDir: service.dataDir);
      }
      final message = activationUncertain
          ? '离线结果或当前数据位置未能确认，原库保留；请先核对启动配置再重试：$failure'
          : activated
          ? '新目录已完成激活，服务启动仍待恢复；原库保留：$failure'
          : '操作未完成，原库/启动配置及未完成字节保留：$failure';
      if (mounted) {
        if (backend == null) {
          setState(() => error = message);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(message),
              duration: const Duration(seconds: 15),
            ),
          );
        }
      }
    } finally {
      libraryWorker = null;
      if (mounted) {
        setState(() {
          migrating = false;
          libraryProgress = '';
        });
      }
    }
  }

  Future<void> _migrateSettings() async {
    final service = backend;
    if (service == null || migrating || starting) return;
    if (service.startupWarning != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('启动配置不可写，暂不能迁移。请先恢复配置目录的写入权限；当前数据目录保持不变。'),
        ),
      );
      return;
    }
    final target = await showDataSettings(
      context,
      initial: service.dataDir,
      firstRun: false,
    );
    if (target == null || target == service.dataDir || !mounted) return;
    try {
      await flushAnalysisDraftEditors();
      await shellKey.currentState?.flush();
    } catch (failure) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('迁移已取消，先保存页面：$failure')));
      }
      return;
    }
    setState(() {
      migrating = true;
      backend = null;
    });
    await WidgetsBinding.instance.endOfFrame;
    try {
      await drainWebEnvironments();
      await service.shutdown();
      await Backend.relocateData(
        service.dataDir,
        target,
        configPath: Backend.testData.isEmpty
            ? null
            : '${Backend.testData}.settings.json',
      );
      await _start(dataDir: target);
      if (backend == null) {
        final failure = error;
        await _start(dataDir: service.dataDir);
        throw StateError('目标目录重启失败，已尝试恢复原目录：$failure');
      }
    } catch (failure) {
      if (backend == null) await _start(dataDir: service.dataDir);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('$failure'),
            duration: const Duration(seconds: 12),
            action: SnackBarAction(label: '关闭提示', onPressed: () {}),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => migrating = false);
    }
  }

  @override
  Future<AppExitResponse> didRequestAppExit() async {
    if (migrating || starting || recovering) return AppExitResponse.cancel;
    try {
      await flushAnalysisDraftEditors();
      await shellKey.currentState?.flush();
    } catch (failure) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('页面尚未保存，退出已取消：$failure')));
      }
      return AppExitResponse.cancel;
    }
    closing = true;
    await backend?.shutdown();
    return AppExitResponse.exit;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    final operation = libraryWorker;
    if (operation != null) {
      unawaited(operation.cancel().catchError((Object _) {}));
    }
    backend?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Column(
      children: [
        if (migrating && libraryProgress.isNotEmpty)
          MaterialBanner(
            content: Text(libraryProgress),
            actions: [
              TextButton(
                onPressed:
                    libraryWorker == null ||
                        libraryWorker!.cancellationRequested
                    ? null
                    : () async {
                        await libraryWorker!.cancel();
                        if (mounted) {
                          setState(
                            () => libraryProgress = '正在停止，原库和未完成字节保留，请稍候',
                          );
                        }
                      },
                child: Text(
                  libraryWorker?.cancellationRequested == true
                      ? '正在停止'
                      : '取消离线操作',
                ),
              ),
            ],
          ),
        if (backend?.startupWarning != null)
          MaterialBanner(
            content: Text(
              '${backend!.startupWarning}\n当前数据目录：${backend!.dataDir}',
            ),
            actions: [
              TextButton(
                onPressed: () =>
                    Clipboard.setData(ClipboardData(text: backend!.dataDir)),
                child: const Text('复制数据位置'),
              ),
            ],
          ),
        if (connectionError != null)
          MaterialBanner(
            content: Text(connectionError!),
            actions: [
              TextButton(
                onPressed: starting || recovering ? null : _recover,
                child: const Text('重启后端并恢复页面'),
              ),
            ],
          ),
        Expanded(
          child: backend != null
              ? WorkspaceShell(
                  key: shellKey,
                  backend: backend!,
                  playerHtml: playerHtml!,
                  onSettings: _settings,
                  backendAvailable: connectionError == null,
                )
              : GlassBackdrop(
                  child: error != null
                      ? StartupFailure(
                          details: error!,
                          onRetry: recoveryLayouts == null ? _start : _recover,
                          onUseDefault: recoveryLayouts == null
                              ? _useDefault
                              : null,
                          onChooseData: recoveryLayouts == null
                              ? _chooseData
                              : null,
                          onRestoreBackup: recoveryLayouts == null
                              ? () => _library(restore: true)
                              : null,
                        )
                      : const Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              CircularProgressIndicator(),
                              SizedBox(height: 20),
                              Text('正在启动或迁移本地工作台，请勿关闭…'),
                            ],
                          ),
                        ),
                ),
        ),
      ],
    ),
  );
}
