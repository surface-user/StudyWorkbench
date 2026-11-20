# 未登记题目的恢复

## M2-05i2 只读核对

依据 [i1 契约](https://github.com/surface-user/StudyWorkbench/pull/86)，后端针对用户选定的一个目录逐项核对原件、题目正文、共享材料和附件。与原写入入口复用 MD 序列化规则。缺少或多出文件、出现同批歧义、来源变化或摘要不符时拒绝匹配，原件和目录保留。

以 Python 3.12 和 3.13 分别执行下列相关自动化，两次均为 48 项通过、两个既有弃用提示、退出 0。

```shell
python -m pytest -q backend/tests/test_markdown_questions.py backend/tests/test_legacy_asset_integrity.py backend/tests/test_pdf_chunks.py backend/tests/test_complex_question_splitting.py
```

Ruff、题目 Schema 检查、Windows 后端构建与冻结源码比对均退出 0，48 个业务模块一致。用自编含共享材料及图片的文档生成一次真实写入中断，再通过源码和冻结包各执行 10 项 HTTP 检查。两次启动均取得相同候选摘要，同长度改动原件会被拒，恢复夹具原字节后可再次匹配。原候选和图片保持原样，题目登记数保持为零。

首次冻结探针在启动被测程序前因测试脚本读取环境变量时大小写不匹配退出 1，修正后用新的独立测试库通过。完整运行日志按项目约定留在忽略的 artifacts 目录。此切片交付只读核对，后续 i3 实现用户确认和收据。审查暂缓、人工测试已取消。
