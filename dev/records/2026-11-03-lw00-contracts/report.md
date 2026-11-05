# LW-00 普通学习流程契约设计

2026-11-03。用户要求阅读AGENTS、学习工作台路线和task并推进开发。当前队列第一项为LW-00，本批完成其本地技术设计，不把设计当功能实现。基线HEAD：29f23d3558740545a950a51ca04398f9420088fd，开始时工作区已有大量文档治理/R6改动，均保留。未读取个人库、未创建子Agent、未安装依赖、未提交/推送/合并/发行。

## 需求、设计与任务拆分

完整阅读AGENTS.md、requirements、architecture、question-content-spec、task、learning-workbench-roadmap；补读data-model、api-spec、security-privacy、agent-design、dev/README、相关ADR0008/0011及源码。依ponytail复用既有机制，先形成LW-00实施输入而非先建未定表。

1. 核对Note/WorkspaceNode/DocumentWorkfile、DocumentFiles读写恢复、note_revision、旧笔记编辑与R5关系、布局草稿、媒体模型、迁移备份和数据迁移锁。
2. 形成一门虚构课程PDF/课件/MD/TXT/视频的桌面设计走查；明确其非真实文件/窗口证据。
3. 确定新自由笔记复用MD、旧notes原ID/权威保留；位置协议、严格URI、marks关系及删除；拟议API/迁移分批；完整整库恢复、格式等级和逐批验证门槛。
4. 追加ADR0012并同步架构/模型/API/安全/Agent/需求/路线/任务及索引。LW-00保留设计待验，下一项LW-01，不销去任何旧任务或失败。

## 交付与自审

主文档：[普通学习流程契约](../../../docs/learning-workbench-contracts.md)；决策：[ADR0012](../../../docs/adr/0012-learning-notes-anchors-and-backup.md)。新增实体和API全部标为规划，无运行时修改或迁移。未将新名字放进当前已实现接口表。

自审纠正了初始设计的两点：新笔记固定创建ID注释避免与TXT同字节blob产生查看器后缀分流冲突；显示名在最终写事务内按既有规则编号，不引入需要所有导入/改名调用方配合的名称预留机制。另明确旧R5 note_id只能指旧notes、新文件笔记用节点ID；MD变化不自动重定向、派生PDF按产物hash校验、备份保留失败字节且不还原授权。

本批自审完成，非独立人工批准。业务测试/Flutter/Windows构建不适用：本批只修改设计文档，无业务代码/依赖/构建变更，不能靠旧测试数字证明拟议功能。真实样本、窗口与用户文档/阶段验收均未执行。LW-00保留待验，按既有延后人工授权可进入LW-01；不据此声称用户已经批准技术细节。

## 实际命令、结果与限制

cwd均为D:/computer_work/project/StudyWorkbench，PowerShell；检查脚本与结果位于artifacts/lw00-20261103/，由Git忽略。以下是本批实际操作，不沿用历史测试结果：

- `Get-Content`读取必读及相关文档，`git status --short`、`rg`检索源码/测试/ADR，成功读/检索批次退出0。
- 两个源码探测组合命令退出1：猜测的backend/tests/test_notes.py及backend/study_workbench/migrations.py不存在。后续已改读实际test_library.py、migrate.py、data_root.py，不影响设计结论；未创建替代文件或删除失败证据。
- `git rev-parse HEAD`退出0，返回上述基线。未查询远程PR/CI，PR #2/#3状态维持本批未知，不继承旧head绿灯。
- 一次task.md补丁因匹配文字错误（技术设计/技术方案）未应用；重新读取现行段落后补丁成功，无半应用改动。
- `.venv/Scripts/python.exe artifacts/lw00-20261103/check_docs.py`首轮及最终复测均退出0：12份文档UTF-8/结尾/尾随空白、最终139处本地链接及2处标题锚点通过；示例JSON可解析，关键契约和任务保护状态存在；JSON结果为artifacts/lw00-20261103/docs-check.json。脚本检查文档结构，不证明协议实现或样本学习流程通过。
- `git diff --check -- docs/README.md docs/data-model.md docs/api-spec.md docs/architecture.md docs/security-privacy.md docs/agent-design.md docs/requirements.md docs/task.md docs/learning-workbench-roadmap.md docs/learning-workbench-contracts.md docs/adr/0012-learning-notes-anchors-and-backup.md dev/records/2026-11-03-lw00-contracts/report.md`退出0；Git仅提示security-privacy.md后续可能LF转CRLF，无空白错误。未跟踪文件由Python检查覆盖。
- `rg -n`核对规划/待验/下一项与当前能力用语、`git check-ignore artifacts/lw00-20261103/check_docs.py artifacts/lw00-20261103/docs-check.json`组合退出0，两个产物均被忽略。检查后将relocate描述从“已验证”改成准确的“具有校验逻辑”，避免源码阅读冒充重测。

## 下一步与PR要求

LW-01按契约追加实际head迁移/创建幂等收据、MD原件/副本创建及资源/文档/媒体入口，运行隔离后端/Flutter及Windows验证，更新独立LW-01报告。提交/PR默认本地不要求，未授权推送/合并/发行；若后续明确要求PR，再记录具体head、审查与CI。LW-05启动退出协调、精确profile排除、LW-06组件及LW-07来源/组件仍待分项设计，不阻塞已明确的LW-01输入。


## 原设计自审依据归位（2026-11-04）

以下两段从现行契约移入本设计记录，原文保留2026-11-03设计批次语境，不代表后续LW-01未做测试；后续实施结果见LW-01报告。

已通过源码核对的复用依据：DocumentFiles当前只根据Resource.original_name分流且工作副本正文为权威；note_revision是标题/富内容摘要；WorkspaceNode同hash不等同身份；现有媒体能力独立、layout具备MD草稿；migrate已有升级前SQLite backup，relocate具有空目录/锁/文件hash校验逻辑，不等同产品备份。未执行这些模块的新一轮功能测试。

设计自审处理：避免自由笔记再建一套正文；明确旧R5 note_id不指向新文件节点；创建多阶段收据及同hash后缀冲突不能省略；MD行位置不用渲染像素；课件绑定派生hash；去掉URL内任意路径/能力；全库恢复保留墓碑/失败字节且不还原授权。自审不是独立审查或用户批准。
