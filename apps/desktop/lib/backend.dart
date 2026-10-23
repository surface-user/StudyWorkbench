import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

class Backend {
  Backend(this.process, this.port, this.token, this.dataDir);
  final Process process;
  final int port;
  final String token;
  final String dataDir;
  final _http = HttpClient();

  static Future<Backend> start() async {
    const root = String.fromEnvironment('STUDY_ROOT');
    const media = String.fromEnvironment('STUDY_MEDIA');
    const testData = String.fromEnvironment('STUDY_DATA_DIR');
    // Build-time override isolates technical tests; user-facing directory settings belong to M1.
    final data = testData.isEmpty
        ? '${Platform.environment['LOCALAPPDATA']!}/StudyWorkbench/m0'
        : testData;
    if (!Directory(data).isAbsolute) {
      throw ArgumentError('STUDY_DATA_DIR 必须使用绝对路径');
    }
    final random = Random.secure();
    final token = base64Url.encode(
      List.generate(32, (_) => random.nextInt(256)),
    );
    final executable = File(Platform.resolvedExecutable).parent.path;
    final process = await Process.start(
      root.isEmpty
          ? '$executable/backend/study_backend.exe'
          : '$root/.venv/Scripts/python.exe',
      [
        if (root.isNotEmpty) ...['-m', 'study_workbench'],
        '--data-dir',
        data,
        if (media.isNotEmpty) ...['--media', media],
      ],
      workingDirectory: root.isEmpty ? executable : '$root/backend',
    );
    final errors = StringBuffer();
    process.stderr.transform(utf8.decoder).listen((part) {
      if (errors.length < 4096) errors.write(part);
    });
    process.stdin.writeln(jsonEncode({'token': token}));
    try {
      final line = await process.stdout
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .first
          .timeout(const Duration(seconds: 20));
      final hello = jsonDecode(line) as Map<String, dynamic>;
      if (hello['api_version'] != 0 || hello['port'] is! int) {
        throw const FormatException('后端协议不匹配');
      }
      final backend = Backend(process, hello['port'] as int, token, data);
      for (var i = 0; i < 40; i++) {
        try {
          await backend.request('GET', '/api/health');
          return backend;
        } on SocketException {
          await Future<void>.delayed(const Duration(milliseconds: 100));
        }
      }
      backend.close();
      throw StateError('后端未就绪');
    } catch (_) {
      process.kill();
      throw StateError('无法启动本地后端：$errors');
    }
  }

  Future<dynamic> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    final request = await _http
        .openUrl(method, Uri.parse('http://127.0.0.1:$port$path'))
        .timeout(const Duration(seconds: 5));
    request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
    if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    final response = await request.close().timeout(const Duration(seconds: 5));
    final text = await utf8.decoder
        .bind(response)
        .join()
        .timeout(const Duration(seconds: 5));
    if (response.statusCode != 200) {
      throw HttpException('请求失败 ${response.statusCode}');
    }
    return path == '/api/player' ? text : jsonDecode(text);
  }

  Future<String> player() async =>
      (await request('GET', '/api/player') as String).replaceAll(
        '__ORIGIN__',
        'http://127.0.0.1:$port',
      );

  void close() {
    _http.close(force: true);
    process.stdin.close();
    process.kill();
  }
}
