# PAR-03f Word 正文选区

本次确定按原件正文位置选区的规则、输入预算和恢复条件。[选区契约](../../../docs/question-markdown-spec.md#docx-content-ranges)列出后续持久任务的验收条件。现有 Word 整篇导入仍使用既有入口。

用标准库 ZipFile 和 ElementTree 读取项目两份自编 DOCX 及编号单元格测试生成的原件，逐一核对正文直属元素、表内段落及输入摘要。三份文件分别有 7、7、8 个正文位置，其中表格分别为第 4、5、5 项；按所有后代元素计数会得到 10、10、14 个段落。三份原件读取前后摘要相同，检查退出 0。

`python -m pytest -q backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py backend/tests/test_markdown_questions.py` 在 Python 3.12、3.13 各通过 40 项，退出 0。现阶段验证了已有整篇解析的兼容性。按位置读取、选区拆题、取消和恢复将在实现后分别验证。

## PAR-03g 托管 Word 原件的正文位置预览

用户可按已知摘要，从指定位置读取一份 Word 原件的段落和表格索引。每次返回最多 50 项，含绝对位置和简短摘录。索引服务不写数据库，遇到无法确定位置的直属元素会返回原因。原件通过整包限制与归属校验后，在独立子进程中解析。

| 自动化检查 | 结果 |
| --- | --- |
| `python -m pytest -q backend/tests/test_word_outline.py backend/tests/test_document_files.py backend/tests/test_documents.py backend/tests/test_pdf_chunks.py` | 两个 Python 版本各 41 项通过，退出 0。覆盖跨页索引、嵌套表格、空段落、范围、跨空间与原件变化 |
| `packaging/windows/build-backend.ps1` | 退出 0，49 个冻结业务模块与源码匹配 |
| `tools/check_resource_explorer.py --documents --without-office`，源码与 Windows 可执行文件 | 各退出 0，核实普通资料复制、索引、重启后一致性及来源保留 |
| 自编带图片 DOCX 的普通资料复制 | 9,775,713 字节、53 个正文位置。源码解析与实际 Windows 服务末段索引一致，重启后可复读，原件逐字节相同 |
| Ruff 和 Git 空白检查 | 均退出 0。现有工作进程文件保留原有 CRLF，空白检查识别该行尾 |

按选区拆题、共享材料接续和持久化恢复仍待实现。

追加的正文用例复现制表符和换行使相邻文字黏连，修复前 1 项失败。摘录现在以空格保留这两种边界，达到 120 个字符即停止读取。修复后两版各 41 项通过，源码和重新构建的 Windows 程序均返回相同的分隔文字；原 53 个位置的大文档末段复读通过。
