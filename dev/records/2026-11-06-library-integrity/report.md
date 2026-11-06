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
