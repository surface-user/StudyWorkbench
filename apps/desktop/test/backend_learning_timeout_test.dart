import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

class _Process implements Process {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('bounded learning resolution can finish after the normal five-second timeout', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final backend = Backend(
      _Process(),
      server.port,
      'fixture-token',
      'fixture',
    );
    server.listen((request) async {
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer fixture-token',
      );
      await request.drain<void>();
      await Future<void>.delayed(const Duration(seconds: 6));
      request.response.headers.contentType = ContentType.json;
      request.response.write('{"status":"valid"}');
      await request.response.close();
    });
    try {
      expect(
        await backend.request(
          'POST',
          '/api/workspaces/default/internal-links/resolve',
          {'uri': 'fixture'},
        ),
        {'status': 'valid'},
      );
    } finally {
      await server.close(force: true);
    }
  });
}
