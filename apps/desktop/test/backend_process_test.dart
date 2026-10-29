import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

void main() {
  const repository = String.fromEnvironment('STUDY_ROOT');
  test(
    'unwritable config preserves selected directory and learning on restart',
    () async {
      final scratch = await Directory('$repository/.local/tmp')
          .create(recursive: true);
      final fixture = await scratch.createTemp('study-config-denied-');
      final blocked = File('${fixture.path}/profile')
        ..writeAsStringSync('retained file');
      final data = '${fixture.path}/selected data';
      var service = await Backend.start(
        dataDir: data,
        configPath: '${blocked.path}/settings.json',
      );
      try {
        expect(service.startupWarning, contains('未保存'));
        expect(
          service.startupWarning!.replaceAll('\\', '/'),
          contains(blocked.path.replaceAll('\\', '/')),
        );
        expect(service.dataDir, data);
        await service.request('POST', '/api/attempts', {
          'question_id': 'demo-proof',
          'response': {'text': '配置不可写仍保留'},
        });
        await service.shutdown();
        service = await Backend.start(
          dataDir: data,
          configPath: '${blocked.path}/settings.json',
        );
        final attempts = await service.request('GET', '/api/attempts') as List;
        expect(attempts.single['response']['text'], '配置不可写仍保留');
        expect(blocked.readAsStringSync(), 'retained file');
      } finally {
        await service.shutdown();
      }
    },
    skip: repository.isEmpty ? 'Requires STUDY_ROOT' : false,
  );
  test(
    'real backend pipe migration preserves attempts and returns after EOF',
    () async {
      final scratch = await Directory('$repository/.local/tmp')
          .create(recursive: true);
      final fixture = await scratch.createTemp('study-dart-service-');
      final source = '${fixture.path}/source 中文';
      final target = '${fixture.path}/target space';
      final config = '${fixture.path}/settings.json';
      var service = await Backend.start(dataDir: source);
      try {
        final result = await service.request('POST', '/api/attempts', {
          'question_id': 'demo-proof',
          'response': {'text': '真实进程迁移保留'},
        });
        expect(result['status'], 'pending_review');
        final original = utf8.encode('真实管道导入与迁移保留');
        final job = await service.uploadImport('default', '迁移笔记.md', original);
        expect(job['status'], 'preview');
        expect(
          await service.request('GET', '/api/workspaces/default/notes'),
          isEmpty,
        );
        await service.request(
          'POST',
          '/api/workspaces/default/imports/${job['id']}/confirm',
        );
        expect(
          await service.resourceBytes('default', job['resource_id']),
          original,
        );
        await service.shutdown();
        await Backend.relocateData(source, target, configPath: config);
        final configured =
            jsonDecode(await File(config).readAsString())['data_dir'] as String;
        expect(await FileSystemEntity.identical(configured, target), true);
        expect(await File('$source/study.db').exists(), true);
        service = await Backend.start(dataDir: target);
        final attempts = await service.request('GET', '/api/attempts') as List;
        expect(attempts.single['response']['text'], '真实进程迁移保留');
        final notes = await service.request(
          'GET',
          '/api/workspaces/default/notes',
        ) as List;
        expect(notes.single['content'][0]['text'], '真实管道导入与迁移保留');
        expect(
          await service.resourceBytes('default', job['resource_id']),
          original,
        );
      } finally {
        await service.shutdown();
      }
    },
    skip: repository.isEmpty
        ? 'Run explicitly with STUDY_ROOT and isolated STUDY_DATA_DIR'
        : false,
  );
}
