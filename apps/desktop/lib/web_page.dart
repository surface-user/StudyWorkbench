import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:url_launcher/url_launcher.dart';

import 'url_policy.dart';
import 'webview_lifecycle.dart';

class WebPage extends StatefulWidget {
  const WebPage({required this.profile, this.html, super.key});
  final String profile;
  final String? html;
  @override
  State<WebPage> createState() => _WebPageState();
}

class _WebPageState extends State<WebPage> {
  final address = TextEditingController(text: 'https://example.com');
  WebViewEnvironment? environment;
  InAppWebViewController? controller;
  String? error;
  bool ready = false;
  bool get player => widget.html != null;
  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      if (await WebViewEnvironment.getAvailableVersion() == null) {
        throw StateError('未安装 WebView2 Runtime，请安装后重试或使用系统浏览器');
      }
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
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> navigate() async {
    if (!await resolvesPublicly(address.text)) {
      if (mounted) setState(() => error = '仅允许可解析到公网的 HTTPS 页面');
      return;
    }
    if (mounted) setState(() => error = null);
    await controller?.loadUrl(
      urlRequest: URLRequest(url: WebUri(address.text)),
    );
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
                onPressed: () async {
                  if (await resolvesPublicly(address.text)) {
                    await launchUrl(
                      Uri.parse(address.text),
                      mode: LaunchMode.externalApplication,
                    );
                  }
                },
                child: const Text('系统浏览器'),
              ),
            ],
          ),
        ),
      if (error != null)
        Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
      Expanded(
        child: !ready
            ? Center(child: Text(error ?? '正在初始化 WebView2…'))
            : InAppWebView(
                webViewEnvironment: environment,
                initialData: InAppWebViewInitialData(
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
                onCreateWindow: (_, _) async => false,
                onPermissionRequest: (_, request) async => PermissionResponse(
                  resources: request.resources,
                  action: PermissionResponseAction.DENY,
                ),
                shouldOverrideUrlLoading: (_, action) async {
                  if (player) return NavigationActionPolicy.CANCEL;
                  return await resolvesPublicly(action.request.url.toString())
                      ? NavigationActionPolicy.ALLOW
                      : NavigationActionPolicy.CANCEL;
                },
                shouldInterceptRequest: (_, request) async {
                  final url = request.url.toString();
                  final allowed = player
                      ? url.startsWith('http://127.0.0.1:') &&
                            Uri.parse(url).path == '/media/demo'
                      : await resolvesPublicly(url);
                  if (allowed) return null;
                  return WebResourceResponse(
                    data: Uint8List(0),
                    statusCode: 403,
                    reasonPhrase: 'Blocked',
                  );
                },
                onReceivedError: (_, request, failure) {
                  if (request.isForMainFrame == true && mounted) {
                    setState(() => error = '网页加载失败：${failure.description}');
                  }
                },
              ),
      ),
    ],
  );
}
