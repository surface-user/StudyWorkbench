import 'dart:convert';

import 'package:flutter/services.dart';

/// Evaluates the keywords emitted by our pinned Python contract, offline.
/// Cross-field rules remain explicit; Python also validates before persistence.
class QuestionContract {
  QuestionContract(this.schema);
  final Map<String, dynamic> schema;
  static Future<QuestionContract> load({
    bool bundle = true,
    bool fileQuestion = false,
  }) async => QuestionContract(
    jsonDecode(
      await rootBundle.loadString(
        fileQuestion
            ? 'assets/question-file-content-v1.schema.json'
            : 'assets/question${bundle ? '-bundle' : ''}-v1.schema.json',
      ),
    ) as Map<String, dynamic>,
  );

  void validateContent(List<dynamic> blocks) {
    final rule = schema['properties']['stem'] as Map<String, dynamic>;
    if (!_matches(blocks, rule, 0)) {
      throw const FormatException('内容段结构或长度无效，请检查后保存');
    }
    _blocks(blocks);
  }

  void validate(dynamic value, {bool bundle = true}) {
    if (!_matches(value, schema, 0)) {
      throw const FormatException('题目结构或版本不受支持；原件保留，请检查资料');
    }
    final questions = bundle ? value['questions'] as List : [value];
    final passages = bundle ? value['passages'] as List? ?? [] : [];
    final ids = questions.map((q) => q['id']).toSet();
    final passageIds = passages.map((p) => p['id']).toSet();
    if (ids.length != questions.length ||
        passageIds.length != passages.length) {
      throw const FormatException('题目或阅读材料编号重复');
    }
    for (final p in passages) {
      _source(p['source']);
      _blocks(p['content']);
    }
    for (final q in questions) {
      final reading = q['kind'] == 'reading_question';
      if (reading && (q['passage_id'] == null || q['response_kind'] == null) ||
          !reading && q['response_kind'] != null ||
          q['parent_question_id'] == q['id']) {
        throw const FormatException('题型或来源关系无效');
      }
      if (bundle) {
        if (q['passage_id'] != null && !passageIds.contains(q['passage_id'])) {
          throw const FormatException('缺少共享阅读材料');
        }
        final visited = {q['id']};
        var parent = q['parent_question_id'];
        while (parent != null) {
          if (!ids.contains(parent) || !visited.add(parent)) {
            throw const FormatException('题目来源关系缺失或成环');
          }
          parent = questions.firstWhere(
            (p) => p['id'] == parent,
          )['parent_question_id'];
        }
      }
      final kind = reading ? q['response_kind'] : q['kind'];
      final options = q['options'] as List? ?? [];
      final answer = q['answer'] as Map?;
      final blankIds = q['blank_ids'] as List? ?? [];
      if (blankIds.toSet().length != blankIds.length ||
          kind != 'fill_blank' && blankIds.isNotEmpty) {
        throw const FormatException('空格编号重复或与题型不匹配');
      }
      if (kind == 'single_choice' || kind == 'multiple_choice') {
        final optionIds = options.map((o) => o['id']).toSet();
        final selected = answer?['selected'];
        if (optionIds.length < 2 ||
            optionIds.length != options.length ||
            answer != null &&
                (selected is! List ||
                    selected.toSet().length != selected.length ||
                    selected.any((s) => !optionIds.contains(s)) ||
                    kind == 'single_choice' && selected.length != 1)) {
          throw const FormatException('选择题答案必须引用有效且唯一的选项');
        }
      } else {
        if (options.isNotEmpty) throw const FormatException('非选择题不能带选项');
        if (kind == 'fill_blank') {
          final blanks = answer?['blanks'];
          final ids = answer == null
              ? blankIds
              : (blanks is List
                    ? blanks.map((b) => b['id']).toList()
                    : <dynamic>[]);
          if (answer != null && blanks is! List ||
              ids.isEmpty ||
              ids.toSet().length != ids.length) {
            throw const FormatException('填空答案编号无效');
          }
          if (blankIds.isNotEmpty &&
              answer != null &&
              jsonEncode(blankIds) != jsonEncode(ids)) {
            throw const FormatException('空格编号与答案不一致');
          }
        } else if (answer != null && answer['rubric'] is! String) {
          throw const FormatException('主观题需要评分要点');
        }
      }
      _source(q['source']);
      _blocks(q['stem']);
      _blocks(q['explanation']);
      for (final o in options) {
        _blocks(o['content']);
      }
      if (answer?['reference'] is List) _blocks(answer!['reference']);
    }
  }

  void _source(Map source) {
    final ai = source['kind'] == 'ai_generated';
    final time = source['generated_at'];
    if (ai &&
            (source['model'] == null ||
                time is! String ||
                DateTime.tryParse(time) == null ||
                !RegExp(
                  r'(Z|[+-]\d{2}:\d{2})$',
                  caseSensitive: false,
                ).hasMatch(time)) ||
        !ai && (source['model'] != null || time != null) ||
        source['kind'] == 'official' &&
            source['verification'] != 'human_verified') {
      throw const FormatException('来源或AI验证信息无效');
    }
  }

  void _blocks(List blocks) {
    for (final b in blocks) {
      if (b['type'] == 'latex' &&
          RegExp(
            r'\\(?:input|include|includegraphics|openin|openout|read|write|usepackage|documentclass|href|url|html\w*|def|newcommand|renewcommand|csname)(?![A-Za-z])',
            caseSensitive: false,
          ).hasMatch(b['tex'] as String)) {
        throw const FormatException('公式含不允许的命令');
      }
      if (b['type'] == 'table') {
        final width = (b['headers'] as List).length;
        for (final row in b['rows'] as List) {
          if ((row as List).length != width) {
            throw const FormatException('表格各行列数不一致');
          }
        }
        for (final row in [b['headers'], ...b['rows'] as List]) {
          for (final cell in row as List) {
            _blocks(cell as List);
          }
        }
      }
    }
  }

  bool _matches(dynamic value, Map<String, dynamic> rule, int depth) {
    if (depth > 40) return false;
    if (rule[r'$ref'] case final String ref) {
      return _matches(
        value,
        schema[r'$defs'][ref.split('/').last] as Map<String, dynamic>,
        depth + 1,
      );
    }
    for (final keyword in ['anyOf', 'oneOf']) {
      if (rule[keyword] case final List alternatives) {
        final count = alternatives
            .where((r) => _matches(value, r as Map<String, dynamic>, depth + 1))
            .length;
        if (count == 0 || keyword == 'oneOf' && count != 1) return false;
      }
    }
    if (rule.containsKey('const') && value != rule['const']) return false;
    if (rule['enum'] is List && !(rule['enum'] as List).contains(value)) {
      return false;
    }
    final validType = switch (rule['type']) {
      'object' => value is Map<String, dynamic>,
      'array' => value is List,
      'string' => value is String,
      'integer' => value is int,
      'number' => value is num,
      'boolean' => value is bool,
      'null' => value == null,
      null => true,
      _ => false,
    };
    if (!validType) return false;
    if (value is Map) {
      final properties = rule['properties'] as Map? ?? {};
      if ((rule['required'] as List? ?? []).any((k) => !value.containsKey(k))) {
        return false;
      }
      for (final key in value.keys) {
        if (!properties.containsKey(key)) {
          if (rule['additionalProperties'] == false) return false;
        } else if (!_matches(
          value[key],
          properties[key] as Map<String, dynamic>,
          depth + 1,
        )) {
          return false;
        }
      }
    }
    if (value is List) {
      if (value.length < (rule['minItems'] as int? ?? 0) ||
          value.length > (rule['maxItems'] as int? ?? 1000000)) {
        return false;
      }
      if (rule['items'] case final Map<String, dynamic> items) {
        if (value.any((v) => !_matches(v, items, depth + 1))) return false;
      }
    }
    if (value is String) {
      final length = value.runes.length;
      if (length < (rule['minLength'] as int? ?? 0) ||
          length > (rule['maxLength'] as int? ?? 1000000)) {
        return false;
      }
      if (rule['pattern'] case final String pattern) {
        if (!RegExp(pattern).hasMatch(value)) return false;
      }
    }
    if (value is num &&
        rule['minimum'] is num &&
        value < (rule['minimum'] as num)) {
      return false;
    }
    return true;
  }
}
