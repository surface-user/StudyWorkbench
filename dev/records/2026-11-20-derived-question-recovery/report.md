# 未登记题目的恢复

## M2-05i2 只读核对

依据 [i1 契约](https://github.com/surface-user/StudyWorkbench/pull/86)，后端针对用户选定的一个目录逐项核对原件、题目正文、共享材料和附件。与原写入入口复用 MD 序列化规则。缺少或多出文件、出现同批歧义、来源变化或摘要不符时拒绝匹配，原件和目录保留。

以 Python 3.12 和 3.13 分别执行下列相关自动化，两次均为 48 项通过、两个既有弃用提示、退出 0。

```shell
python -m pytest -q backend/tests/test_markdown_questions.py backend/tests/test_legacy_asset_integrity.py backend/tests/test_pdf_chunks.py backend/tests/test_complex_question_splitting.py
```

Ruff、题目 Schema 检查、Windows 后端构建与冻结源码比对均退出 0，48 个业务模块一致。用自编含共享材料及图片的文档生成一次真实写入中断，再通过源码和冻结包各执行 10 项 HTTP 检查。两次启动均取得相同候选摘要，同长度改动原件会被拒，恢复夹具原字节后可再次匹配。原候选和图片保持原样，题目登记数保持为零。

首次冻结探针在启动被测程序前因测试脚本读取环境变量时大小写不匹配退出 1，修正后用新的独立测试库通过。完整运行日志按项目约定留在忽略的 artifacts 目录。此切片交付只读核对，后续 i3 实现用户确认和收据。审查暂缓、人工测试已取消。

## M2-05i3 显式确认与新位置恢复

依赖[只读预览 #89](https://github.com/surface-user/StudyWorkbench/pull/89)。预览展示本批将仅确认所选题目；用户显式同意后才重新核对候选摘要，以独占方式在新的题目目录写入及同步 MD 和附件。复用正常旧题确认的写入逻辑。完成收据与批次状态、题目、来源及 MD 资源登记同事务提交，使用现有批次 JSON 以兼容历史库。相同请求在重启或还原后返回同一目标；不同请求和已变候选被拒。受理写入失败时，事务回滚，已写文件保留，下次重新选择新的目标目录。

在 i2 的 pytest 命令上增加 `backend/tests/test_backup_store.py::test_offline_roundtrip_all_spaces_history_workfiles_snapshots_and_unknown_bytes`，两版 Python 各 50 项通过、两个既有弃用提示，退出 0。用中断产生的完整候选复验写入失败与重试、两次同时确认仅登记一题、变更请求/选题拒绝、普通确认兼容、原目录和失败目录完整保留，以及完整备份还原后的收据重放。Ruff、Schema、Windows 冻结构建均退出 0，48 个业务模块吻合。

真实 HTTP 使用带共享材料和图片的 DOCX，源码与冻结包分别通过 12 项检查：明确同意、候选变化拒绝、并发提交、独立新目录、重启后同收据重放及旧选题规则。最终各只有一条题目登记，原目录和新目录的正文及附件逐字节一致。验证仅用独立测试库。审查暂缓、人工取消，当前提交 CI 以本项草稿 PR 为准。
