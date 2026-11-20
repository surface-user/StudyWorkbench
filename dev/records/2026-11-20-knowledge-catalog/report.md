# 知识点目录契约

[目录契约](../../../docs/knowledge-catalog.md) 确定用户自定义科目与知识点、树形分类、跨知识点关联、同空间资料和题目引用，以及改名、移动、移除、旧数据升级和备份恢复的行为。后端实体、迁移和接口属于后续实现。

核对现有题目协议、统计聚合、学习事件投影和备份恢复的实际入口。当前题库标签、作答时快照与最后一次显式标签修订分别有自己的来源；空修订和未知历史版本均有既有回归。目录规范保留这些语义。

`python -m pytest backend/tests/test_learning_records.py backend/tests/test_learning.py backend/tests/test_backup_archive.py backend/tests/test_backup_store.py -q` 通过 81 项，退出 0。上述结果覆盖现有兼容行为。新目录的并发修改、跨空间拒绝、环检测、历史修订及全库往返需要在实现后通过契约所列的验收用例。
