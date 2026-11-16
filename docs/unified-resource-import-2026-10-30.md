# 统一资源导入与导航（2026-10-30）

## 需求与现状

本轮按用户粘贴说明及两张布局示意实施；继续现有玻璃主题。R1已有受管复制/预算/取消/失败收据，R2已有稳定资源标签，R3–R5已有查看器、题目与记录。缺口是单文件选择立即提交、没有暂存清单/拖放，媒体上传和资料解析入口重复，侧栏仍有“辅助工具”。已有未提交的0012资料删除工作须保留。

## 设计与任务拆分

1. Python增加只读批量识别接口，复用本地路径、重解析点、大小、媒体头校验；逐项返回类型/大小/错误，未知普通文件安全保存并提示无法预览。确认时再次识别，复制时继续原有检查。识别不执行内容解析或LLM。
2. Flutter统一弹窗：中心拖放区、原生多选、路径去重、可移除/清空的待导入列表、确认/取消。确认前不复制；确认后逐个复用后台任务，显示收据、停止及失败重试，成功项不重复提交。文件夹保留层级并沿用1000节点/32层/1GiB限制。
3. 使用现有Windows MethodChannel及系统OLE IDropTarget接收资源管理器文件，按拖放区物理坐标命中测试，进入/离开提示，关闭窗口注销。原生多选独立方法保留旧单选调用兼容，不新增包。
4. 导航顺序为工作空间列表→新建→资源管理器/添加→学习→底部设置。资料处理与媒体视图迁到资源管理器菜单。旧utility/layout兼容保留；媒体添加调用同一弹窗/复制服务。学习记录入口复用学习页并定位记录区域。
5. 原件与题目提取独立：资料处理可选现有资源再提取/预览/确认，保留手工录入、拆题、导出、遗留恢复。网页链接保存复用现有校验；视频分享链接只保存，下载仍未实现。

涉及调用链：Windows runner/MethodChannel、AddResourcesDialog、ResourceExplorer、WorkspaceShell欢迎页/页面工厂、MediaPage、ImportPage、StudyPage、Explorer路由及组件/后端/Windows集成测试。无数据库迁移、无新依赖、无旧数据删除或覆盖。

## 验收标准

多选与单/多文件拖放共用清单；重复事件去重；错误逐项可见；取消不创建任务；确认后资源树刷新、可直接打开；部分失败保留成功项并可重试；重名编号且不覆盖；媒体/计划/草稿/网页Tab兼容。分别记录静态、组件、后端、Windows构建和原生交互证据，截图为实际运行界面。人工/阶段、安装器及干净机仍待验。

## 新信息架构与迁移清单

| 原入口/职责 | 新位置及保留能力 |
|---|---|
| 辅助工具分组 | 分组移除；既有utility标签和layout仍兼容恢复 |
| 导入资料：选文件并立即解析 | 全局添加弹窗先保存原件；资源菜单“资料处理与导出”选择已有原件再提取，保持8MiB/20页的内容分析预算 |
| 拆题、Markdown、预览/确认、笔记编辑、手工题目 | 资料处理与导出；原确认链、来源降权和QuestionFile流程保持 |
| 导出原件、遗留恢复 | 资料处理与导出；不将ZIP误称完整备份 |
| 媒体库：独立上传 | 资源菜单“媒体视图”；添加动作调用同一弹窗和复制服务，仍使用原MediaEntry及播放器 |
| 学习计划/每日任务/练习/知识点/历史 | 学习计划页保留；侧栏“学习记录与错题”复用同一页并展开/定位历史区域 |
| 工作空间/数据设置 | 保留新建/切换/改名/归档恢复；设置固定在侧栏底部，自定义数据目录不变 |
| 资源查找/打开 | 同空间名称搜索、分页及原目录操作；稳定ID打开/聚焦现有Tab，导入弹窗不创建Tab |

主要文件：`apps/desktop/lib/add_resources_dialog.dart`、`resource_explorer.dart`、`workspace_shell.dart`、`media_page.dart`、`import_page.dart`、`resource_picker.dart`、`study_page.dart`；Windows runner的多选及`resource_drop_target.{h,cpp}`；后端`explorer.py`识别/搜索与`imports.py`已有资源分析接口。测试分别在`backend/tests/test_resource_inspections.py`、Flutter组件/Windows integration及`tools/check_resource_drop.cpp`。

## 识别、导入及错误处理

识别仅读取路径/属性/32字节文件头，不生成资源或解析题目；权限不足、缺失、重解析点、非本地路径、超大小逐项报错。PDF/Office/PNG/JPEG核对基本签名，签名不符仍允许作为原件保存并显示预览风险；不是完整格式有效性证明。MP4/WebM/M4A沿用容器头校验及512MiB上限，编码能否播放仍需播放器验证。TXT/HTML/JSON和未知普通文件允许保存，明确当前独立预览边界。没有增加可执行文件运行入口。

拖放和选择器共用`stage`，按规范化路径去重；确认再次识别，再逐项复用后台复制。清单内成功项不重提；轮询失败保留job_id，重试先查询原任务。取消停止当前任务及尚未提交的条目，已完成部分保留。重名自动编号、同字节原件沿用原blob并在收据中说明，不覆盖旧文件。失败/重复复制字节按旧机制保留，可能占磁盘；文件夹部分失败后的重试会产生编号副本，界面明确提示先检查成功部分。

资料处理使用已有原件ID/哈希读取并复用ImportJob，不新增原件或媒体副本；解析不自动确认题目/笔记。网页/分享链接保存继续使用HTTPS校验，不宣称已能下载视频。无LLM配置也可完整使用这些普通流程。

## 实际命令与结果

以下命令均在仓库或`apps/desktop`运行。Windows/pytest采用进程级`TEMP`/`TMP=<repo>/.local/tmp`；Windows另设`NUGET_SCRATCH=<repo>/.local/nuget-scratch`。Flutter需要写项目外SDK缓存锁，使用授权执行环境，未改变系统权限。所有样本与数据库在`.local`，未读写个人学习库。

| 命令 | 退出码 / 结果 |
|---|---|
| `dart.exe format` 本批Dart文件 | 0 |
| `.venv/Scripts/python.exe -m ruff check backend tools`、`git diff --check` | 0 |
| `flutter analyze --no-pub` | 0，无问题（`.local/unified-analyze-delivery.log`） |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_resource_inspections.py backend/tests/test_explorer.py backend/tests/test_imports.py -q --basetemp=.local/unified-backend-02 --tb=short` | 0，49项（`.local/unified-backend-02.log`） |
| `.venv/Scripts/python.exe -m pytest -q --basetemp=.local/unified-full-01 --tb=short` | 0，215项（`.local/unified-full-01.log`） |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_resource_inspections.py -q --basetemp=.local/unified-search-01 --tb=short` | 0，最终4项，含额外搜索/移除/跨空间断言；不是再次全量 |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/unified-pipe-tests` | 0，88项全量（`.local/unified-widgets-full-02.log`） |
| `flutter test --no-pub test/add_resources_dialog_test.dart test/import_page_test.dart` | 0，最终12项，含新增运行中取消及Markdown MIME选择（`.local/unified-final-targeted.log`） |
| `flutter test --no-pub test/media_page_test.dart test/import_page_test.dart test/workspace_shell_test.dart` | 0，20项（`.local/unified-callback-tests.log`）；补齐从媒体/资料入口导入后刷新侧栏的回调 |
| `flutter test integration_test/unified_resource_import_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/unified-native-data-03 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/.local/unified-native-evidence` | 0，1项；真实界面/后端，文件选择和拖放回调明确注入（`.local/unified-native-03.log`） |
| `flutter test integration_test/resource_explorer_test.dart -d windows --no-pub` 加相同ROOT、`.local/unified-legacy-native-data`及EVIDENCE定义 | 0，1项；真实窗口完成详情、链接添加、树刷新、递归删除及layout/源文件保留（`.local/unified-legacy-native.log`） |
| VS2022 `MSBuild.exe apps/desktop/build/windows/x64/runner/resource_drop_check.vcxproj /p:Configuration=Debug /p:Platform=x64 /p:BuildProjectReferences=false /v:minimal` 后运行`runner/Debug/resource_drop_check.exe` | 0；真实OLE注册/释放及CF_HDROP单/混合多文件、UTF-8、命中/越界、进入/离开、禁用/不支持格式、1001项拒绝的COM边界断言（`.local/unified-native-drop-check-05.log`）；不是鼠标拖放 |
| `flutter build windows --release --no-pub` | 0；收尾后重建见`.local/unified-release-delivery.log` |
| `.local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --onedir --name study_backend --distpath .local/unified-frozen --workpath .local/unified-freeze-build --specpath .local/unified-spec --paths backend --collect-submodules study_workbench --copy-metadata docling-slim --copy-metadata docling-core --copy-metadata doclang --copy-metadata pypdfium2 --copy-metadata python-docx --copy-metadata pylatexenc --add-data '<repo>/backend/migrations;migrations' --add-data '<repo>/backend/study_workbench/player.html;study_workbench' --add-data '<repo>/backend/study_workbench/library_player.html;study_workbench' tools/frozen_entry.py` | 0；`<repo>`为`D:/computer_work/project/StudyWorkbench`，实际输入为绝对路径（`.local/unified-freeze.log`） |
| `.venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/unified-frozen/study_backend/study_backend.exe --test-root .local/unified-frozen-check --documents` | 0；新接口、分析复用/未确认、搜索、0012、文档、原件/作答/layout、真实进程重启与删除兼容均通过（`.local/unified-frozen-check.log`） |

## 失败及边界记录

- 首轮后端45通过/1失败：sandbox拒绝创建Junction，复测49通过。保留`.local/unified-backend-01.log`。
- 首轮静态发现多余字段/未使用import和lint，已修复。首轮组件2项因父页面等待弹窗时显示无尽加载而超时，已把页面busy限制到实际请求；第二轮1项是测试按钮名称不匹配。保留`unified-widgets-01.log`、`-02.log`。
- 第一次完整Flutter有3项失败：新增搜索框使旧的全局TextField定位不再唯一。已将测试限定到详情/草稿输入，保留全部断言；最终88通过，旧日志`unified-widgets-full.log`保留。
- 原生自检首轮缺少Windows头文件；随后“错误是最后一条事件”的自检断言忽略了正常DragLeave通知，已改为同时检查拒绝效果和错误事件；这不是削弱文件/边界断言。后续遇到集成测试临时入口消失和本轮自检进程占用，改用独立MSBuild目标、停止自己的失败测试进程后通过。日志`unified-native-drop-check*.log`保留。
- 两次人工输入型Windows集成没有完整通过：第一轮真实原生多选观察到MD与视频两项进入清单、确认前无任务/节点，随后等真实拖放超时；工具明确拒绝跨窗口drag。第二轮文件选择控件自动化未成功完成并超时。日志`unified-native-01.log`、`-02.log`保留，不能归为产品通过。
- 最终Windows集成使用注入回调完成3项暂存/确认/资源树登记，`results.json`明确写`native_multi_select=false`、`explorer_drop=false`。用户之后以Escape停止Computer Use，已停止该工具输入。真实跨窗口鼠标拖放、不同显示器DPI、资源管理器提权差异仍待人工验收，不用COM或回调测试替代。
- 既有插件CMP0175构建警告、Starlette弃用警告保留；不修改上游缓存。无新增依赖，系统OLE初始化要求参考[Microsoft RegisterDragDrop文档](https://learn.microsoft.com/en-us/windows/win32/api/ole2/nf-ole2-registerdragdrop)。

## 截图与交付

实际运行截图在`.local/unified-native-evidence/`：`navigation.png`、`add-resources-empty.png`、`drop-callback-staged.png`、`import-completed.png`、`resource-tree.png`。已目视检查标题/中心拖放区/列表/固定确认取消按钮及侧栏层级；小窗口的较长清单可滚动，第三项可能在滚动区下方。截图中的选择/拖放来源按上述注入边界解释。

独立测试目录为`dist/StudyWorkbench-unified-import-test-20261030/study_workbench.exe`，配套本次Release界面和本次冻结后端，复用已验证的本地CRT；不覆盖以前测试包，必须保留整个目录。启动采用既有数据位置，未自动启动或迁移个人学习库；0012升级备份逻辑属于之前保留的删除工作。

`.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage dist/StudyWorkbench-unified-import-test-20261030`及`tools/check_release.py dist/StudyWorkbench-unified-import-test-20261030`均退出0，1302文件哈希/CPython版本/无数据库/PE依赖检查通过；不等于干净机验证。最终界面`data/app.so`与Release来源SHA256同为`bbf4dd89c367fcb0e6acf55cb6514f9961e0f07bcc676dad8af180f60dfb1d6a`，后端与已验证冻结来源同为`f1637905a6e9b8567496669377cfbbe439f03c7e1a13efc13c93dcc25f3b12e5`。

审查完成：核对所有导入调用、媒体共享数据、原件分析哈希/空间边界、目录预算、重试成功项/未知任务、取消竞争、模态关闭/原生生命周期、Tab/工作副本/作答保护。没有提交、推送或发布；实现/自动化按上表记录，人工和阶段验收待验。下一步在用户普通Windows会话验证Explorer拖放/取消/多屏DPI及安装器/干净机；下载、更多媒体编码和更广格式预览仍按既有缺项保留。
