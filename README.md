# StudyWorkbench

Windows 个人学习、知识、资料和本地媒体工作台。核心业务无需 LLM。

当前为 **M0 技术原型**，不是完整产品。本机 Release 已构建，入口为 `apps/desktop/build/windows/x64/runner/Release/study_workbench.exe`，需保留同目录 DLL、data 和 backend 文件夹。阶段状态见 [docs/task.md](docs/task.md)，测试证据见 [docs/m0-validation.md](docs/m0-validation.md)。

## 开发运行

本次验证基线为 Flutter 3.47.1 / Dart 3.13.1、Python 3.12、Visual Studio C++ 桌面工作负载及 Windows SDK、WebView2 Runtime。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
cd apps/desktop
flutter pub get
# 若插件符号链接权限不足，在仓库根目录执行 tools/prepare-windows.ps1，
# 并将仓库 .local/bin 加入本次进程 PATH，之后用 --no-pub 运行。
flutter run -d windows --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench
```

原型自动启动 Python 后端并从私有 stdin 发送临时令牌；源码运行需 STUDY_ROOT 指向仓库绝对路径。关闭窗口时终止其子进程。生产版使用同目录 backend/study_backend.exe（M1 验证）。数据默认在 `%LOCALAPPDATA%/StudyWorkbench/m0`，不在程序目录。

开发/测试可用 `--dart-define=STUDY_DATA_DIR=D:/absolute/test-data` 隔离数据与 WebView profile；该开关只在构建时指定，不代替 M1 的首次目录选择或安全迁移设置。不得指向正式学习目录做技术测试。

视频验证：通过 `--dart-define=STUDY_MEDIA=C:/absolute/path/owned-video.mp4` 指定本人有权使用的视频。不指定时播放器显示缺少样本；不会下载网络视频。建议先测 H.264/AAC MP4，再测 VP9/Opus WebM；具体编解码支持必须实测。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend tools
cd apps/desktop
flutter analyze
flutter test
flutter build windows --release
```

文档入口：[需求](docs/requirements.md) · [架构](docs/architecture.md) · [题目协议](docs/question-content-spec.md) · [依赖审查](docs/dependencies.md)。


