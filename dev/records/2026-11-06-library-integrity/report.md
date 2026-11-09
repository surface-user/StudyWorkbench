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
