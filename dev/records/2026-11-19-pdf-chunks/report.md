# PAR-03 大文档分块提取

## PAR-03a 协议

已有导入按原件 SHA-256 去重，每份资源关联整篇导入任务。直接让旧接口接收页区间会混淆同一资源的不同提取结果。本次把分块任务的身份、累计预算、取消与重启语义写入[提取规范](../../../docs/question-markdown-spec.md#pdf-chunk-jobs)，在[任务表](../../../docs/task.md)拆开解析子进程、持久任务和端到端验证。旧接口继续保留。

首版选用最多 8 MiB 的原生 PDF、每任务最多 100 页。20 页和 25 秒限制作用于单个子进程。100 页是待实现和验证的任务上限，尚无对应的产品性能结论。更大字节数、DOCX 和 OCR 需各自的预算与测试。

在独立 pdf-chunks 副本，以 Python 3.13.17、3.12.7 分别执行 `python -X utf8 -m pytest backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py -q`。首次指定的 basetemp 父目录尚未建立，两次均退出 1，各 15 项通过、5 项 fixture 初始化错误。创建 artifacts 后分别用独立 basetemp 和 JUnit 路径复验，两次均退出 0，各 20 项通过、2 个既有弃用警告。报告在副本 artifacts/q.xml、p.xml。覆盖现有真实 PDF 和 DOCX 解析、超时、原件保留、候选确认和重启。分块功能的实现及新测项由 b–d 承接。独立审查暂缓，人工测试已取消。
