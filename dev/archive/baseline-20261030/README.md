# StudyWorkbench

2026-10-26：资源中心方案已确认，R1资源树、R2资源身份标签及R3受限文件阅读/Markdown编辑已实施；本批增加可选离线DOCX/PPTX分页预览、公式/图表检查、取消与缓存。实际命令、截图、受限格式和验收边界见[R3记录](docs/r3-office-validation-2026-10-26.md)、[任务](docs/task.md)。默认包不自动附带约1.47GiB转换组件，未替换StudyWorkbench-current；旧DOC/PPT、动态内容、完整发行/干净机及人工/阶段验收仍待验。下方各日期条目为历史，当前状态以上述记录为准。

2026-10-25最新产品方向：以文件和学习资源为核心，拟采用资源树、具体资源标签和类型查看器，题目MD与SQLite学习记录通过稳定ID/确认版本关联。本轮只完成架构审查与文档，**方案待确认，当前开发包仍是此前UI版本**。先看[产品大纲](docs/requirements.md)、[架构](docs/architecture.md)、[审查及最小方案](docs/resource-first-architecture-review.md)与[实施顺序R1–R6](docs/task.md)。

2026-10-25 UI改造：标签栏已更新为38px连续编辑器样式，支持溢出列表、右键关闭、Ctrl+数字定位、未保存草稿确认。关闭/重排其他标签保持网页与播放器实例，后台视频继续播放；61项Flutter、9项后端空间回归和1项真实Windows五标签流程通过。截图、失败修复与限制见[UI交付记录](docs/editor-tabs-validation-2026-10-25.md)。人工/阶段仍待统一验收。

2026-10-25当前开发入口：`dist/StudyWorkbench-current/study_workbench.exe`（完整目录约154MiB）。首次自动使用Windows默认用户数据位置，之后可在设置修改；原数据位置拒写时，错误页可明确选择“使用默认数据位置”，不会删除原目录。默认位置的真实Windows/冻结后端启动已自动验证，普通用户人工/阶段验收仍待执行。工程体积与缓存清理、测试/打包证据见[最新记录](docs/default-startup-2026-10-25.md)。后续交付固定此目录，下面带日期开发包均为历史版本。

2026-10-25启动修复开发版：`dist/StudyWorkbench-startup-fixed-20261025-2af3c1f0/study_workbench.exe`。配置目录不可写时可继续使用所选可写数据目录并明确提示位置未保存；请从Windows文件资源管理器打开开发目录运行并选择原数据目录。命令、自动化及实际普通启动待验边界见[启动修复记录](docs/startup-config-fix-2026-10-25.md)。下面开发包保留为此前批次。

2026-10-25最新批次：拆题预览支持人工合并/分割/PDF重裁/共享材料；笔记支持图片附件选择上传替换；播放器标签支持本地媒体入库、跳转倍速字幕及续播。最新开发目录、命令/证据与待开发内容见[M2/M4记录](docs/m2-m4-continuation-2026-10-25.md)及[任务状态](docs/task.md)。人工/阶段仍待统一验收，完整备份恢复和下载队列尚未实现。以下旧批次能力/产物说明保留为历史。

2026-10-25：按用户澄清推进“文档识别拆题→每题独立Markdown→本地知识库”。PDF/DOCX同等接入显式题号候选，侧栏“导入资料”选择`contracts/samples/numbered-questions.docx`或`.pdf`，点击“检查拆题，逐题存为Markdown”，检查后确认；已保存题目在“本地题目知识库（Markdown）”中独立打开/按标题检索，资料导出附可单独打开的MD与图片。当前范围和本机开发目录见[本批记录](docs/m2-splitting-2026-10-25.md)，人工/阶段仍待验，OCR和手动边界调整未实现。后文M1安装包保持历史说明，不代表包含本批功能。

2026-10-24：当前源码继续开发 M2，人工/阶段验收按用户要求在 task.md 完成后统一进行（ADR 0005）。新增“导入资料”入口，支持原件保留/哈希去重、JSON与文本资料预览确认、共享文章/笔记及表格/受控图片预览。使用侧栏“导入资料”，可选择 contracts/import-bundle-v1.json 查看自编样例。当前源码结果和限制见 [M2记录](docs/m2-validation.md)；下列 dist 的 M1 安装包是此前产物，不包含本轮 M2 功能。

Windows 个人学习、知识、资料和本地媒体工作台。核心业务无需 LLM。

以下为此前 **M1 开发预览** 的运行说明。工作空间隔离、动态标签与拖动、数据目录选择/校验迁移、异常恢复和独立冻结安装包构建的历史记录见 [M1报告](docs/m1-completion-2026-10-24.md)；当前源码与任务状态以 [docs/task.md](docs/task.md) 和 [M2记录](docs/m2-validation.md) 为准。

本机最新普通预览入口：`dist/StudyWorkbench-M1-20261024-background-fixed/study_workbench.exe`；安装包：`dist/StudyWorkbench-M1-setup.exe`。此目录含本轮后台测试修复，旧 090800 目录保留。命令与限制见 [后台续测](docs/m1-background-2026-10-24.md)。同目录 backend/DLL/data/licenses 必须保留；无需仓库 Python。Debug 目录可能是集成测试入口，请勿拿它当普通产品。安装包尚未通过实际安装/卸载及干净机验收，应用未签名；Windows 文件安全提示须用户手动处理，程序不会关闭安全防护。

侧栏可创建、重命名、移除/恢复工作空间；移除需要确认并保留学习数据。右上角“+”新增题目、网页或播放器标签，标签上的关闭按钮关闭页面，旁边恢复按钮重新打开最近关闭页。每空间的作答、草稿、标签和最后选中页独立保存，重启后恢复。

## 开发运行

本次验证基线为 Flutter 3.47.1 / Dart 3.13.1、Python 3.12、Visual Studio C++ 桌面工作负载及 Windows SDK、WebView2 Runtime。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
cd apps/desktop
flutter pub get
# 若插件符号链接权限不足，在仓库根目录执行 tools/prepare-windows.ps1，
# 并将仓库 .local/bin 加入本次进程 PATH，之后用 --no-pub 运行。
flutter run -d windows --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m1-dev
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

2026-10-27 R4源码：题目Markdown可预览、显式确认不可变版本后作答，缺答案待批改；旧JSON/提取MD可显式创建编辑文件，保留原件和旧分数。协议、实际测试、失败与限制见[R4记录](docs/r4-validation-2026-10-26.md)。本批未替换dist/StudyWorkbench-current，人工/阶段验收仍待统一进行；下一步R5。

2026-10-29 R5进行中：学习历史可追加错误注记/自评/复习记录，查看作答时确认快照及打开当前题目/来源。自动化与剩余工作见[R5首批](docs/r5-records-2026-10-29.md)。本批没有替换现有发行包，人工/阶段仍待统一验收。

2026-10-29 R5完成批：笔记显式关联/阅读、记录知识点修订和可重建投影已完成实现、自动化与审查，保留旧分数/原题及历史版本未知。实际命令、截图、失败和限制见[R5完成记录](docs/r5-completion-2026-10-29.md)。人工/阶段待统一验收，现有发行目录未替换。
