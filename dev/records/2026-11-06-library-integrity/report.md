# M2-05 资料完整性与孤立派生目录巡检

2026-11-06，用户要求继续推进数据可靠性。依现行规则不执行人工/Computer Use，不接模型，不删除学习资料；沿用ponytail最小完整实现，不增加依赖。

## 设计与本轮任务

首个交付切片为离线维护CLI --check-library，配合--data-dir及显式--confirm-all-workspaces。仅检查已有当前schema资料库，不启动HTTP、不迁移/创建业务库、不激活配置；复用DataLock与SQLite只读连接。数据锁文件可创建，业务数据库和学习文件不改写。正在运行的库拒绝检查。

检查SQLite完整性/FK、当前schema，核对原件/就绪媒体/确认版正文附件/就绪Office PDF的大小与hash；工作副本hash变化只报告索引差异，不覆盖。保存收据保留before/pending，已提交后pending缺失是正常情况。预览失败/中断任务的source/profile/output和已登记确认版receipt均属于保留材料，不误判为可删除文件。

孤立候选仅覆盖working、question-files、question-versions、previews四类受管目录：按数据库路径/预览任务建立所属集合，发现无登记归属的目录只提示，绝不推断可删除；其他未知目录保留不猜测。覆盖全部空间及归档，墓碑仍是有效引用。无新表/API/Agent工具，本轮不增加桌面入口，不声称完成自动恢复、三方合并或全部派生类型。

资源预算：最多20000文件/目录项、50000引用行、512MiB读取、30秒、200条问题；超过或无法读取返回complete=false，不能表示健康。报告只含相对路径、类别和计数，不输出正文/会话信息；结果不自动持久化。

顺序：实现扫描与CLI→只读/坏输入/路径/预算/锁/CLI自动回归→恢复故障注入→全量/冻结入口验证→代码自审、契约和任务更新。独立阶段草稿PR以#4分支为base，要求提交/当前head CI，不要求合并。保留既有未提交summary.md及本机.vscode。


## 实施与自审补充

实现library_integrity.py及固定离线CLI，不增加HTTP/Agent接口或数据库表。复用备份的只读连接、安全路径与数据锁；覆盖墓碑和归档记录。working按node及生成目录两级归属，避免已登记node掩盖未登记的旧generation；版本receipt、预览任务source/profile/tmp按已登记所有者保留。保存prepared与笔记创建中断、根部恢复/迁移暂存目录独立提示，不改写收据。相对路径先检查Windows安全名称、重解析点及所属空间；锁文件本身的junction也在取锁前拒绝。

healthy仅表示checked_scope=managed_files_and_derived_directories本次范围未发现问题，不证明任意格式语义、所有历史业务JSON或外部编辑原子性。哈希读取最多512MiB，SQLite另受30秒进度期限与既有限值约束；不会自动恢复、迁移或删除，其他派生类型/桌面入口/三方合并继续后续。时间限制为协作式检查点，不能保证中断单次阻塞文件系统调用。

已新增4项恢复故障注入：提升后目标被外部修改、提升阶段磁盘耗尽、激活后暂存清理拒绝、备份打包期间源修改。均核旧库/旧配置保持；清理拒绝允许已完整校验的新库激活并cleanup_pending=true，保留暂存，不能误报成恢复未完成。

已执行：target-01为19通过24.40秒，target-02为24通过29.23秒；fault-01为4通过8.97秒，均退出0。target-03退出1（27通过1失败）：新junction锁用例第一次巡检已创建.study.lock，随后rename准备锁junction时目标已存在；改为先保留旧锁文件再移动测试junction，原路径保护断言保留。target-04退出1（29通过1失败）：跨空间读监控正确阻止扫描读取，但测试事后snapshot也被同一监控拦住；将监控限定于扫描调用后，保留全文件字节不变断言。原日志/JUnit/失败现场保留，不能将这些夹具问题归为产品回归通过。后续target-05/完整验证另列。


target-05退出0，31通过38.44秒；后续补ready预览元数据/旧schema/递归损坏元数据，target-06退出1（33通过1失败）：旧库夹具make_0006要求不存在的目录，改为tmp_path内新old-library子目录，保护断言不变。target-07巡检专项退出0，30通过35.49秒，另4项故障已通过。最初开发/发行全量backend312/backend313分别508通过（306.78/283.02秒），此时后补两项测试尚未纳入计数，不能报510；最终final312/final313另记。

冻结首构frozen.log退出0，136.6秒；自审异常处理补丁后再增量构建frozen-final.log退出0、6.8秒，但真正PYZ源一致性断言退出1：打包check_library的co_names缺RecursionError，证明增量包未包含最新安全降级。尚未在该包执行业务探针，没有把构建成功当代码一致。新增tools/check_frozen_sources.py，以固定CPython3.13.17读取PYZ，比较所有本项目业务模块的字节码、常量、嵌套代码、参数/作用域及异常表，忽略构建路径/调试行号；不执行打包代码。frozen-source-before.log退出1成功拦截旧包。标准build-backend.ps1加入--clean，并在每次打包后强制调用该一致性检查，失败则构建失败；无新依赖。干净构建、真实冻结及最终回归继续验证，不提交不一致包。

本轮分支codex/library-integrity，base=147198a（PR #4），保持原分支及未提交summary.md/.vscode；独立阶段草稿PR交付，不合并/发行。Windows前端源未改，人工测试已取消，本轮不制作窗口验收包。


## 最终固定版本验证

本节P=.venv/Scripts/python.exe（3.12.7）、Q=.local/release-venv/Scripts/python.exe（3.13.17），cwd仓库根，原始日志/JUnit均artifacts/integrity-20261106/，以下退出码实际收取：

| 命令/验证 | 结果 | 原始记录 |
|---|---|---|
| P -m pytest backend/tests -q --basetemp=.local/integrity-final312 --junitxml=artifacts/integrity-20261106/final312.xml | 0，510通过，295.00秒 | final312.log/xml |
| Q -m pytest backend/tests -q --basetemp=.local/integrity-final313 --junitxml=artifacts/integrity-20261106/final313.xml | 0，510通过，291.06秒 | final313.log/xml |
| packaging/windows/build-backend.ps1（--clean及强制源码一致性检查） | 0，88.3秒；41业务模块全部匹配，含嵌套代码/常量/异常表 | frozen-clean.log |
| P tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root .local/integrity-frozen-resource --documents | 0，原CI资料/文档/移除/重启与schema严格校验 | resource.log |
| 冻结exe --data-dir该样本库绝对路径 --check-library --confirm-all-workspaces（PATH仅System32） | 1，正确发现原探针故意制造的workfile_index_changed；不能把该冲突样本当健康库 | frozen-scan.log |
| P tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/integrity-frozen-final | 0，纯黑盒新库：持锁拒绝、正常健康、未登记旧generation与外部编辑诊断；每次扫描前后业务DB/文件hash相等，不修复 | frozen-check-final.log、隔离result.json |
| 新TEMP/TMP junction .local/integrity-lifecycle-alias→integrity-lifecycle-real；P tools/check_backend_lifecycle.py --exe同包 | 0，正常退出/EOF/重启/崩溃/两次迁移/父EOF取消，原CI整链 | lifecycle.log |
| P tools/check_document_workers.py --exe同包 | 0，真实DOCX/PDF文字/图片/公式/页与分题 | document-workers.log |
| P tools/check_learning_workbench.py --exe同包 --test-root .local/integrity-workbench | 0，笔记/标记/链接/检索、授权审核与收据、重启/整库恢复、源hash一致 | workbench.log/result.json |
| Q tools/check_rN_blackbox.py .local/integrity-rN，N顺序1..5，失败即退出 | 0，既有公开HTTP完整回归 | r1至r5.log |

新CI巡检步骤改用独立全新黑盒样本，不修改既有资源探针的冲突场景，不把警告改为健康来放行；同时断言真正持锁拒绝与扫描前后字节保持。初次冲突样本退出1保留。测试新增失败均保留，未删测试或降低断言，原Starlette/anyio弃用及PyInstaller既有hidden-import警告仍记录。

自审完成：CLI互斥/全部空间确认、锁与只读SQL、不隐式迁移、档案/墓碑引用、注册失败任务与创建/保存收据、working两级归属、路径/跨空间/锁junction、预算/部分结果、损坏/深层JSON、真实冻结源码一致性与无开发PATH运行。非独立批准；人工测试已取消。前端未改，不制作UI候选；远端阶段PR仍需当前head CI实查。


CI新增探针原命令最终复核：P tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/ci-library-integrity退出0（frozen-ci-exact.log），输出healthy_case_verified、持锁拒绝、孤立/外部编辑发现及业务字节保持均true。该探针只使用标准库和全新自编HTTP样本，不修改既有冲突样本或个人库。

Ruff、Question Schema --check及git diff --check均退出0；本地Markdown检查56份/277链接无缺失（docs.json，包含用户先前未提交的summary）。报告链接/任务入口按当前目录检查，无新doc平行入口。--check-library无前端改动，本轮本地不重复构建Flutter；远端CI保留原桌面检查/Release/COM/全部冻结链，并新增真正冻结CLI探针和构建时41模块一致性门禁。

新冻结包完成验证后，先核旧a541候选特定SHA256、两个目标的workspace绝对路径及无重解析点，再用原生PowerShell删除旧artifacts/lw06-native-20261106/frozen-alias/dist和build/study_backend，退出0；保留本轮dist/study_backend一份当前包，原始日志/失败/JUnit/转储/源码快照不删，无人工窗口包或新组件副本。


## 阶段PR交付

实现提交434d4921d939d40c5c1128518f537da651baa720已commit/push，退出0；创建[草稿PR #5](https://github.com/surface-user/StudyWorkbench/pull/5)，base=codex/learning-workbench-20261106（#4、147198a），未合并/发行。该阶段实现/本地自动化/自审已完成，当前head CI继续实查；M2-05其他恢复范围仍进行中，不以本切片退出整个任务。

本节及task仅补实际PR链接，为文档增量，不再改产品/测试代码。文档提交后的最终head CI以PR实时检查及描述为准，不将先前head绿灯套用到后续提交，不为记录自身SHA循环提交。用户未提交summary.md及.vscode仍保留未纳入本PR，旧分支不改写。原始数据/失败记录不上传，报告命令/源码快照及筛选边界按前述执行。

## 保存恢复点切片设计（2026-11-07）

首切片PR #5最终1357d44的三组CI全通过（run 42233131907）；本轮从该提交创建codex/document-recovery，不改旧PR分支、不合并/发行。继续同一M2-05报告，不另建流水目录。

问题：保存中断虽保留before/pending和收据，普通用户尚无查看/找回入口。新增同空间节点的只读收据分页及指定before/pending内容读取，严格验证受管路径、收据归属、UTF-8/1MiB及记录hash。无路径输入/路径输出，不枚举磁盘推测记录，不写文件/数据库。pending经replace消耗后不可读属于正常情况，不能回退成其他正文。

桌面MD工作副本增加“保存恢复点”：选择收据及旧稿/待写稿，字面预览；当前可读且无prepared保存时，用户另行确认才放入编辑草稿。已有未保存草稿时要求先处理，避免丢弃。载入只改既有layout草稿，记录预览时当前hash；随后用户点击原“保存工作文件”，仍经旧的expected hash/恢复点/收据流程，不修改原件、确认版或历史作答。预览后外部修改仍409。当前缺失/坏编码/超限或待启动对账时只预览，不能借恢复点覆盖。无自动写回/删除/三方合并/新表/依赖/模型。

任务：服务与API→路径/归属/损坏/分页/字节不变/重启及冲突回归→普通UI及取消/脏稿/失败/保存守卫组件测试→双Python/Flutter自动化及冻结链→自审/契约/task/同报告更新→阶段草稿PR与当前head CI。人工及Computer Use已取消。原失败记录和用户未提交文件保留；仅保留一份当前后端包。

### 保存恢复点实施、失败与复测

新增DocumentFiles两个GET入口及DocumentRecoveryDialog，复用TEXT_LIMIT、text_bytes/resource_path、archive_path和既有会话鉴权；只读正文受既有2并发门禁。working物理目录按空间/节点/层级核对，question-files兼容现有独立目录；收据before/pending必须在当前工作文件同目录且名称严格匹配记录ID/版本，不能通过修改收据路径读取其他文件。数据锁/启动对账/普通保存流程未改，无数据库迁移或新Agent工具。

原始记录写artifacts/recovery-20261107/。cwd根，P=.venv/Scripts/python.exe，Q=.local/release-venv/Scripts/python.exe，均仅新建.local隔离样本；测试成功目录按现行pytest策略回收，失败日志/JUnit/现场保留。

- P -m pytest backend/tests/test_document_recovery.py backend/tests/test_document_files.py -q --basetemp=.local/recovery-target01 --junitxml=artifacts/recovery-20261107/target01.xml：退出1，18通过2失败，35.68秒。损坏workspace归属被FK在注入时拦截，另mklink在受限执行环境创建失败。target02同命令替换批次名退出1，18通过2失败，33.21秒：先建另一空间仍不能破坏节点复合FK，链接仍创建失败。损坏归属用独立sqlite3连接明确构造坏库（该连接不启用FK），保护断言不变；Windows链接用正常测试执行权限，不跳过或mock真实重解析点。
- target03同命令替换批次名退出0，20通过，30.21秒。随后补物理foreign-node目录守卫和真实QuestionFile/确认版/作答/墓碑只读回归；P -m pytest backend/tests/test_document_recovery.py -q --basetemp=.local/recovery-target04 --junitxml=artifacts/recovery-20261107/target04.xml退出0，14通过，9.12秒。仅夹具缩短链接路径并保留原目录，未删除保护断言。
- 初次dart.bat format等待未结束，终止本次调用退出1；改用现有SDK的dart.exe直接format，退出0，不修改SDK。一次新增测试静态检查指出未用Path导入，另一次指出工具urllib导入顺序，均修正后Ruff退出0；没有删测试。一次format使用桌面cwd却传仓库相对路径导致未找到文件，随后从正确根路径实际format退出0。
- cwd=apps/desktop，flutter test test/document_recovery_test.dart test/document_page_test.dart首轮退出1，8通过3失败，约8秒：父页面把整个用户选择对话框当文件处理而保持busy，持续进度动画令pumpAndSettle超时。改为沿用现有marks/insertLink模态交互模式，由对话框自身维护网络busy，不给等待用户选择展示文件处理进度，未增加等待上限或削弱断言。flutter-target02.log同命令退出0，11通过，约2秒；补400×800窄视图/50+1分页后flutter test test/document_recovery_test.dart退出0，5通过，约2秒（flutter-target03.log）。

新后端回归逐项检查收据/MD字节及所有业务表不变、pending已消耗明确失败、坏编码/超限/hash不符/路径/空间/节点/junction、prepared只读、缺失当前仅预览、重启冲突状态、普通保存拒绝预览后的外改，并在显式重试保存时追加新恢复点保留外改字节。题目确认快照、旧作答和墓碑访问语义保留。

冻结CI复用原tools/check_library_integrity.py步骤扩展真实HTTP：保存→查看before/已消耗pending拒绝→MD字节不变→预览后外改→旧hash保存409→重新核对后普通保存→旧恢复点保留；随后原持锁/离线健康/孤立/外改/业务字节保持全部断言仍执行。无新工具层、组件或窗口测试。

### 保存恢复点最终本地验证

cwd仓库根，P/Q及原始目录同上。所有下列退出码实际收取，完整回归后的产品/测试源码未再改：

| 实际命令（相对仓库根，另注明cwd） | 退出/结果 | 原始记录 |
|---|---|---|
| P -m pytest backend/tests -q --basetemp=.local/recovery-full312 --junitxml=artifacts/recovery-20261107/full312.xml | 0；524通过，354.42秒 | full312.log/xml |
| Q -m pytest backend/tests -q --basetemp=.local/recovery-full313 --junitxml=artifacts/recovery-20261107/full313.xml | 0；524通过，329.63秒 | full313.log/xml |
| cwd=apps/desktop；SDK dart.exe format lib/document_page.dart lib/document_recovery_dialog.dart test/document_recovery_test.dart；flutter analyze | 0；格式无变化，静态无问题 | format-final.log、analyze-final.log |
| 同cwd；flutter test --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/recovery-flutter | 0；158通过，约52秒 | flutter-full.log |
| ./packaging/windows/build-backend.ps1（默认Q，干净构建） | 0；约147秒，41业务模块全部与源码匹配 | build.log |
| P tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/recovery-frozen | 0；新增恢复点三项及全部旧巡检断言通过 | frozen-recovery.log、隔离result.json |
| P tools/check_resource_explorer.py --exe同包 --test-root .local/recovery-frozen-resources --documents | 0；原冻结CI导入/文档/移除/重启链 | frozen-resources.log |
| 新TEMP/TMP junction .local/recovery-lifecycle-alias→recovery-lifecycle-real；P tools/check_backend_lifecycle.py --exe同包 | 0；EOF/崩溃/重启/两次迁移/取消及旧字节/收据/记录保持 | frozen-lifecycle.log |
| P tools/check_document_workers.py --exe同包（继承上述TEMP/TMP） | 0；DOCX/PDF真实文字/图像/公式/分题 | frozen-workers.log |
| P -m ruff check backend tools；P tools/export_question_schema.py --check；git diff --check | 各0，无新增依赖或Schema漂移 | 工具返回，原警告保留 |

首轮flutter analyze退出1，3处跨行if缺大括号；修复后上述最终静态/全套通过。初次format --output=none --set-exit-if-changed lib test integration_test退出0；最终新增三文件format无变化，其余文件未修改。包内/源码快照46文件及exe SHA256保存在source-snapshot.json，不含令牌、个人库或原件。Starlette/anyio弃用、固定依赖可更新和PyInstaller既有hidden-import警告仍保留，没有升级依赖或屏蔽警告。文档相对链接检查54份/269链接无缺失（后续PR链接补交再校验）。

自审完成：全调用方/路由、原SaveText和启动recover未改、受控路径/节点/空间和hash、只读GET/正文预算、pending消耗、prepared/当前缺失降级、模态等待/取消/异步mounted、脏稿不覆盖、确认后草稿基线hash与普通保存冲突、QuestionFile/旧作答保护及冻结CI保留原断言。此次为自审，非独立批准；本地不重复生成Windows UI候选，Windows Release/COM及全量R1–R5由本阶段当前head CI执行并另核。人工测试及Computer Use已取消。无自动修复/删除/三方合并；当前文件缺失的写回仍未实现。提交/阶段草稿PR及最终head CI继续跟进，不合并/发行。

实现提交a272b4f94de8de9475b32b51313d467802e34cde已commit/push，均退出0；[草稿PR #6](https://github.com/surface-user/StudyWorkbench/pull/6)已创建，以未合并#5的1357d44为base。本节及task仅补真实交付链接；文档补交后的最终head CI、检查时间及交付结论以该PR描述/实时检查为准，不以旧head替代，也不为记录自身SHA循环提交。仍保留用户未提交summary.md及.vscode，旧分支不改写，未合并/发行。

## 恢复点另存笔记切片设计（2026-11-09）

PR #6最终4686c8b的三组CI通过记录保留；本轮从该提交建立codex/recovery-note-copy，按用户要求继续M2-05并提交独立草稿PR、核实最终head CI，不合并/发行。继续同一任务报告，不接模型、不做人工测试。

问题：当前工作文件缺失时，恢复点已有只读API，但重启后的页面无法打开恢复入口，也不能将所选内容变成可继续使用的文件。首批补“另存为新笔记”：错误页也可打开MD保存恢复点；明确选择/字面预览及填写新名称后，复用现有新建笔记收据和普通expected hash保存接口创建独立副本，不修复或覆盖原缺失路径，不发布题目版本。

设计：创建前重读所选恢复点核对hash/正文；同一窗口失败重试固定request_id和名称/正文，创建响应丢失不重复建笔记。新笔记初始hash来自既有创建响应；保存前回读目标，已是所选正文则对账成功，仍为初始hash才保存，其他内容拒绝覆盖。保存响应丢失可重试对账；失败保留新笔记、源恢复点和原文件。关闭后创建收据及原恢复点仍可查，不承诺跨关闭自动续写。成功返回普通新节点，由既有导航打开；打开失败时新文件保留并明确提示。不新增后端写接口、表、依赖、原地修复/三方合并或Agent工具。

实施顺序：入口/受控另存交互→响应丢失/冲突/取消/失败/重启/空稿与字面内容自动回归→冻结HTTP串联及源/历史保持→全量/自审→契约、task、原报告→PR与当前head CI。仅一份当前后端构建；不改用户未提交summary.md/.vscode，不清除历史失败。

### 另存副本实施与专项验证

DocumentRecoveryDialog在同窗口冻结创建请求及已核对正文，正常创建/回读/保存均复用现有接口；PUT只向新节点，expected hash为创建返回的初始值。目标已是预期hash和正文时对账，不重复保存；其他改动拒绝覆盖。错误名在创建前仍可编辑。保存中禁用关闭及系统返回，异步卸载后不继续后续请求；成功后普通导航失败也明确文件已保存。原草稿恢复操作保持原确认与hash守卫；读取失败页不以树名称后缀猜格式，交服务校验恢复资格。

原始产物artifacts/recovery-copy-20261109/，P/Q、cwd约定同前，只用新.local隔离样本。本轮未改backend/study_workbench业务源码或后端契约字段，无需新迁移/依赖或重复冻结大包；Q tools/check_frozen_sources.py --exe dist/study_backend/study_backend.exe实际退出0，41模块仍匹配当前源码，使用唯一当前包。当前PR的远端CI仍执行全新Windows Release/后端构建/源码一致性及整条冻结链，不用旧CI代替。

- 首次format报告导入指令错误放到声明之后；修正导入位置后实际format通过。最初复合命令末尾读取文件使整体返回0，不能用该0宣称format通过。未执行有语法问题的组件测试；后续独立format退出0。
- cwd=apps/desktop；flutter test test/recovery_note_copy_test.dart test/document_recovery_test.dart test/document_page_test.dart退出0，19项通过，约2秒（flutter-target01.log）。覆盖新入口、空/字面内容、创建/保存响应丢失同请求重试、改后目标不覆盖、导航失败保留、取消和异步卸载；后补无后缀改名、名称校验纳入最终全量。
- P -m pytest backend/tests/test_document_recovery.py backend/tests/test_markdown_notes.py -q --basetemp=.local/recovery-copy-target01 --junitxml=artifacts/recovery-copy-20261109/backend-target01.xml退出0，27通过，18.97秒（backend-target01.log/xml）。新增真实HTTP缺失源→读取pending→新建/保存→重复请求/陈旧覆盖拒绝→重启，原件/源恢复点保持，空稿与字面正文均覆盖。
- P tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/recovery-copy-frozen退出0（frozen-copy.log/result.json），新增missing_source_copy/copy_creation_idempotent/original_missing_not_repaired均true，原恢复点/持锁/健康/孤立/索引变化/业务字节保持断言仍通过。只在完成缺失源不被修复的断言后，重置本探针自编的缺失夹具以继续原健康巡检，不改产品、不清除故障证据。
- 首轮flutter analyze退出1，测试内2处跨行if缺大括号（analyze01.log）；修正后最终analyze无问题，退出0（analyze-final.log）。无忽略规则、删测试或降断言。原依赖可更新/Starlette警告继续保留，未升级依赖。

自审边界：源码调用方仅DocumentPage/恢复对话框及其测试，导航沿用现有回调，创建收据和保存语义未改；保存先核目标初始hash，重复请求不覆盖外部编辑；同窗口重试固定内容/名称，跨关闭不自动重放。不自动绑定来源标记，不把正文里的旧ID注释解释为新笔记身份或自动发布QuestionFile。另存不恢复原缺失路径，不将有缺失的源库标为健康，原完整性/备份规则不放宽。三方合并、原地修复及其他派生类型仍在M2-05。

自审发现实际_WorkspacePages._openResource会拦截导航异常，不能仅依靠DocumentPage的catch提示副本已保存。补在调用导航前明确显示保存成功，即使标签上限等错误被导航层处理也不会误报成保存失败；相应断言纳入最终回归。修补前全量flutter-full.log为167项通过，不能直接套用至补丁后；补丁后另记flutter-final.log/analyze-navigation.log。后端业务源码仍未改变，双Python本轮结果不受该纯UI提示修改影响。

### 另存切片最终验证与交付要求

| 命令（cwd根，除另注明） | 实际退出与覆盖 | 原始记录 |
|---|---|---|
| P -m pytest backend/tests -q --basetemp=.local/recovery-copy-full312 --junitxml=artifacts/recovery-copy-20261109/full312.xml | 0；526通过，321.55秒 | full312.log/xml |
| Q -m pytest backend/tests -q --basetemp=.local/recovery-copy-full313 --junitxml=artifacts/recovery-copy-20261109/full313.xml | 0；526通过，297.74秒 | full313.log/xml |
| cwd=apps/desktop；SDK dart.exe format lib test integration_test | 0；85文件，无变化 | format-final.log |
| 同cwd；SDK dart.exe format lib/document_page.dart test/recovery_note_copy_test.dart；flutter analyze（导航提示补丁后） | 各0；格式及静态无问题 | format-navigation.log、analyze-navigation.log |
| 同cwd；flutter test --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/recovery-copy-final-flutter | 0；167通过，约45秒 | flutter-final.log |
| Q tools/check_frozen_sources.py --exe dist/study_backend/study_backend.exe | 0；41业务模块匹配，当前唯一包复用未变化的后端 | 工具实际返回及source-snapshot.json |
| P tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/recovery-copy-frozen | 0；新增另存及全部既有冻结巡检/恢复守卫 | frozen-copy.log/result.json |
| P -m ruff check backend tools；P tools/export_question_schema.py --check；git diff --check | 各0 | 实际工具返回，旧警告保留 |

当前产品/测试源码47文件hash及复用exe hash记录于source-snapshot.json；导航补丁前快照另保留，不将旧UI版本结果冒充最终版本。后端41模块及exe与11-07已验证包hash一致，本轮未新建重复二进制、Office组件或UI验收包。相对文档链接54份/269链接无缺失（docs.json，交付链接补交另核）。全量后临时测试文件已由原流程清理，用户未提交文件未处理。

本地自审已完成，未执行独立人工批准；人工测试/Computer Use明确取消。当前head CI须包含Windows Release、COM、全量R1–R5和全新冻结包整条原有链；本地不重复Windows/原冻结其他专项，不把旧包模块一致性当作新UI构建证明。阶段草稿PR依赖#6，要求提交/PR/当前head CI，不要求合并。整体M2-05仍进行中，原地缺失恢复、三方合并等不退出。

实现提交8e7142c5c63a56f67a778c462bbd873434af8fc2已本地commit，退出0。首次及重试git push，以及会话级OpenSSL/已有HTTP/SOCKS代理尝试均退出1（TLS握手失败）；GitHub连接工具也出现传输错误，不是CI失败。一次SOCKS调用的自动权限检查超时未执行，重试后正常执行仍TLS失败，未当成安全拒绝。用户明确确认当时本机网络异常并恢复后，git -c http.sslVersion=tlsv1.2 -c http.version=HTTP/1.1 push -u origin codex/recovery-note-copy退出0；未关闭证书校验/持久改网络配置，不将协议参数推断为故障根因。备用API上传仅准备本机临时JSON并已移除，未使用其创建远端代码对象，远端仍是原提交。

[草稿PR #7](https://github.com/surface-user/StudyWorkbench/pull/7)已创建，base=#6的4686c8b；本节及task补实际链接后，最终文档head CI、检查时间及切片交付结论持续记录在该PR描述/实时检查，不以旧head替代，不为记录自身SHA循环提交。未合并/发行，用户未提交summary.md/.vscode保留，后端与Office未复制新包。


## M2-05a：保守三方合并预览核心（2026-11-09）

需求/拆分：在#7的a959b9f31d5f511eb785dea6b398ee7c10e262ff之上，先完成独立纯文本核心与测试。基线核验、空间鉴权、预览API、编辑器确认和保存竞态留给后续独立任务；本切片没有运行时入口，不把它记成完整三方合并。现行内部边界写入architecture的规划节，现有文档/保存接口及数据库均未改。

设计/实现：仅Python标准库，输入/输出各限1MiB UTF-8；按LF拆分保留CR/尾换行/Unicode字面内容。每侧公共前后缀之间视作一个变更区间，线性扫描，无二次方diff。相同版本或单侧变化直接采用；不相交替换/删除/插入可组合；重叠和插入贴边均返回conflicted=true、text=None，不注入标记。不尝试猜测重复行语义；多处不连续编辑可能保守冲突，后续可扩展但不得自动覆盖。调用方必须验证基线并保留输入，以当前hash走既有保存，不修改确认版或历史。

环境/实际命令：本轮是Linux云环境，Python3.12.14，不是原Windows工作目录。环境目录只列云电脑；git clone https://git.chatgpt-team.site/surface-user/StudyWorkbench.git StudyWorkbench退出128（无法取得用户名），未取得完整checkout。通过已连接GitHub工具按固定head读取规定文档、相关源码及工作流，局部落盘，仅发布明确列出的文件；不碰用户本机未提交文件。

- 初始python -m pytest --version及python -m ruff --version均退出1（模块未安装）；随后python -m pip install --target .local/check-tools pytest==9.0.1 ruff==0.14.6退出0，未新增项目依赖。
- 工作目录为本轮StudyWorkbench局部源码目录；PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_markdown_merge.py -v退出0，8项；日志artifacts/merge-core/unittest.log。
- PYTHONPATH=.local/check-tools:backend python -m pytest backend/tests/test_markdown_merge.py -q --junitxml=artifacts/merge-core/pytest.xml退出0，8项及77子测试通过（含另行穷举行区间组合断言，不按断言重复计测试数）。
- PYTHONPATH=.local/check-tools python -m ruff check backend退出0；仅本轮两份Python文件，不是完整后端静态检查。python -m compileall -q backend退出0。
- 覆盖等值/单侧、空稿、删除/插入、贴边冲突、重复行、中文、混合换行/尾换行、标记字面量、UTF-8及输入/结果预算和对称性。自审已逐项核对无I/O/新增依赖，保守拒绝不丢输入；独立人工审查未执行，按仓库约束未创建子Agent。

本地未执行完整后端、Flutter、Windows构建及冻结；不得套用#7历史绿灯。本轮后续必须核对独立草稿PR当前head的双Python全量、ruff、R1–R5、桌面和冻结CI。既有打包--collect-submodules study_workbench会收集新核心，check_frozen_sources.py仍逐模块检查，未降低断言或改变工作流。人工测试/Computer Use按用户指令取消，不记通过。不合并/发行。

交付：独立分支codex/markdown-merge-core，base为codex/recovery-note-copy。草稿PR URL、最终head及实时CI结论记录在对应PR描述，避免为记录自身SHA循环提交；未核验前本切片保持待交付。M2-05整体仍进行中。

### M2-05a Windows打包跟进（2026-11-09）

本轮通过GitHub连接器核对：#2→#3→#4→#5→#6→#7→#8依次堆叠，均open/未合并；除#3外均draft。#2–#7当前head分别为29f23d3、7aa8251、147198a、1357d44、4686c8b、a959b9f，对应PR运行40928912483、41559301426、42148998075、42233131907、42276748748、42563863313均completed/success。#2已有代理自审且三个线程resolved；#3–#8没有提交的GitHub review或未解决行内线程。以上不表示独立审查通过。

#8原head e3dfed4的[CI #48](https://github.com/surface-user/StudyWorkbench/actions/runs/42569120398)实际失败：双Python/R1–R5成功，桌面格式/分析/167测试/Windows Release/COM成功，但冻结源码检查抛出`KeyError: No entry named 'study_workbench.markdown_merge' found in the archive!`，后续冻结探针未执行。上节“collect-submodules会收集新核心”被此实际结果纠正，旧失败保留，不重跑冒充通过。

根因在本机固定PyInstaller源码与真实collect_submodules调用确认：生成spec的collect_submodules前导段先于Analysis的pathex设置执行；仅--paths backend不能让前导收集找到源码包，返回空列表。旧41模块因静态调用链进入包，新核心没有调用方而遗漏。修补只在build-backend.ps1调用期间将本仓库backend前置到PYTHONPATH，finally还原调用者原值；保留--clean、--collect-submodules、全部逐模块/嵌套代码/常量/异常表一致性检查及原CI，不手工导入核心或跳过检查。无新依赖或业务改动，继续原#8交付，不为同一任务修补另建PR。

隔离环境：本机原工作区仍停在codex/recovery-note-copy；未跟踪的.vscode与阶段summary.md保留。git fetch退出1（原.git/FETCH_HEAD只读，未更新）；git clone --no-hardlinks --no-checkout . .local/markdown-merge-followup退出128（Git/MSYS命名对象权限失败，未取得checkout），未重试同一权限操作。改用只读git archive e3dfed4（退出0）及Expand-Archive（退出0）取得固定版本到.local/markdown-merge-followup-src；所有编辑/验证在此副本，远端仅更新明确文件并核对expected head，不改写他人工作。gh不可用，PR/CI均使用已连接GitHub工具。

本轮cwd=.local/markdown-merge-followup-src，Q为原仓库.local/release-venv/Scripts/python.exe（独立CPython3.13.17）；原始输出写该副本artifacts/merge-core-followup/：

- 未设置PYTHONPATH时，Q -c调用collect_submodules('study_workbench')退出0但返回[]，复现错误收集；前置本副本backend后同调用并断言markdown_merge在内，退出0，42模块。
- Q -m pytest backend/tests/test_markdown_merge.py -q --junitxml=artifacts/merge-core-followup/target.xml：退出0，8项及77子测试通过。
- Q -m ruff check backend tools：退出0，完整后端/工具静态检查通过。
- ./packaging/windows/build-backend.ps1 -Python Q（PYTHONPATH预置restore-sentinel，返回后断言还原）：退出0；约140秒，42冻结模块全部与源码一致，包括新核心/嵌套代码/常量；调用者PYTHONPATH还原断言通过。原CI失效门禁未改变。完整输出build.log。最终head CI以#8实时检查/描述为准，不用原head后端或Flutter成功代替整条CI。
- Q tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/merge-core-frozen：退出0，真实冻结HTTP/恢复点只读/陈旧保存拒绝/另存幂等/持锁/巡检及业务字节保持全部原断言通过，frozen-integrity.log。
- Q tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root .local/merge-core-resource --documents：退出0，真实冻结统一导入/文档/布局/原件/作答/删除与重启保持通过，frozen-resources.log。新包仅作本轮验证，成功后清理副本产物，保留原工作区唯一当前包，不覆盖其构建目录。

审查：自审覆盖打包参数、固定解释器、PYTHONPATH继承/异常还原、核心及其测试、全部业务模块源码检查和冻结探针调用链。没有独立审查批准；按用户规则不创建子Agent。人工测试/Computer Use已取消，未执行窗口测试。不合并/发行；修复本前置阻塞后下一独立任务为验证基线归属/hash的只读预览API，UI确认载入与普通保存另分切片，均不能将纯核心冒充编辑器功能。

上传校验纠正：中间提交经本机Python默认GBK管道回传中文时乱码，且Windows git archive导出的CRLF与原始Git blob的LF不同。仅PR中的task/报告受影响，未合并/触及个人库。由保留的正确UTF-8副本重建，以Base64传输UTF-8/LF字节，逐文件核对Git blob SHA及回读内容；错误中间提交保留，不改写历史，最终head重新核实CI。

## M2-05b：受控只读合并预览API设计（2026-11-09）

独立切片基于#8打包修补及UTF-8记录恢复后的ac9cd02，分支codex/markdown-merge-preview-api；PR交付须先核对#8该head CI，再核对本PR最终head完整CI。不合并/发行，不接UI或模型，人工测试已取消。

范围：POST N/document-merge-preview只读取同空间MD工作副本。请求显式指明base=original/before/pending、可选同节点save_id、expected_base_sha256、expected_current_sha256及本地草稿text。基线从该节点原件或已校验的保存收据读取，不接受调用方自报基线正文或任意磁盘路径；原件/恢复点与期望hash不同、prepared未对账、当前不可读/变化、未知/跨空间/跨节点均拒绝。继承Bearer/Host/Origin及两并发门禁；本路由独立采用8MiB实际帧预算以容纳1MiB JSON转义文字，普通其他路由仍64KiB。每份文本及合并结果仍1MiB UTF-8。

实现复用recovery_work/recovery_text、原件读取与text_bytes路径/hash守卫及#8纯核心，不新增表/文件/收据/草稿镜像，不调用recover或save_text。响应只给conflicted/text及base/local/current hash，冲突无候选/无标记。干净候选仍不是保存许可；未来UI须明确确认载入并使用响应current hash走原PUT document，预览后的外改仍409。无法找回真实草稿基线时不猜测；保守行区间核心的冲突边界保留。

拆分：服务/严格请求模型及帧预算→HTTP授权/归属/故障/预算/只读/外改保存/QuestionFile历史保护回归→冻结HTTP探针→全量后端与静态→自审/契约/task→独立PR及当前head CI。UI选择/确认载入与完整编辑流程为下一独立任务，不将此API切片登记成完整编辑器合并。

### M2-05b实施与首次失败

DocumentFiles新增严格MergeText请求与只读路由，复用已有路径/收据读取、RLock与VIEW_SLOTS；读取/计算后再次校验当前文件hash。RequestLimits只扩大这个具体路由的实际帧预算，其他路由不变。无Schema/新依赖/写接口/迁移/Agent工具。冻结CI仍运行同一check_library_integrity.py，补只读候选、陈旧保存409和冲突无候选断言，原完整巡检与另存断言均保留。

本轮cwd与P/Q同前，P为原仓库.venv/Scripts/python.exe（Python3.12.7），Q为独立CPython3.13.17；原始产物位于副本artifacts/merge-api/及artifacts/merge-api-target*.log，隔离测试只新建.local目录。

- Q -m pytest backend/tests/test_document_merge.py -q --basetemp=.local/merge-api-target01 --junitxml=artifacts/merge-api/target01.xml：退出1，19通过4失败。两个跨节点收据测试先被不匹配的当前hash正确拒绝为409，夹具改为提供目标节点当前hash后仍断言404；QuestionFile作答夹具缺确认版ID被正确拒绝409，补实际确认ID再验证历史不变。另一个是真实边界错误：Pydantic拒绝未配对surrogate后，FastAPI默认校验错误回显原输入，JSONResponse无法编码而500。新增模型wrap校验，仅本请求返回固定422，不回显非法输入，未放宽UTF-8或字段校验。
- target02同命令更换批次名：退出1，22通过1失败；合并结果预算用例第二个资源夹具重名触发既有唯一约束，补独立名称，未降低预算/原件保持断言。
- Q -m pytest backend/tests/test_document_merge.py backend/tests/test_document_recovery.py backend/tests/test_document_files.py backend/tests/test_markdown_merge.py -q --basetemp=.local/merge-api-target03 --junitxml=artifacts/merge-api/target03.xml：退出1，54通过1失败及77子测试通过；唯一失败为原恢复点测试的Windows mklink/J被沙箱拒绝Access is denied。未改测试/跳过/降低断言；检查确认working链接不存在、retained-working字节保留后，以允许该隔离夹具创建junction的执行权限继续一次完整回归，结果另记。不是产品合并失败，也不将该轮记通过。
- 初次Ruff退出1指出新测试未使用DocumentSave导入，移除后完整backend/tools Ruff及Schema --check均退出0。非法Unicode回归还覆盖hash及未知字段，不只测正文。

### M2-05b最终本地验证与审查

所有下列命令cwd均为本轮隔离源码副本；最终业务源码/测试未在通过后再修改，仅补本报告和task交付链接。

| 实际命令 | 退出/结果 | 原始记录 |
|---|---|---|
| Q -m pytest backend/tests -q --basetemp=.local/api-full313 --junitxml=artifacts/merge-api/full313.xml | 0；557项及77子测试，298.98秒，真实junction保护包含在内 | full313.log/xml |
| P -m pytest backend/tests -q --basetemp=.local/api-full312 --junitxml=artifacts/merge-api/full312.xml | 0；557项及77子测试，304.83秒；两轮串行，TEMP/TMP指本副本.local/tmp | full312.log/xml |
| ./packaging/windows/build-backend.ps1 -Python Q | 0；约86秒，42业务模块全部与当前源码一致，旧验证包先安全清理，仅本副本产生临时新包 | build.log |
| Q tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/merge-api-frozen | 0；新增merge_preview_readonly/merge_stale_save_refused/merge_conflict_has_no_candidate及全部原恢复点/另存/锁/巡检/字节保持断言通过 | frozen-api.log/result.json |
| Q -m ruff check backend tools；Q tools/export_question_schema.py --check | 各0；无新依赖/Schema漂移 | 实际命令输出 |
| Q -X utf8 -运行内联相对链接检查（docs全部MD、dev/records各report及dev/README） | 0；49文档，无缺失目标 | 实际工具输出；交付链接补交仍校验 |

全量复测使用正常自动化执行权限，仅允许在各自新建隔离夹具中生成Windows junction；没有重试旧缺失链接或访问个人库。Starlette/anyio弃用和PyInstaller既有可选hidden-import警告保留，无升级/屏蔽。通过的pytest临时目录由现行failed策略自动回收；失败日志/JUnit/最小现场不删。冻结新包验证后清理本副本成功产物，原工作区包不覆盖，保留一份原有Office组件，不制作人工验收包。

自审已核对实际差异、DocumentFiles所有新增调用方及app.include_router继承鉴权、RequestLimits实际分块预算、恢复点所有权/路径/hash/重解析点守卫的复用、prepared拒绝、当前读取期间外改、原expected hash保存、失败不写库/文件、QuestionFile确认版/实际旧作答与墓碑语义。新增23项HTTP用例覆盖空稿/CRLF/字面内容、原件及before/pending基线、错误基线/版本、跨节点/空间、401/403/Host、非法字段与Unicode、1MiB输入/结果及8MiB无Content-Length帧、两并发忙、预览后外改和实际普通保存。无独立审查批准；不将本轮CI或另一个任务的自审当独立审查。按项目规则不创建子Agent。

本地不重复Flutter/Windows UI构建：此独立切片没有Dart/UI/原生改动，项目原完整桌面/COM/全量R1–R5/冻结生命周期及文档worker仍由本PR最终head CI执行并逐项核对，不沿用#8结果。#8功能head 5d74ad6的CI #52已全部通过；记录UTF-8纠正后的最终#8 head ac9cd02已于2026-11-09核对[CI #58](https://github.com/surface-user/StudyWorkbench/actions/runs/42573718426)三组全部completed/success，含所有原冻结链；本切片依赖满足，仍无独立审查批准。独立API草稿PR的实际URL、最终head/运行/检查时间在其描述与task交付条目维护，不为记录自身SHA循环提交。UI合并确认载入未实施，整体M2-05继续进行中；未合并/发布。

实际交付：实现提交b227d9cc663808a4189905c73769897700aa79a5，独立[草稿PR #9](https://github.com/surface-user/StudyWorkbench/pull/9)，base为#8的ac9cd02。9份文件均以Base64传输规范UTF-8/LF字节并核对返回Git blob SHA，正文无替换字符；远端回读和最终head全CI继续核对。此处与task仅补实际PR链接，最终head/运行/退出结论持续记录在PR描述，不为记录自身SHA循环提交。任务要求实现、相关自动化、自审/如实披露独立审查状态、独立PR及当前head CI；不要求合并/发行。未通过当前head CI前不宣称切片退出。

## M2-05c：桌面合并预览与确认载入设计（2026-11-09）

基线核对：PR #9仍open/draft，head 37fa76e339de8dd1076d807daeaf80609353122c、base ac9cd02；当前head CI #63三组success，无未解决行内线程，仅有明确标注的自审，无独立批准。沿用已校验的隔离源码副本，DocumentPage/恢复对话框/task/本报告规范UTF-8内容的Git blob SHA逐项与该head核对一致；不重试原工作区只读.git操作，原.vscode/summary.md保留。独立远端分支codex/markdown-merge-desktop从该head建立；提交/独立草稿PR/当前head全CI为交付要求，不要求合并/发行。

需求与设计：仅在已有MD工作副本且draft_base_sha256非空时提供合并入口，空草稿仍是有效草稿。对话框冻结原草稿/基线，仅允许选择与原draft_base_sha256一致的原件或同节点before/pending收据，记录有界分页；基线/当前字节最终由#9 API核验，不猜测基线，不新增后端接口。显式点击预览后先读取当前工作文件hash，再请求只读合并，字面显示候选（可为空）或冲突无候选。取消/错误/缺失基线不修改任何原草稿。

用户另行点击确认载入时，以预览时相同的基线、本地草稿和expected_current_sha256再调用只读API，候选/基线/当前版本不一致或外改则拒绝，必须重新预览。返回父页前后均检查mounted，父页再次核对资源/标签身份、原草稿文字和原基线未变化；仅更新TextEditingController及既有tab.draft/draft_base_sha256，切换原文编辑。后续点击原保存按钮才PUT document，expected hash使用候选对应current hash，后续外改仍409且草稿保留。重复打开/预览/确认有本地忙门禁，不自动保存、解析/发布题目，不改原件、确认版或历史。

任务拆分：独立只读对话框及DocumentPage入口/确认载入→原件/恢复点/分页、取消、确认时陈旧/外改、空稿、冲突无候选、重复操作/卸载、父草稿变更保持及普通保存回归→Flutter格式/分析/全量与Windows构建/原CI→自审→更新现行契约/task及本报告→独立PR并核实最终head CI。复用现有组件/Backend/layout，无新依赖或迁移；不接模型，不执行人工测试/Computer Use，不新建UI验收包，保留旧失败。

### M2-05c实现、失败及修补

新增DocumentMergeDialog，仅调用既有GET document、分页GET document-saves和POST document-merge-preview。仅匹配原草稿基线的选项可见；点击预览读取当前hash，候选按字面显示，可为空，冲突无候选。确认重发已核对的相同请求，不刷新expected current绕过陈旧检查；base/current/local绑定或候选不一致拒绝。DocumentPage冻结原标签/资源prefix/Backend实例/草稿/基线，返回时再次核对，才更新既有草稿字段与当前hash；普通save流程未改。后台来源切换、父草稿变化、取消、卸载或异步错误均不覆盖原草稿。

环境仍为本轮隔离副本，原工作区.git只读未重试写入。固定Flutter3.47.1/Dart3.13.1，P/Q同前；所有原始日志位于本副本artifacts/merge-ui-*.log及merge-ui-api.xml，不入Git。

- cwd=apps/desktop，flutter pub get --offline退出1：依赖解析完成，但Windows未启用symlink支持；未更改系统Developer Mode。既有锁文件逐字规范核对不变，没有新依赖。后续--no-pub静态/组件测试正常执行，Windows Release/COM交最终head CI，不能把该次pub get记成功。
- 为完整Flutter真实后端管道测试，在本副本.venv建立到原已有Python环境的单一junction，不复制或修改环境。首次执行的自动权限审批超时，CreateProcess未启动；实际Test-Path确认链接不存在、目标环境仍为普通目录后，仅重试一次更小的New-Item Junction命令，退出0。无需用户修改全局权限，不访问个人学习目录。
- 首轮flutter analyze --no-pub退出1：新文件两处跨行if缺块（analyze01）；补块后关闭守卫增加了另一处跨行if，第二轮退出1（analyze-final），修复后最终analyze02退出0，6.9秒。未关闭lint或降低规则。
- flutter test --no-pub test/document_merge_test.dart test/document_recovery_test.dart test/document_page_test.dart：target01退出1，18通过13失败。多数新测试未等待选择后的widget重绘即点击仍禁用的预览，补pump；窄视图夹具从当前B开始编辑却要求选择原件A，修正夹具使真实草稿基线与原件一致，不允许产品猜测。target02退出1，30通过1失败；target03退出1，33通过1失败。剩余直接重复callback测试触发Flutter guard冲突：mock异步回调中使用guarded expect与pump重叠，改为等价expectSync，断言保留。
- 自审发现关闭动画期间State仍mounted，确认成功finally清busy会让迟到callback再次POST甚至再次pop。新增dismiss-red回归实际退出1：关闭期间第二次确认回调产生第3次POST，预期仅2次；另一失败为上述fixture guard。新增不可逆closing状态，覆盖成功、取消、系统返回；每个await后及catch/finally均检查关闭状态，关闭后不续发请求、不重启按钮、不再次pop。target04退出0，相关36项通过；新增系统返回/重复取消继续纳入最终全量。没有删除失败测试或增加超时掩盖问题。

### M2-05c最终验证与审查

| 命令（cwd另注明） | 实际退出/覆盖 | 原始记录 |
|---|---|---|
| cwd=apps/desktop；SDK dart.exe format lib/document_merge_dialog.dart lib/document_page.dart test/document_merge_test.dart | 0；最终3文件规范 | 实际输出 |
| 同cwd；flutter analyze --no-pub | 0；无问题，6.9秒 | merge-ui-analyze02.log |
| 同cwd；flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench/.local/markdown-merge-followup-src --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/markdown-merge-followup-src/.local/merge-ui-full-data | 0；全量193项，约44秒；真实后端进程测试使用该副本#9源码及新隔离数据 | merge-ui-full.log |
| cwd副本根；Q -m pytest backend/tests/test_document_merge.py backend/tests/test_markdown_merge.py -q --basetemp=.local/merge-ui-api-tests --junitxml=artifacts/merge-ui-api.xml | 0；31项及77子测试，13.08秒 | merge-ui-api.log/xml |

新增26项组件回归包含原件/before/pending、50+1分页/基线不符不猜测、预览/确认/取消/系统返回、关闭动画迟到响应/重复确认和取消、空稿、字面候选/冲突无候选、确认时外改/结果变化、载入后陈旧保存拒绝、父草稿变化不覆盖、能力变化/失效收据/错误响应绑定、卸载及400×800视图。组件/后端分项证据不冒充实际窗口测试。后端业务源码未改，两个API模块Git blob与#9逐项相同；本地不重复双Python全量/冻结包和原生Windows构建，最终head CI仍执行双Python全量/R1–R5、Flutter/Windows Release/COM及全套冻结链，不沿用#9绿灯。静态/全量后仅更新现行契约/task/本报告。

自审已核对新增路由调用与所有受影响的DocumentPage load/edit/save/recovery/草稿布局、Backend实例及资源身份、空稿和异步失效、PopScope所有退出路径、关闭竞态先失败后通过、原普通expected hash保存以及QuestionFile/历史权威。无新表/迁移/依赖/Agent工具，不自动修复路径或发布确认版；旧恢复入口和失败证据保留。此次仅自审，无独立批准；不把CI当独立审查。人工测试/Computer Use按用户指令取消。独立草稿PR/最终head CI继续核实，未合并/发行；M2-05其他派生恢复与容量治理仍未完成。

交付前附加检查：SDK dart.exe format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test退出0，87文件无变化；显式8文件UTF-8/替换字符/尾空白检查和49文档相对链接检查退出0，无缺失。原工作区分支及未提交文件未切换/覆盖；远端仅上传上述3份Dart实现/测试和4份现行文档及本报告，采用Base64/UTF-8和逐文件Git blob SHA/回读检查。最终head/CI另在PR描述维护，不为记录自身SHA循环提交。

实际PR交付：[草稿PR #10](https://github.com/surface-user/StudyWorkbench/pull/10)，实现84b841e195784c828959fd860f2cca84c2322861，base为#9的37fa76e，独立分支codex/markdown-merge-desktop。8份明确文件上传后blob SHA逐项核对，本节/task补实际交付链接；最终head/CI运行/核对时间及切片退出结论继续PR描述，不记录自身SHA形成循环提交。没有独立批准，不合并/发行；task.md仍有其他未完成项，后续继续按依赖推进。

## M2-05d：恢复副本容量只读报告设计（2026-11-09）

本轮重新核对#10仍open/draft，head af6fec76bb7d8497fe68f78cad38ec379ac277bc、base 37fa76e，当前CI #68全部success，无未解决行内线程。原工作区仍codex/recovery-note-copy，仅原.vscode和阶段summary.md未跟踪；未切换/覆盖。沿用隔离副本，__main__/library_integrity/task/本报告规范UTF-8 Git blob逐项与#10核对一致。新独立分支codex/recovery-storage-report基于该head，交付要求实现/自动化/自审/独立草稿PR与最终head CI，不要求合并/发行。

用户边界：本轮只界定和实施容量可见性，不授权删除恢复点、失败字节或任何学习数据，不自动删除/覆盖。新离线--report-recovery-storage须显式--confirm-all-workspaces，持既有数据锁和SQLite只读连接；拒绝正在使用、缺库、旧schema、其他操作/config/media/parent-pipe组合，不迁移/启动服务/写配置。锁文件沿用原DataLock约定可创建/锁定，不写学习数据。

首批范围限定所有空间（含归档/墓碑）的workspaces/*/working和question-files，读取document_workfiles/document_saves及节点/题目映射以核对归属和严格before/pending名称。原件/媒体/确认快照、Office失败预览、下载attempt、未知根目录及备份/恢复暂存不纳入，后续单独设计。统计current、before、pending及未登记工作目录文件的数量/逻辑长度，按收据状态计数，并给最多20个较大文件的受限相对路径。成功保存后缺失的committed pending单独计数，不假称损坏或已释放空间；其他缺失/不安全引用/不可读/变化/预算中止标不完整。

逻辑长度按不同相对文件路径计数，重复引用不重复累计；不同路径的hardlink可重复计长，不声称实际磁盘分配/去重或可回收字节。仅元数据，不读正文/核hash，不证明库健康；外部编辑器不受数据锁约束，报告非原子文件系统快照。任何分类/未登记状态/文件大小都不构成删除依据，不提供清理开关、年龄/TTL推断或写接口。最多20000目录项、50000相关行、30秒协作期限和200问题，输出明确complete/bytes_kind/content_integrity_checked/data_modified/deletion_authorized等边界，复用既有路径/只读/锁守卫，不放宽原完整性巡检。

任务拆分：只读容量服务/CLI→真实保存中断/状态/消费pending/旧generation与未登记字节、归档墓碑/QuestionFile、坏路径/归属/重解析点/特殊文件、缺失/变化/预算/旧库及参数回归，逐字节保持→冻结CLI串联及旧全部探针→双Python全量/静态/当前head完整CI→自审与契约/task/原报告→独立草稿PR。不新增依赖/迁移、HTTP/桌面/Agent入口，不接模型，不做人工测试。

### M2-05d 实施与验证（2026-11-10）

实现落在recovery_storage.py与__main__.py，新CLI独立互斥分支，沿用DataLock、validate_root、archive_path、no_links及SQLite mode=ro/query_only。按受限目录扫描，不对数据库外报路径做stat，不读正文；逐项累计数量/逻辑长度并维持最多20文件列表，坏引用/缺失/变化/预算停止均不假称完整。原完整性巡检逻辑、现有收据/恢复/合并/普通保存及全部断言保留。无新表、迁移、依赖、模型或Agent接口。已更新API/架构/数据模型以区分当前范围与后续容量治理。

首轮Q专项capacity-target01退出1：13失败/13通过。真实实现错误为Windows DirEntry缓存的inode/时间精度与Path即时stat不同，正常文件全部误判变化；改为两次即时stat签名复核，仍核对缓存大小/类型并保留变化回归。另有夹具错误：给多工作文件设置相同非法路径触发UNIQUE；改为各节点独立坏路径。第二轮target02退出1：3失败/23通过；第三轮target03退出1：1失败/25通过。归档夹具原本未创建题目工作文件，补真实working-copy创建以保证实际覆盖QuestionFile；junction断言原先错把其他归档空间正常working也排除，改为精确断言default被链接范围不展开，同时核对保留目标字节。未删失败、跳过Windows边界或降低产品断言；旧日志/XML及失败fixture保留在artifacts/capacity-*与.local/cap-t01..03。

cwd均为隔离副本.local/markdown-merge-followup-src。Q=D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe，独立CPython3.13.17；P=.venv/Scripts/python.exe，链接原项目Python3.12.7环境，测试源码仍是本副本。以下日志仅保存生成fixture/脱敏结果，不包含个人库：

| 实际命令 | 退出/结果 | 原始记录（副本artifacts/） |
|---|---|---|
| Q -m pytest backend/tests/test_recovery_storage.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/cap-t04 --junitxml=artifacts/capacity-target04.xml | 0；26项，44.73秒 | capacity-target04.log/xml |
| Q -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/cap-qfull01 --junitxml=artifacts/capacity-qfull01.xml | 0；583项及77子测试，341.62秒 | capacity-qfull01.log/xml |
| P -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/cap-pfull01 --junitxml=artifacts/capacity-pfull01.xml | 0；最终源码583项及77子测试，389.33秒；与Q串行 | capacity-pfull01.log/xml |
| Q -m ruff check backend tools | 0；全量静态检查 | 实际输出；首轮--fix亦0且无额外文件改动 |
| Q tools/export_question_schema.py --check | 0；协议无漂移 | 实际输出 |
| ./packaging/windows/build-backend.ps1 -Python Q | 0；43模块与当前源码一致，包括新CLI模块/嵌套代码/常量；约146秒 | capacity-build01.log |
| Q tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/capacity-frozen01 | 0；原HTTP恢复/另存/三方合并/持锁/健康/孤立目录/外改巡检全链，新报告持锁拒绝、业务字节保持与未登记容量精确增加均通过 | capacity-frozen01.log；.local/capacity-frozen01/result.json |
| Q tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root .local/capacity-resources01 --documents | 0；原统一导入/文档/布局/作答/原件及删除/重启保持，schema0016 | capacity-resources01.log |

新增26项覆盖所有收据状态与消费pending、归档/墓碑及真实QuestionFile工作文件、旧generation/二进制未登记字节、无正文读取、参数互斥与显式全空间确认、只读逐字节保持、坏路径/归属/ID/状态、缺失/不可读/损坏库/变化、4预算、旧schema/无迁移/持锁、实际Windows junction、1GiB逻辑长度与较大文件截断、hardlink按路径重复计长。不是全库健康/真实磁盘可释放空间证明。

辅助失败如实保留：误调用不存在的Q tools/check_schema.py退出1，随后用仓库实际export_question_schema.py --check退出0；无协议文件改动。原.git仍只读，未再fetch/clone；GitHub工具不返回commit tree，匿名REST读取遇共享IP限流，未用于判定CI。已按本地#7固定树和#8–10全部实际变更路径、#10逐文件blob SHA重建基树838715922517e74a040788a45af1c22d72c9b3b2，无分支引用变更；后续仅显式9文件上传并核对expected head，既有工作不覆盖。

自审核对调用方/参数、读取范围与路径/空间/题目归属、锁与只读事务、扫描及SQL预算、分类失效/部分小计、Windows缓存/重解析点/外改、hardlink/逻辑长度解释、输出无正文/绝对路径、冻结收集与原探针未弱化。只有自审，无独立批准，CI不计作独立审查。P全量、冻结资源探针、最终head全CI及实际PR链接继续本节/PR实时描述；人工测试已取消，不合并/发行。其他失败字节范围及全部派生恢复仍未完成，删除/覆盖学习数据或恢复点未获授权。

验证边界及留存：Q全量在追加目录即时类型守卫前启动，最终源码由Q专项26项、43模块源码一致性、冻结两探针、P全量及当前head CI复核，不把启动前导入的进程称作最终源码全量。业务UI未改，本地不重复Flutter/Windows构建；最终head CI仍完整执行双Python/R1–R5、Flutter/Windows/COM和全套冻结链，不能沿用#10。artifacts/capacity_validate.py退出0：明确9份改动，其他427份基线文件保持、48文档相对链接无缺失、UTF-8/替换字符/尾空白检查通过。该辅助脚本不入Git。

两冻结探针成功/进程退出后，以PowerShell Resolve-Path逐一确认隔离副本范围且全部子项无reparse point，再Remove-Item -LiteralPath -Recurse -Force清理仅本副本dist/study_backend、build/study_backend、.local/capacity-frozen01、.local/capacity-resources01，退出0。先保存包SHA256至capacity-package-hash.json、文件数量/逻辑长度及精确路径至capacity-generated-artifacts.json、结果至capacity-frozen-result.json，全部日志/JUnit保留。原仓库当前冻结包/Office组件、.venv环境junction、用户数据与所有失败现场未动；此为明确生成产物回收，不是新容量报告提供删除功能。

本地收尾：P全量最终源码退出0，583及77子测试；两环境仅既有Starlette anyio别名弃用警告。原工作区仍a959b9f/codex/recovery-note-copy，仅原.vscode与summary.md未跟踪、SHA256与任务开始相同，未切换分支或修改原文件。实现/相关自动化/自审完成，独立审查没有取得；下一步为本切片独立草稿PR及最终head完整CI，不将已跑本地或父PR绿灯替代新head。M2-05整体未完成；下一候选是另行界定Office失败预览/下载attempt的只读容量范围与有效归属，尚未设计实施，不授权清除恢复点或学习数据。

实际交付：[草稿PR #11](https://github.com/surface-user/StudyWorkbench/pull/11)，独立分支codex/recovery-storage-report，base=#10的af6fec76bb7d8497fe68f78cad38ec379ac277bc，实现提交2b06b07d41a5f722eaedb00d6ac27a51eacabac0。仅上述9文件，远端实现commit完整差异逐项核对一致，无额外基线改动；均以规范UTF-8/LF Base64上传并校验Git blob SHA。首次create_blob遇连接器Transport send error，未执行任何分支更新；先读取目标分支__main__确认仍为原blob 3ebfaca，再恢复内容寻址的blob上传成功，随后带expected_sha推进独立分支，未强推/重试不确定的分支写入。实际PR链接补入task/原报告；最终head、当前CI运行/核对时间及切片退出结论另在PR描述维护，不为记录自身SHA循环提交。CI尚未确认前待交付，不将CI视为独立批准；不合并/发行。

文档链接补交检查：直接关闭autocrlf比较LF基线与Windows CRLF副本的git diff --no-index --check退出1，将所有行末CR作为空白告警；规范上传字节检查原已通过。随后artifacts/capacity_diffcheck.py对与Git上传完全相同的UTF-8/LF临时副本逐一执行git -c core.autocrlf=false diff --no-index --check；辅助脚本首次误要求退出0失败，核对--no-index隐含--exit-code后按0/1且stdout/stderr均空严格判定（1也表示存在正常差异）。九文件检查结果保存capacity-diffcheck.log；不改源文件或放宽正文空白断言。

## M2-05e：Office预览目录容量只读统计设计（2026-11-10）

前置核对：#11仍open/draft，head bd9b4ddcb1c755251bedbb601b8ae61de03192f8、base af6fec7，CI #73三个job/每步success，无未解决行内线程，仅自审；不是独立批准。副本九文件逐项与此head远端blob SHA一致。原工作区仍codex/recovery-note-copy，原.vscode/settings.json及summary.md SHA256保持，未切换或覆盖。新分支codex/office-preview-storage-report从该head建立；继续隔离副本和连接器，不重试原.git写权限操作。独立切片要求实现、相关自动化、自审、独立草稿PR及最终head CI，不合并/发行；人工测试已取消，不接模型。

选择Office而非下载：Office任务已有固定previews/<id>/output/source.pdf路径与DocumentPreview归属，目录还保留source.docx/pptx、profile和tmp；这些是失败/来源证据，不是天然垃圾。下载attempt路径可能就是已入库媒体的权威字节，须另行核对复用关系，不混在本切片。

范围：新增互斥离线--report-office-storage --confirm-all-workspaces，仅统计所有空间（含归档/墓碑）的workspaces/*/previews。复用#11的有界元数据扫描/锁/只读事务和共同输出边界，保留原Markdown CLI及schema/范围不变；不新增通用扫描框架、依赖或表。Office专用只读查询严格核对32位任务ID、精确relative_pdf、空间存在、节点类型/空间/源资源一致及原件同空间后，才按queued/running/ready/failed/interrupted/cancelled状态归属整个任务目录；不读取/导出原件标题、任务错误或运行时指纹，不打开正文、PDF、profile或Office组件。

输出按上述六状态的*_preview_file及unregistered_preview_file累计文件数/逻辑长度，records_by_status仅统计表中记录状态；同一状态目录中的所有文件均计入，不把profile/tmp当可清缓存。未登记只表示未能匹配有效任务。ready的固定PDF缺失标不完整；其他状态PDF可尚未生成，missing_nonready_pdf单独计数，不推断损坏或已释放；queued/running收据保持原状，不借报告启动对账/重试转换。没有就绪内容/hash或全库健康证明。

继续限制20000目录项、50000相关行、30秒协作时间、200问题和前20个较大文件；输出非原子观测的按路径逻辑长度，不承诺分配/可回收字节，hardlink不同路径可重复计长。重解析点不展开，坏归属/路径/未知状态/缺失/不可读/变化/预算不足均明确不完整。原件、媒体、Markdown恢复点、确认版、下载、其他目录及备份/恢复暂存不在Office范围。任何结果均不授权删除/覆盖、保留策略执行或自动恢复；无HTTP、桌面或Agent入口。

拆分：共用扫描仅提取必要分支，保留原26项→Office专用状态/真实失败字节/归档墓碑/坏归属/缺失/排除/预算/锁/CLI/重解析点与逐字节保持回归→扩展原冻结探针的合成Office任务样本（无组件依赖，不弱化原断言）→串行双Python全量、Ruff/Schema、干净冻结及现有探针→自审/现行契约/task/原报告→独立草稿PR、最终head CI。整个M2-05/task.md仍未完成。

### M2-05e 实施与本地验证

实现只增加report_office_storage公开业务函数与互斥CLI；recovery_storage.py内的私有共同扫描保留原Markdown对外schema/目录与missing_committed_pending语义。Office只读SQL明确选取必要字段，校验空间存在、节点/源资源绑定和严格路径后建目录状态映射；整个有效任务目录按状态计长。无新模块、表、迁移、依赖、HTTP/桌面/Agent入口。原巡检算法、Office转换与下载实现未改；只是扩展原冻结巡检探针，所有旧断言仍在。

失败与修正：Q的office-target01退出1，2失败/46通过；均为夹具建库阶段，六状态用了相同源字节触发resources空间/hash唯一约束，node_kind注错时未清空resource_id触发CHECK。分别改用每状态不同自建OOXML及合法folder+NULL绑定，保留坏归属判定。target02退出1，1失败/47通过：同级节点仍同名触发ux_nodes_sibling_name，修正为状态独立名称。针对全状态夹具office-one01退出0、1项、3.26秒；最终target03退出0，48项、74.81秒。没有删除失败、跳过Windows边界或降低断言；old目标日志/XML及失败fixture保留。

首轮Q全量office-qfull01在修正前已导入旧测试函数，运行期间源文件修正不会替换其Python函数；最终退出1，2失败/603通过及77子测试，365.35秒，仍是首轮源重复/hash与node_kind旧夹具失败（traceback可能回显修改后的磁盘行，不能以其证明执行了新夹具）。此结果保留，不伪记全量成功。后续以冻结最终源码、最终48专项及串行P/Q新全量和最终head CI复核，不用旧进程结果替代最终版。

cwd仍为隔离副本.local/markdown-merge-followup-src；P=.venv/Scripts/python.exe（原Python3.12.7环境junction），Q=D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（独立3.13.17）。实际命令/证据：

| 命令 | 退出/结果 | 副本artifacts/ |
|---|---|---|
| Q -m ruff check backend tools | 0；全量静态 | 实际输出 |
| Q tools/export_question_schema.py --check | 0；协议无漂移 | 实际输出 |
| Q -m pytest backend/tests/test_office_storage.py backend/tests/test_recovery_storage.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/off-t03 --junitxml=artifacts/office-target03.xml | 0；48项（新22+原26），74.81秒 | office-target03.log/xml |
| P -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/off-pfull01 --junitxml=artifacts/office-pfull01.xml | 0；最终版本605项及77子测试，476.14秒 | office-pfull01.log/xml |
| Q -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/off-qfull02 --junitxml=artifacts/office-qfull02.xml | 0；最终版本605项及77子测试，387.01秒；在P结束后串行 | office-qfull02.log/xml |
| ./packaging/windows/build-backend.ps1 -Python Q | 0；43冻结模块与最终源码/嵌套代码/常量一致，约135秒 | office-build01.log |
| Q tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/office-frozen01 | 0；原恢复/另存/合并/持锁/完整性/字节保持全链与新Office CLI持锁拒绝、空范围/失败profile+源副本+tmp计长/未登记/缺失非就绪计数/缺失ready不完整且业务字节保持 | office-frozen01.log，.local/office-frozen01/result.json |
| Q tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root .local/office-resources01 --documents | 0；原导入/文档/布局/原件/作答/删除与重启保持，schema0016 | office-resources01.log |

新22项覆盖真实归档/墓碑元数据、六持久状态不对账、源副本/profile/tmp/输出及未登记二进制字节、hardlink按路径计长、前20截断/排序、无内容读取、缺失ready/其他状态、8种坏归属/ID/路径/状态、4预算、旧库/无库/损坏库/持锁、Windows实际junction和全部CLI参数互斥/显式确认及逐字节保持。故意用不解析的PDF/Office字节证明报告不声称内容健康，不冒充真实转换测试；既有转换/worker及冻结探针仍保留。

实现自审：逐项核对共用扫描的MD不变分支及所有调用方、Office表/路径/空间/源关系、边界预算、部分小计、非原子/逻辑长度含义、profile/tmp不当垃圾、ready非内容证明、参数互斥、只读事务及无组件/正文调用。没有发现剩余阻断实现问题；只有自审，无独立批准，CI不计作独立审查。双Python最终全量、补交校验、独立PR与当前head CI继续；人工测试已取消，不合并/发行。下一候选为下载attempt与入库权威的只读容量范围及交叉引用，未实施，不授权删除或清除恢复证据。

补交校验：Q -X utf8 artifacts/office_validate.py退出0，明确9份文件、其余428份#11基线文件保持；48文档相对链接无缺失，UTF-8/替换字符/尾空白及规范UTF-8/LF上传字节的git diff --no-index --check逐项通过，详见office-diffcheck.json。--no-index隐含--exit-code，正常非空差异返回1；检查要求stdout/stderr均空且返回0/1，不修改空白断言。脚本/日志不入Git；业务UI、依赖和schema未改，本地不重复Flutter/Windows大包，最终head CI仍执行全部原流程，不沿用#11绿灯。

本地收尾：串行P/Q最终全量均605及77子测试通过，仅既有Starlette anyio别名弃用警告。全部本地验证成功、持有的冻结样本进程已退出后，以PowerShell Resolve-Path逐一验证隔离副本边界、Get-ChildItem检查无重解析点，再仅Remove-Item -LiteralPath -Recurse -Force清理本副本dist/study_backend、build/study_backend、.local/office-frozen01、.local/office-resources01，退出0；包SHA256、精确路径/数量/逻辑长度及样本结论先保存office-package-hash.json、office-generated-artifacts.json、office-frozen-result.json。原工作区当前包/Office组件、.venv junction、用户数据及所有失败现场未动；这不是容量报告删除功能。下一步独立PR/最终head全CI及补交链接；未确认前仍待交付，不把一个切片冒充整个M2-05/task.md完成。

实际交付：[草稿PR #12](https://github.com/surface-user/StudyWorkbench/pull/12)，分支codex/office-preview-storage-report，base=#11的bd9b4ddcb1c755251bedbb601b8ae61de03192f8，实现30c09878a16a2bafebc5adca5af1e89955ec333a。创建前复核#11未变化；全部九文件规范UTF-8/LF经Base64上传/逐项Git blob SHA核对，远端实现commit完整差异恰为九份，无额外基线修改；分支用expected_sha推进，未强推。task/原报告补实际交付链接，最终head、CI运行/核对时间及切片退出结论另在PR描述维护，避免为记录自身SHA循环提交；未知/未完成时仍待交付。不把CI算作独立批准，不合并/发行，剩余下载统计/其他派生恢复与整个task.md继续保留。

## M2-05f：下载attempt与媒体引用只读容量统计设计（2026-11-10）

已重新核对#12仍open/draft，head f141770fca6daa1ce57508e3349db3262576d921、CI #78三组/每步success，无未解决行内线程，仅自审，不是独立批准。副本九份文件逐项与该head远端Git blob一致；原分支codex/recovery-note-copy、未提交.vscode/settings.json及summary.md保持原hash。新分支codex/download-storage-report从此head建立，继续隔离副本/连接器，不写原.git或覆盖他人工作。要求本切片独立草稿PR、相关自动化、自审及最终head全CI，不要求合并/发行；不接模型，不做人工测试，不创建子Agent。

依据现有下载实现与LW-07契约：首次成功下载可直接成为MediaEntry原件路径；重复hash复用旧媒体身份，但本次完整下载文件仍保留；restart增加attempt，旧字节保留且没有逐attempt状态账。故本轮只描述实际路径和声明引用，不能把ready、failed、低编号或无MediaEntry引用解释为可清理。遵守本轮用户明确限制，不删除/覆盖或建议清理任何用户学习数据或恢复证据。

新增独立互斥离线--report-download-storage --confirm-all-workspaces，仅统计全部空间（含归档/墓碑）的workspaces/*/downloads。复用既有锁/SQLite只读事务/元数据扫描/路径与预算，原Markdown和Office命令及schema保持；私有扫描只接受三个固定调用模式，不开放任意目录。下载表仅选ID/空间/attempt/relative_path/status，媒体表仅选空间/relative_path/status和空间存在性；不读URL、名称、progress/result/ETag、播放数据、正文或hash，不启动网络/下载worker/对账。既有DNS边界、下载/入库/重试算法不变。

先严格核对32位任务ID、正整数attempt、现存空间以及固定workspaces/<space>/downloads/<job>/<attempt>.mp4/webm/m4a路径，再识别当前文件；同目录同后缀的较小正整数标准文件名只标lower_numbered，不猜测其历史状态。MediaEntry使用规范相对路径/同空间存在性核对，所有状态的有效引用均单独累计（重复行不重复计文件字节），ready引用优先作为必须存在；未知媒体状态标不完整且不把路径降为无引用。任何媒体引用文件优先归media_referenced_file；其他依次current_attempt_file/lower_numbered_attempt_file/other_download_file。顶层categories互斥计长，较大文件另外给attempt_relation/current_job_status/media_reference_count，以表达同一路径既是attempt又是媒体原件。current_job_status不是旧attempt历史状态。

所有有效ready下载当前路径或ready/未知状态的媒体路径缺失，报告不完整；所有引用均非就绪时缺失只计missing_optional_download_files，按不同预期路径去重，不对账/修复。media_reference_rows/media_referenced_paths分别是范围内有效声明引用行/路径数，不是内容验证。按路径匹配，不比较hash或读取job.result以重建去重结果，不穷尽其他表、正文或文件系统alias引用；缺少本报告引用不代表没有价值/可弃。attempt_history_checked=false，任何分类均无清理建议或删除授权。

预算沿用20000目录项、50000相关行（下载任务及扫描的媒体行合计）、30秒协作期限、200问题、前20较大文件；超限返回不完整观测小计，不推算全库容量。仅逻辑长度，hardlink不同路径可重复计长，非磁盘分配/可回收字节，非原子文件系统快照；重解析点不展开。其他命名空间/未知根目录/备份恢复暂存排除，不提供HTTP/UI/Agent/保留策略。无新表、迁移或依赖。

拆分：必要的固定模式扩展与只读引用合并→真实API的首次入库/去重/restart保留关系、各状态/归档墓碑/重复引用/旧编号及未知文件、坏元数据/缺失/预算/锁/重解析点/无正文URL与字节保持，回归原48项→原冻结探针追加合成下载/媒体引用及缺失场景且保持旧断言→串行双Python全量/Ruff/Schema/干净冻结→自审/现行契约/task/原报告→独立草稿PR及最终head CI。整个M2-05/task.md仍有其他未完成项，不以本切片代替全部开发完成。

### M2-05f 实施与验证

在既有recovery_storage.py内增加固定downloads调用模式与report_download_storage/互斥CLI，无新模块/依赖/表/迁移。任务与媒体独立验证，媒体有效路径不会因任务元数据损坏而被忽略；重复媒体引用以required逻辑或合并，同路径字节只计一次，任一ready要求存在。较大文件给声明引用数及当前任务上下文，不猜测旧文件状态。原MD/Office返回字段与命名空间保持；下载/worker/入库算法及DNS边界未改，没有HTTP/UI/Agent入口。

自动化保留：首次Ruff退出1（新增测试未使用hashlib导入），移除后完整backend/tools退出0，pytest当时未执行。download-target01随后退出1，3失败/76通过、108.27秒，失败均是注入attempt=0/未知状态的夹具先被0015 CHECK挡住，报告未执行；已在这些一次性坏库fixture的独立SQLite连接中显式ignore_check_constraints=ON以构造需检查的损坏，不改变业务/报告连接的约束或断言。初轮测试函数在导入后不会因磁盘修补而变化，旧失败日志/XML和.local/dl-t01现场保留。最终download-target02退出0，79项、110.15秒。

新31项包括：stub网络但执行真实本地API的首次入库、重复hash复用同MediaEntry、独立节点/墓碑、两次restart保留低编号文件及当前queued不对账；媒体ready/failed路径优先、重复引用不重复计字节/缺失、缺少下载记录的媒体权威；六持久状态、归档空间、低编号/未来编号/非标准名/后缀及嵌套未知文件、hardlink/前20截断、8种坏任务及2种坏媒体引用、4预算及媒体行共用预算、缺库/旧schema/损坏/锁、真实Windows junction和CLI互斥/全空间确认。Path.open guard拒绝读取正文，SQLite authorizer拒绝读取URL/名称/progress/result/error/播放数据/hash/大小等非必要列；数据库及所有业务文件前后字节一致，输出无签名query/主机/标题/绝对路径。不是实际公网下载或内容格式健康证明，旧公网来源限制本轮不绕过。

cwd=.local/markdown-merge-followup-src，P=.venv/Scripts/python.exe（原3.12.7环境junction），Q=D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（独立3.13.17）。实际命令及退出：

| 命令 | 退出/结果 | 副本artifacts/ |
|---|---|---|
| Q -m ruff check backend tools | 0；完整静态 | 实际输出，旧未用导入失败保留于本节 |
| Q tools/export_question_schema.py --check | 0；协议无漂移 | 实际输出 |
| Q -m pytest backend/tests/test_download_storage.py backend/tests/test_office_storage.py backend/tests/test_recovery_storage.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/dl-t02 --junitxml=artifacts/download-target02.xml | 0；新31+原48共79项，110.15秒 | download-target02.log/xml |
| P -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/dl-pfull01 --junitxml=artifacts/download-pfull01.xml | 0；最终版本636项及77子测试，463.00秒 | download-pfull01.log/xml |
| Q -m pytest -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/dl-qfull01 --junitxml=artifacts/download-qfull01.xml | 0；最终版本636项及77子测试，402.19秒；在P结束后串行 | download-qfull01.log/xml |
| ./packaging/windows/build-backend.ps1 -Python Q | 0；43模块与最终源码/嵌套代码/常量一致，约155秒 | download-build01.log |
| Q tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/download-frozen01 | 0；原全部恢复/另存/合并/Office/持锁/巡检保持；新增下载CLI持锁拒绝、媒体旧编号路径优先、重复引用字节只计一次、可选缺失计数和缺失ready媒体不完整、私有URL不输出及逐字节保持 | download-frozen01.log，.local/download-frozen01/result.json |
| Q tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root .local/download-resources01 --documents | 0；原导入/文档/布局/原件/作答/删除与重启保持，schema0016 | download-resources01.log |

串行P/Q全量与原冻结/资源探针继续独立记录；不把本地专项当作全量或最终head CI。实现自审核对三固定模式所有调用方、严格路径/空间/attempt类型、所有状态媒体引用保护与required合并、部分小计/预算、互斥分类/引用数/逻辑长度/未知历史、SQL私有列及无网络/内容调用、旧MD/Office分支和原冻结断言。当前仅自审，无独立批准，CI不计作独立审查；最终全量/CI及独立PR未确认前待交付。人工测试已取消，未合并/发行；剩余其他派生恢复与task.md其他项继续，任何统计不作清理建议。

补交检查：首次临时脚本生成命令因PowerShell引号解析失败，未写出download_validate.py，未执行验证；改为读取既有模板后定向生成独立辅助文件，Q -X utf8 artifacts/download_validate.py退出0。只九份明确文件，其余429份#12基线文件逐项保持；48文档相对链接无缺失、UTF-8/替换字符/尾空白与规范上传字节的git diff --no-index --check通过（正常非空差异退出1但无告警，辅助脚本0），逐项结果download-diffcheck.json。辅助脚本与所有原始日志/JUnit仅在artifacts，不进Git。

本地收尾：最终串行P/Q均636及77子测试通过，仅既有Starlette anyio别名弃用警告；两冻结探针均0。先记录新临时包SHA256和精确构建路径/文件数/逻辑长度（download-package-hash.json、download-generated-builds.json），以Resolve-Path核对隔离副本范围并确认无重解析点，再仅Remove-Item -LiteralPath -Recurse -Force移除本副本dist/study_backend与build/study_backend，退出0，原工作区唯一当前包/Office组件不动。按本轮保留恢复证据限制，.local/download-frozen01（含retained-current-attempt.bin/retained-media-authority.bin）与download-resources01作为小型隔离复现保留，结论另存download-frozen-result.json；没有删除或覆盖用户数据、恢复/失败现场，也不提出清理建议。

实现/相关本地自动化/自审完成，独立批准仍没有；下一步仅本切片独立PR与最终head全CI，不用父PR或本地通过代替它。现行API/架构/数据模型/task已写清范围与当前/后续状态，业务UI和依赖未变，本地不重复Flutter/Windows大包，最终head CI仍跑全部原流程。人工测试已取消，不接模型，不合并/发行；M2-05及task.md整体仍有未完成项。

实际交付：[草稿PR #13](https://github.com/surface-user/StudyWorkbench/pull/13)，分支codex/download-storage-report，base=#12的f141770fca6daa1ce57508e3349db3262576d921，实现e1c40532db979d31543eb7019027f6863779a1e0。创建前复核父PR未变化，九份文件按规范UTF-8/LF Base64上传并校验Git blob SHA，远端实现commit完整差异恰为九份，其余429基线文件保持；以expected_sha推进分支，未强推。task/原报告补实际链接，最终head、CI运行/检查时间和切片交付结论另在PR描述维护，不为记录自身SHA循环提交；未核实前待交付。只有自审，不将CI计作独立批准；原分支/未提交改动及所有用户数据/恢复证据保留，不合并/发行。其他派生恢复及task.md剩余项未因本切片销项。
