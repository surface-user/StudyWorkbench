# 资源中心续开发记录（2026-10-26）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

后续已完成R3受限DOCX/PPTX离线分页增量，追加0009；当前命令、真实公式/图表内容、取消/缓存/迁移及冻结/Windows证据见[R3后续记录](r3-office-validation-2026-10-26.md)。下方“Word/PPT仍未实施”为首批历史结论，不代表当前；人工及阶段仍统一待验。

用户授权从R1检查后按R1–R6顺序继续开发、自动测试和审查。人工与阶段验收仍统一待验。本轮不创建子Agent，不读取/迁移个人库，不发布、合并或替换已有开发包。当前分支codex/m1-workspaces-tabs，前序大量未提交内容保持。

## R1复核

已完整阅读AGENTS.md、docs/requirements.md、architecture.md、question-content-spec.md、task.md，以及R1设计/验证与资源架构审查。根目录不存在简写的architecture.md/question-content-spec.md/task.md，改为docs下实际路径读取。复核当前目录服务、0007迁移与调用链。

证据目录：docs/evidence/resource-continuation-20261026。

| 实际命令（仓库根） | 退出码/结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q --basetemp=.local/resource-continuation-r1 --junitxml=docs/evidence/resource-continuation-20261026/r1-baseline.xml`，TEMP/TMP为.local/tmp，PYTHONUTF8=1 | 1；153通过，1失败；r1-baseline.log。唯一失败是受限进程创建隔离测试目录联接被拒绝，未改断言 |
| 同环境 `.venv/Scripts/python.exe -m pytest backend/tests/test_explorer.py::test_reparse_points_rejected -q --basetemp=.local/resource-continuation-junction --junitxml=docs/evidence/resource-continuation-20261026/r1-junction.xml`，自动审批允许隔离联接测试 | 0；1通过；r1-junction.log |

R1已有实现及上一轮冻结/Windows证据继续保留；本轮基线不冒充组合安装包验收。人工/阶段仍待验。

## R2资源身份标签

设计与任务拆分见[r2-design.md](r2-design.md)。实现及审查完成，自动化通过；人工/阶段待验。资源树点击通过统一openResource打开具体节点，同空间resource_item_id+view_kind去重，同名/同hash的不同节点不合并。v1旧utility/ID/顺序/草稿/URL保持；v2未知kind有预算地原样保存并显示惰性占位，已知kind不能借未知分支绕过校验。跨空间现存ID拒绝，缺失ID可保留占位/重试。资源改名/移动同步标题，重开优先恢复关闭历史中的同资源及模式/位置，历史中已打开的别名只激活而不重复建页。

新建快捷键/标签空白双击进入欢迎页。EditorTabBar/PageHost继续使用原动效、稳定实例、16开/10关预算和关闭释放。网页保持独立WebView无桥/令牌；媒体按MediaEntry直接申请能力，后端重启重新申请，URL只在内存。记录/搜索关联仍待R5数据关系，统一方法已可复用，不宣称这些旧入口已经关联到具体文件。

R2单独检查结果：Python3.12全量156，发行Python3.13定向38，Flutter68，Windows真实资源标签1，Release构建、Ruff与Dart分析通过。R3后的最终合并回归见下表。截图与JSON：resource-tabs-windows.png、resource-tabs-native.json。

## R3首批文件查看/编辑

设计/兼容决策见[r3-design.md](r3-design.md)、[ADR0008](../../../docs/adr/0008-resource-tabs-and-document-workfiles.md)。首批实现、自动化和审查已完成；**R3全阶段尚未完成，不越过Word/PPT转换缺项进入R4。** 人工/阶段待统一验收。

- MD明确创建受管工作副本后编辑，原文/阅读页内切换，已有flutter_math_fork公式，受保护逻辑相对PNG/JPEG；外部/绝对图片拒绝，链接只显示地址。当前保存工作副本不改既有Question/MarkdownQuestion判分缓存与历史作答。空字符串草稿用expected hash区分“有意清空”和“没有草稿”。
- 0008仅增document_workfiles与document_saves。保存前校验磁盘hash，保留旧字节和待写内容/fsync，prepared收据先提交、同目录replace、最后索引/committed。重启区分new/old/其他hash，不回放覆盖外部文件。测试覆盖替换失败、文件已换但DB提交失败、外部内容、备份/原件/旧行/FK保持。恢复点与失败字节不自动清理。
- PDF读取128MiB/2000页，逐页最长边2048像素，不再套用旧拆题8MiB/20页预算；真实21页阅读及末页PNG通过，旧拆题限制保持。图片PNG/JPEG经Pillow规范化，16MiB/1600万像素；DOCX复用8MiB结构转换，含中文/公式/图片，不代表分页全保真。来源资源/hash及渲染/转换版本随预览返回；页图当前按请求生成，不提前建通用缓存。
- layout v2持久化文档模式、页码、缩放、滚动、文件草稿/基准hash；保存layout仍视为文件未保存，关闭继续确认，文件保存冲突保留标签/草稿。窗口级早期快捷键避免编辑框/根焦点吞掉Ctrl+W；当前路由非活动（对话框/弹窗）时不拦截。实际原生WebView焦点/硬件键盘仍有人工边界。
- 新增flutter_markdown_plus1.0.12和markdown7.3.1，精确锁定及许可/维护/Windows/未验项记录于dependencies.md；未修改玻璃库、上游或缓存源码。普通功能不依赖LLM，未运行Office或安装新转换器。

## 实际命令与最终证据

Flutter在apps/desktop执行，`flutter-snapshot`完整前缀为：`& 'D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe' 'D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot'`。Dart为同目录dart.exe。后端命令在仓库根，TEMP/TMP为项目.local/tmp、PYTHONUTF8=1。Windows先执行`. ../../tools/prepare-windows.ps1`并将`.local/bin`加入本进程PATH；未修改机器配置。SDK缓存锁与隔离联接测试按工具审批运行。

| 实际命令/操作 | 退出码/结果与日志（均在本轮证据目录） |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q --basetemp=.local/r2-full312 --junitxml=docs/evidence/resource-continuation-20261026/r2-full312.xml` | 0，156；r2-full312.log |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests/test_workspaces.py backend/tests/test_explorer.py -q --basetemp=.local/r2-target313 --junitxml=docs/evidence/resource-continuation-20261026/r2-target313.xml` | 0，38；r2-target313.log |
| `flutter-snapshot test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r2-flutter-full02` | 0，68；r2-flutter-full02.log |
| `.venv/Scripts/python.exe -m pytest -q --basetemp=.local/r3-full312-final --junitxml=docs/evidence/resource-continuation-20261026/r3-full312-final.xml` | 0，164无跳过；r3-full312-final.log |
| `.local/release-venv/Scripts/python.exe -m pytest -q --basetemp=.local/r3-full313-final --junitxml=docs/evidence/resource-continuation-20261026/r3-full313-final.xml` | 0，164无跳过；r3-full313-final.log |
| `flutter-snapshot pub get` | 0，仅增加上述两个纯Dart/Flutter包；r3-pub-get.log |
| `flutter-snapshot test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r3-flutter-full-final02` | 0，73，含真实后端管道；r3-flutter-full-final02.log |
| `dart.exe format lib test integration_test`；`dart.exe analyze lib test integration_test` | 0，53文件；分析无问题，r3-analyze-final02.log；后续只补原生截图树刷新 |
| `.venv/Scripts/python.exe -m ruff check backend tools --fix` | 0；r3-ruff-final.log（先前仅修import排序）；最终另做无修改检查 |
| Windows准备后 `flutter-snapshot test integration_test/resource_tabs_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r2-native02 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/resource-continuation-20261026 --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/m4-generated.webm` | 0，1；r2-native02.log，最终R3上同流程复跑另记r2-native-final.log |
| Windows准备后 `flutter-snapshot test integration_test/document_viewers_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r3-native07 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/resource-continuation-20261026` | 0，1；r3-native07.log及document-viewers-native.json，截图document-viewers-windows.png；最终树刷新截图复跑另记 |
| Windows准备后 `flutter-snapshot build windows --release --no-pub` | 0；r2-release.log、r3-release-final.log。只构建，未启动个人默认目录或装入旧开发包 |
| 独立CPython PyInstaller初建（参数见下）；`.local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath .local/r3-frozen/dist --workpath .local/r3-frozen/build .local/r3-frozen/study_backend.spec` | 均0；r3-frozen-build.log、r3-frozen-build-final.log；新的.local/r3-frozen，不覆盖旧dist |
| `.local/release-venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/r3-frozen/dist/study_backend/study_backend.exe --test-root .local/r3-frozen-docs-final --documents` | 0；r3-frozen-docs-final.log。无源码cwd/移除开发Python环境及PATH，真实loopback复制、去重身份、MD保存/冲突/重启、PDF末页、DOCX及v2草稿/作答保持 |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe .local/r3-frozen/dist/study_backend/study_backend.exe` | 0；r3-frozen-lifecycle-final.log。EOF/异常重启/锁、作答、旧导入/拆题/媒体及两次迁移，未传个人seed-db |
| `git -c core.safecrlf=false diff --check` | 0；diff-check-first.log，最终文档/路径检查另记 |

PyInstaller初建完整参数：`.local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --onedir --name study_backend --distpath .local/r3-frozen/dist --workpath .local/r3-frozen/build --specpath .local/r3-frozen --paths "$PWD/backend" --collect-submodules study_workbench --copy-metadata docling-slim --copy-metadata docling-core --copy-metadata doclang --copy-metadata pypdfium2 --copy-metadata python-docx --copy-metadata pylatexenc --add-data "$PWD/backend/migrations;migrations" --add-data "$PWD/backend/study_workbench/player.html;study_workbench" --add-data "$PWD/backend/study_workbench/library_player.html;study_workbench" tools/frozen_entry.py`。

## 失败保留与修复

- R1基线及r2-targeted01的联接创建被受限进程拒绝；R1单项与后续完整授权隔离回归均通过，未删除或跳过用例。
- r2-flutter01受SDK lockfile写权限拒绝；按工具审批使用已有SDK复跑。r2-flutter-full01为67通过/1失败：仍期望旧study默认页，更新为明确welcome规则；旧交互/历史断言保持，02为68通过。r2-native01因测试点击屏外关闭按钮失败，使用真实Ctrl+W后02通过。
- r3-docs01为6通过/1失败，PDFium页面对象不支持上下文管理器，改显式try/finally close；02为7通过。审查再补并发预算用例，最终双Python各164。
- r3-flutter01测试公式字符串未转raw造成Dart插值编译失败；改真实多行raw样例，02的14定向通过。r3-flutter-full01为72通过/1失败，文档页不需要的WebView profile提前读取让测试替身缺dataDir；将profile延迟到网页/媒体分支，同时Dart文档状态合并缺省字段。最终73通过。
- r3-native01/02冲突步骤输入连接/重建时序未触发，补真实点击获焦、帧更新及控制器/草稿断言；03–05在冲突后Ctrl+W失败，保留失败日志，定位窗口根焦点而非文档子树，改窗口当前路由的早期分派，组件另验证对话框隔离；06继续暴露从树重开丢编辑模式，改统一打开恢复关闭记录/ID/状态并增强同名/别名回归；07完整通过。没有跳过冲突或关闭保护步骤。
- 首次直接Python render探针未设PYTHONPATH而ModuleNotFoundError，随后用项目backend路径重跑才定位PdfPage异常；不把探针启动失败算渲染证据。各次lint提示最终清零。构建保留既有插件CMP0175警告，pytest保留Starlette/anyio弃用警告。

## 审查、限制与下一步

审查从Python布局校验/目录权限/原件读取/媒体能力/保存事务、迁移/故障测试到Dart序列化/树回调/统一打开/页面工厂/关闭确认/快捷键/播放器重启调用方，保留旧测试和完整旧表行值比较。当前无阻断已实施首批范围的已知问题；不以此证明R3余项或发行验收完成。

Word/PPT分页转换、旧DOC/PPT、无Office独立转换包及缺组件/超时/取消矩阵、干净机/完整安装升级卸载、真实硬件DPI/原生WebView焦点和外站矩阵仍待验；未知格式清晰提示，未悄悄上传或自动运行外部程序。PDF当前逐页翻阅/缩放，无全文搜索/连续页/标注；MD不是WYSIWYG，预览200000字符，工作文件/草稿1MiB；外部变更冲突可关闭明确放弃草稿后重新打开，尚无三方合并UI。

阅读位置随工作空间标签及最后10条关闭历史保留，不宣称无限期独立资源位置库；未添加外部目录监听。文件hash检查与replace之间仍有极短外部程序竞争窗口，恢复点保留检查时旧内容；未提供OS级外部编辑排他锁。保存历史/失败副本保留会增长磁盘，暂不自动清理。人工/阶段验收保持待统一进行，历史M0失败不清除。

下一步继续R3：Word/PPT受控分页转换及无Office离线发行实证、转换来源缓存与取消/故障矩阵，再按task进入R4→R5→R6。已有授权覆盖按序开发，不再请求重复许可。没有提交/推送/合并/发布/替换dist/StudyWorkbench-current，也没有用当前内容补造旧作答快照。

最终收尾：r2-native-final.log为0，R3最终源码上的资源标签/WebView/媒体原生回归1项通过。r3-native-final.log记录仅补树刷新与最终截图的同一完整文档流程。后端最终双环境各164、Flutter最终73及Ruff无修改检查通过，旧0007 SHA与R1证据比较和文档链接/新增文本检查汇总见final-review.json。所有过程失败日志保留。

收尾实际追加：`dart.exe format --output=none --set-exit-if-changed lib test integration_test`首次报告新增截图测试的1文件排版变化（format-final-check.log，格式子命令1；当时后续analyze为0，不用整个shell的0冒充格式通过）。执行`dart.exe format lib test integration_test`为0（format-final02.log）后，单独同一不修改检查为0，53文件无变化（format-final03-check.log）；analyze-final-check.log为0，无问题。`git -c core.safecrlf=false diff --check`最终0（diff-check-final.log）。本地Python断言审查为0：双JUnit各164/失败0/跳过0、Flutter73、两原生流程/构建/冻结日志、65条文档本地链接及新增文本检查通过；0007迁移、R1 explorer与media_library的SHA256与R1记录一致。final-review.json保存摘要与本轮核心源码hash，不记录任何令牌或个人路径。
