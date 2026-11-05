import 'dart:io';

bool isCurrentLibraryPlayer(String? expected, String? current) {
  if (expected == null || current != expected) return false;
  final uri = Uri.tryParse(expected);
  return uri != null &&
      RegExp(r'^/media/library/[a-f0-9]{32}/player$').hasMatch(uri.path) &&
      allowedPlayerResource(expected, current!);
}

bool allowedPlayerResource(String primaryUrl, String requestedUrl) {
  final primary = Uri.tryParse(primaryUrl);
  final candidate = Uri.tryParse(requestedUrl);
  if (primary == null ||
      primary.scheme != 'http' ||
      primary.host != '127.0.0.1' ||
      candidate == null) {
    return false;
  }
  if (requestedUrl.startsWith('blob:${primary.origin}/')) return true;
  if (candidate.scheme != primary.scheme ||
      candidate.userInfo.isNotEmpty ||
      candidate.origin != primary.origin) {
    return false;
  }
  final capability = primary.queryParameters['cap'];
  return capability != null &&
      capability.isNotEmpty &&
      candidate.queryParameters.length == 1 &&
      candidate.queryParameters['cap'] == capability &&
      ['/player', '/content', '/state'].any(
        (suffix) =>
            candidate.path ==
            primary.path.replaceFirst(RegExp(r'/player$'), suffix),
      );
}

bool publicHttpsUrl(String value) {
  final uri = Uri.tryParse(value);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      uri.host.isEmpty) {
    return false;
  }
  if (uri.hasPort && uri.port != 443) return false;
  final host = uri.host.toLowerCase();
  if (!host.contains('.') ||
      host.endsWith('.') ||
      host.endsWith('.localhost') ||
      host.endsWith('.local') ||
      host.endsWith('.internal')) {
    return false;
  }
  if (InternetAddress.tryParse(host) != null ||
      RegExp(r'^[0-9.]+$').hasMatch(host)) {
    return false;
  }
  return true;
}

Future<bool> resolvesPublicly(String value) async {
  if (!publicHttpsUrl(value)) return false;
  try {
    final addresses = await InternetAddress.lookup(Uri.parse(value).host)
        .timeout(const Duration(seconds: 3));
    return addresses.isNotEmpty &&
        addresses.every((address) {
          final b = address.rawAddress;
          if (b.length == 16) return b[0] & 0xe0 == 0x20;
          return !(b[0] == 0 ||
              b[0] == 10 ||
              b[0] == 127 ||
              b[0] >= 224 ||
              (b[0] == 169 && b[1] == 254) ||
              (b[0] == 172 && b[1] >= 16 && b[1] <= 31) ||
              (b[0] == 192 && b[1] == 168) ||
              (b[0] == 100 && b[1] >= 64 && b[1] <= 127));
        });
  } catch (_) {
    return false;
  }
}
