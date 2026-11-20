# 用户自定义知识科目的后端

从已包含 0018 迁移的 [#106](https://github.com/surface-user/StudyWorkbench/pull/106) 追加 0019。用户可以创建、列出、改名或移除本空间的科目，查看每个稳定 ID 的完整修订。相同请求重试返回当时的回执；过期修订、活动名称冲突及跨空间访问均有回归。功能入口见 [API 规范](../../../docs/api-spec.md)。知识点树、资料和题目关联继续单独实施。

## 验证

- 两个受支持的 Python 版本运行科目、旧数据升级、备份、媒体、文档及学习记录的 16 个相关测试文件，各 290 项通过，退出 0。使用基线对应的两个锁定环境另跑 `python -m pytest backend/tests/test_knowledge_subjects.py backend/tests/test_learning_records.py -q`，各 8 项通过；两组计数有重叠。
- 旧版兼容和故障注入均覆盖 0018 的库、记录、备份及保留文件。并发同名创建和并发改名分别只有一个写入成功；同名新科目使用新 ID。备份与恢复分别拒绝互相冲突的活动名称，恢复原有配置保持。首次两版各有一项未来版本反例失败，原因是 0019 已成为有效版本。保留该反例，将输入更新为 0020 后原拒绝断言通过。
- 在仅包含源码的干净副本运行 `packaging/windows/build-backend.ps1`，51 个冻结模块核源通过。旧 Windows 后端通过正常接口创建 0018 库和作答。新后端读取同一库，升级至 0019，保留 0018 备份。通过真实 HTTP 完成创建、改名、移除、重试与查历史。通过新后端的 `--backup-to` 和 `--restore-backup` 进行整库往返，原库及恢复库重启后均保留三条修订及旧作答。全部退出 0。
- `python -m ruff check backend tools` 和 `python tools/export_question_schema.py --check` 退出 0。冻结程序仅用于此分支的功能验证，采用 #106 的依赖基线。最终发行仍需整合已修复的依赖与发行门禁。审查暂缓，人工测试已取消。
