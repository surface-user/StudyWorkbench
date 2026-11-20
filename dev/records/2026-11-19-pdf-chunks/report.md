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

#70 首次 CI 的 Windows 冻结包检查通过，Python 3.12 的三条新增子进程测试因找不到 study_workbench 失败，矩阵取消了另一版本。开发环境显式设置了 PYTHONPATH，CI 仅给 pytest 自身配置了源码目录。测试现从 backend 目录执行子进程，沿用同一解释器和断言。原失败保留在[首次 CI](https://github.com/surface-user/StudyWorkbench/actions/runs/44495155155)。

## PAR-03c 分块任务 API、重启与备份

后端按空间、资源、原件 SHA-256、解析版本及页段建唯一任务。一个 advance 最多执行 20 页，领取与提交各自使用短事务。解析在事务外运行，父进程限时 25 秒，stdout 读取上限为 96 MiB 加一个超限探测字节。取消会废弃执行代次；提交前再检查代次、源文件和整个任务累计附件/候选/材料预算。已提交块按任务和起始页唯一索引，步进重放不重复写入。每块的图片复用原有托管资源存储，整库备份检查原件关系、连续性和图像引用。这个接口交付到 parsed，跨块候选拼接和用户确认由 PAR-03d 继续。

从 schema 0016 加两张表升级到 0017。对旧库重新执行逐表字段/旧作答、升级前备份的一致性测试。现有当前版本/备份名称断言随本次迁移前移，未知版本拒绝用例改用 0018。使用独立人工生成的 PDF 和数据库，没有读取个人库。

在 pdf-chunk-jobs 副本，以 Python 3.13.17 与 3.12.7 执行 `python -X utf8 -m pytest backend/tests/test_pdf_chunks.py backend/tests/test_backup_archive.py backend/tests/test_backup_store.py -q`。首轮各 64 通过、1 失败，Windows 沙箱拒绝创建备份旧用例需要的目录联接。针对该用例在项目隔离目录用原生权限两版复验，各 1 通过。加入完整备份还原/引用拒绝后，对最终业务代码原生运行整组，各 66 项通过、2 项既有弃用警告，退出 0，JUnit 在 artifacts/native-final-q.xml、native-final-p.xml。

新增 `test_intermediate_revision_preserves_every_old_column[0016]` 两版各 1 项通过，退出 0。另有首次 Ruff 报 1 处导入次序，整理后 `python -m ruff check backend tools` 与 `python tools/export_question_schema.py --check` 退出 0。实际自动化覆盖双提交、20/21 页边界、取消后迟到结果、重启中断、源路径/版本不符、累计超限、备份恢复。选区自动抽题与当前提交的完整 CI 单列跟踪。

## PAR-03d 跨块题目、共享材料和显式确认

解析完成后显式创建页段预览，按原页序连续拼接题目或共享材料。尚未识别到题号的前缀留在原页。不可定位的布局阻断自动接续。复用现有编辑、确认、Markdown 导出和修订摘要，保留原始页号和选定范围。相同预览或确认重放返回已有结果。旧整篇导入继续取自己的导入任务，整篇重试不会改写选区候选。选区公开预览按现有每题内容协议验证，序列化预算为 8 MiB。

在 pdf-chunk-candidates 独立副本对 21 页自建样本先提交前 20 页、重启、提交第 21 页，验证共享材料跨页关联两题、文字片段、正式题目只在显式确认后出现、已确认修订和原件字节保持。另测仅选择原件第 2 页后，从原始坐标继续裁题。旧裁切算法将绝对页码直接作为页图数组索引，专门回归修补前 1 失败（HTTP 422），保存于 artifacts/crop-before.log。现在按所选起页换算索引；旧整篇入口默认从第 1 页算起。

Python 3.12.7 和 3.13.17 未设置 PYTHONPATH，分别执行 `python -X utf8 -m pytest -q backend/tests/test_pdf_chunks.py backend/tests/test_documents.py backend/tests/test_complex_question_splitting.py backend/tests/test_markdown_questions.py backend/tests/test_draft_editing.py`，各 46 项通过、2 个既有弃用警告，退出 0。首次 Ruff 报两处导入顺序，修正后再运行通过。原件和门户数据均为本任务生成。

`python tools/check_api_errors.py --test-root artifacts/http01` 首轮在既有外部 Origin 拒绝检查读响应时遇到 Windows 10054 连接复位，退出 1。使用新建的 http02 隔离数据目录重跑同一脚本退出 0。使用 `packaging/windows/build-backend.ps1` 打包，首次打包期间裁题模块发生修正，核源拒绝旧模块，保留 artifacts/build.log。稳定源重建退出 0，46 个冻结模块与源码逐一匹配。对新生成的 exe 执行 `tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root artifacts/frozen-final` 退出 0。源码与冻结各 68 项 HTTP 检查、31 个不同错误 ID，均实际经过重启、续题、两次同选确认及原件字节校验。记录位于 artifacts/build-final.log、frozen-final.log 及两版 final JUnit。

本次覆盖原生 PDF 有界分块的后端路径，更大字节原件、OCR、多栏和桌面入口仍在任务表分别跟踪。人工测试已取消，独立审查按本批要求暂缓。当前提交的 CI 另核。

## PAR-03e 较大托管 PDF 的流式校验和页段提取

从普通资料添加入口复制进工作区的 PDF 可以按页段处理，最大文件与该入口一致，均为 128 MiB。任务创建、推进、恢复、结果提交和首次选题确认都核对活动空间、资源身份、实际长度和 SHA-256。准备解析时按最多 1 MiB 的读取块同时生成系统临时文件快照，PDFium 从可定位的文件句柄按需读取，后端与子进程通过标准输入传递快照。单页 OCR、单页双栏预览、旧整篇上传保留 8 MiB 输入限额。页数、每块 20 页、25 秒、96 MiB 输出、64 MiB 累计图像和 200 道候选的上限沿用。快照写入或刷盘空间不足返回 507，过期原件不接受新结果。

先用带有自编 PDF 合法填充的 9 MiB、32 MiB 样本验证原生工作进程计页、左栏题干与右栏续题。真实业务样本包含一页自编 RGB 噪声扫描图和第二页双栏题目，源码路径实际 9,076,345 字节。正常资料添加、SHA-256、单栏和双栏任务分离、取消与恢复、仅提取第 2 页、原页区域、显式确认的幂等性及取回原件字节均有断言。冻结边界样本在相同图像和题目内容前提下补入 PDF 注释并重算 xref 偏移，实际恰好 134,217,728 字节。两次测试都用了新建的业务数据目录。

首次双 Python 专项各 56 通过、2 失败（退出 1）。Windows 管道的 seekable 值不能判断是否为可定位的普通文件，导致旧管道子进程拒绝合法样本。改由 fstat 的文件类型决定处理方式，原反例均保留。双 Python 管道专项各 9 通过，之后双 Python 3.12.7 / 3.13.17 全部相关专项各 58 通过、2 项已有警告，退出 0。实验、失败日志和最终 JUnit 均在 pdf-large-managed/artifacts。

```powershell
python -X utf8 -m pytest -q backend/tests/test_pdf_chunks.py backend/tests/test_documents.py backend/tests/test_markdown_questions.py backend/tests/test_ocr_page.py backend/tests/test_document_files.py
ruff check backend tools
python tools/export_question_schema.py --check
python tools/check_api_errors.py --test-root artifacts/source-final
./packaging/windows/build-backend.ps1 -Python (Resolve-Path '../starlette-fix/.local/starlette-q-isolated/Scripts/python.exe').Path
python artifacts/check_bound.py --exe dist/study_backend/study_backend.exe --test-root artifacts/frozen-final
```

首次 Ruff 指出测试文件一处导入排序，修正后 Ruff 及协议检查均退出 0。源码正常业务路径 90 次 HTTP；最终冻结包 48 个模块核源通过，128 MiB 上限样本 92 次 HTTP。两端各 31 个不同错误 ID，支持恢复与确认的端到端检查均退出 0。一次冻结通过旧管道修正前的同类上限样本，已保留记录；交付采用修正后重建的最终 exe。其他文档格式和桌面分块交互另行跟踪。独立审查暂缓，人工测试取消。
