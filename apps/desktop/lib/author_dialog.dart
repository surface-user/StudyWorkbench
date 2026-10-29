import 'package:flutter/material.dart';

/// Human editing produces a preview; it never writes the question bank directly.
class AuthorDialog extends StatefulWidget {
  const AuthorDialog({this.link = false, super.key});
  final bool link;
  @override
  State<AuthorDialog> createState() => _AuthorDialogState();
}

class _AuthorDialogState extends State<AuthorDialog> {
  final form = GlobalKey<FormState>();
  String title = '';
  String body = '';
  String subject = '数学一·高等数学';
  String kind = 'note';
  String responseKind = 'subjective';
  String optionText = '';
  String reference = '';
  String explanation = '';
  String points = '';
  String passage = '';
  String? error;
  final selected = <int>{};
  List<String> get options =>
      optionText.split('\n').where((s) => s.trim().isNotEmpty).toList();
  String get effectiveKind => kind == 'reading_question' ? responseKind : kind;
  bool get choice =>
      ['single_choice', 'multiple_choice'].contains(effectiveKind);
  List<Map<String, dynamic>> blocks(String text) => [
    for (var i = 0; i < text.length; i += 20000)
      {
        'type': 'text',
        'text': text.substring(
          i,
          i + 20000 > text.length ? text.length : i + 20000,
        ),
      },
  ];

  void submit() {
    if (!form.currentState!.validate()) return;
    try {
      if (widget.link) {
        final url = Uri.tryParse(body.trim());
        if (url == null ||
            url.scheme != 'https' ||
            !url.hasAuthority ||
            url.userInfo.isNotEmpty) {
          throw const FormatException('请输入完整 HTTPS 链接');
        }
        Navigator.pop(context, {
          'filename': '${title.trim()}.url',
          'url': body.trim(),
        });
        return;
      }
      if (kind == 'note') {
        Navigator.pop(context, {
          'schema_version': 1,
          'kind': 'note',
          'title': title.trim(),
          'blocks': blocks(body),
        });
        return;
      }
      if (points.trim().isEmpty || reference.trim().isEmpty && !choice) {
        throw const FormatException('请填写知识点与参考答案或评分要点');
      }
      if (choice &&
          (options.length < 2 ||
              selected.isEmpty ||
              effectiveKind == 'single_choice' && selected.length != 1 ||
              selected.any((i) => i >= options.length))) {
        throw const FormatException('至少填写两个选项，并勾选有效的正确答案');
      }
      if (kind == 'reading_question' && passage.trim().isEmpty) {
        throw const FormatException('请填写共享阅读材料');
      }
      final id = 'manual-${DateTime.now().microsecondsSinceEpoch}';
      final source = {
        'kind': 'manual',
        'title': title.trim(),
        'verification': 'unverified',
      };
      final Map<String, dynamic> answer = choice
          ? {'selected': selected.toList()..sort()}
          : effectiveKind == 'fill_blank'
          ? {
              'blanks': [
                for (final (i, line) in reference.split('\n').indexed)
                  {
                    'id': 'blank-${i + 1}',
                    'accepted': line.split('|').map((s) => s.trim()).toList(),
                    'normalization': 'trim',
                  },
              ],
            }
          : {'rubric': reference, 'reference': blocks(reference)};
      if (choice) {
        answer['selected'] = (answer['selected'] as List)
            .map((i) => 'option-${i + 1}')
            .toList();
      }
      Navigator.pop(context, {
        'schema_version': 1,
        'passages': [
          if (kind == 'reading_question')
            {'id': '$id-passage', 'content': blocks(passage), 'source': source},
        ],
        'questions': [
          {
            'schema_version': 1,
            'id': id,
            'revision': 1,
            'subject': subject,
            'kind': kind,
            if (kind == 'reading_question') ...{
              'passage_id': '$id-passage',
              'response_kind': responseKind,
            },
            'stem': blocks(body),
            'options': [
              if (choice)
                for (final (i, option) in options.indexed)
                  {'id': 'option-${i + 1}', 'content': blocks(option)},
            ],
            'answer': answer,
            'explanation': blocks(
              explanation.trim().isEmpty ? '暂无解析' : explanation,
            ),
            'knowledge_points': points
                .split('、')
                .map((s) => s.trim())
                .where((s) => s.isNotEmpty)
                .toList(),
            'source': source,
          },
        ],
      });
    } on FormatException catch (failure) {
      setState(() => error = failure.message);
    }
  }

  Widget field(
    String label,
    String initial,
    ValueChanged<String> change, {
    int lines = 1,
    bool required = false,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextFormField(
      key: ValueKey(label),
      initialValue: initial,
      minLines: lines,
      maxLines: lines + 3,
      maxLength: lines == 1 ? 240 : 16000,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      onChanged: change,
      validator: (s) =>
          required && (s == null || s.trim().isEmpty) ? '请填写$label' : null,
    ),
  );

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.link ? '保存资料链接' : '手动录入'),
    content: SizedBox(
      width: 640,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              field('标题', title, (s) => title = s, required: true),
              if (!widget.link)
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: '内容类型'),
                  items: [
                    for (final entry in const {
                      'note': '笔记',
                      'single_choice': '单选题',
                      'multiple_choice': '多选题',
                      'fill_blank': '填空题',
                      'calculation': '计算题',
                      'proof': '证明题',
                      'subjective': '主观题',
                      'reading_question': '阅读题',
                    }.entries)
                      DropdownMenuItem(
                        value: entry.key,
                        child: Text(entry.value),
                      ),
                  ],
                  onChanged: (s) => setState(() {
                    kind = s!;
                    selected.clear();
                  }),
                ),
              field(
                widget.link
                    ? 'HTTPS 链接'
                    : kind == 'note'
                    ? '笔记内容'
                    : '题干',
                body,
                (s) => body = s,
                lines: 3,
                required: true,
              ),
              if (kind != 'note' && !widget.link) ...[
                field('科目', subject, (s) => subject = s, required: true),
                field('知识点（用顿号分隔）', points, (s) => points = s, required: true),
                if (kind == 'reading_question') ...[
                  field(
                    '共享阅读材料',
                    passage,
                    (s) => passage = s,
                    lines: 3,
                    required: true,
                  ),
                  DropdownButtonFormField<String>(
                    initialValue: responseKind,
                    decoration: const InputDecoration(labelText: '作答类型'),
                    items: [
                      for (final e in const {
                        'single_choice': '单选',
                        'multiple_choice': '多选',
                        'fill_blank': '填空',
                        'subjective': '主观',
                      }.entries)
                        DropdownMenuItem(value: e.key, child: Text(e.value)),
                    ],
                    onChanged: (s) => setState(() {
                      responseKind = s!;
                      selected.clear();
                    }),
                  ),
                ],
                if (choice) ...[
                  field(
                    '选项（每行一个）',
                    optionText,
                    (s) => setState(() {
                      optionText = s;
                      selected.clear();
                    }),
                    lines: 3,
                  ),
                  const Text('勾选正确答案'),
                  for (final (i, option) in options.indexed)
                    CheckboxListTile(
                      title: Text(option),
                      value: selected.contains(i),
                      onChanged: (value) => setState(() {
                        if (effectiveKind == 'single_choice') selected.clear();
                        if (value == true) {
                          selected.add(i);
                        } else {
                          selected.remove(i);
                        }
                      }),
                    ),
                ] else
                  field(
                    effectiveKind == 'fill_blank'
                        ? '填空答案（每行一空，同义答案用 | 分隔）'
                        : '参考答案与评分要点',
                    reference,
                    (s) => reference = s,
                    lines: 3,
                  ),
                field('解析', explanation, (s) => explanation = s, lines: 2),
              ],
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              const Text('新内容须检查预览后确认；原始资料和历史作答会保留。'),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('取消'),
      ),
      FilledButton(onPressed: submit, child: const Text('生成预览')),
    ],
  );
}
