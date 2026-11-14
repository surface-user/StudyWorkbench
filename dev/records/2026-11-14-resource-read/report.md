# R6-01 通用资料受控读取

## 来源与范围

本任务承接task中READY的R6-01，先交付R6-01a设计，不接模型、凭据或远端服务。基于已验收#55 6d1078f8eca2923bb0d77a76136f0b8f5e921738/tree49028e80314a23c9b7fc3ecfcfc4ca6084636691，将498个blob逐一复制校验到独立resource-read-contract副本，保留旧根checkout/用户原件。#55当前CI43583174480成功是父项证据，不冒充本设计重跑。

按AGENTS及requirements/architecture/question-content-spec/task、agent-design/API/学习契约/数据模型核范围，读取实际agent_access、markdown_notes、learning_marks、learning_search、db.Note及library.NoteEdit。现有analyze_attempts只读指定作答；自由MD是资源节点，旧notes是富内容JSON，标记/关系另有稳定身份/版本。假设database.py/notes.py/annotations.py/main.py的只读搜索返回不存在后，已改按实际文件清单核对。首次文档patch因旧段落上下文不完全一致失败，无产品变更；改用完整标题/旧语句唯一锚点更新，保留错误事实。

## R6-01a设计与后续

唯一现行契约归docs/agent-design.md“规划中，R6-01”章节，不把本报告再作平行规范。read_resources与analyze_attempts用途隔离、共享进程配额/期限/撤销；resource_node/legacy_note/learning_mark封闭选择默认元数据，正文单独明确已保存版本，原件/工作副本/旧富内容不混权威。首批纯文本/Markdown/旧笔记/标记，其余格式元数据及后续provider条件单列；关联/内部URI/附件不扩权。

预算沿旧授权64KiB单正文/1MiB规范上下文及既有TEXT_LIMIT/富内容深度16，累计文件I/O16*TEXT_LIMIT含核验重读；全量失败不静默截断。服务端版本/指纹与空间/状态读前后重验，不回读任意路径/URL或执行外部处理，不缓存进库/备份或远端传输。撤销不删持久候选；临时grant不恢复。当前旧API/模型/备份格式均未改变。

后续API/封闭提供器、普通UI确认/撤销、源码/冻结/整库无模型回归分别拆小PR；未支持格式另列依赖，不把有限文本读取当全格式或R6整体通过。父任务保持IN_PROGRESS，未选模型/语义场景不纳入本项。

## 验证与交付

本切片仅四文档：agent-design、task、dev索引和本报告。没有产品/测试/依赖/迁移/API修改，不以镜像实现的测试替代文档核对。提交前核全部498基线/仅四文档、两锁/其他原blob、Markdown引用/锚点、任务ID/依赖和Git空白，再执行Schema漂移检查；实际结果及独立PR/current-head CI另记，未执行前不写通过。

R6-01a REVIEW，当前独立草稿PR与head CI待交付；代码审查暂缓、人工取消、未合并/发行。无模型/远端工具或全格式支持结论；后续本任务实现/重复测试/PR跟进继续本报告。


### R6-01a 实际文档检查

2026-11-14，工作目录为独立resource-read-contract：共享Python执行tools/export_question_schema.py --check，退出0，现行题目Schema无漂移。根执行artifacts/goal-20261112/check_resource_read_contract.py，退出0：499文件/仅四文档变更、495原blob保持，115本地引用/4锚点/61唯一调度行通过，Git空白、旧两锁/当前API/架构/数据模型保持。最初任务链接标题少“受控”二字，在提交前改为精确当前标题锚点后核通过；无业务或测试断言修改。

任务表同步已独立有限验收的#54/#55、#52 v2公网失败BLOCKED及#56待CI的REVIEW，不把其他PR工具合并到本分支；M3-03d从通用READY分组拆出但保留其单独条目，避免与现行状态矛盾。R6父项仍IN_PROGRESS，a转REVIEW，b/c/d/e按各自前置保留BLOCKED，不记实现完成或人工通过。

本切片没有运行新的本地产品/模型/窗口测试，具体原因是仅定义规划契约、产品源和全部测试保持父#55原blob；本head完整CI仍必须运行。独立草稿PR/current head CI待提交核验，不以父项绿灯代替。
