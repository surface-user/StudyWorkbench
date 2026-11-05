# LW-01 自由Markdown笔记

2026-11-03。按用户“开始推进任务”实施；设计输入为LW-00契约/ADR0012。当前批次本地交付，不要求提交或新PR，未授权推送/合并/发行；既有PR义务不变。人工/阶段继续统一待验，不操作个人学习库。

## 范围与拆分

1. 追加0013创建收据迁移；复用原件/节点/工作副本，持久幂等及中断重试，不改旧notes/作答。
2. 创建API、请求状态查询、启动中断标记、独占写/hash回读与最终写事务，失败保留字节。
3. 资源目录新建/文件夹菜单及资料、媒体页记笔记，创建后打开MD编辑；复用草稿/冲突/关闭确认。
4. 隔离后端故障/迁移/兼容测试、Flutter组件/静态检查及Windows Release，自审后更新文档。

无新增依赖、无子Agent。基线HEAD为29f23d3558740545a950a51ca04398f9420088fd，保留开始时已有文档治理/R6/其他未提交改动。本批本地实现和自动化完成，人工/阶段待验，不据此退出task。

## 实际实现与设计细化

- 0013只新增markdown_note_creations，不改旧行/旧文件。创建ID同时作稳定节点ID，原件ID独立；规范请求JSON负责同空间幂等；初始MD、hash和受管路径由这些ID/名称确定性派生，避免第三套正文及冗余索引列。原件前置创建ID注释，避免空笔记与旧TXT同hash后缀分流问题。
- prepared收据先提交，原件/工作副本独占写、fsync、回读校验，最后写事务登记资源/节点/工作副本及ready；失败保留字节，启动只标中断，不自动续写。同请求重试沿用原ID，不覆盖已编辑笔记，不复活墓碑。creation_status与当前节点status分开，原件缺失不能伪装ready。
- 增加POST/GET markdown-notes、GET requests及GET requests/{request_id}。枚举按Resource.original_name的MD/MARKDOWN格式，跨文件夹且不依赖显示名后缀；收据列表解决客户端重启/响应丢失后不知道原request_id的问题。两类列表有分页/空间校验，路径不返回客户端。请求沿用64KiB帧预算，不改变旧notes编辑2MiB或MD1MiB预算。
- 资源管理器根目录及文件夹菜单提供新建；共用ResourcePage为资料/媒体页面提供“记笔记”，可新建或选择已有MD，创建后进入既有编辑器。选择前再查节点状态/正文格式，改名/移动仍按ID。没有工作副本的旧MD仍走原显式创建副本规则；旧富内容笔记入口/NoteEditor不变。
- 创建窗口同请求重试，名称修改另建须新request_id；忙时禁止关闭；关闭后的请求保留在后端列表。新笔记复用layout v2草稿/base hash、保存冲突、关闭确认和重启恢复，未引入另一套草稿持久化。
- 更新需求/架构/模型/API/Agent/安全/路线/契约/ADR及task，已实现与规划分开；下一项LW-02。旧M0故障/阶段待验/PR #2/#3义务保持。没有Agent/模型调用、标准答案或作答写入。

## 验证命令与结果

以下PowerShell命令均在仓库根执行，Flutter/Dart命令在apps/desktop。D=`D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe`，F=`D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot`；调用形式为`& D F --suppress-analytics <参数>`，使用现有SDK，没有下载或修改上游代码。产物统一artifacts/lw01-20261103/（Git忽略），各次失败原日志/JUnit保留。

| 实际命令/环境 | 退出码及证据 |
|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests/test_markdown_notes.py -q --basetemp=.local/lw01-notes-01 --junitxml=artifacts/lw01-20261103/notes-01.xml` | 1，7通过/1失败；迁移样本缺默认演示题，启动按旧逻辑补题影响逐行比较。补齐旧库样本演示题，保持原逐行断言，未修改业务来迁就测试 |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/lw01-full-02 --junitxml=artifacts/lw01-20261103/backend-02.xml` | 1，225通过/1失败；既有test_reparse_points_rejected创建junction被沙箱Access denied，未进入安全业务断言。不跳过用例，申请所需工具权限重跑 |
| 同完整命令，basetemp=.local/lw01-full-04、JUnit=backend-04.xml，所需权限执行 | 0，227通过；随后自审补当前节点状态/改名笔记枚举及测试，再跑末轮 |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/lw01-full-final-06 --junitxml=artifacts/lw01-20261103/backend-final-06.xml`，所需权限 | 0，229通过，158.96秒；保留Starlette/AnyIO弃用告警。包括旧notes/R5/QuestionFile/媒体/导出/历史迁移、升级备份与失败回滚，以及新创建故障/幂等/隔离/重启/改名/删除 |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_markdown_notes.py -q --basetemp=.local/lw01-notes-final-05 --junitxml=artifacts/lw01-20261103/notes-final-05.xml` | 0，10通过；节点当前状态自审修正后定向验证 |
| 同笔记专项命令，basetemp=.local/lw01-notes-final-07、JUnit=notes-final-07.xml | 0，11通过/7.94秒；新增导出原件ZIP读回断言，不把当前自由笔记工作副本误称已导出 |
| `.venv/Scripts/python.exe -m ruff check backend tools`、`.venv/Scripts/python.exe tools/export_question_schema.py --check` | 最终均0；首次Ruff仅app.py导入排序失败，已修，未关闭规则 |
| `dart format`（SDK的bat包装） | 首次等待无输出后中止，退出1；改用D直接执行格式化，退出0，不修改SDK |
| `D F test --no-pub test/markdown_note_dialog_test.dart test/resource_explorer_test.dart test/document_page_test.dart test/workspace_layout_test.dart` | 首次-1073741816，SDK cache/lockfile拒写；获工具权限重跑退出1，20通过/1失败：测试tap文字同时匹配输入框和ListTile；改为定位具体ListTile，保留断言 |
| `D F analyze --no-pub` | 初次1，6处花括号风格info；补齐花括号，重跑0。最终flutter-analyze-final.log无问题 |
| `D F test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw01-flutter-03` | 0，99通过；Flutter完整组件/真实后端管道回归，flutter-full-03.log。包含新6项、旧草稿/关闭失败/重启及旧笔记编辑等 |
| `D format --output=none --set-exit-if-changed lib/markdown_note_dialog.dart lib/resource_explorer.dart lib/resource_page.dart lib/workspace_layout.dart lib/workspace_shell.dart test/markdown_note_dialog_test.dart`；`D F analyze --no-pub`；`D F test --no-pub test/markdown_note_dialog_test.dart` | 最终均0；final-exit-codes.json，末轮笔记专项6项通过。末轮查询改为按原件格式枚举后重测；无降低分析/测试要求 |
| `D F build windows --release --no-pub` | 首次1，WebView插件NuGet自定义步骤MSB3073，windows-release-04.log；沿项目prepare-windows约定设置进程级TEMP/TMP=.local/tmp及NUGET_SCRATCH=.local/nuget-scratch后，05轮0/50.3秒；最终源码再次构建0/43.6秒，windows-release-final.log。保留既有插件CMake CMP0175开发告警 |
| `.venv/Scripts/python.exe artifacts/lw01-20261103/check_docs.py` | 0，13份文档、150处本地链接、3处标题锚点与5份新增代码文件UTF-8/尾随空白检查通过；任务待验和旧失败/PR条目存在，docs-final.json。不是业务验收 |
| `git diff --check --` 本批Dart/Python文件、backend/tests、docs及本报告 | 0，仅已有LF/CRLF转换提示；未跟踪新增文件同样由Python检查覆盖 |

旧迁移回归中指向当前head的backup文件名/版本断言由0012同步为0013，未改旧迁移、移除失败断言或放宽数据保持比较。新增0012旧库包含笔记，升级后逐行保持、原件hash及backup原库一致；完整旧DDL故障回滚用例仍通过。

## 审查、限制与人工验收

本批自审完成，非独立人工批准。复核所有insert_node调用方、创建/重试与文件替换、UI打开和layout各分支、当前状态/墓碑、旧notes/事件/导出兼容、分页及空间鉴权。自审修复：另建时复用旧request_id、选择时未重验墓碑、ready收据遮蔽原件缺失、仅按显示名查找漏掉改名和.MARKDOWN笔记；均有针对回归。文件/SQLite不是跨介质事务，也没有新增OS级排他编辑锁；外部同用户进程最后回读到登记之间仍可能改文件，现有读取/保存继续核验hash并保留冲突字节。

限制：未做真实Windows窗口/中文IME/个人库/安装器/干净机/阶段验收；构建不是实际交互证据。没有更新dist或冻结后端组合包。笔记选择仅MD/MARKDOWN，旧富内容笔记继续原入口；来源位置关联仍在LW-02。已有export v1/v2只包含自由笔记初始原件，不含当前MD工作副本，不是完整恢复包；用户当前内容仍在受管工作文件，完整备份/关系恢复必须由LW-05落实。未查询远程PR/CI，不将此前head绿灯当本轮结果。

## 交付状态与下一步

本地实现/自动化/自审已完成，LW-01保持待验收，不满足最终退出条件。无需本批提交/新PR的具体原因：任务约定本地交付且未授权发布本工作区既有改动；未提交/推送/合并/发行。人工按既有统一延后安排保留，下一项LW-02按LearningAnchor v1细化并实现位置书签/备注，不跳过相关自动化和安全测试。
