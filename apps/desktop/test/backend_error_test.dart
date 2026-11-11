import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

class _Process implements Process {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  final identifier = 'a' * 32;
  final envelope = {
    'detail': <Object>[],
    'error': {
      'code': 'validation_failed',
      'message': '请求参数无效',
      'request_id': identifier,
    },
  };

  test('old detail and status remain usable with optional metadata', () {
    final old = BackendError.fromResponse(409, jsonEncode({'detail': '草稿保留'}));
    expect(old.statusCode, 409);
    expect(old.message, '请求失败 409: 草稿保留');
    expect(old.code, isNull);
    expect(old.requestId, isNull);
    expect(BackendError(404, '未找到').statusCode, 404);
    final modern = BackendError.fromResponse(422, jsonEncode(envelope));
    expect(modern.message, '请求失败 422: 请求参数无效');
    expect(modern.code, 'validation_failed');
    expect(modern.requestId, identifier);
    final business = BackendError.fromResponse(
      409,
      jsonEncode({...envelope, 'detail': '恢复原请求；文件保留'}),
    );
    expect(business.message, contains('恢复原请求；文件保留'));
  });

  test('invalid metadata and non-JSON never display raw responses', () {
    for (final text in [
      'Traceback private path and token',
      jsonEncode(['private']),
      jsonEncode({
        'detail': [
          {'input': 'private'},
        ],
      }),
      jsonEncode({
        'error': {
          'code': 'private/invalid',
          'request_id': identifier,
          'message': 'private',
        },
      }),
      jsonEncode({
        'error': {
          'code': 'internal_error',
          'request_id': 'private',
          'message': 'private',
        },
      }),
    ]) {
      final error = BackendError.fromResponse(500, text);
      expect(error.message, '请求失败 500');
      expect(error.code, isNull);
      expect(error.requestId, isNull);
    }
    expect(
      BackendError.fromResponse(409, jsonEncode({'detail': '文' * 300})).message,
      '请求失败 409: ${'文' * 240}',
    );
  });

  test('JSON, import, media and attachment callers share error metadata and retain guidance', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final backend = Backend(
      _Process(),
      server.port,
      'fixture-token',
      'fixture',
    );
    final root = await Directory.systemTemp.createTemp('api-error-media-');
    final media = File('${root.path}/fixture.mp4');
    await media.writeAsBytes([1, 2, 3]);
    var calls = 0;
    server.listen((request) async {
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer fixture-token',
      );
      await request.drain<void>();
      calls++;
      request.response.statusCode = 422;
      request.response.headers.contentType = ContentType.json;
      request.response.write(jsonEncode(envelope));
      await request.response.close();
    });
    try {
      final operations = <Future<dynamic> Function()>[
        () => backend.request('POST', '/api/workspaces', {'name': ''}),
        () => backend.uploadImport('default', 'fixture.txt', [1]),
        () => backend.uploadMedia('default', media, (_) {}),
        () => backend.resourceBytes('default', 'fixture'),
      ];
      final guidance = ['', '请刷新导入记录核实状态', '请刷新记录核对；原文件保留', '附件读取失败'];
      for (var i = 0; i < operations.length; i++) {
        await expectLater(
          operations[i](),
          throwsA(
            isA<BackendError>()
                .having((e) => e.statusCode, 'status', 422)
                .having((e) => e.code, 'code', 'validation_failed')
                .having((e) => e.requestId, 'request id', identifier)
                .having((e) => e.message, 'guidance', contains(guidance[i])),
          ),
        );
      }
      expect(calls, 4);
      expect(await media.readAsBytes(), [1, 2, 3]);
    } finally {
      await server.close(force: true);
      await root.delete(recursive: true);
    }
  });
}
