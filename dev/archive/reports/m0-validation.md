# M0 验证报告（2026-10-23）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

2026-10-24 持续开发：用户已要求恢复 M0 排查。本轮独立 CPython 冻结、原库只读快照、真实网页/视频/字幕回归通过；普通 Release 已出现位置选择页，系统文件安全提示待用户手动处理。用户默认目录完整启动/作答尚未复验，不把快照通过改写为原现场修复。具体命令和状态见 [持续开发报告](m1-completion-2026-10-24.md)。

2026-10-24 阶段调整：用户明确要求暂时忽略 M0 问题、提前开发 M1，已按 ADR 0003 更新约束。本文件保留 M0 历史结果，不将其改为通过；当前 M1 首批状态见 [M1 验证](m1-validation.md)。下文“不进入 M1”为当时的阶段结论。

2026-10-24 后续修复：[修复与复测报告](m0-followup-fixes-2026-10-24.md)。中文编辑菜单和浏览器启动失败反馈已修复；最终 12 组件、增强的 1 项原生集成（新增字幕解码、跳转精度）、静态分析和 Debug 构建通过；真实中文粘贴提交和字幕文件显示通过。浏览器最终 URL 核对被 Computer Use 安全检查中止，未计通过；SmartScreen 的未签名与用户放行已单独记录。Release、用户人工与阶段门禁仍未通过。

2026-10-24 最新验证：[自动交互与自动测评报告](m0-auto-evaluation-2026-10-24.md)。已恢复测试：40 后端、7 组件、1 Windows 集成、源码进程 smoke 及普通 Debug 构建通过；另有真实鼠标/按键与重启持久化证据。首轮沙箱 TEMP 的 5 项 setup errors 已保留，改项目临时目录后通过。系统浏览器回退、中文 IME/文本注入等限制逐项列出。Release 故障继续按用户要求搁置，人工与 M0 阶段验收仍未通过。以下“测试暂缓”和旧计数是 10 月 23 日历史快照。

结论：架构与文档基线、Windows 技术原型及部分自动化链路已建立；**用户 Release 启动人工验收失败，M0 未通过，不进入 M1**。这里的历史“通过”只对应下表实际范围，不能代表当前改动已验证。

后续开发核对：用户要求暂时忽略 Release 故障，本轮未排查或重测该故障。M0-09 加入题目加载重试和作答保存/历史读取分离提示，新增 5 项组件测试但未运行；实际人工验收与文档评审仍待完成。完整范围见 [开发收尾核对](m0-completion-audit.md)。以下历史测试数与构建证据不覆盖本轮代码。

最新状态：用户要求暂缓测试，继续 M0 剩余开发。启动失败页已加入重试、复制详情与滚动显示，后端启动错误补充 UTF-8 捕获和路径；未运行本轮测试、静态检查或重新构建，现有 Release 不包含这些新改动。原始故障见 [用户截图](../../../artifacts/legacy-evidence/user-release-startup-failed.png)。此前新增的冻结后端默认目录集成失败见 [保留日志](../../../artifacts/legacy-evidence/windows-packaged-default-failed.log)：构建后连接成功，但首次作答 HTTP 500；根因仍待排查。AOT 对比诊断被自动审批拦截，未作为验证证据。

环境：Windows 11 25H2（10.0.26200.9711）、Flutter 3.47.1 / Dart 3.13.1、Visual Studio 2022 17.14.19、Windows SDK 10.0.26100.0、WebView2 Runtime 已安装（目录包含 156.0.4314.42）、Python 3.12.7（Anaconda 来源 venv）、SQLite 3.45.3。

| 实际检查 | 结果 | 证据与边界 |
|---|---|---|
| Flutter doctor Windows 工具链 | 退出 0，Windows/VS 通过 | Android SDK 空格路径、未找到 Chrome 是非 Windows 项；不修改用户环境 |
| 玻璃库固定 SHA 原有测试 | 23 项，退出 0 | 包括 4 个 golden；不修改断言或 golden；不证明目标 GPU 帧率 |
| pytest | 40 项，退出 0 | [JUnit](../evidence/backend.xml)，鉴权/Origin/Host、客观与主观评分、多次作答/重启、非法输入、媒体 capability/Range；测试含多个断言 |
| Ruff | 退出 0 | backend + tools；不等于漏洞审计 |
| Flutter analyze | 退出 0，No issues found | lib/test/integration_test |
| Flutter test | 2 项，退出 0 | 公式真实 Math widget 与 URL scheme/私网字面量策略 |
| Windows 原生集成 | 1 项，退出 0 | [通过日志](../evidence/windows-integration-passed.log)，真实 Debug 窗口 + 自有 FastAPI 子进程 + SQLite + WebView2 |
| PyInstaller onedir | 退出 0 | 最终使用 6.22.3；本机冻结 exe smoke 通过，不是干净机分发验收 |
| 源码/冻结后端进程 smoke | 均退出 0 | 握手随机端口、Bearer HTTP、SQLite、stdin EOF 退出；不打印令牌 |
| Windows Release | 退出 0，36.1 秒 | [构建日志](../evidence/windows-release-passed.log)；已复制冻结 backend 到 Release/backend，Release 窗口人工验收待做 |
| GitHub CI | 固定 runner 后整轮通过（5070948）；协议补充提交另行复验 | [通过运行](https://github.com/surface-user/StudyWorkbench/actions/runs/39939193755)；[首次失败证据](../evidence/ci-first-run-failure.md) 保留，未以本地通过替代远程结果 |
| setup.exe | 待验证 | 只有 Inno 模板，当前未安装/运行 ISCC，无安装产物 |

原生集成具体行为：通过实际 UI 提交积分选项得到 1.0、提交解题文字得到 pending_review；切换网页标签读取真实 WebView2 DOM；切到本地播放器，加载由开发用 FFmpeg testsrc 生成的 6 秒 320×180 / 24fps VP9 WebM，无音轨；检查 readyState>=1、播放 currentTime>0、暂停 true、倍速 1.5；最后销毁页面并检查无 Flutter 异常。跳转设置了 currentTime=2，但没有单独作 seek 精度验收。测试通过不证明真实鼠标键盘人工操作或音频播放。

截图：[真实 Windows 原型渲染](../evidence/m0-question.png)。WebView 内容通过原生插件访问，不是静态网页替身。实际运行测试向隔离的 `%LOCALAPPDATA%/StudyWorkbench/m0` 演示库追加作答，不读取用户学习资料。

复现：先按 README 解析依赖；若本机无 Developer Mode，可执行 tools/prepare-windows.ps1（仅项目内 junction 和签名 NuGet），然后本次进程 PATH 加仓库 `.local/bin`；后续 Flutter 命令加 `--no-pub`。`flutter pub get` 重建链接后需再次 prepare。

```powershell
.\.venv\Scripts\python.exe -m pip install --target .local/test-tools imageio-ffmpeg==0.6.0
.\.venv\Scripts\python.exe tools/generate_sample.py
cd apps/desktop
flutter test integration_test/m0_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/e2e-protocol-1 --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm
```

失败保留：

1. Git 初次 clone 遇到 schannel SEC_E_NO_CREDENTIALS；单次 `git -c http.sslBackend=openssl` clone 成功，未改全局配置。
2. 普通沙箱 Flutter 无法写 SDK lock/preferences；工具执行使用受审查的扩展权限。未更改 SDK 源码。
3. Flutter 插件符号链接权限缺失；使用项目内 junction，未启用系统 Developer Mode。
4. 首轮原生构建 NUGET-NOTFOUND / MSB3073 9009；项目内 NuGet 签名校验后设置进程 PATH。
5. 首轮静态错误：AppExitResponse 导入位置、不可用 javaScriptBridgeEnabled；改为 dart:ui 并在安全文档明确当前插件限制。
6. 首轮 E2E 因 IndexedStack 隐藏页定位索引错误中断；修正 finder，未降低播放断言。
7. 第二轮播放断言通过，但 teardown MissingPluginException，整轮仍算失败：[原始日志](../evidence/windows-integration-disposal-failed.log)。根因与版本限定兼容见 ADR 0002，修复后整轮重跑通过。
8. Release/Debug 共享生成资源并行构建时 Release 最后 INSTALL 失败；串行复验，不能据此声称首轮通过。

待验收/风险：人工玻璃性能、DPI/键盘/焦点；外部站点导航/登录/后退/刷新/系统浏览器；DNS 重绑定与所有子资源/弹窗/下载隔离；音频、H.264/AAC 与其他编码/硬件矩阵；字幕选择与真实文件显示；跨启动续播；缺 Runtime 错误路径；独立 CPython 构建、完整许可/NOTICE/SBOM、干净机 setup 安装/自选路径/升级/卸载保留；用户对文档与原型的人工验收。


协议补充：全部七类题型/富内容块的 Python 校验和 JSON Schema 已建立；判分从题目读取选项 ID。40 项后端测试含非法内容、来源、答案、阅读/父题引用与 Schema 漂移；这不证明 M2 全量渲染、导入或业务校验已完成。

本机临时目录复验：当前系统 TEMP 下 NuGetScratch 锁访问失败；新旧冻结后端均在该 TEMP 打开数据库失败，而工作区 ASCII/中文路径都可启动。改用开发进程级 `.local/tmp` 和 `.local/nuget-scratch` 后，NuGet 和冻结后端 smoke 通过。未改系统 TEMP、未删除旧锁；该结果仅证明项目内可写目录，系统 TEMP/其他账户 ACL 的通用兼容性仍待正式环境验证。开发准备脚本已统一设置这些进程级目录。

协议补充后的 Windows 回归：首先 NuGet 锁失败（evidence/windows-protocol-integration-build-failed.log），改进程级临时目录后构建通过，但默认 M0 profile 的答题提交等待超时（evidence/windows-protocol-integration-profile-failed.log）。独立 Python API 对同一默认演示库写入返回 200；该 GUI 超时原因未完全确定。随后使用显式 STUDY_DATA_DIR 隔离到工作区，同样全部断言通过（28.3 秒构建 + 11 秒运行），见 evidence/windows-protocol-integration-passed.log。隔离结果不能替代默认 profile 的后续排查或人工验收。
