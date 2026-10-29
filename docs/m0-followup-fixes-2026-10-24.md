# M0 自动交互问题跟进（2026-10-24）

用户要求继续测试并修复，不以“环境限制”直接结束。Release 启动故障仍按之前要求搁置，本轮未测试或修改其根因。

## 诊断与实现

1. 文本输入：同一普通权限窗口中，自动工具 `type_text` 无法输入，但从自建记事本文本正常复制、通过 Flutter 可见菜单粘贴，可以完整显示中文并提交 pending_review。[实际中文作答](evidence/2026-10-24-followup/chinese-paste-saved.png)、[无障碍文本](evidence/2026-10-24-followup/chinese-paste-saved.txt)。该现象与 [上游 Computer Use/Flutter 快捷键兼容报告](https://github.com/openai/codex/issues/43575)一致；本机没有原生按键消息跟踪，不能直接宣称已证明其 scan code 根因。没有修改 SDK、自动工具或产品键盘消息，不把测试工具失败解释为中文文本不受支持。中文 IME 组字仍未验证。

2. 中文菜单：实际编辑菜单原来显示英文 Paste。现在接入 Flutter SDK 的 flutter_localizations，将应用 locale/supportedLocales 配为 zh_CN，沿用 SDK 的标准本地化委托，不自造编辑菜单。[修复后真实“粘贴”菜单](evidence/2026-10-24-followup/chinese-menu.png)及正常粘贴均已观察。增加本地化回归，读取 StudyApp 实际配置，断言 Material 的粘贴标签为中文。

3. 浏览器回退：原实现忽略 launchUrl 返回 false，且无失败提示。新增 openExternalPage，保留公网 HTTPS/DNS 校验；false 明确抛出中文错误，插件异常保留给 UI 显示。按钮显示错误并在等待时禁用，防止重复启动；没有硬编码浏览器路径、改变默认关联、降低 URL 规则或自动提权。四项回归覆盖拒绝 URL 不调用浏览器、返回 false、原生异常及合法 URL 单次交接。

4. 字幕/跳转：没有发现需修改播放器的故障。扩大现有原生集成测试，真实 WebView2 解码生成的 WebVTT Blob，检查 track readyState=2、解码后的中文 cue；跳转新增 2 秒±0.25 秒断言，保留原有播放/暂停/倍速/销毁断言。另在普通窗口通过系统文件对话框，逐层导航到自建 subtitle.vtt 并选择，画面实际显示中文字幕。[真实字幕文件显示](evidence/2026-10-24-followup/real-subtitle.png)。文件对话框输入和菜单操作最初受目标截图/焦点影响；最终针对工具返回的独立对话框截图点击文件完成，没有替代为直接写 DOM。

## SmartScreen 与运行上下文

为排除上次提权环境影响，使用现有桌面壳 `Start-Process explorer.exe -ArgumentList <Debug exe>` 启动。只读查询 Windows TokenElevation：该次测试应用 PID 34100 elevated=false，桌面壳亦为 false。SmartScreen 提示由用户自行点击运行；未自动操作安全提示、去除来源标记、关闭防护或修改系统安全设置。

已检查 Debug exe：Authenticode 为 NotSigned，仅有 `:$DATA` 流，未发现 Zone.Identifier。SHA256 为 `627FEFE522C0FDB340E9E6A9FDA62F3612EBA31BACF122AA7EC8910A7167A0EC`。这证明本机产物没有签名；不能仅凭截图宣称发现病毒，也不能凭无来源流宣称 Microsoft 一定信任它。SmartScreen 的“不认识应用”与应用信誉机制有关，未签名是本机已确认因素，实际信誉判断未查询。正式签名、发布渠道和信誉建立属于发行工作，不能通过自签名保证所有电脑不再提示。参考 [Microsoft 的应用信誉说明](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)。

默认 HTTPS ProgId 为 MSEdgeHTM，对应现有 Edge 可执行文件；只读检查关联，没有修改。普通窗口点击回退后没有应用错误，但起初未观察到浏览器。通过桌面壳打开同一公开网址的对照，随后出现 Example Domain 的 Edge 窗口。再次从应用点击回退，最终想要核对 Edge 的 URL 时，Computer Use 因“无法足够可靠地确定当前浏览器 URL”终止了本轮交互。已停止全部窗口操作；没有通过其他 UI 工具继续或把系统对照启动冒充应用启动成功。**本轮浏览器最终 URL 验收仍未完成**，不能把 launchUrl 返回成功当成页面已显示。

## 实际命令与退出码

工作区根目录为 `D:/computer_work/project/StudyWorkbench`，Flutter 命令工作目录为 `apps/desktop`。所有新运行日志在 [本轮证据目录](evidence/2026-10-24-followup/)。

| 命令 | 退出码 / 结果 |
|---|---|
| `flutter pub get --offline` | 0；接入 flutter_localizations SDK 与 intl 0.20.3，锁文件更新；其他版本保持约束 |
| `dart format lib test integration_test` | 0；格式化新测试文件；最后的无修改格式检查另见工具输出 |
| `flutter analyze --no-pub` | 0；首次 No issues found（43.6 秒），最终包含新增本地化测试再次 No issues found（10.7 秒） |
| `flutter test --no-pub` | 0；首次 11 项，新增本地化测试后最终 **12 项通过** |
| 下述 Windows 原生集成 | 0；**1 项通过**，34.0 秒构建、约 13 秒运行；包含新增字幕及 seek 断言，已有 CMake CMP0175 警告保留 |
| 下述普通 Debug 构建 | 0；30.2 秒；不代表 Release 或安装包 |
| 只读 Get-AuthenticodeSignature、Get-Item -Stream、Get-FileHash、TokenElevation、注册表 HTTPS 关联与进程检查 | 用于诊断，不计为业务测试；最初查询不存在的 Zone.Identifier/未启动进程令组合命令退出 1，后续分开核对正常；未更改文件来源或系统关联 |

```powershell
. ../../tools/prepare-windows.ps1
$env:PATH = 'D:\computer_work\project\StudyWorkbench\.local\bin;' + $env:PATH

flutter test integration_test/m0_test.dart -d windows --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/e2e-followup-20261024 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm `
  --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/artifacts/2026-10-24-followup

flutter build windows --debug --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/interaction-followup-20261024 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm
```

本轮未改变 Python 业务；之前 40 项后端测试证据仍保留，未重复执行或声称本轮重跑。真实中文粘贴提交仅向隔离的 `.local/interaction-20261024` 演示库追加一条测试作答，最终 Debug 使用单独 followup 目录；不包含个人数据库、原件或令牌。没有子 Agent、提交、推送或发布。自审核对了 WebPage 的原有导航和系统浏览器调用者、URL 策略、SDK 本地化、集成测试及锁文件。

实现：中文菜单与回退失败反馈已完成。自动化：12 组件、1 Windows 原生集成、静态与 Debug 构建通过。真实交互：中文粘贴提交、中文菜单与实际字幕显示通过；浏览器 URL 验收被工具中止。人工和阶段：用户整体人工验收未完成，仍为 M0。后续在安全检查允许的浏览器会话中继续回退 URL 核对，以及 IME、DPI/性能与编码/音轨矩阵；Release 故障仍搁置。
