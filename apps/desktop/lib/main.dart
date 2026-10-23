import 'dart:async';

import 'dart:ui' show AppExitResponse;

import 'package:flutter/material.dart';
import 'package:lightweight_liquid_glass/lightweight_liquid_glass.dart';

import 'backend.dart';
import 'question_page.dart';
import 'web_page.dart';

void main() => runApp(const StudyApp());

class StudyApp extends StatelessWidget {
  const StudyApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'StudyWorkbench · M0',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorSchemeSeed: const Color(0xff426da9),
      fontFamily: 'Microsoft YaHei',
      extensions: const [LiquidGlassThemeData()],
    ),
    home: const Workbench(),
  );
}

class Workbench extends StatefulWidget {
  const Workbench({super.key});
  @override
  State<Workbench> createState() => _WorkbenchState();
}

class _WorkbenchState extends State<Workbench> with WidgetsBindingObserver {
  Backend? backend;
  String? error;
  String? playerHtml;
  int selected = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _start();
  }

  Future<void> _start() async {
    Backend? service;
    try {
      service = await Backend.start();
      final html = await service.player();
      if (!mounted) {
        service.close();
        return;
      }
      setState(() {
        backend = service;
        playerHtml = html;
      });
    } catch (e) {
      service?.close();
      if (mounted) setState(() => error = '$e');
    }
  }

  @override
  Future<AppExitResponse> didRequestAppExit() async {
    backend?.close();
    return AppExitResponse.exit;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    backend?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: GlassBackdrop(
      child: SafeArea(
        child: Row(
          children: [
            GlassSurface(
              width: 210,
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'StudyWorkbench',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const Text('M0 技术验证 · 无需 AI'),
                  const Divider(height: 32),
                  const ListTile(
                    leading: Icon(Icons.school_outlined),
                    title: Text('我的考研学习'),
                  ),
                  const Spacer(),
                  Text(
                    error != null
                        ? '后端启动失败'
                        : backend == null
                        ? '正在启动后端…'
                        : '本地后端已连接',
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '工作空间管理、导入及下载将在后续阶段实现。',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
            Expanded(
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: SegmentedButton<int>(
                      segments: const [
                        ButtonSegment(
                          value: 0,
                          label: Text('富内容题目'),
                          icon: Icon(Icons.functions),
                        ),
                        ButtonSegment(
                          value: 1,
                          label: Text('网页'),
                          icon: Icon(Icons.language),
                        ),
                        ButtonSegment(
                          value: 2,
                          label: Text('本地播放器'),
                          icon: Icon(Icons.play_circle_outline),
                        ),
                      ],
                      selected: {selected},
                      onSelectionChanged: (value) =>
                          setState(() => selected = value.first),
                    ),
                  ),
                  Expanded(
                    child: error != null
                        ? Center(child: SelectableText(error!))
                        : backend == null
                        ? const Center(child: CircularProgressIndicator())
                        : IndexedStack(
                            index: selected,
                            children: [
                              QuestionPage(backend: backend!),
                              WebPage(
                                profile: '${backend!.dataDir}/web-profile',
                              ),
                              WebPage(
                                profile: '${backend!.dataDir}/player-profile',
                                html: playerHtml,
                              ),
                            ],
                          ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
