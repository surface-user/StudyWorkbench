import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/services.dart';

import 'question_contract.dart';

class BackendError extends HttpException {
  BackendError(this.statusCode, String message) : super(message);
  final int statusCode;
}

class Backend {
  Backend(
    this.process,
    this.port,
    this.token,
    this.dataDir, {
    this.startupWarning,
  });
  final Process process;
  final int port;
  final String token;
  final String dataDir;
  final String? startupWarning;
  final _http = HttpClient();

  static const testData = String.fromEnvironment('STUDY_DATA_DIR');
  static Future<String> _windowsDirectory(String method) async {
    final root = await const MethodChannel('study/desktop')
        .invokeMethod<String>(method);
    if (root == null || !Directory(root).isAbsolute) {
      throw const FormatException('无法确定Windows用户数据目录，请通过数据位置恢复入口选择目录');
    }
    return root;
  }

  static Future<String> get storageRoot => _windowsDirectory('storageRoot');

  static Future<String> get settingsPath async =>
      '${await _windowsDirectory('settingsRoot')}/settings.json';
  static Future<bool> sameDataDirectory(String? first, String? second) async {
    if (first == null || second == null) return false;
    try {
      return await FileSystemEntity.identical(first, second);
    } on FileSystemException {
      return false;
    }
  }

  static Future<String?> configuredData({String? configPath}) async {
    if (configPath == null && testData.isNotEmpty) {
      final isolated = '$testData.settings.json';
      if (!await File(isolated).exists()) return testData;
      configPath = isolated;
    }
    var file = File(configPath ?? await settingsPath);
    // Keep explicit selections saved by older builds, even when the runtime profile changes.
    if (configPath == null && !await file.exists()) {
      final legacy = File(
        '${Platform.environment['LOCALAPPDATA']!}/StudyWorkbench/settings.json',
      );
      if (await legacy.exists()) file = legacy;
    }
    if (!await file.exists()) return null;
    final settings =
        jsonDecode(await file.readAsString()) as Map<String, dynamic>;
    if (settings['version'] != 1 ||
        settings['data_dir'] is! String ||
        !Directory(settings['data_dir']).isAbsolute) {
      throw const FormatException('数据位置配置无效，请保留配置文件并重新选择原数据目录');
    }
    return settings['data_dir'] as String;
  }

  static Future<String> get defaultData async {
    final home = await storageRoot;
    return await File('$home/m0/study.db').exists() ? '$home/m0' : '$home/data';
  }

  static Future<Backend> start({String? dataDir, String? configPath}) async {
    const root = String.fromEnvironment('STUDY_ROOT');
    const media = String.fromEnvironment('STUDY_MEDIA');
    final data = dataDir ?? await configuredData() ?? await defaultData;
    final config = configPath ?? (testData.isEmpty ? await settingsPath : null);
    if (!Directory(data).isAbsolute) {
      throw ArgumentError('STUDY_DATA_DIR 必须使用绝对路径');
    }
    final random = Random.secure();
    final token = base64Url.encode(
      List.generate(32, (_) => random.nextInt(256)),
    );
    final executable = File(Platform.resolvedExecutable).parent.path;
    final backendExecutable = root.isEmpty
        ? '$executable/backend/study_backend.exe'
        : '$root/.venv/Scripts/python.exe';
    final Process process;
    try {
      process = await Process.start(
        backendExecutable,
        [
          if (root.isNotEmpty) ...['-m', 'study_workbench'],
          '--data-dir',
          data,
          if (config != null) ...['--config', config],
          '--install-dir',
          executable,
          if (media.isNotEmpty) ...['--media', media],
        ],
        workingDirectory: root.isEmpty ? executable : '$root/backend',
        environment: {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
      );
    } on ProcessException catch (error) {
      throw StateError('无法运行本地后端：$backendExecutable\n数据目录：$data\n$error');
    }
    var errors = '';
    final stderrDone = Completer<void>();
    process.stderr.transform(const Utf8Decoder(allowMalformed: true)).listen((
      part,
    ) {
      errors += part;
      if (errors.length > 8192) errors = errors.substring(errors.length - 8192);
    }, onDone: () => stderrDone.complete());
    try {
      process.stdin.writeln(jsonEncode({'token': token}));
      final line = await process.stdout
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .first
          .timeout(const Duration(seconds: 20));
      final hello = jsonDecode(line) as Map<String, dynamic>;
      if (hello['api_version'] != 0 || hello['port'] is! int) {
        throw const FormatException('后端协议不匹配');
      }
      final backend = Backend(
        process,
        hello['port'] as int,
        token,
        data,
        startupWarning: hello['startup_warning'] as String?,
      );
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
    } catch (error) {
      process.kill();
      await stderrDone.future.timeout(
        const Duration(seconds: 2),
        onTimeout: () {},
      );
      throw StateError(
        '无法启动本地后端（数据目录：$data）：\n${errors.isEmpty ? error : errors}',
      );
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
    final response = await request.close().timeout(
      (path.contains('/media/') && path.endsWith('/player') ||
              path.contains('/document') ||
              path.contains('/question-file') ||
              path.contains('/question-versions/') ||
              path.endsWith('/file-preview') ||
              path.endsWith('/file') ||
              RegExp(r'/previews/[^/?]+/page(?:\?|$)').hasMatch(path) ||
              path.contains('/relative-image') ||
              path.contains('/learning-marks') ||
              path.endsWith('/learning-anchor') ||
              path.endsWith('/internal-links/resolve') ||
              path.contains('/learning-search?') ||
              RegExp(r'/nodes/[^/?]+$').hasMatch(path))
          ? const Duration(seconds: 60)
          : const Duration(seconds: 5),
    );
    final text = await utf8.decoder
        .bind(response)
        .join()
        .timeout(const Duration(seconds: 5));
    if (response.statusCode != 200) {
      var detail = '';
      try {
        final decoded = jsonDecode(text);
        if (decoded is Map && decoded['detail'] is String) {
          detail =
              ': ${(decoded['detail'] as String).substring(0, min(240, (decoded['detail'] as String).length))}';
        }
      } on FormatException {
        // Non-JSON errors should not expose raw backend tracebacks in the UI.
      }
      throw BackendError(
        response.statusCode,
        '请求失败 ${response.statusCode}$detail',
      );
    }
    if (path == '/api/player') return text;
    final decoded = jsonDecode(text);
    if (method == 'GET' && RegExp(r'/questions/[^/?]+$').hasMatch(path)) {
      final fileQuestion =
          decoded is Map && decoded['confirmed_version_id'] != null;
      final content = Map<String, dynamic>.from(decoded as Map)
        ..remove('confirmed_version_id')
        ..remove('resource_item_id');
      (await QuestionContract.load(
        bundle: false,
        fileQuestion: fileQuestion,
      )).validate(content, bundle: false);
    } else if (method == 'GET' &&
        (path.endsWith('/question-file') ||
            RegExp(r'/question-versions/[^/?]+$').hasMatch(path))) {
      (await QuestionContract.load(
        bundle: false,
        fileQuestion: true,
      )).validate(decoded['question'], bundle: false);
    }
    return decoded;
  }

  Future<String> player() async =>
      (await request('GET', '/api/player') as String).replaceAll(
        '__ORIGIN__',
        'http://127.0.0.1:$port',
      );

  Future<dynamic> uploadImport(
    String workspaceId,
    String filename,
    List<int> bytes,
  ) async {
    if (bytes.isEmpty || bytes.length > 8 * 1024 * 1024) {
      throw const FormatException('请选择非空且不超过 8 MiB 的文件');
    }
    final uri = Uri.http(
      '127.0.0.1:$port',
      '/api/workspaces/$workspaceId/imports',
      {'filename': filename},
    );
    final request = await _http
        .postUrl(uri)
        .timeout(const Duration(seconds: 5));
    request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
    request.headers.contentType = ContentType.binary;
    request.contentLength = bytes.length;
    request.add(bytes);
    final response = await request.close().timeout(const Duration(seconds: 30));
    final result = await utf8.decoder
        .bind(response)
        .join()
        .timeout(const Duration(seconds: 30));
    if (response.statusCode != 200) {
      throw HttpException('导入请求失败 ${response.statusCode}，请刷新导入记录核实状态');
    }
    final job = jsonDecode(result) as Map<String, dynamic>;
    if (job['preview']?['kind'] == 'questions') {
      (await QuestionContract.load()).validate(job['preview']['bundle']);
    }
    return job;
  }

  Future<Uint8List> exportArchive(String workspaceId) => _bytes(
    '/api/workspaces/${Uri.encodeComponent(workspaceId)}/export',
    160 * 1024 * 1024,
  );

  Future<dynamic> uploadMedia(
    String workspaceId,
    File file,
    ValueChangedProgress progress,
  ) async {
    final size = await file.length();
    if (size <= 0 || size > 512 * 1024 * 1024) {
      throw const FormatException('本地媒体须非空且不超过512MiB');
    }
    final uri = Uri.http(
      '127.0.0.1:$port',
      '/api/workspaces/$workspaceId/media/import',
      {'filename': file.uri.pathSegments.last},
    );
    final request = await _http
        .postUrl(uri)
        .timeout(const Duration(seconds: 5));
    request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
    request.headers.contentType = ContentType.binary;
    request.contentLength = size;
    var sent = 0;
    await request
        .addStream(
          file.openRead(0, size).map((chunk) {
            sent += chunk.length;
            progress(sent / size);
            return chunk;
          }),
        )
        .timeout(const Duration(minutes: 5));
    final response = await request.close().timeout(const Duration(minutes: 2));
    final text = await utf8.decoder
        .bind(response)
        .join()
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw HttpException('媒体入库未完成 ${response.statusCode}，请刷新记录核对；原文件保留');
    }
    return jsonDecode(text);
  }

  Future<Uint8List> resourceBytes(
    String workspaceId,
    String resourceId,
  ) => _bytes(
    '/api/workspaces/${Uri.encodeComponent(workspaceId)}/resources/${Uri.encodeComponent(resourceId)}',
    8 * 1024 * 1024,
  );

  Future<Uint8List> _bytes(String path, int limit) async {
    final request = await _http
        .getUrl(Uri.parse('http://127.0.0.1:$port$path'))
        .timeout(const Duration(seconds: 5));
    request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
    final response = await request.close().timeout(const Duration(seconds: 5));
    final bytes = BytesBuilder(copy: false);
    await for (final chunk in response.timeout(const Duration(seconds: 10))) {
      bytes.add(chunk);
      if (bytes.length > limit) {
        throw const FormatException('附件超过大小限制');
      }
    }
    if (response.statusCode != 200) {
      throw HttpException('附件读取失败 ${response.statusCode}');
    }
    return bytes.takeBytes();
  }

  void close() {
    _http.close(force: true);
    process.stdin.close();
    process.kill();
  }

  Future<void> shutdown() async {
    _http.close(force: true);
    await process.stdin.close();
    try {
      await process.exitCode.timeout(const Duration(seconds: 10));
    } on TimeoutException {
      process.kill();
      await process.exitCode.timeout(const Duration(seconds: 5));
    }
  }

  static Future<void> relocateData(
    String source,
    String target, {
    String? configPath,
  }) async {
    const root = String.fromEnvironment('STUDY_ROOT');
    final executable = File(Platform.resolvedExecutable).parent.path;
    final worker = await Process.start(
      root.isEmpty
          ? '$executable/backend/study_backend.exe'
          : '$root/.venv/Scripts/python.exe',
      [
        if (root.isNotEmpty) ...['-m', 'study_workbench'],
        '--data-dir',
        source,
        '--move-data',
        target,
        '--parent-pipe',
        '--config',
        configPath ?? await settingsPath,
        '--install-dir',
        executable,
      ],
      workingDirectory: root.isEmpty ? executable : '$root/backend',
      environment: {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
    );
    final output = worker.stdout.drain<void>();
    var errors = '';
    final stderr = worker.stderr
        .transform(const Utf8Decoder(allowMalformed: true))
        .listen((part) {
          errors += part;
          if (errors.length > 8192) {
            errors = errors.substring(errors.length - 8192);
          }
        })
        .asFuture<void>();
    final int exitCode;
    try {
      exitCode = await worker.exitCode;
      await output;
      await stderr;
    } finally {
      await worker.stdin.close();
    }
    if (exitCode != 0) {
      final lines = const LineSplitter()
          .convert(errors)
          .where((line) => line.trim().isNotEmpty)
          .toList();
      final text = lines.isEmpty ? '后端未能完成迁移（$exitCode）' : lines.last;
      throw StateError(
        '数据迁移失败，旧目录保留：${text.substring(max(0, text.length - 240))}',
      );
    }
  }

  static Future<OfflineLibraryOperation> libraryOperation({
    required bool restore,
    required String dataDir,
    required String zipPath,
    String? configPath,
    ValueChangedStage? onStage,
  }) async {
    const root = String.fromEnvironment('STUDY_ROOT');
    final executable = File(Platform.resolvedExecutable).parent.path;
    final worker = await Process.start(
      root.isEmpty
          ? '$executable/backend/study_backend.exe'
          : '$root/.venv/Scripts/python.exe',
      [
        if (root.isNotEmpty) ...['-m', 'study_workbench'],
        '--data-dir',
        dataDir,
        restore ? '--restore-backup' : '--backup-to',
        zipPath,
        if (!restore) '--confirm-all-workspaces',
        if (configPath != null) ...['--config', configPath],
        '--parent-pipe',
        '--install-dir',
        executable,
      ],
      workingDirectory: root.isEmpty ? executable : '$root/backend',
      environment: {'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
    );
    return OfflineLibraryOperation(worker, onStage: onStage);
  }
}

typedef ValueChangedProgress = void Function(double value);
typedef ValueChangedStage = void Function(String stage);

class OfflineLibraryOperation {
  OfflineLibraryOperation(this.process, {ValueChangedStage? onStage}) {
    done = _wait(onStage);
  }
  final Process process;
  late final Future<Map<String, dynamic>> done;
  bool cancellationRequested = false;
  Future<void> cancel() async {
    if (cancellationRequested) return;
    cancellationRequested = true;
    await process.stdin.close();
  }

  Future<Map<String, dynamic>> _wait(ValueChangedStage? onStage) async {
    Map<String, dynamic>? result;
    String? protocolError;
    var errors = '';
    final output = process.stdout
        .transform(const Utf8Decoder(allowMalformed: true))
        .transform(const LineSplitter())
        .listen((line) {
          try {
            final message = jsonDecode(line) as Map;
            if (message['stage'] is String) {
              onStage?.call(message['stage'] as String);
            }
            if (message['result'] is Map) {
              result = Map<String, dynamic>.from(message['result'] as Map);
            }
          } catch (_) {
            protocolError = '离线进程返回了无法确认的结果';
          }
        })
        .asFuture<void>();
    final stderr = process.stderr
        .transform(const Utf8Decoder(allowMalformed: true))
        .listen((part) {
          errors += part;
          if (errors.length > 8192) {
            errors = errors.substring(errors.length - 8192);
          }
        })
        .asFuture<void>();
    try {
      final exitCode = await process.exitCode;
      await output;
      await stderr;
      if (exitCode != 0 || result == null || protocolError != null) {
        final lines = const LineSplitter()
            .convert(errors)
            .where((line) => line.trim().isNotEmpty)
            .toList();
        final detail =
            protocolError ??
            (lines.isEmpty ? '离线操作未完成（$exitCode）' : lines.last);
        throw StateError(
          '${detail.substring(max(0, detail.length - 300))}；原库及未完成字节保留',
        );
      }
      return result!;
    } finally {
      await process.stdin.close();
    }
  }
}
