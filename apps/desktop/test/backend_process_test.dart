import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/backend.dart';

void main() {
  const repository = String.fromEnvironment('STUDY_ROOT');
  test(
    'isolated restored settings remain selected on a fresh application start',
    () async {
      final profile = Backend.testData.replaceAll('\\', '/');
      final repositoryProfile = repository.replaceAll('\\', '/');
      expect(profile.startsWith('$repositoryProfile/.local/'), true);
      final file = File('${Backend.testData}.settings.json');
      expect(
        await file.exists(),
        false,
        reason: 'Each run requires a new isolated profile',
      );
      final root = await Directory('$repository/.local/tmp')
          .create(recursive: true);
      final restored = await root.createTemp('selected-restored-profile-');
      await file.parent.create(recursive: true);
      await file.writeAsString(
        jsonEncode({'version': 1, 'data_dir': restored.path}),
      );
      expect(await Backend.configuredData(), restored.path);
    },
    skip: repository.isEmpty || Backend.testData.isEmpty
        ? 'Requires fresh isolated profile'
        : false,
  );
  test(
    'offline backup and restore keep real attempts, notes and configuration',
    () async {
      final scratch = await Directory('$repository/.local/tmp')
          .create(recursive: true);
      final fixture = await scratch.createTemp('study-backup-process-');
      final source = '${fixture.path}/original',
          target = '${fixture.path}/restored';
      final config = '${fixture.path}/profile/settings.json',
          archive = '${fixture.path}/library.zip';
      var service = await Backend.start(dataDir: source, configPath: config);
      try {
        await service.request('POST', '/api/attempts', {
          'question_id': 'demo-proof',
          'response': {'text': '备份真实进程作答'},
        });
        final note = await service.request(
          'POST',
          '/api/workspaces/default/markdown-notes',
          {'name': '备份笔记.md', 'request_id': 'real-backup-note-request'},
        ) as Map;
        final node = note['resource_item_id'];
        final doc = await service.request(
          'GET',
          '/api/workspaces/default/nodes/$node/document',
        ) as Map;
        await service.request(
          'PUT',
          '/api/workspaces/default/nodes/$node/document',
          {'expected_sha256': doc['sha256'], 'text': '保留的当前正文'},
        );
        final point = await service.request(
          'POST',
          '/api/workspaces/default/nodes/$node/learning-anchor',
          {'kind': 'resource'},
        ) as Map;
        await service.request(
          'POST',
          '/api/workspaces/default/learning-marks',
          {
            'request_id': 'real-backup-mark-request',
            'title': '备份备注',
            'anchor': point,
            'targets': [
              {'kind': 'file_note', 'id': node},
            ],
          },
        );
        await service.shutdown();
        final backup = await Backend.libraryOperation(
          restore: false,
          dataDir: source,
          zipPath: archive,
          configPath: config,
        );
        final saved = await backup.done;
        expect(saved['source_retained'], true);
        expect(saved['data_activated'], false);
        expect(await File(archive).exists(), true);
        final restore = await Backend.libraryOperation(
          restore: true,
          dataDir: target,
          zipPath: archive,
          configPath: config,
        );
        final restored = await restore.done;
        expect(restored['data_activated'], true);
        expect(
          await Backend.sameDataDirectory(
            restored['data_dir'] as String,
            '$target/.',
          ),
          true,
        );
        expect(
          await Backend.sameDataDirectory(
            await Backend.configuredData(configPath: config),
            target,
          ),
          true,
        );
        service = await Backend.start(dataDir: target, configPath: config);
        final attempts = await service.request('GET', '/api/attempts') as List;
        expect(attempts.single['response']['text'], '备份真实进程作答');
        final current = await service.request(
          'GET',
          '/api/workspaces/default/nodes/$node/document',
        ) as Map;
        expect(current['text'], '保留的当前正文');
        final marks = await service.request(
          'GET',
          '/api/workspaces/default/learning-marks',
        ) as List;
        expect(marks.single['targets'].single['id'], node);
        expect(await File('$source/study.db').exists(), true);
      } finally {
        await service.shutdown();
      }
    },
    skip: repository.isEmpty ? 'Requires isolated real backend' : false,
  );

  test('parent-pipe cancellation stops offline operation without changing original config', () async {
    final scratch = await Directory('$repository/.local/tmp')
        .create(recursive: true);
    final fixture = await scratch.createTemp('study-backup-cancel-');
    final source = '${fixture.path}/source',
        config = '${fixture.path}/profile/settings.json';
    final service = await Backend.start(dataDir: source, configPath: config);
    await service.shutdown();
    final before = await File(config).readAsString();
    final operation = await Backend.libraryOperation(
      restore: false,
      dataDir: source,
      zipPath: '${fixture.path}/cancel.zip',
      configPath: config,
    );
    final failure = expectLater(operation.done, throwsStateError);
    await operation.cancel();
    await failure;
    expect(await File(config).readAsString(), before);
    expect(await File('$source/study.db').exists(), true);
    expect(await File('${fixture.path}/cancel.zip').exists(), false);
  }, skip: repository.isEmpty ? 'Requires isolated real backend' : false);
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
