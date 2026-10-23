# 数据实体与关系

M0 实际迁移：`questions(id, content JSON)` 与 `attempts(id, question_id FK, response JSON, status, score nullable, created_at)`；一题多次追加作答。数据库开启外键。示例题为明确标注的人工演示题。

后续设计实体（尚无对应表）：

| 实体 | 关系及约束 |
|---|---|
| workspace | 独立命名空间；所有所属数据必须带 workspace_id，服务端检查归属 |
| resource / attachment | 工作空间、相对路径、SHA256、MIME、字节数、来源；不接受任意文件路径 |
| import_job / extraction | 原 resource、解析器版本、状态、错误、预览、去重指纹；确认后提交 |
| passage / question | 共享文章，多题引用；question protocol_version/content/source/verification |
| question_relation | parent/variant、生成模型和草稿/人工验证/拒绝状态 |
| attempt / grading | 独立作答；题目版本快照、提交时间、客观得分或待批改；人工评分保留历史 |
| knowledge_point / question_knowledge | 科目树、多对多关联；不从一次错误推断永远薄弱 |
| mastery / review / task | 作答证据、掌握稳定性、到期时间、每日计划；允许用户覆盖建议 |
| note | 资料/题目/知识点关联，AI 草稿必须确认后保存 |
| download / media / playback | 下载状态机、源、格式、目标、续传元数据；视频资源、字幕、进度 |
| settings / migration_journal | 配置分层与路径迁移事务日志；API 密钥不存普通 SQLite |

M1 工作空间设计需先加入迁移和隔离测试；M3 前冻结题目快照与答案修订机制，避免修改答案改变历史成绩。
