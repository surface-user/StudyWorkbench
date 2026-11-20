# PAR-01b 修正 Word 表格编号导致的多拆题

旧冻结后端把复杂单元格的段落同时写入表格 Markdown 和正文。实际生成三道题的 Word 文件，第一题单元格含“9.”、前导零编号、图片和公式。旧后端返回四个候选，题号为 1、9、2、3，回归检查退出 1。

现在沿 Docling 文档结构遍历。表格已输出为非空 Markdown 时，标记其中的富单元格，在其文本已序列化的范围内跳过重复正文。表格后的题号照常拆分，图片及公式仍作为独立富内容块归入原题。原始 Word 文件不变。新解析记录的版本后缀为 cell-text-v2，普通 Word 结构预览版本相应递增；旧记录没有迁移。

## 验证

```shell
python -m pytest -q backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py backend/tests/test_markdown_questions.py
python tools/check_document_workers.py
./packaging/windows/build-backend.ps1 -Python <发行Python路径>
python tools/check_document_workers.py --exe <新冻结后端>
```

Python 3.12 和 3.13 各 40 项通过。经普通导入接口验证仅有 1、2、3 三个候选，并回读原件逐字节相同。源码及新 Windows 冻结进程分别通过七组 Word/PDF 检查。表内编号文字在正文中只出现一次，前导零、两张图和单元格公式保留，后续真实题目仍独立。48 个冻结业务模块与源文件相符，Ruff 通过。

在 [#101](https://github.com/surface-user/StudyWorkbench/pull/101) 跟踪的依赖范围中，本次复验覆盖了实包的 Word 表格、图片、公式及拆题入口。该结果不推断第三方库的所有命令行入口或动态分支均可用。独立审查和人工测试按本轮安排跳过。
