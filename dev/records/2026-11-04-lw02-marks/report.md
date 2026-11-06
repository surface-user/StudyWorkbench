# LW-02 位置书签与备注

2026-11-04。按用户继续开发授权推进，采用LW-00契约及ADR0012。独立功能使用本任务唯一报告，后续重测/审查继续追加。仅本地交付，不要求本批提交/新PR，不授权推送/合并/发行；人工/阶段统一待验。

## 实施设计与任务拆分

1. 0014新增标记、修订与显式笔记关系；旧库先备份、旧记录不重写，删除仅墓碑，修订追加。
2. 严格LearningAnchor v1及受控捕获：资源级、PDF/派生PDF页、MD/TXT原文行、媒体时间。后端读取真实hash/页数/行数/时长，未知时长不能建时间标记。列表只读摘要，详情/跳转才做完整校验，避免100份大文档同时重渲染。
3. 媒体时长采用标准库受限读取MP4/M4A mvhd、WebM Info元数据，不安装新组件；不执行媒体内容，不等同验证解码。依据Apple Movie header atom及Matroska元素规范；不完整/未知时长降级资源级。
4. API创建幂等、expected_revision冲突、编辑/重关联保留旧修订；跨空间约束、分页、移除/内容变化提示。关系区分文件笔记与旧富内容笔记，不改R5事件。
5. 原生书签/备注列表及编辑、关联/打开笔记、来源回跳；文档按页/原文行，播放器仅在本地可信页面读当前位置/执行数值跳转，不向外部网页注册业务桥或传令牌。
6. 隔离后端/Flutter/静态及Windows构建、自审和对应规范更新。原始日志写artifacts/lw02-20261104/；不操作个人库，不创建子Agent。

接口细化：POST W/nodes/{id}/learning-anchor由后端生成位置快照；GET标记列表返回摘要且不声称已验证位置，GET单标记核对当前位置；GET修订按页读取旧快照。关联笔记替换集合推进修订并保留旧集合；恢复来源不复活目录墓碑。实际字段见[API](../../../docs/api-spec.md)，持久化结构见[数据模型](../../../docs/data-model.md)。

参考：[Apple mvhd](https://developer.apple.com/documentation/quicktime-file-format/movie_header_atom)、[Matroska元素](https://www.matroska.org/technical/elements.html)。这些仅为读取时长的格式依据，不是产品功能通过证明。设计时尚未验证；实施与验证结果追加如下。

## 实施与自审

本批基于HEAD `29f23d3558740545a950a51ca04398f9420088fd`及既有未提交工作树继续开发；以下结果对应本地修改，不是该提交自身的功能证明。保留前批目录治理、LW-00/01及R6变更，未提交、推送或查询远程CI。

- 后端增加0014、learning_marks及受限媒体元数据读取器；原件不改写，跨空间组合外键、修订禁止UPDATE/DELETE，标记仅墓碑移除。创建收据绑定初始规范化请求，编辑/删除后同请求重试仍可辨认原结果，不能复活旧记录。
- 支持同位置多条命名书签、备注、修订、显式关联Markdown文件与旧富内容笔记。标题/备注修改、关系替换与重新定位均要求expected_revision；未知历史锚点原样保留并报告不支持。列表分页读取摘要，详情才验证字节及位置，沿用查看器并发预算。
- 原生目录提供集中入口，文档/资源媒体提供当前位置入口。PDF按页，MD/TXT按明确原文行，媒体时间要求播放器已就绪且后端有可信时长。跳转前重读状态；改名/移动保持ID，内容变化/移除/缺失均有明确反馈。Office旧分页版本保持原预览ID/hash，存在新版时提示将打开保留旧版。
- 文件笔记入口自动保存来源关系；反向查询来源并回跳。创建笔记与关联分两步：关联失败保留已创建笔记和固定重试请求，不重复创建笔记；已存在同资料/笔记关系时复用，不每次打开都添记录；已移除收据不能当新关联成功。旧R5事件/富内容笔记仍保留。
- 本批自审修复：内容版本不符时不能先更新为未展示的新hash；忙碌保存期间到达的定位须在保存后执行且不循环；播放器只允许精确匹配当前本地player URL/cap的固定数值脚本；来源关联失败与重试不能假报成功。临时定位只在运行时tab状态中传递，不混入持久布局。

自审覆盖调用方、迁移与边界测试，属于开发者自审；未进行独立人工代码批准。无新增第三方依赖、模型调用或Agent数据权限。现行需求、架构、协议、数据/API及安全文档按职责更新，任务进度只放task与本报告。

## 自动化命令与结果

工作目录除Flutter命令外均为仓库根。Python使用`.venv/Scripts/python.exe`（下称`P`）；Flutter目录`apps/desktop`，Dart使用`D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe`（下称`D`），工具快照`D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot`（下称`F`）。Flutter实际入口为`D F --suppress-analytics <参数>`，未升级SDK/依赖。

环境：`FLUTTER_SUPPRESS_ANALYTICS=true`、`DART_SUPPRESS_ANALYTICS=true`，`TEMP/TMP=D:/computer_work/project/StudyWorkbench/.local/tmp`，`NUGET_SCRATCH=D:/computer_work/project/StudyWorkbench/.local/nuget-scratch`。SDK缓存写入及Windows junction测试使用获准的扩展执行权限；没有操作个人库或结束用户进程。原始日志/JUnit位于被Git忽略的`artifacts/lw02-20261104/`，未整包晋升evidence。

| 实际命令（入口缩写如上） | 退出码/结果 | 原始产物 |
|---|---|---|
| `P -m pytest backend/tests --basetemp=.local/lw02-full-final-06 --junitxml=artifacts/lw02-20261104/backend-final-06.xml -q` | 0；239通过，148.25秒 | backend-final-06.log/xml |
| `P -m pytest backend/tests/test_learning_marks.py --basetemp=.local/lw02-marks-final-07 --junitxml=artifacts/lw02-20261104/marks-final-07.xml -q` | 0；10通过，18.96秒；全套后仅增强迁移测试断言 | marks-final-07.log/xml |
| `P -m ruff check backend tools` | 0；通过 | 终端输出及退出码static-final.json |
| `P tools/export_question_schema.py --check` | 0；通过，既有题目协议未漂移 | 同上 |
| `D format lib/learning_marks_dialog.dart lib/markdown_note_dialog.dart lib/document_page.dart lib/media_page.dart lib/resource_explorer.dart lib/resource_page.dart lib/workspace_layout.dart lib/web_page.dart lib/url_policy.dart test/learning_marks_test.dart test/markdown_note_dialog_test.dart` | 0；11文件格式通过 | dart-format-final-07.log |
| `D F --suppress-analytics analyze --no-pub` | 0；No issues found | flutter-analyze-final-07.log |
| `D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw02-flutter-final-07` | 0；112通过 | flutter-full-final-07.log |
| `D F --suppress-analytics build windows --release --no-pub` | 0；44.0秒，生成Release exe | windows-release-final-07.log |
| `P artifacts/lw02-20261104/check_docs.py` | 0；44份Markdown、215处本地链接/6处标题锚点通过，114份受保护历史文件SHA256不变，8项原报告索引 | docs-checks.json |
| `git diff --check`；`git check-ignore artifacts/lw02-20261104/docs-checks.json` | 各0；格式检查通过，原始产物仍忽略；Git仅提示既有LF/CRLF转换策略 | static-final.json |

末轮Flutter四项退出码存`flutter-exit-final-07.json`。构建仍有CMake CMP0175开发警告；Python仍有Starlette引用anyio旧别名的弃用警告，两者不算零警告。未更新冻结后端、dist、安装包或发行配置，不能把本地源码测试/桌面构建等同已验证的完整发行组合。

后端覆盖创建重试/并存、修订冲突与不可变性、改名移动、内容变化/重新定位、重启、源移除、跨空间、未知锚点、分页、笔记关系、PDF页、MP4 v0/v1与WebM时长边界、Office保留旧预览/损坏、0013→0014成功及故障回滚。升级专项核对失败仍为0013、成功为0014、旧记录/字节与备份保留，升级后可建标记并关联旧笔记。Flutter覆盖确认移除、保存/关联失败重试、未就绪播放器、精确本地URL、原文行、旧hash、保存期间定位及来源复用/墓碑收据；不替代实际WebView解码和鼠标流程。

## 中间失败与复测

- 首轮静态检查发现导入/未使用变量与测试lambda，逐项修正后通过；未删除测试或弱化断言。
- `flutter-targeted-03.log`保留24通过/1失败：测试输入后未pump即点击仍禁用的保存按钮，补pump后保留原断言。该轮分析另报未使用导入，随后真实播放器测试使用该导入。
- `flutter-full-04.log`保留108通过/1失败：新增“保存期间定位”测试输入与初值相同，未触发保存；修正为真正编辑内容，仍要求保存结束后定位。新增测试一度误放class内导致格式语法失败，移回main后继续验证。
- `flutter-full-05.log`为109通过，`flutter-full-final-06.log`为110通过；后续新增来源关系墓碑/复用检查，最终112通过。final-06分析报两处测试流程缺花括号的info，补齐后final-07分析通过。
- 早期后端7/10项、全套239及Windows各轮结果保留原日志；不以末轮绿灯删除中间失败或既有M0/owner/PR故障。

## 人工、交付与下一步

实现、自动化及本批自审完成；真实窗口/中文IME/DPI、真实媒体编码和本地播放器seek、复杂Office、用户人工/阶段、安装/干净机均未执行，保持**待验收**。MP4/WebM单元测试是元数据构造样本，不证明能播放。传统媒体工具页无稳定资源节点时不提供位置标记，需从资料树资源页进入。未保存的备注草稿只在当前窗口保留并提示关闭确认，不承诺崩溃恢复。

当前export v1/v2仍缺自由工作文件、标记/修订/关系的完整恢复；迁移备份不等于LW-05整库备份。内部URI/集中搜索仍属LW-03/04。下一开发项为LW-03；本任务保留在task，不据自动化通过退出。本批不要求提交/新PR；未创建PR、未推送/合并/发行，远程head/CI未知，旧PR交付义务不变。
