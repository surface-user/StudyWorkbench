# 连续 Word 正文的分块处理

基于[单段选区任务 #141](https://github.com/surface-user/StudyWorkbench/pull/141)。同一任务现在可选择连续的 21–100 个正文位置。每处理完一块，保存其原件位置、文本、图片引用和已用预算。重试旧的起点会返回现有进度。任务可在取消、服务重启或还原备份后从最后一次提交的位置继续。最终按正文顺序拆题，确认前可以查看题干和共享材料实际来自哪些位置。[接口](../../../docs/api-spec.md) · [选区约定](../../../docs/question-markdown-spec.md)

两次正常业务流程分别通过源码和 Windows 打包程序运行。自编 Word 的共享材料位于第 19、20 个位置，两道题位于第 21、22 个位置。两次均在第 20 个位置取消，重启、恢复后确认第二题，并取得相同选择的首次收据。两次退出 0。打包程序内的 51 个应用模块与本次源码一致。自动化只使用测试目录中的自制资料。

```text
python tools/check_resource_explorer.py --test-root <新目录> --documents --without-office
packaging/windows/build-backend.ps1 -Python <构建解释器>
python tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root <另一新目录> --documents --without-office
python tools/export_question_schema.py --check
ruff check backend tools
```

首次测试把以“第一题”开头的续文写成了另一个有效题号，获得三道候选。将自编正文改为明确的续文后复测。一次打包期间，备份模块又增加了实际图片大小核对，冻结源码匹配检查按预期拒绝该包，最终重新构建并复验。两个版本在受限目录中的首次备份回归均因无法创建目录联接而失败，原记录留在本机。

**适用范围。** 每块最多 20 个正文位置。整项任务最多 200 个富内容块及 200 道候选，图片合计最多 64 MiB，预览元数据最多 8 MiB。确认后的题目可追溯到完整选区。任务沿用原有导入记录，无新增迁移。Windows 实际窗口测试和代码审查已按本批安排暂缓。

`python -m pytest -q backend/tests/test_word_multirange.py backend/tests/test_word_jobs.py backend/tests/test_word_candidates.py backend/tests/test_backup_store.py backend/tests/test_draft_editing.py backend/tests/test_markdown_questions.py backend/tests/test_word_outline.py` 的最终 52 个不同用例在 Python 3.12.7 和 3.13.17 均通过。3.12.7 先运行 51 项，再补跑五块边界用例。按测试名称核对两个版本的通过集合完全相同，均为退出 0。覆盖 100 个连续位置、跨块题干、跨块共享材料、空段、取消后的迟到结果、失效原件、重复确认、累计限额以及中间图片的实际字节数和备份完整性。Schema 检查、Ruff 和按仓库已有 CRLF 风格运行的 Git 空白检查也均退出 0。

## 第二块执行时进程退出后的完整还原

源码和最终 Windows 打包程序各在全新测试目录使用正常接口导入含图片和共享材料的 22 位置自制 Word。第一块提交后启动第二块请求，另一次读取任务确认状态为 running、已完成 20 个位置，此时终止这个测试后端。进行中的请求断开。直接只读检查 SQLite，两个库的状态均仍为 running，保留一个 20 位置的已提交块。验证过程未写入或补造数据库状态。

对原库运行 `--data-dir <原测试库> --backup-to <备份> --confirm-all-workspaces --config <测试配置>`，随后以 `--data-dir <新目录> --restore-backup <备份> --config <测试配置>` 还原。两个版本四次离线操作均退出 0。各用相应程序打开还原库，任务均转为 interrupted，执行代次递增，进度为 20。未恢复即推进返回 409。显式恢复和处理尾块后，两道题仍指向位置 19、20 的共享材料，第一块图片可读。仅确认位置 22 后再次重启，同一请求返回原收据，题库中只有选定的一题。源码和冻结端到端验证各退出 0。原始执行输出和两个测试库仅在本机保存。
