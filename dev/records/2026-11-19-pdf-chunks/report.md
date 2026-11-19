# PAR-03 大文档分块提取

## PAR-03a 协议

已有导入按原件 SHA-256 去重，每份资源关联整篇导入任务。直接让旧接口接收页区间会混淆同一资源的不同提取结果。本次把分块任务的身份、累计预算、取消与重启语义写入[提取规范](../../../docs/question-markdown-spec.md#pdf-chunk-jobs)，在[任务表](../../../docs/task.md)拆开解析子进程、持久任务和端到端验证。旧接口继续保留。

首版选用最多 8 MiB 的原生 PDF、每任务最多 100 页。20 页和 25 秒限制作用于单个子进程。100 页是待实现和验证的任务上限，尚无对应的产品性能结论。更大字节数、DOCX 和 OCR 需各自的预算与测试。

在独立 pdf-chunks 副本，以 Python 3.13.17、3.12.7 分别执行 `python -X utf8 -m pytest backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py -q`。首次指定的 basetemp 父目录尚未建立，两次均退出 1，各 15 项通过、5 项 fixture 初始化错误。创建 artifacts 后分别用独立 basetemp 和 JUnit 路径复验，两次均退出 0，各 20 项通过、2 个既有弃用警告。报告在副本 artifacts/q.xml、p.xml。覆盖现有真实 PDF 和 DOCX 解析、超时、原件保留、候选确认和重启。分块功能的实现及新测项由 b–d 承接。独立审查暂缓，人工测试已取消。

## PAR-03b PDF 页区间子进程

在现有文档子进程增加内部参数 `--parse-pdf-pages FIRST LAST`，沿用 PDFium、全文块和裁图区间处理。跨块所需的页首接续、题目和材料标记按原件顺序返回；无法定位题号时保留整页并标记歧义。区间外的页不提取。旧整篇入口仍拒绝超过 20 页的 PDF。产品任务调度、父进程读取预算、取消及聚合确认属于 c/d。

自建 22 页输入将两页共享材料放在原件第 20、21 页，末页补空白。真实子进程只取第 21 页，验证绝对页号、首段续文、两个题号、区域和所选区间两端的提示；取全空白页只存一份页图。非法页码类型、越界、单块过多页、超过 8 MiB 的原件、缺少可定位标记均有负例。

在独立 pdf-chunk-worker 副本，Python 3.13.17 / 3.12.7 执行 `python -X utf8 -m pytest backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py -q`。首轮各 27 通过。补充输入边界后，两版各 1 失败、27 通过、3 个错误：Windows 默认管道编码使中文拒绝结果无法按 JSON UTF-8 解码，pytest 又将整份 8 MiB 测试参数编码进测试名称，超过 Windows 环境变量长度。分块的错误改用 ASCII 转义 JSON，测试改以大小参数生成同样字节。复验两版分别 30 通过、2 个既有弃用警告，退出 0。所有中间日志及最终 JUnit 位于副本 artifacts。未更改旧解析语义或删减错误断言。

`python -m ruff check backend tools`、`python tools/export_question_schema.py --check` 和源码模式 `python tools/check_document_workers.py` 退出 0。后者在原有整篇 DOCX/PDF 检查后新增第 2 页片段的实际子进程检查；同一脚本也由 Windows CI 对本次构建出的冻结包执行。以当前提交的运行结果核实冻结覆盖。审查暂缓、人工测试已取消。
