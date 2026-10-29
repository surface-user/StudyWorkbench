import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

/// Windows 0.6.0 creates the disposal channel using the static object's ID
/// instead of the returned environment's ID. See ADR 0002 before upgrading.
final _releases = <Future<void>>{};

Future<void> drainWebEnvironments() async {
  await Future.wait(_releases.toList());
}

Future<void> releaseWebEnvironment(WebViewEnvironment environment) {
  final release = _release(environment);
  _releases.add(release);
  return release.whenComplete(() => _releases.remove(release));
}

Future<void> _release(WebViewEnvironment environment) async {
  if (Platform.isWindows) {
    await MethodChannel(
      'com.pichillilorenzo/flutter_webview_environment_${environment.id}',
    ).invokeMethod<void>('dispose');
  } else {
    await environment.dispose();
  }
}
