# M0 自动交互与自动测评（2026-10-24）

后续状态已更新，见 [修复与复测报告](m0-followup-fixes-2026-10-24.md)：中文菜单与回退失败反馈已修复；真实中文粘贴与字幕显示通过，组件增至 12 项，原生集成新增字幕与 seek 断言通过。浏览器 URL 的最终核对被工具安全检查中止。以下保留首次评估快照。

用户授权恢复自动交互与自动测评。Release 启动故障继续搁置，没有重建或验证 Release，也没有处理默认 profile 的 mkdir/HTTP 500。结论：本轮范围内的自动化检查通过；实际 Debug 窗口的主要交互通过，系统浏览器回退及中文文本注入受到环境/工具限制。**不标记人工或 M0 阶段验收通过，不进入 M1。**

本轮未增加业务功能或依赖。Dart 格式化调整了 backend.dart 与 question_page_test.dart；没有修改现有断言、golden、失败日志或个人数据库。

## 自动化命令与结果

以下命令在仓库根目录运行，Flutter 命令则在 `apps/desktop` 运行。工具路径为现有 `D:/computer_work/Tools_work/flutter`；使用已有依赖，不运行 pub get。证据均保留在 [本轮目录](evidence/2026-10-24/)。

| 实际命令 | 退出码 / 结果 | 证据与范围 |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=artifacts/2026-10-24/backend.xml` | 1；35 passed、5 errors | [首轮失败 XML](evidence/2026-10-24/backend-initial-temp-failed.xml)；系统沙箱 TEMP 的目录创建失败，5 项均未进入业务断言 |
| 设置本进程 TEMP/TMP 为 `.local/tmp` 后，`.venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=artifacts/2026-10-24/backend-project-temp.xml` | 0；40 passed | [XML](evidence/2026-10-24/backend-project-temp.xml)、[日志](evidence/2026-10-24/backend-project-temp.log)；有一条既存 Starlette/AnyIO 弃用警告；包括鉴权、Origin/Host、评分/追加/重启、协议及 Schema 漂移 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 0；All checks passed | 命令输出见本轮工具记录；不等于漏洞审计 |
| `dart format lib test` | 0；9 files、2 changed | 仅格式化；后续 `dart format --output=none --set-exit-if-changed lib test` 退出 0、0 changed |
| `flutter analyze --no-pub`（扩展权限执行） | 0；No issues found | [日志](evidence/2026-10-24/flutter-analyze-host.log)，21.4 秒；直接调用现有 Flutter snapshot 的一次诊断也退出 0，不计为额外覆盖 |
| `flutter test --no-pub`（扩展权限执行） | 0；7 tests passed | [日志](evidence/2026-10-24/flutter-test-host.log)；含新增 5 项题目重试、历史读取失败、保存未确认、历史延迟的组件回归；使用替身后端，不代表真实 HTTP |
| `.venv/Scripts/python.exe tools/smoke_backend.py`（本进程 TEMP/TMP 指向 `.local/tmp`） | 0 | [日志](evidence/2026-10-24/backend-process.log)；源码后端真实进程的随机端口、鉴权 SQLite health、stdin EOF 退出 |
| 下述 Windows 集成命令（扩展权限执行） | 0；1 test passed | [日志](evidence/2026-10-24/windows-integration.log)；52.2 秒 Debug 构建、约 12 秒运行；已有插件 CMake CMP0175 开发警告 |
| 下述普通入口 Debug 构建（扩展权限执行） | 0 | [日志](evidence/2026-10-24/windows-debug-build.log)；44.3 秒；不是 Release 或安装包 |
| `git diff --check` | 0 | 仅有 Git 的 LF/CRLF 提示，无空白错误 |

```powershell
# apps/desktop；仅本进程目录与 PATH，不修改系统设置
. ../../tools/prepare-windows.ps1
$env:PATH = 'D:\computer_work\project\StudyWorkbench\.local\bin;' + $env:PATH

flutter test integration_test/m0_test.dart -d windows --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/e2e-20261024 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm `
  --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/artifacts/2026-10-24

flutter build windows --debug --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/interaction-20261024 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm
```

集成测试使用真实 Flutter 窗口、自有源码 Python 后端、SQLite 和 WebView2。检查客观题 1.0、主观题 pending_review、内置网页真实 DOM、视频 readyState、播放 currentTime 增加、暂停、1.5 倍速及销毁无 Flutter 异常。[集成渲染截图](evidence/2026-10-24/native-integration-question.png)只包含 Flutter 截图边界，原生视频另由交互截图证明。集成脚本虽设置 currentTime=2，但没有 seek 精度断言，不能单独作为跳转精度验证。

执行限制：最初普通沙箱中的 Flutter analyze/test 因 SDK 启动锁写权限持续无输出；停止了本轮两个已识别的 flutter.bat 子进程，两个执行会话退出 -1，未计为通过。随后扩展权限命令正常通过，没有改 SDK、全局 TEMP 或 ACL。一次证据复制使用了错误工作目录，复制报找不到文件，已按仓库根目录重新复制并核对产物；没有覆盖历史证据。

## 普通 Debug 入口的真实窗口交互

使用 computer-use 的窗口定向点击与按键；没有通过 API 注入作答，没有脚本修改视频 DOM。数据固定在本轮 `.local/interaction-20261024` 演示目录，不读取个人学习数据。

| 操作 | 实际结果 | 边界 / 证据 |
|---|---|---|
| 点击第二个答案，再点第一个答案 | 0.0 / 共 1 次，随后 1.0 / 共 2 次 | 真实鼠标点击；结果同时由最后的测试库只读核对确认 |
| 主观输入与提交 | `press_key('x')` 能输入；点击提交得到 pending_review / 共 3 次 | [截图](evidence/2026-10-24/interaction-question.png)、[无障碍文本](evidence/2026-10-24/interaction-question.txt) |
| 打开网页、后退、前进 | 公开 HTTPS 页面实际显示；后退恢复内置页；前进恢复外站页面 | [外站截图](evidence/2026-10-24/interaction-web.png)；不覆盖第三方登录、安全矩阵或所有站点 |
| 系统浏览器回退 | 未通过本轮交互验收 | 出现 Edge“需以更高权限运行”的提示，未确认；需要非提权会话复测，不推断为业务代码缺陷 |
| 播放与跳转 | 鼠标启动视频后从 0 秒到 6 秒；点击进度条回到显示约 2 秒 | [播放结束截图](evidence/2026-10-24/interaction-player.png)、[跳转截图](evidence/2026-10-24/interaction-seek.png)；未测亚秒精度 |
| 切回题目 | 输入 x、待批改结果及 3 次记录仍保留 | 标签内状态通过；不代表跨启动恢复草稿 |
| 最大化布局 | 公式、输入与操作可见，无可见溢出 | [截图](evidence/2026-10-24/interaction-maximized.png)；不是多 DPI 或 GPU 帧率测量 |
| 关闭并重启，再提交正确选项 | 1.0 / 共 4 次，旧作答未丢失 | [重启截图](evidence/2026-10-24/interaction-restart.png)、[无障碍文本](evidence/2026-10-24/interaction-restart.txt) |
| 正常关闭 | 观察到窗口消失，末次 PID 42744 及其直接子进程查询为空 | 原型正常退出路径；未做崩溃/强杀/多实例矩阵 |

最后以 SQLite `mode=ro` 只读打开本轮测试库，断言四条记录顺序为 `graded/0.0`、`graded/1.0`、`pending_review/null`、`graded/1.0`，退出 0。[只含测试记录摘要](evidence/2026-10-24/interaction-db-summary.json)没有题目原件、个人数据或会话令牌。数据库文件未加入 Git。

交互工具限制：两次 `sky.launch_app` 超时，确认没有应用进程后，用 `Start-Process -FilePath .../Debug/study_workbench.exe -WorkingDirectory .../Debug -PassThru` 启动，退出 0。Flutter 无障碍节点 ID 在交互期间快速变化，一次按旧索引点击未执行，重新截图后改用窗口定向坐标。`type_text` 的中文和 ASCII 文本都没有显示，重新聚焦后仍如此；真实 `press_key('x')` 成功。本轮不能证明中文 IME 或长文本粘贴可用，也不能据此认定其不可用。倍速下拉的真实点击未获得可确认选择结果，因此只采用集成测试中 playbackRate=1.5 的证据。

## 状态与下一步

- 实现：M0-09 收尾代码保留，当前代码完成本轮自动化；原有启动诊断/失败页也参与了静态分析和 Debug 构建，但没有诱发启动失败来验证复制/重试 UI。
- 自动化：40 后端 + 7 组件 + 1 Windows 集成均通过；源码进程 smoke 与普通 Debug 构建通过。真实窗口交互按上表逐项记录，不能合并称“全部通过”。
- 人工：本轮为 Agent 自动操作，用户人工验收和文档评审未完成。
- 阶段：M0 未通过。Release 问题暂时搁置，不能把 Debug、源码后端、隔离数据目录的结果替代该项。

下一步为非提权环境的系统浏览器回退、真实中文 IME/粘贴、字幕实际显示、音轨与更多编码、DPI/性能和用户评审；Release 故障继续按用户后续指示处理。干净机安装、工作空间、数据根选择/迁移、完整题库与下载分别仍按 M1 及后续阶段排期。没有合并、推送或发布。
