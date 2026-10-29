import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:study_workbench/question_contract.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late QuestionContract contract;
  late Map<String, dynamic> sample;
  setUp(() async {
    contract = await QuestionContract.load();
    sample = jsonDecode(
      await File('../../contracts/import-bundle-v1.json').readAsString(),
    ) as Map<String, dynamic>;
  });
  test('canonical rich bundle and shared reading pass offline', () {
    expect(() => contract.validate(sample), returnsNormally);
  });
  test('file contract accepts seven explicitly unanswered kinds while old v1 stays strict', () async {
    final fileContract = await QuestionContract.load(
      bundle: false,
      fileQuestion: true,
    );
    final oldContract = await QuestionContract.load(bundle: false);
    for (final kind in [
      'single_choice',
      'multiple_choice',
      'fill_blank',
      'calculation',
      'proof',
      'subjective',
      'reading_question',
    ]) {
      final q = jsonDecode(
        jsonEncode(sample['questions'][0]),
      ) as Map<String, dynamic>;
      q['kind'] = kind;
      q['answer'] = null;
      q['knowledge_points'] = [];
      q['blank_ids'] = kind == 'fill_blank' ? ['blank-1'] : [];
      if (kind == 'reading_question') {
        q['passage_id'] = sample['passages'][0]['id'];
        q['response_kind'] = 'subjective';
      } else {
        q.remove('passage_id');
        q.remove('response_kind');
      }
      if (!['single_choice', 'multiple_choice'].contains(kind)) {
        q['options'] = [];
      }
      expect(
        () => fileContract.validate(q, bundle: false),
        returnsNormally,
        reason: kind,
      );
      expect(
        () => oldContract.validate(q, bundle: false),
        throwsFormatException,
      );
    }
  });
  test('seven response kinds use their own answer structure', () {
    for (final kind in [
      'single_choice',
      'multiple_choice',
      'fill_blank',
      'calculation',
      'proof',
      'subjective',
      'reading_question',
    ]) {
      final copy = jsonDecode(jsonEncode(sample)) as Map<String, dynamic>;
      final q = copy['questions'][0] as Map<String, dynamic>;
      q['kind'] = kind;
      if (kind == 'reading_question') {
        q['passage_id'] = copy['passages'][0]['id'];
        q['response_kind'] = 'subjective';
      } else {
        q.remove('response_kind');
        q.remove('passage_id');
      }
      if (kind == 'single_choice' || kind == 'multiple_choice') {
        q['options'] = [
          {
            'id': 'a',
            'content': [
              {'type': 'text', 'text': '甲'},
            ],
          },
          {
            'id': 'b',
            'content': [
              {'type': 'text', 'text': '乙'},
            ],
          },
        ];
        q['answer'] = {
          'selected': kind == 'single_choice' ? ['a'] : ['a', 'b'],
        };
      } else {
        q['options'] = [];
        q['answer'] = kind == 'fill_blank'
            ? {
                'blanks': [
                  {
                    'id': 'blank',
                    'accepted': ['答案'],
                    'normalization': 'trim',
                  },
                ],
              }
            : {'rubric': '按过程批改', 'reference': []};
      }
      expect(() => contract.validate(copy), returnsNormally, reason: kind);
    }
  });
  test(
    'unknown versions, blocks, extra fields and invalid references reject',
    () {
      final mutations = <void Function(Map<String, dynamic>)>[
        (b) => b['schema_version'] = true,
        (b) => b['schema_version'] = 2,
        (b) => b['extra'] = 'value',
        (b) => b['questions'][0]['stem'] = [
          {'type': 'html', 'html': '<script/>'},
        ],
        (b) => b['questions'][0]['stem'] = [
          {'type': 'latex', 'tex': r'\input{secret}'},
        ],
        (b) =>
            b['questions'][0]['parent_question_id'] = b['questions'][0]['id'],
        (b) => b['questions'][0]['passage_id'] = 'missing-passage',
        (b) => b['questions'][0]['revision'] = 0,
        (b) => b['questions'].add(jsonDecode(jsonEncode(b['questions'][0]))),
        (b) => b['questions'][0]['source'] = {
          'kind': 'official',
          'title': 'claimed',
          'verification': 'unverified',
        },
        (b) => b['questions'][0]['source'] = {
          'kind': 'ai_generated',
          'title': 'AI',
          'model': 'model',
          'generated_at': '2026-10-24T00:00:00',
        },
        (b) => b['questions'][0]['stem'] = [
          {
            'type': 'table',
            'headers': [
              [
                {'type': 'text', 'text': '列'},
              ],
            ],
            'rows': [[]],
          },
        ],
      ];
      for (final mutate in mutations) {
        final copy = jsonDecode(jsonEncode(sample)) as Map<String, dynamic>;
        mutate(copy);
        expect(() => contract.validate(copy), throwsFormatException);
      }
    },
  );
}
