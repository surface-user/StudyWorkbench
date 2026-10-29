# M2 拆题、资料管理与 M4 本地媒体续开发

本批按用户最新优先级推进，PDF/DOCX同等支持；实现、自动化、人工和阶段验收分开记录。ADR 0005继续有效，人工及阶段验收待统一执行，M0默认Release/默认数据目录历史失败未据此清除。本批没有提交、推送、发布或修改用户原件。

## 实现与使用

- **文档拆题**：导入PDF/Word后打开“检查拆题，逐题存为Markdown”。确认前可以改标题、合并相邻候选、拆分Word内容/文字、选择PDF页并调整水平裁切线、手动将原资料块作为多题共享材料。每次修改带候选摘要防止陈旧覆盖；关闭预览后刷新列表，修改仍保留。正式入库后禁止用旧预览覆盖已存MD。
- PDF再次裁切从整页图生成新图，支持跨页候选；因没有逐字坐标，手动裁切后的子题仅保存精确图像，标记`manual_crop_image_only`，不重复复制无法定位的提取文字。Word保留语义块，不能宣称真实分页裁图。共享材料和图像进入每题独立MD及便携导出，原件保留。
- **资料管理**：笔记编辑可从当前空间资源分页选择/上传图片或附件、替换引用，保存前预览；替换不删除旧资源。表格可移除末行/末列且至少保留一行一列。上传成功后即保留资源，即使取消笔记编辑也不自动删除原件。
- **本地媒体**：“播放器”标签成为空间内媒体库，支持MP4/WebM/M4A导入、进度、失败记录及打开播放。512MiB预算按实际接收帧统计，流式写入/计算SHA256，启动后中断的导入标记失败并保留文件。Alembic 0006新增`media_entries`。
- **播放与隔离**：WebView2 HTML5播放器支持跳转、0.5–3倍速、本地WebVTT字幕，自动保存播放位置/速度/字幕，关闭重开可恢复。播放器仅取得绑定单个媒体的临时能力URL，不能调用业务API；Range/HEAD支持、工作空间归属、Origin、文件变化/重新发放前SHA256校验均由Python负责，网页无主机对象和业务令牌。

## 自动验证

证据目录：`docs/evidence/m2-m4-20261025/`。以下命令退出码均为0；各项是自动化证据，不是人工或阶段通过。

| 命令（仓库根目录，Flutter命令在apps/desktop） | 结果 / 日志 |
|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests/test_draft_editing.py backend/tests/test_markdown_questions.py` | 8通过，drafts-01.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_media_library.py` | 3通过，media-01.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests` | Python3.12，122通过，backend312-01.log/xml |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests` | Python3.13，122通过，backend313-01.log/xml |
| `.venv/Scripts/python.exe -m ruff check backend tools` | ruff-04.log；早期歧义变量、导入顺序及urllib局部遮蔽已修复，旧日志保留 |
| `dart format --output=none --set-exit-if-changed lib test integration_test` | 36文件无改动，format-final.log |
| `flutter analyze --no-pub` | analyze-final-02.log；早期风格提示/新增花括号提示修复，旧日志保留 |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m2-m4-pipe-final-02` | 49通过，flutter-all-final-02.log |
| `flutter test integration_test/m0_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m2-m4-native-02 --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/m4-generated.webm --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/m2-m4-20261025` | Windows原生完整流程1项通过，windows-native-02.log；真实解码/播放/跳转/倍速/字幕，并等待服务端保存后重开断言恢复 |
| `powershell -File packaging/windows/build-backend.ps1` | 冻结构建成功，frozen-build-01.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | frozen-lifecycle-01.log；含媒体、题目/笔记/MD、重启/崩溃/两次迁移、EOF/RST等既有断言 |
| `.local/release-venv/Scripts/python.exe tools/check_document_workers.py --exe dist/study_backend/study_backend.exe` | frozen-workers-01.log；真实Word/PDF及逐题解析 |
| `flutter build windows --release --no-pub` | windows-release-01.log；插件既有CMake开发警告仍保留 |

pytest分别使用`.local/m2-m4-drafts-01`、`media-01`、`full312-01`、`full313-01`独立basetemp，并写入同名JUnit文件。Flutter命令实际通过固定SDK的dart.exe运行flutter_tools.snapshot；SDK路径`D:/computer_work/Tools_work/flutter/bin/cache/`，未更换工具链。构建复用`.local/bin`与`.local/nuget-scratch`；Python设置PYTHONUTF8=1，TEMP/TMP使用`.local/tmp`。

原生测试样本是开发工具FFmpeg生成的6秒、320×180、24fps、VP9、无音轨WebM：`-f lavfi -i testsrc=size=320x180:rate=24 -t 6 -c:v libvpx-vp9 -pix_fmt yuv420p -an`，生成退出码0（sample-generation-01.log）。FFmpeg未新增为运行依赖、未随产品分发。后端MP4测试字节仅证明传输/权限/状态，不能证明该字节可解码；原生WebM测试才是实际播放证据，不涵盖音频和全部编码。

## 审查、交付与剩余项

审查覆盖：跨空间/陈旧摘要拒绝、原件保留、共享材料附件复制、手工裁图文字边界、取消后预览刷新、资源替换字段刷新、能力URL不越权、实际帧大小限制、Range/HEAD、文件篡改、播放器并发状态保存及重启恢复。失败断言未删除，迁移head断言按新增0006更新，原有数据保留检查继续运行。

开发目录为`dist/StudyWorkbench-M2-M4-dev-20261025-b3a02497`（同时记录在`evidence/m2-m4-20261025/dev-stage.txt`），入口`study_workbench.exe`。由本批Release和冻结后端复制，入口exe、Dart app.so、后端exe与构建输出逐一比对；`release_inventory.py --stage <上述目录>`退出0，1273文件/71构建环境包，清单/许可见inventory-01.log和stage-check-01.log。最终`ruff check backend tools`与`git diff --check`退出0，见ruff-final.log和diff-check-final.log。它是开发预览，不是新安装包或正式发布；使用时保留同目录backend/data/DLL/licenses。

**仍待开发**：扫描OCR、多栏/复杂题号、共享材料自动归组、MD回写及题目版本编辑；完整备份恢复/ZIP重新导入（现有ZIP不含完整作答/任务和新媒体）；任意表格排版/合并格/图表数据编辑；派生资源孤立恢复；yt-dlp/FFmpeg下载队列、质量选择、取消重试/断点恢复、转码与自动入库。当前本地上传没有续传机制，失败文件保留。**仍待验证**：更广PDF/Word样本、音轨/编码矩阵、大媒体性能、外站兼容、实际安装/卸载/干净机、默认入口和人工/阶段验收。本批不标M2/M4全部完成。
