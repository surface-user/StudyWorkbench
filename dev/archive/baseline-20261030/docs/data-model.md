# 数据模型：现状、目标及兼容策略

2026-10-26后续：head为0009，追加document_previews（同空间节点/源Resource复合FK、源hash、运行时/选项hash、状态、派生路径/hash/大小/页数、取消/错误、创建时间）。不修改0001–0008；旧Resource/题目/作答/工作副本和布局不改。0008升级、故障回滚、备份和所有旧表行逐项保持已回归。重启仅将未完成预览标中断，失败文件和原件保留，不作自动清理。下方0008首批记录保留为历史；当前设计见[ADR0009](adr/0009-offline-office-previews.md)。

2026-10-26增量：当前head已为0008，仅新增document_workfiles（同空间节点→受管Markdown工作副本、索引hash）与document_saves（old/new hash、旧版本/待写路径、prepared/committed/interrupted/conflict收据）。R2布局v2已实现，旧v1/未知标签保留；R3首批查看/编辑在验证中。下文“head0007/后续拟议”为2026-10-25记录，当前状态见[续开发](resource-continuation-2026-10-26.md)、[ADR0008](adr/0008-resource-tabs-and-document-workfiles.md)。没有更改旧题目/作答表或自动生成历史快照。

2026-10-25资源中心方向经用户确认，本轮仅实施R1。**当前Alembic head为0007；只在隔离数据上验证迁移，未读取或操作个人学习库。** workspace_nodes/resource_add_jobs已落表；R2–R6拟议表名仍只表达职责，后续实现前逐阶段审查具体约束。

## 当前实际模型

以`backend/study_workbench/db.py`和0001–0007迁移为准。服务层有workspace校验，不表示所有旧跨表关系都已用复合外键保证。

| 已有实体 | 实际职责及约束 | 新方向下的结论 |
|---|---|---|
| workspaces / desktop_state | 空间归档、layout JSON、当前空间 | 继续复用；不是磁盘文件夹模型 |
| resources | 原名称、相对路径、MIME、大小、SHA256；空间内hash唯一 | 当前偏不可变原件/附件存储，不能直接当可编辑文件目录 |
| import_jobs | 原件、解析版本、状态、预览、失败、时间 | 复用预览/确认及幂等；不是资源目录树 |
| questions | `(id, workspace_id)`复合主键，content JSON为QuestionDocument | 现在是练习内容来源；目标改为已确认MD的编译缓存，旧读路径保留 |
| markdown_questions | 独立ID、空间、原件/MD资源、任务/ordinal、标题、块内容；任务+ordinal唯一 | 已落盘逐题MD，但未与questions或attempts建立映射 |
| attempts | 自增ID、空间/题目复合FK、response/status/score/time、revision/request_id | 每次追加、空间内非空request_id唯一；只有版本号，没有不可变题目正文/答案快照 |
| attempt_reviews | attempt_id、score、feedback、time | 追加评分修订，保留原答卷；继续复用 |
| study_tasks | 空间/标题/题目ID JSON列表/创建时间 | 继续复用；列表中的题目引用需在新身份层校验 |
| notes / passages | 富内容JSON及原件关系；笔记有编辑版本摘要 | 当前并非Markdown文件编辑，须显式导出/关联而非假装已文件化 |
| media_entries | 自己的路径/hash/MIME/状态和playback JSON | 复用媒体与播放状态；目前不在Resource统一目录中，先适配后再考虑合并 |
| workspace_nodes | 稳定ID、空间/父级、name/name_key、folder/resource/media/link及互斥定位 | 空间内复合FK；NFC/casefold兄弟名称唯一；移动/改名保持ID |
| resource_add_jobs | 空间、目标父级、来源路径、状态、取消标记、逐项结果与复制路径收据 | 后台逐文件提交；取消/中断/失败保留结果和字节，重启不自动重读外部来源 |

当前掌握/到期主要由`learning.study_rows`从SQLite作答/评分记录计算，并无独立掌握表或错误类型/用户自评表。当前MD元数据未写入它在SQLite中的题目ID；把MD带离数据库后无法只靠现有文件恢复稳定题目身份。现有MD没有解析回QuestionDocument或外部修改再索引流程；哈希不符会409。

## 必须区分的身份与权威数据

| 概念 | 建议身份 | 内容权威/用途 |
|---|---|---|
| 工作空间 | workspace_id | 资源与学习记录的隔离边界 |
| 树节点/学习资源 | resource_item_id（R1逻辑ID） | 改名/移动保持；目前定位原件、媒体或链接，工作文件留后续 |
| 原件/快照blob | 既有Resource.id + SHA256 | 不可变字节校验/去重；不是文件身份 |
| 文件夹 | 稳定节点ID | 父子关系；不能用标题当主键 |
| 题目 | 文件内question_id，查询时含workspace_id | 跨文件/历史关联；不能用题干hash或路径代替 |
| 题目确认版本 | question_id + revision + content_hash | 不可变快照及判分依据 |
| 编辑器标签 | tab_id + resource_item_id + view_kind | 会话/视图状态；多次打开同资源优先复用 |
| 作答 | attempt_id | 每次追加，关联题目和当时确认版本 |

Markdown保存当前内容和相对稳定元数据；SQLite是目录/检索/已确认版本缓存及学习记录所在。缓存标明来源hash，未确认文件变更只使缓存过期，不在加载时悄悄覆盖已确认答案。原件、可编辑副本、派生预览必须分别定位。不得将可编辑工作文件原地写进现有不可变Resource后再修改hash以掩盖覆盖。

新逻辑资源字段统一为`resource_item_id`，区别既有资源读取API里的`resource_id`（原件blob ID）；旧`/resources`语义不改，不混用两类ID。

## 按阶段提出的最小增量

### R1：目录/资源适配

已实现`workspace_nodes`：稳定ID、workspace_id、parent_id可空、kind、name/name_key，以及resource_id/media_id/url互斥载荷。文件夹无载荷；原件/媒体父子与定位使用同空间复合FK，服务事务验证文件夹父级及无环。NFC+casefold规范化，Windows保留名称/路径字符/尾空格点拒绝；添加重名自动编号，改名/移动重名409。根级coalesce(parent_id,'')唯一索引。工作文件路径留R3，未提前建列。具体约束见[R1设计](r1-design.md)。

旧Resource与MediaEntry只添加目录适配引用，保留所有旧ID、路径和哈希，不立即搬文件或把媒体全复制成Resource。目录中的两个逻辑文件可复用同一原件blob；现有hash去重不能合并两个不同逻辑文件的身份。

树为逻辑组织；文件夹导入保留相对层级，工作文件可在受管目录下落盘。直接挂载外部目录/符号链接跟随/监听属于后续设计，不默认授予任意文件权限。

### R2：标签布局v2

保留v1 tabs/closed_tabs/active_tab_id与限制。新增资源ID/查看器类型和版本化页面状态，严格限定支持字段；支持v1读取/legacy utility恢复，不猜测旧总览中哪个具体文件曾被打开。恢复缺失资源显示可处理的占位页，不删标签或草稿。业务令牌与媒体能力URL不进入layout。

### R3/R4：工作文件、派生预览及题目映射

- 工作文件记录当前相对路径、hash与期望保存版本；正文不成为SQLite唯一副本。新保存通过原子替换及操作日志/恢复对账，不把文件写入称为SQLite事务的一部分。
- 派生预览记录源ID/hash、转换器/版本、选项hash、产物资源/路径及状态。首批复用现有任务机制，不另建通用任务平台。
- 拟议`question_files`：`(workspace_id, question_id)`到资源节点及MD文件、格式版本、当前确认revision/hash、解析状态的映射。复用questions复合身份和已有QuestionDocument，不再创建第三套判分题库。
- 已有MarkdownQuestion.id优先保留为其未来question_id；已有Question.id也保留。两者不能凭同名/相似题干自动合并；出现同ID或导入复制冲突时，提示链接现有题或显式生成新ID，不能最后写入者覆盖。
- 新MD文件自带ID和格式标识。旧v1末尾来源JSON没有ID，先legacy读取；补写ID/格式升级必须预览、备份并明确确认，不能在打开文件时改写旧MD，更不能改原始Word/PDF。
- 已有notes仍可读；转为笔记MD走显式导出和关系映射，旧行/附件保留。

### R4/R5：版本快照、学习记录

拟议`question_versions`在用户确认题目时保存不可变正文/附件引用或不可变MD快照、hash、确认时间、解析/评分协议版本和当时知识点。questions.content仅缓存当前确认版本，旧快照不能更新。

新attempt需关联该确认版本并校验空间/题目归属，旧attempt的主键、题目ID、答案、分数、时间、revision及request_id原样保留。新增字段先允许旧记录null，双读期间不强制伪造关联；历史没有足够证据时显示版本未知，不用迁移当天的当前题目冒充历史快照。

错误类型/自评/知识点修订/复习覆盖建议作为追加注记或事件（拟议`attempt_annotations`/学习事件职责，精确结构留R5评审）；评分更正继续AttemptReview。掌握/到期基于事件和明确算法版本生成，必要时持久化投影但能重建，不能仅保存最后结果。原题文件不承载每次错误记录。

## 迁移评审清单

1. R1从0006追加0007，不改旧0001–0006迁移。未来每阶段从实际head创建增量revision，不提前预占编号。
2. 先对隔离旧库副本盘点：0001→0006升级、现有0006、有/无布局、归档空间、questions/MD ID冲突、无标准答案、旧revision为空等。执行前备份SQLite和受影响文件，保留收据/哈希。
3. 原有作答/评分ID、内容、状态和行数不变；映射在同空间有效，foreign_key_check/integrity_check通过。不能用删除旧表/失败用例或弱化断言迁就迁移。
4. 首批只追加索引/映射，不搬原件；文件写入/重命名与数据库提交之间故障要能恢复，对账不自动删除孤立原件或未登记派生文件。
5. 旧服务读路径与v1标签保留兼容期。旧版程序未必能读新库，“可回滚”依靠保留备份/文件和明确版本检查，不承诺破坏性downgrade。
6. 新记录提交、原题改名/移动、外部修改、丢失、重复ID、评分修订、重启恢复、记录反向打开与导出重导都要有针对性回归，再讨论退役旧缓存/入口。

[架构方案](architecture.md) / [审查证据](resource-first-architecture-review.md) / [任务](task.md)。旧数据模型全文见[历史快照](archive/resource-direction-baseline-2026-10-25.md)。

## R4实际增量（0010）

此前R4/R5拟议中的R4部分已落地：question_files以(workspace_id,question_id)为主键、空间内node_id唯一，保存来源映射与可空当前确认ID；question_versions保存不可变revision、MD/编译内容hash、快照路径、标题/题目/材料JSON、附件清单及时间。触发器拒绝更新/删除版本、跨空间/题目确认绑定。attempts只追加可空question_version_id及索引，触发器检查归属并禁止改绑；旧行新列为null，版本未知，未补造历史。0001–0009不修改，0010失败恢复备份与旧行保留已自动验证；downgrade明确拒绝破坏性删除。文件写入与SQLite非同一事务，孤立快照/receipt保留供对账，不自动重放。追加注记、学习事件与完整反向打开仍为R5。详见[R4记录](r4-validation-2026-10-26.md)。

## 0011学习事件（2026-10-29）

learning_events(id、attempt_id FK、request_id、content JSON、created_at)，唯一(attempt_id,request_id)、(attempt_id,id)索引。事件继承所属attempt空间，受控接口检查归属；数据库触发器禁止更新/删除。只追加表，不改旧作答或确认版本。知识点历史读取作答绑定的QuestionVersion，旧空版本保持未知。笔记绑定、知识点修订与投影规则仍待R5接续，见[R5首批](r5-records-2026-10-29.md)。

## 0012资源树删除（2026-10-30）

`workspace_nodes.removed_at`为可空UTC时间字符串，旧行初始NULL。`ux_nodes_sibling_name`只约束removed_at为NULL的节点；原ID、父子/资源/工作副本/题目及学习记录外键保留。DELETE仅标记子树，不删除文件和业务行；旧资源适配仍识别移除节点，防止重新生成身份。详见[资料删除设计与验证](resource-removal-2026-10-30.md)。

## R5事件投影完成（2026-10-29）

复用0011 learning_events.content保存可选note_id及knowledge_points，不另建重复关系表，不改旧事件/迁移。关联笔记按稳定ID读取当前内容，缺失关系保留；最后明确知识点修订投影为记录当前标签，当时快照值仍独立保留。reviewed_count按事件重算，掌握/到期由实际作答与人工评分重算，算法版本和界面语义分开。细则见[ADR0011](adr/0011-learning-record-projections.md)及[R5完成记录](r5-completion-2026-10-29.md)，完整学习数据库备份恢复仍非当前资源导出的能力。
