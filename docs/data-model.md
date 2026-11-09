# 数据模型与权威关系

状态基线：2026-11-05本地ORM与迁移。源码为[db.py](../backend/study_workbench/db.py)，迁移目录为[versions](../backend/migrations/versions/)。本文件分开当前已实现、规划中和待验证；不把未来表名当成现有实体。

## 当前已实现

当前迁移链为0001→0016，末版0016_analysis_review。此处描述代码schema，不表示任何个人库已经升级；开发仅使用隔离样本验证，不打开个人数据库。

| 实体 | 职责及约束 |
|---|---|
| workspaces / desktop_state | 工作空间归档、活动选择及版本化layout JSON；不是系统目录 |
| resources | 不可变原件/附件，原名/相对路径/MIME/大小/hash；同空间hash唯一 |
| import_jobs | 原件、解析版本、预览、确认/失败/中断状态；不承担目录身份 |
| workspace_nodes | 稳定逻辑ID、空间/父级、规范名、folder/resource/media/link互斥载荷；同空间复合FK；removed_at为空才参与同层名称唯一性 |
| resource_add_jobs | 来源本地路径、目标父级、状态/取消、逐项结果和复制收据；路径留本机库，不写Git |
| media_entries | 媒体路径/hash/MIME、入库状态和播放位置/倍速/字幕；经节点适配 |
| media_download_jobs | 同空间request_id幂等、受控HTTPS来源/文件名/父目录、queued/running/paused/interrupted/failed/ready状态、attempt独占路径、进度/强ETag/前缀hash及结果；source_url含query只存个人库，不由列表返回。父目录复合FK；重启中断不自动联网，重新开始保留旧attempt文件；完成字节直接作为不可变媒体原件，无正文镜像 |
| document_workfiles / document_saves | 显式MD工作副本、索引hash；old/new hash及prepared/committed/interrupted/conflict保存收据 |
| markdown_note_creations | 自由MD笔记创建收据；id同时为预分配节点ID，resource_id独立；workspace_id/request_id唯一、规范请求JSON、prepared/ready/interrupted/conflict及错误；初始MD/hash及受管相对路径由ID/规范名称确定性派生，不存正文镜像 |
| document_previews | 同空间节点/原件、源hash、运行时/选项指纹、状态、派生PDF路径/hash/大小/页数与错误 |
| questions | (id,workspace_id)题目缓存；旧QuestionDocument与确认后FileQuestion双读，写入继续经服务校验 |
| markdown_questions | 旧逐题提取MD独立索引，任务+ordinal唯一；不是已经确认可判分的QuestionFile |
| notes / passages | 富内容JSON和来源；笔记保留expected_revision冲突检查，不伪装成MD文件 |
| question_files | (workspace_id,question_id)映射，空间内node_id唯一，来源及当前确认ID |
| question_versions | 不可变revision、MD/编译hash、快照路径、标题/题目/材料JSON、附件及时间；触发器拒绝更新/删除和跨空间绑定 |
| attempts | 追加原作答/分数、revision/request_id及可空question_version_id；旧版本未知保持null，触发器禁止改绑历史确认版 |
| attempt_reviews | 追加人工评分/说明，不覆盖原作答 |
| learning_events | attempt_id、request_id、content JSON、时间；(attempt_id,request_id)唯一，触发器禁止更新/删除 |
| learning_marks | workspace/稳定资源节点、v1 anchor、标题/备注、严格递增revision、request_id/规范creation_content及时间/墓碑；空间内请求唯一，同空间节点复合FK，禁止物理删除 |
| learning_mark_revisions | (mark_id,revision)旧标记/关系JSON快照及时间；与当前改写同事务追加，触发器禁止更新/删除，保留旧anchor不冒充当前有效位置 |
| learning_mark_notes | mark及file_node_id/legacy_note_id互斥载荷、kind；空间复合FK、关系唯一；notes增加(workspace_id,id)唯一索引支持旧笔记关联，不改旧notes/R5事件 |
| analysis_review_drafts | 同空间创建幂等、外部候选/未验证来源、上下文hash及作答/确认版引用；pending/adopting/adopted/rejected/failed、严格修订与payload hash、采用参数/笔记结果和失败；不存grant或正文上下文镜像 |
| analysis_review_revisions | (draft_id,revision)旧候选/审核状态快照；改写同事务追加，触发器拒绝更新/删除；重启中断采用追加历史后标失败，不自动重放文件写入 |
| study_tasks | 题目ID集合、标题及时间，进度由作答推导 |

### 身份与权威

- workspace_id是隔离边界；resource_item_id是树节点ID，区别resource_id原件blob。
- tab_id是页实例/profile身份，资源页按空间+resource_item_id+view_kind去重；同名或同hash不合并逻辑节点。
- 内部URI只编码空间、nodes/marks/notes类型及稳定ID，无新表；运行时往返视图和定位请求不进入layout JSON或正文镜像。链接不传递Agent授权。
- 当前Markdown/工作副本是编辑权威，question_versions快照是判分权威，questions.content是当前确认内容的缓存。
- 旧JSON和提取MD的ID保留，显式转换建立文件映射；冲突拒绝，不能按标题合并或迁移补造旧快照。
- 只有新版本确认才更新题目缓存；新旧request_id、答案和版本的幂等语义不因后续编辑改变。

### 当前事件投影

learning_events.content存kind=annotation/reviewed、note及可选error_type/self_rating/note_id/knowledge_points。省略/null知识点不修订，[]明确清除；最多100项独立非空知识点，每项500字符。最后明确声明形成latest-explicit-annotation-v1；遍历完整事件流，不受当前分页影响。当时knowledge_points独立保留，旧无版本不拿当前题目补造。

每条作答最多显式关联100份同空间笔记；缺失关系保留，读取再次检查空间/作答/事件关系。reviewed_count按复习事件数重建；掌握/到期用attempt-review-streak-v1，依实际Attempt/最新Review，复习点击、自评和记录标签不加正确连击或改旧分数。三次实际满分连击才掌握，待批改保持独立。

### 文件与恢复

已实现离线只读巡检，复用现有原件/工作副本/保存及创建收据/预览/确认版路径，不新增表或持久报告。孤立派生目录只列候选，不自动修复或删除；完整范围及预算见API，不能据此将后续自动恢复标为已实现。

恢复副本容量报告复用document_workfiles、document_saves与节点/题目归属，按所有空间working/question-files的当前文件、before、pending及未登记文件统计逻辑长度，不新增表或持久报告。committed pending正常缺失单独计数，其他缺失/不安全引用标不完整；不核正文/hash，不能证明库健康。按相对路径计长，hardlink不同路径可重复计数，不代表实际磁盘分配/可回收空间。任何分类均不授权删除；Office/下载失败字节及其他派生恢复仍不在此切片范围。

原件、可编辑工作文件、派生预览、确认快照分别定位。保存收据按old/new hash恢复索引，不自动回放覆盖外部内容；确认版发布前后回读正文和附件。失败/孤立字节保留，文件与SQLite非同一事务。

保存恢复点浏览复用document_saves的before/pending路径及old/new hash，不新增表、正文镜像或恢复状态。只读预览不改收据；UI确认后复用layout的draft/draft_base_sha256，后续普通保存追加新收据，旧恢复点不清除。已确认版本和旧作答不随恢复草稿改变。

三方合并只读预览API复用同节点原件或document_saves的before/pending核验基线，不接受外部自报基线正文；仅返回候选与base/local/current hash，不持久化正文或改变上述权威。桌面明确确认且版本/原草稿未变化后，复用tab.draft/draft_base_sha256及正常layout持久化；空文本仍有非空base标识。再次普通保存才追加新DocumentSave，确认版/历史不变。对话框候选与基线选择仅存运行时，不新增表/迁移/恢复状态。

0012仅标记树的removed_at，保留父子/原件/工作文件/题目和历史外键；旧节点初始NULL，旧资源适配识别墓碑，刷新不生成替代身份。当前题目/来源入口过滤已移除节点，历史快照保留；已开标签仍按ID访问保留工作文件。

layout v1/v2双读写；旧utility/未知类型保留；16开/10关；MD草稿1MiB、旧题目草稿16000字符、独立question_draft64000字符；状态不存令牌/能力URL。具体视图字段见[API](api-spec.md)。

## 规划中

LW-00已形成[普通学习流程契约](learning-workbench-contracts.md)，上述LW-01/02实体均已落地。内部URI解析复用上述身份、不新增实体；集中检索按请求读取这些实体和当前MD，不建正文镜像；LW-05已实现离线整库快照/新空目录恢复；文件与表行摘要验证后激活，不新增学习正文表。现有notes及R5事件note_id不改，后续迁移从实施时实际head追加。完整备份覆盖这些实体、旧关系、墓碑和失败字节；不会恢复进程授权。详见[ADR0012](adr/0012-learning-notes-anchors-and-backup.md)。

- 完整学习数据库及事件/笔记关系的备份恢复；现有资源导出v1/v2不能替代它。
- R6凭据及其他候选实体未实施；外部分析候选/修订已落表。临时授权仍仅进程内存（重启失效），不存数据库；API见api-spec.md。
- 外部目录监听/原地修改、独立长期阅读位置库、通用投影持久化尚未实现；是否落表待具体需求设计。
- 失败副本容量治理已实现上述Markdown只读统计；其他失败字节范围、保留策略和全部派生孤立目录恢复仍需设计实施，删除学习数据/恢复点未获授权。三方合并已覆盖有可核验基线的MD预览/确认载入与原保存，不提供自动修复或任意版本猜测。

## 待验证

旧版升级、DDL故障回滚、旧行/hash保持已有隔离自动化；个人库、真实安装升级/回滚及干净机仍待验。回滚依靠保留备份和旧文件，不承诺破坏性downgrade。文件保存与外部进程仍有最后hash检查到replace间竞争窗口，无OS级排他编辑锁。

迁移规则：每次从实际head追加，不改旧迁移；备份SQLite（含WAL一致性）、受影响文件和收据；integrity_check/foreign_key_check、逐列旧值与原件hash回归；禁止通过删旧记录/失败用例解决兼容问题。详见[任务](task.md)、[ADR](adr/)。
