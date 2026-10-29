import 'dart:async';

import 'dart:ui' show AppExitResponse;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:lightweight_liquid_glass/lightweight_liquid_glass.dart';

import 'backend.dart';
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
    if (starting) return;
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
          if (mounted &&
              identical(backend, startedService) &&
              !migrating &&
              !closing) {
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
    backend?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Column(
      children: [
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
