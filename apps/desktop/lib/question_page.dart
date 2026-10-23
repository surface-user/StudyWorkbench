import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

import 'backend.dart';

class ContentBlocks extends StatelessWidget {
  const ContentBlocks(this.blocks, {super.key});
  final List<dynamic> blocks;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: blocks
        .map<Widget>(
          (block) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: switch (block['type']) {
              'text' => Text(block['text'] as String),
              'latex' => SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Math.tex(
                  block['tex'] as String,
                  textStyle: const TextStyle(fontSize: 24),
                ),
              ),
              _ => const Text('此内容块尚未支持（已保留原数据）'),
            },
          ),
        )
        .toList(),
  );
}

class QuestionPage extends StatefulWidget {
  const QuestionPage({required this.backend, super.key});
  final Backend backend;
  @override
  State<QuestionPage> createState() => _QuestionPageState();
}

class _QuestionPageState extends State<QuestionPage> {
  late final Future<dynamic> question = widget.backend.request(
    'GET',
    '/api/questions/demo',
  );
  final written = TextEditingController();
  String? result;
  bool busy = false;
  Future<void> submit(String id, Map<String, dynamic> response) async {
    setState(() => busy = true);
    try {
      final answer = await widget.backend.request('POST', '/api/attempts', {
        'question_id': id,
        'response': response,
      });
      final history =
          await widget.backend.request('GET', '/api/attempts') as List;
      if (mounted) {
        setState(
          () => result = answer['status'] == 'pending_review'
              ? '已保存，待人工批改 · 共 ${history.length} 次作答'
              : '已保存，得分 ${answer['score']} · 共 ${history.length} 次作答',
        );
      }
    } catch (e) {
      if (mounted) setState(() => result = '提交失败：$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    written.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
    future: question,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return Center(child: Text('题目加载失败：${snapshot.error}'));
      }
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final q = snapshot.data as Map<String, dynamic>;
      return SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              q['subject'] as String,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const Text('人工演示题 · 非真题 · 未验证'),
            ContentBlocks(q['stem'] as List),
            for (final option in q['options'] as List)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => submit(q['id'] as String, {
                          'selected': [option['id']],
                        }),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('选择答案  '),
                      ContentBlocks(option['content'] as List),
                    ],
                  ),
                ),
              ),
            const Divider(height: 36),
            const Text('主观题验证：说明计算过程（默认待批改）'),
            TextField(
              controller: written,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: '输入解题过程',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: busy
                  ? null
                  : () => submit('demo-proof', {'text': written.text}),
              child: const Text('提交主观作答'),
            ),
            if (result != null)
              Padding(padding: const EdgeInsets.all(12), child: Text(result!)),
          ],
        ),
      );
    },
  );
}
