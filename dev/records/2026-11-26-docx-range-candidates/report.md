# PAR-03h 托管 Word 正文选区的只读候选

基于原件正文位置索引 [PR #125](https://github.com/surface-user/StudyWorkbench/pull/125)。用户提交当前空间内的托管节点、原件 SHA-256 和连续正文位置，可取得选区富内容、候选、附件和原位置。后端在提取前及返回结果前复核来源。调用不写题库，数据库迁移、持久任务状态、取消、恢复和确认留给后续任务。[现行接口与预算](../../../docs/question-markdown-spec.md#docx-content-ranges)

固定 Word 解析器在有界子进程中读取经过整包检查的原件。先沿原件正文和表内段落读取同一自动编号实例的计数，再在内存中将能核实的单层十进制编号交给富内容提取器。需要复核的编号有明确位置提示。正文覆盖无歧义时，原有拆题规则生成候选和共享材料，表格内题号不触发切分。所有输出片段按原件位置归属，包括公式及图片。

| 自编用例 | 核对结果 |
|---|---|
| 三道连续自动编号题，只读位置 2–3 | 源码接口与 Windows 冻结程序均返回原题 2、3；每道题的位置分别为 2、3。首题文字未进入结果 |
| 单格表内同一自动编号清单 | 单元格显示 2，紧邻的下一题仍是原题 3。表格归其原件位置，单元格自身不生成一道题 |
| 富单元格、公式、图片、共享材料及截断 | 整表纳入选区；公式、实际图片附件和表格文字保留。越过材料选择起点时不附带外部材料；完整材料带原位置 |
| 缺失编号、层级、重启覆盖及有歧义的前置编号 | 保留原文字，列出需核对的位置，未生成猜测题号 |
| 预算、空间和源版本 | 超过旧 8 MiB 的已托管 DOCX 可以读选区；超过表格或候选预算整块拒绝。外部关系在整包预检处拒绝。范围非法、文件变化、旧摘要及跨空间请求分别验证 |

单次最多 20 个正文位置，仍使用阅读侧两个执行槽、25 秒超时、96 MiB 输出和 64 MiB 图片总量预算。表格在转 Markdown 前先核原件位置、行列和跨列，再核渲染文本长度。普通整篇 Word 导入、Word 正文索引及 PDF 页段继续使用其既有入口。

## 自动化复验

```text
python -m pytest backend/tests/test_word_candidates.py backend/tests/test_word_outline.py backend/tests/test_complex_question_splitting.py backend/tests/test_documents.py backend/tests/test_pdf_chunks.py backend/tests/test_document_files.py -q
ruff check backend tools
python tools/export_question_schema.py --check
python tools/check_document_workers.py
python tools/check_resource_explorer.py --test-root <新目录> --documents --without-office
packaging/windows/build-backend.ps1 -Python <独立 Python>
python tools/check_document_workers.py --exe dist/study_backend/study_backend.exe
python tools/check_resource_explorer.py --exe dist/study_backend/study_backend.exe --test-root <另一新目录> --documents --without-office
```

本机首次按环境名称划分的两组最终测试各有 66 项通过，两组实际都是 Python 3.13.17。随后在项目独立的 Python 3.12.7 中先断言精确版本，再执行相同测试，66 项通过、退出 0。Python 3.13.17 的实测同为 66 项通过。Ruff、协议导出及差异检查退出 0。源码与最终 Windows 执行文件的工作进程和实际 HTTP 入口各通过一次，冻结包的 50 个业务模块均与当前源码一致。GitHub 当前提交的检查另见相应 PR。

两次开发中的冻结包被源码一致性检查拒绝，分别在构建期间修改了表格边界规则和无法还原的前置编号规则。失败记录均保留，最终交付使用代码固定后重新构建的版本。原件、依赖环境、运行日志及可执行文件保留本机。独立审查暂缓，人工测试已取消。
