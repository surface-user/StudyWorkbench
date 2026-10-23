import 'dart:io';

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
