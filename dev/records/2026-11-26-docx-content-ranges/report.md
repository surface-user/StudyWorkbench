# PAR-03f Word 正文选区

本次确定按原件正文位置选区的规则、输入预算和恢复条件。[选区契约](../../../docs/question-markdown-spec.md#docx-content-ranges)列出后续持久任务的验收条件。现有 Word 整篇导入仍使用既有入口。

用标准库 ZipFile 和 ElementTree 读取项目两份自编 DOCX 及编号单元格测试生成的原件，逐一核对正文直属元素、表内段落及输入摘要。三份文件分别有 7、7、8 个正文位置，其中表格分别为第 4、5、5 项；按所有后代元素计数会得到 10、10、14 个段落。三份原件读取前后摘要相同，检查退出 0。

`python -m pytest -q backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py backend/tests/test_markdown_questions.py` 在 Python 3.12、3.13 各通过 40 项，退出 0。现阶段验证了已有整篇解析的兼容性。按位置读取、选区拆题、取消和恢复将在实现后分别验证。
