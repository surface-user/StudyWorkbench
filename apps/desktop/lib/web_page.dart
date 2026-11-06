import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

import 'external_page.dart';
import 'page_activity.dart';
import 'url_policy.dart';
import 'webview_lifecycle.dart';

class PlayerCommands {
  PlayerCommands({required this.readPositionMs, required this.seekToMs});
  final Future<int?> Function() readPositionMs;
  final Future<bool> Function(int) seekToMs;
}

class WebPage extends StatefulWidget {
  const WebPage({
    required this.profile,
    this.html,
    this.initialUrl,
    this.onUrlChanged,
    this.playerUrl,
    this.onActivity,
    this.onPlayerReady,
    super.key,
  });
  final String profile;
  final String? html;
  final String? initialUrl;
  final ValueChanged<String>? onUrlChanged;
  final String? playerUrl;
  final PageActivityChanged? onActivity;
  final ValueChanged<PlayerCommands>? onPlayerReady;
  @override
  State<WebPage> createState() => _WebPageState();
}

class _WebPageState extends State<WebPage> {
  late final address = TextEditingController(
    text: widget.initialUrl ?? 'https://example.com',
  );
  String? restoreUrl;
  WebViewEnvironment? environment;
  InAppWebViewController? controller;
  String? error;
  bool ready = false;
  bool pageLoading = true;
  bool openingExternal = false;
  bool initializing = false;
  bool missingRuntime = false;
  bool get player => widget.html != null || widget.playerUrl != null;

  Future<bool> trustedPlayer() async =>
      widget.playerUrl != null &&
      controller != null &&
      isCurrentLibraryPlayer(
        widget.playerUrl,
        (await controller!.getUrl())?.toString(),
      );

  Future<int?> readPositionMs() async {
    if (!await trustedPlayer()) return null;
    final value = await controller!.evaluateJavascript(
      source: "(()=>{const v=document.getElementById('video');return v&&v.readyState>=1&&Number.isFinite(v.currentTime)?Math.floor(v.currentTime*1000):null})()",
    );
    if (value is! num || !value.isFinite || value < 0 || value > 604800000) {
      return null;
    }
    return value.toInt();
  }

  Future<bool> seekToMs(int milliseconds) async {
    if (milliseconds < 0 ||
        milliseconds > 604800000 ||
        !await trustedPlayer()) {
      return false;
    }
    return await controller!.evaluateJavascript(
          source:
              "(()=>{const v=document.getElementById('video');if(!v)return false;const seek=()=>{if(Number.isFinite(v.duration))v.currentTime=Math.min($milliseconds/1000,v.duration)};if(v.readyState>=1)seek();else v.addEventListener('loadedmetadata',seek,{once:true});return true})()",
        ) ==
        true;
  }

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    if (initializing || ready) return;
    initializing = true;
    widget.onActivity?.call(loading: true);
    try {
      if (!player && widget.initialUrl != null) {
        if (await resolvesPublicly(widget.initialUrl!)) {
          restoreUrl = widget.initialUrl;
        } else {
          error = '上次的网页地址暂时无法安全加载，可修改地址后重试';
        }
      }
      if (await WebViewEnvironment.getAvailableVersion() == null) {
        missingRuntime = true;
        throw StateError('未安装 WebView2 Runtime，请安装后重试或使用系统浏览器');
      }
      missingRuntime = false;
      Directory(widget.profile).createSync(recursive: true);
      final env = await WebViewEnvironment.create(
        settings: WebViewEnvironmentSettings(userDataFolder: widget.profile),
      );
      if (!mounted) {
        await releaseWebEnvironment(env);
        return;
      }
      setState(() {
        environment = env;
        ready = true;
      });
    } catch (e) {
      if (mounted) {
        setState(() => error = '$e');
        widget.onActivity?.call(loading: false, error: error);
      }
    } finally {
      if (mounted) setState(() => initializing = false);
    }
  }

  Future<void> navigate() async {
    if (!await resolvesPublicly(address.text)) {
      if (mounted) {
        setState(() => error = '仅允许可解析到公网的 HTTPS 页面');
        widget.onActivity?.call(loading: false, error: error);
      }
      return;
    }
    if (!mounted) return;
    setState(() => error = null);
    await controller?.loadUrl(
      urlRequest: URLRequest(url: WebUri(address.text)),
    );
  }

  Future<void> openBrowser() async {
    if (openingExternal) return;
    setState(() {
      openingExternal = true;
      error = null;
    });
    try {
      await openExternalPage(address.text);
    } catch (failure) {
      if (mounted) setState(() => error = '无法打开系统浏览器：$failure');
    } finally {
      if (mounted) setState(() => openingExternal = false);
    }
  }

  @override
  void dispose() {
    address.dispose();
    final env = environment;
    if (env != null) {
      releaseWebEnvironment(env).catchError((Object error, StackTrace stack) {
        FlutterError.reportError(
          FlutterErrorDetails(exception: error, stack: stack),
        );
      });
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      if (!player)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              IconButton(
                tooltip: '后退',
                onPressed: () => controller?.goBack(),
                icon: const Icon(Icons.arrow_back),
              ),
              IconButton(
                tooltip: '前进',
                onPressed: () => controller?.goForward(),
                icon: const Icon(Icons.arrow_forward),
              ),
              IconButton(
                tooltip: '刷新',
                onPressed: () => controller?.reload(),
                icon: const Icon(Icons.refresh),
              ),
              Expanded(
                child: TextField(
                  controller: address,
                  onSubmitted: (_) => navigate(),
                  decoration: const InputDecoration(labelText: '网页地址（HTTPS）'),
                ),
              ),
              TextButton(onPressed: navigate, child: const Text('打开网页')),
              TextButton(
                onPressed: openingExternal ? null : openBrowser,
                child: const Text('系统浏览器'),
              ),
            ],
          ),
        ),
      if (error != null)
        Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
      if (!ready && !initializing)
        Wrap(
          children: [
            TextButton(onPressed: _initialize, child: const Text('重试初始化网页组件')),
            if (missingRuntime)
              TextButton(
                onPressed: () async {
                  try {
                    await openExternalPage(
                      'https://developer.microsoft.com/microsoft-edge/webview2/',
                    );
                  } catch (failure) {
                    if (mounted) {
                      setState(() => error = '无法打开 Runtime 下载页：$failure');
                    }
                  }
                },
                child: const Text('下载 Microsoft WebView2 Runtime'),
              ),
          ],
        ),
      Expanded(
        child: !ready
            ? Center(child: Text(error ?? '正在初始化 WebView2…'))
            : InAppWebView(
                webViewEnvironment: environment,
                initialUrlRequest: widget.playerUrl != null
                    ? URLRequest(url: WebUri(widget.playerUrl!))
                    : restoreUrl == null
                    ? null
                    : URLRequest(url: WebUri(restoreUrl!)),
                initialData: restoreUrl != null || widget.playerUrl != null
                    ? null
                    : InAppWebViewInitialData(
                        data: player ? widget.html! : '<!doctype html><html lang="zh"><meta charset="utf-8"><h2>内置网页</h2><p>输入 HTTPS 网址后选择打开网页。</p></html>',
                      ),
                initialSettings: InAppWebViewSettings(
                  useShouldOverrideUrlLoading: true,
                  useShouldInterceptRequest: true,
                  isInspectable: false,
                  supportMultipleWindows: false,
                  mediaPlaybackRequiresUserGesture: true,
                ),
                onWebViewCreated: (value) => controller = value,
                onLoadStart: (_, _) {
                  if (!mounted) return;
                  setState(() => error = null);
                  pageLoading = true;
                  widget.onActivity?.call(loading: true);
                },
                onTitleChanged: (_, title) {
                  if (!player && mounted) {
                    widget.onActivity?.call(
                      loading: pageLoading,
                      error: error,
                      title: title,
                    );
                  }
                },
                onLoadStop: (_, url) {
                  pageLoading = false;
                  widget.onActivity?.call(loading: false, error: error);
                  if (!mounted) return;
                  if (widget.playerUrl != null &&
                      url?.toString() == widget.playerUrl) {
                    widget.onPlayerReady?.call(
                      PlayerCommands(
                        readPositionMs: readPositionMs,
                        seekToMs: seekToMs,
                      ),
                    );
                  }
                  if (!player &&
                      url != null &&
                      publicHttpsUrl(url.toString())) {
                    address.text = url.toString();
                    widget.onUrlChanged?.call(url.toString());
                  }
                },
                onCreateWindow: (_, _) async => false,
                onPermissionRequest: (_, request) async => PermissionResponse(
                  resources: request.resources,
                  action: PermissionResponseAction.DENY,
                ),
                shouldOverrideUrlLoading: (_, action) async {
                  if (player) {
                    return widget.playerUrl != null &&
                            action.request.url.toString() == widget.playerUrl
                        ? NavigationActionPolicy.ALLOW
                        : NavigationActionPolicy.CANCEL;
                  }
                  return await resolvesPublicly(action.request.url.toString())
                      ? NavigationActionPolicy.ALLOW
                      : NavigationActionPolicy.CANCEL;
                },
                shouldInterceptRequest: (_, request) async {
                  final url = request.url.toString();
                  final primary = widget.playerUrl == null
                      ? null
                      : Uri.parse(widget.playerUrl!);
                  final localMedia =
                      primary != null &&
                      allowedPlayerResource(widget.playerUrl!, url);
                  final allowed =
                      player && primary == null && url.startsWith('blob:') ||
                      localMedia ||
                      (player && primary == null
                          ? url.startsWith('http://127.0.0.1:') &&
                                Uri.parse(url).path == '/media/demo'
                          : !player && await resolvesPublicly(url));
                  if (allowed) return null;
                  return WebResourceResponse(
                    data: Uint8List(0),
                    statusCode: 403,
                    reasonPhrase: 'Blocked',
                  );
                },
                onReceivedHttpError: (_, request, response) {
                  if (request.isForMainFrame == true && mounted) {
                    setState(
                      () => error = '网页加载失败：HTTP ${response.statusCode}',
                    );
                    widget.onActivity?.call(loading: false, error: error);
                  }
                },
                onReceivedError: (_, request, failure) {
                  if (request.isForMainFrame == true && mounted) {
                    setState(() => error = '网页加载失败：${failure.description}');
                    widget.onActivity?.call(loading: false, error: error);
                  }
                },
              ),
      ),
    ],
  );
}
