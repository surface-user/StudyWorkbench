import 'package:url_launcher/url_launcher.dart';

import 'url_policy.dart';

Future<bool> _launchBrowser(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.externalApplication);

Future<void> openExternalPage(
  String value, {
  Future<bool> Function(String) validate = resolvesPublicly,
  Future<bool> Function(Uri) launch = _launchBrowser,
}) async {
  if (!await validate(value)) {
    throw ArgumentError('仅允许可解析到公网的 HTTPS 页面');
  }
  if (!await launch(Uri.parse(value))) {
    throw StateError('系统浏览器未能打开，请检查 Windows 默认浏览器设置');
  }
}
