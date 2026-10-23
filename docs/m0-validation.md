# M0 验证报告（2026-10-23）

结论：架构与文档基线、可运行 Windows 技术原型及主要自动化链路已建立；**M0 尚待人工验收，不进入 M1**。这里的“通过”只对应下表实际范围。

环境：Windows 11 25H2（10.0.26200.9711）、Flutter 3.47.1 / Dart 3.13.1、Visual Studio 2022 17.14.19、Windows SDK 10.0.26100.0、WebView2 Runtime 已安装（目录包含 156.0.4314.42）、Python 3.12.7（Anaconda 来源 venv）、SQLite 3.45.3。

| 实际检查 | 结果 | 证据与边界 |
|---|---|---|
| Flutter doctor Windows 工具链 | 退出 0，Windows/VS 通过 | Android SDK 空格路径、未找到 Chrome 是非 Windows 项；不修改用户环境 |
| 玻璃库固定 SHA 原有测试 | 23 项，退出 0 | 包括 4 个 golden；不修改断言或 golden；不证明目标 GPU 帧率 |
| pytest | 4 项，退出 0 | [JUnit](evidence/backend.xml)，鉴权/Origin/Host、客观与主观评分、多次作答/重启、非法输入、媒体 capability/Range；测试含多个断言 |
| Ruff | 退出 0 | backend + tools；不等于漏洞审计 |
| Flutter analyze | 退出 0，No issues found | lib/test/integration_test |
| Flutter test | 2 项，退出 0 | 公式真实 Math widget 与 URL scheme/私网字面量策略 |
| Windows 原生集成 | 1 项，退出 0 | [通过日志](evidence/windows-integration-passed.log)，真实 Debug 窗口 + 自有 FastAPI 子进程 + SQLite + WebView2 |
| PyInstaller onedir | 退出 0 | 最终使用 6.22.3；本机冻结 exe smoke 通过，不是干净机分发验收 |
| 源码/冻结后端进程 smoke | 均退出 0 | 握手随机端口、Bearer HTTP、SQLite、stdin EOF 退出；不打印令牌 |
| Windows Release | 退出 0，36.1 秒 | [构建日志](evidence/windows-release-passed.log)；已复制冻结 backend 到 Release/backend，Release 窗口人工验收待做 |
| GitHub CI | 已建立工作流 | 远程结果另行记录，不能以本地结果替代 |
| setup.exe | 待验证 | 只有 Inno 模板，当前未安装/运行 ISCC，无安装产物 |

原生集成具体行为：通过实际 UI 提交积分选项得到 1.0、提交解题文字得到 pending_review；切换网页标签读取真实 WebView2 DOM；切到本地播放器，加载由开发用 FFmpeg testsrc 生成的 6 秒 320×180 / 24fps VP9 WebM，无音轨；检查 readyState>=1、播放 currentTime>0、暂停 true、倍速 1.5；最后销毁页面并检查无 Flutter 异常。跳转设置了 currentTime=2，但没有单独作 seek 精度验收。测试通过不证明真实鼠标键盘人工操作或音频播放。

截图：[真实 Windows 原型渲染](evidence/m0-question.png)。WebView 内容通过原生插件访问，不是静态网页替身。实际运行测试向隔离的 `%LOCALAPPDATA%/StudyWorkbench/m0` 演示库追加作答，不读取用户学习资料。

复现：先按 README 解析依赖；若本机无 Developer Mode，可执行 tools/prepare-windows.ps1（仅项目内 junction 和签名 NuGet），然后本次进程 PATH 加仓库 `.local/bin`；后续 Flutter 命令加 `--no-pub`。`flutter pub get` 重建链接后需再次 prepare。

```powershell
.\.venv\Scripts\python.exe -m pip install --target .local/test-tools imageio-ffmpeg==0.6.0
.\.venv\Scripts\python.exe tools/generate_sample.py
cd apps/desktop
flutter test integration_test/m0_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm
```

失败保留：

1. Git 初次 clone 遇到 schannel SEC_E_NO_CREDENTIALS；单次 `git -c http.sslBackend=openssl` clone 成功，未改全局配置。
2. 普通沙箱 Flutter 无法写 SDK lock/preferences；工具执行使用受审查的扩展权限。未更改 SDK 源码。
3. Flutter 插件符号链接权限缺失；使用项目内 junction，未启用系统 Developer Mode。
4. 首轮原生构建 NUGET-NOTFOUND / MSB3073 9009；项目内 NuGet 签名校验后设置进程 PATH。
5. 首轮静态错误：AppExitResponse 导入位置、不可用 javaScriptBridgeEnabled；改为 dart:ui 并在安全文档明确当前插件限制。
6. 首轮 E2E 因 IndexedStack 隐藏页定位索引错误中断；修正 finder，未降低播放断言。
7. 第二轮播放断言通过，但 teardown MissingPluginException，整轮仍算失败：[原始日志](evidence/windows-integration-disposal-failed.log)。根因与版本限定兼容见 ADR 0002，修复后整轮重跑通过。
8. Release/Debug 共享生成资源并行构建时 Release 最后 INSTALL 失败；串行复验，不能据此声称首轮通过。

待验收/风险：人工玻璃性能、DPI/键盘/焦点；外部站点导航/登录/后退/刷新/系统浏览器；DNS 重绑定与所有子资源/弹窗/下载隔离；音频、H.264/AAC 与其他编码/硬件矩阵；字幕选择与真实文件显示；跨启动续播；缺 Runtime 错误路径；独立 CPython 构建、完整许可/NOTICE/SBOM、干净机 setup 安装/自选路径/升级/卸载保留；用户对文档与原型的人工验收。

