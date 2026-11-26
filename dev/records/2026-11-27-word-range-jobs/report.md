# PAR-03 单段 Word 选区任务的取消、恢复和逐题确认

基于 [Word 正文选区候选 PR #135](https://github.com/surface-user/StudyWorkbench/pull/135)。用户可以为同一份托管 Word 原件选取连续的 1–20 个正文位置，查看任务状态，取消或在中断后恢复，最后按当前预览明确选择需要保存的题目。[现行接口](../../../docs/api-spec.md)

任务沿用导入记录和逐题确认收据。任务标识绑定空间、节点、原件资源、SHA-256、所选位置和解析器版本。开始处理时记录执行代次。处理在数据库事务外进行。只有仍处于该代次且原件保持一致时，结果才可登记附件和候选。取消后子进程最多运行至原有的 25 秒时限，其返回值随后丢弃。新建任务、恢复、中断和失败的完成位置数均为零。全部提交后才显示选区长度。服务重启将运行中的任务标为中断，由调用方显式恢复。

候选、共享材料、表格、公式和图片沿用原件正文位置。候选拆分或合并后仍可核对各片段的位置。首次确认会重新核对原件。重复提交相同修订和选择返回已有记录，改选另一组时返回冲突。备份核查任务绑定、范围、状态和同空间附件。备份恢复后可继续预览和确认。

## 自动化验证

用自编文档通过正常接口验证以下情况。

| 场景 | 可观察结果 |
|---|---|
| 正文选区与显式确认 | 三题中选第二、三题，预览保留题号 2、3。只确认第三题时，产生一份含原件正文位置 3 的 Markdown。重复确认同一选择返回同一记录。 |
| 取消后旧结果迟到 | 延迟第一次真实解析结果，取消、恢复并重新解析。新结果先提交。旧请求返回 409，旧图片标识没有写入数据库或形成文件。 |
| 原件变化 | 解析后、提交结果前替换原件字节会使任务失败。已生成预览后，原件字节变化或节点改为另一原件都会阻止首次确认。确认后重试仍返回原收据。 |
| 中断与备份 | 重启将运行中的任务记为中断。还原备份后可显式恢复。包含图片和公式的候选还原后与原预览一致，图片字节匹配，可明确确认。备份拒绝缺失附件和错配的原件摘要。 |
| 候选编辑与其他导入 | 合并两个候选保留位置 2、3，拆开后分别回到各自位置。共享材料保留来源位置。整篇原件导入另建任务。 |

执行所用的测试集和入口如下。每次运行均使用独立测试库和临时目录。

```text
python -m pytest backend/tests/test_word_jobs.py backend/tests/test_word_candidates.py backend/tests/test_pdf_chunks.py backend/tests/test_backup_store.py backend/tests/test_draft_editing.py backend/tests/test_markdown_questions.py backend/tests/test_word_outline.py backend/tests/test_document_files.py -q
python -m pytest backend/tests/test_backup_store.py::test_real_reparse_roots_and_nested_entries_are_refused_without_touching_target -q
ruff check backend tools
python tools/export_question_schema.py --check
python tools/check_resource_explorer.py --test-root <新目录> --documents --without-office
packaging/windows/build-backend.ps1 -Python <打包解释器>
python tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root <另一新目录> --documents --without-office
git -c core.whitespace=cr-at-eol diff --cached --check
```

在各自的解释器进程中先断言 Python 精确版本，再执行 pytest。Python 3.12.7 和 3.13.17 在最终测试集上各有 69 项通过，另有 1 项因本机限制拒绝创建测试目录联接而失败，整体退出 1。以允许在临时测试库创建目录联接的权限，原样单独重跑该测试，两版本各 1 项通过，均退出 0。每个版本合计有 70 个不同用例获得通过结果。增加最后一个原件重新绑定用例之前的两次试运行亦各有 68 项通过和同一目录联接失败。首轮四项专项测试退出 0。失败记录均保留。

源码和打包后的 Windows 程序分别启动实际 HTTP 服务，运行了新建、取消、恢复、解析、按选择确认、重启及收据重试，均退出 0。冻结程序的 51 个业务模块与当前源码一致。协议导出、Ruff 及差异检查均退出 0。

本项覆盖一个连续选区的一次完整提交。更长选区的多段进度、跨段候选拼接和桌面任务交互仍待另行实现。未改数据库迁移。独立审查暂缓，人工测试已取消。完整日志、备份、运行样本和可执行文件只保留在本机。
