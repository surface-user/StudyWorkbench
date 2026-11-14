# 开发记录与证据规则

本目录保存任务过程和交付记录；当前产品规范在[docs](../docs/README.md)，任务状态在[task](../docs/task.md)。

## 放置规则

| 要保存的内容 | 位置 |
|---|---|
| 当前需求、架构、协议、操作指南 | docs/；按职责更新原文件 |
| 同一任务的讨论输入、设计自审、实施/验证/PR跟进 | records/原任务目录；过程持续写原report.md，输入材料可附在同目录 |
| 被替代的方案、历史快照及旧共享证据 | archive/；默认不读，不因整理清除失败 |
| 完整原始日志/JUnit/自动截图 | 仓库artifacts/，Git忽略 |
| 本机依赖、测试profile和数据库 | 仓库.local/，Git忽略 |

不再新增平行的doc/目录。讨论被采纳后，把有效要求提炼到对应docs规范，原评估留在原任务目录，不再把全文复制为另一份当前方案。整理目录属于DOC-01后续工作，继续其原报告；不按对话轮次新建“整理/复查/最终”报告。

任务进度/下一项/测试计数由task和原报告维护；路线只负责范围与依赖，契约只负责行为与约束。报告中的“当前/下一步”属于当时批次，不能取代task；未完成验收的任务不因记录较旧就整目录归档。

## report.md 生成规则

- 单个小 Bug 修复：更新现有任务报告。
- 同一任务反复测试：追加到原报告，保留失败与后续复测，不再创建“final02”报告。
- 独立功能开发：创建独立任务目录及 report.md。
- 阶段性开发交付：创建批次目录及 report.md，引用已有任务报告，避免复制全文。
- 同一任务的PR审查继续追加该报告；既有 pr-review.md 保留为迁移前拆分记录，不作为新增惯例。

目录使用稳定名称，例如 records/2026-10-30-unified-resource-import/report.md。日期标识任务建立日，同日重测不另建目录。报告记录问题与范围、设计/任务拆分、实现、验证、审查、人工验收、PR交付、限制和下一步。每项验证写实际命令、工作目录、环境、退出码、覆盖范围和产物位置；没有运行就写未执行，不能沿用旧数字冒充本批结果。PR记录URL、head、对应CI结果及检查时间；未核验写未知。

## artifacts 与 evidence

按用户2026-11-06要求限制留存：通过测试的临时目录自动清理；仅保留一份当前冻结包和一份可用Office组件。保留失败日志/JUnit/最小复现/转储及源码版本，不用“保留失败”永久保留所有重复二进制和通过测试的数据库副本。人工测试已取消，不再制作窗口验收包。

| 位置 | 用途 | Git规则 |
|---|---|---|
| ../artifacts/<运行批次>/ | 完整原始日志、JUnit、自动截图和临时诊断输出 | 已忽略；本机或CI运行产物，不保证随仓库获取 |
| records/<任务>/evidence/ | 为报告结论专门筛选、脱敏、解释过的必要证据 | 可评审后显式提交；禁止递归塞入整个artifacts目录 |
| ../.local/ | 依赖环境、测试profile、数据库和本机临时现场 | 已忽略；不作为可共享证据的唯一来源 |
| archive/evidence/ | 迁移前已纳入Git的47份共享证据 | 原样保留原有选择，不表示本轮重新审核或新一轮验证 |

证据晋升必须逐项确认：支持哪个结论、为何需长期共享、是否含令牌/个人路径/原件/学习数据、来源运行及版本。复制一份日志并改名不等于证据筛选。未来运行先写artifacts；evidence仅收必要片段、截图或摘要并保留来源。既有失败产物不得因本次整理删除。

## 任务记录索引

目录日期是任务建立日，不是每次运行日期；继续任务时按下表定位原报告，不另建同任务目录。当前进度仍以task为准。

| 任务 | 原报告 | 同任务附属材料 |
|---|---|---|
| API-01a 兼容错误响应 | [report](records/2026-11-12-api-errors/report.md) | detail兼容、校验脱敏、服务端关联ID、桌面及冻结HTTP回归 |
| M2-05 资料完整性与保存恢复点 | [report](records/2026-11-06-library-integrity/report.md) | 离线只读诊断、恢复点浏览及恢复故障回归，同任务持续记录 |
| M0-02 / M1-04 发行文件完整性 | [report](records/2026-11-10-release-integrity/report.md) | staging完整文件集合/hash校验及构建前门禁，不等于完整发行验收 |
| DOC-01 文档治理 | [report](records/2026-10-30-documentation/report.md) | 含本次目录归位与检查 |
| 资料树删除 | [report](records/2026-10-30-resource-removal/report.md) | — |
| 统一资源导入 | [report](records/2026-10-30-unified-resource-import/report.md) | [迁移前独立PR跟进](records/2026-10-30-unified-resource-import/pr-review.md)，保留原拆分，后续写report |
| R6 本地授权切片 | [report](records/2026-11-03-r6-agent-access/report.md) | evidence/仅存已筛选证据 |
| R6-01 通用资料受控读取 | [report](records/2026-11-14-resource-read/report.md) | 本地授权契约、后续API/UI和无模型回归，同任务持续记录 |
| PLAN-02 学习工作台方向 | [report](records/2026-11-03-learning-workbench-direction/report.md) | [原始差异评估](records/2026-11-03-learning-workbench-direction/gap-review.md)，讨论来源 |
| LW-00 学习流程设计 | [report](records/2026-11-03-lw00-contracts/report.md) | 含设计自审，现行契约在docs |
| LW-01 自由笔记 | [report](records/2026-11-03-lw01-notes/report.md) | 同任务重试/失败与末轮结果均在原报告 |
| LW-02 位置书签与备注 | [report](records/2026-11-04-lw02-marks/report.md) | 含0014迁移、来源关系、失败与最终回归 |
| LW-03 内部超链接 | [report](records/2026-11-04-lw03-links/report.md) | 含URI/空间校验、插入跟随、往返与验证 |
| LW-04 集中查找 | [report](records/2026-11-04-lw04-search/report.md) | 含预算、截断、结果版本与回归 |
| LW-05 完整备份恢复 | [report](records/2026-11-04-lw05-backup/report.md) | 离线快照/受控恢复/UI本地实现，窗口/人工/发行待验 |
| LW-09 学习流程集成 | [report](records/2026-11-04-lw09-integration/report.md) | 冻结后端真实进程闭环；人工窗口测试已按用户要求取消 |
| 11-06 学习工作台阶段交付 | [report](records/2026-11-06-learning-workbench-delivery/report.md) | 当前版本PR、依赖与CI跟进；不代替人工验收 |
| LW-08 授权与外部候选审核 | [report](records/2026-11-05-lw08-authorization-review/report.md) | 无模型授权扩展、持久候选/人工采用；自动化及窗口状态见报告 |
| LW-07 直接媒体下载（进行中） | [report](records/2026-11-05-lw07-downloads/report.md) | HTTPS传输/持久队列/普通UI切片，完整回归与真实来源待验证 |
| LW-06 格式扩展（进行中） | [report](records/2026-11-04-lw06-formats/report.md) | UTF-8文本/XLSX及Office自动化矩阵；人工窗口测试已取消 |

[历史索引](archive/README.md)默认不参与日常开发上下文。任务满足[退出条件](../docs/task.md#任务退出条件)后仍保留完成摘要和报告链接。
