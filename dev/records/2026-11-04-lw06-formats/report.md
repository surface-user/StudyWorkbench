# LW-06 格式支持扩展

2026-11-04，按持续开发/统一待验授权推进后台工作；LW-09冻结API闭环通过，实际窗口因用户使用电脑暂缓，不标阶段通过。独立功能用本任务唯一报告，无子Agent、新运行依赖或发布授权。

## 分批设计

1. 当前切片：JSON/CSV/LOG/VTT/SRT复用1MiB UTF-8原文只读查看，保留字节/hash；不执行/自动编译题库，不开放工作副本编辑。位置v1仍仅MD/TXT原文行，其余新文本仅资料级标记；集中查找不扩成资料全文索引，Agent权限不变。
2. 后续XLSX：标准库受限ZIP/XML读取器放既有超时子进程，首批常见OOXML多表只读/缓存值；不执行公式/宏、不启动Excel。缺缓存逐格明确提示，日期/样式/图表/合并版式不冒充Excel保真。先确定源/解压/XML/表/单元格及输出预算，再实现解析/UI/安全与故障测试；尚未实施。
3. 更新格式能力矩阵（留存/查看/标注/编辑/Agent可读分列），测试非法UTF-8/预算/原件不变/改名不变格式、资源级位置及组件显示；不为反复重试另建报告。原始产物artifacts/lw06-20261104/。

本任务进行中；首批文本切片不代表XLSX或全部格式完成。用户操作电脑期间不启动/控制前台窗口，仅后台开发与自动化。

## 当前实现与自审

document_files.py按原件original_name后缀决定格式，JSON/CSV/LOG/VTT/SRT（含大写后缀）严格UTF-8解码、1MiB预算，返回type=text、source_format、position_kind=resource。不解析JSON/CSV、不执行公式/HTML/脚本、不允许创建工作副本；保留BOM/CRLF及原件hash，树内改名不改变查看类型。TXT原文行语义不变，集中查找和Agent授权范围不扩展。DocumentPage字面显示及资料级书签已有组件覆盖；原生添加筛选器增加文本扩展名。

本批自审完成：查看分支不写原件，非法编码和超限均明确失败，未知格式仍unsupported；仅MD可创建可编辑副本，新增格式不推断原文行位置。无新增表/迁移/运行依赖，未提交/推送/PR/合并/发布，非独立审查批准。

## 实际命令、结果与限制

P=.venv/Scripts/python.exe（仓库根）；D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F=D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot（Flutter命令在apps/desktop执行）。TEMP/TMP指向仓库.local/tmp，关闭Flutter/Dart分析上报。原始日志/JUnit在artifacts/lw06-20261104，不复制到evidence。

| 实际命令 | 退出码/结果 | 产物 |
|---|---|---|
| P -m pytest backend/tests/test_readonly_text.py -q --basetemp=.local/lw06-text-01 --junitxml=artifacts/lw06-20261104/text-01.xml | 0，7通过，4.28秒；Starlette/anyio旧warning保留 | text-01.log/xml |
| D format apps/desktop/lib/document_page.dart apps/desktop/test/learning_marks_test.dart（根目录） | 0，组件测试格式化 | 工具输出 |
| P -m ruff check backend/study_workbench/document_files.py backend/tests/test_readonly_text.py | 首次1，新增测试import排序；P -m ruff check --fix backend/tests/test_readonly_text.py后0 | 工具输出 |
| D F --suppress-analytics test --no-pub test/learning_marks_test.dart | 首次1：从apps/desktop错误引用根目录Python及临时目录；修正绝对TEMP/TMP后0，11通过 | flutter-text-01.log、flutter-text-02.log |
| D F --suppress-analytics analyze --no-pub | 0，No issues found，11.3秒 | analyze-01.log |
| P -m ruff check backend tools | 0 | 工具输出 |
| P tools/export_question_schema.py --check | 0，schema未漂移 | 工具输出 |
| P artifacts/lw06-20261104/check_docs.py | 0，49份Markdown/237本地链接/7锚点，114受保护文件hash不变、13任务报告 | docs-checks.json |
| git -c core.safecrlf=false diff --check | 0 | 工具输出 |

7项新增后端测试不是后端全套重跑；11项组件测试不是Flutter全套重跑。上批343后端/137 Flutter及Windows构建属于LW-05/09版本，不当作本次新文本改动通过。用户正在使用电脑，本切片未重跑Windows构建/冻结后端/实际窗口，原生筛选器新改动仍待构建核验；不启动任何前台应用。

下一步先补当前文本切片全套回归及Windows构建（后台资源合适时），再明确XLSX预算并实现只读组件；LW-09真实阅读/播放、导航和恢复窗口验收等用户方便再继续。任务保留进行中，人工/阶段未通过。

## 2026-11-05 XLSX切片实施设计

用户允许恢复正常操作；Computer Use启动隔离包连续两次返回`computer-use request timed out: launch_app`，未选择到测试窗口，转后台验证，详见LW-09原报告。本批原始产物artifacts/lw06-20261105，不覆盖旧失败。

XLSX只读取常见Transitional OOXML工作簿，使用Python标准库ZIP/XML及既有20秒查看子进程；不增加依赖、不调用Excel、不执行公式/宏/外链、不落盘解包。UI采用按表切换的稀疏单元格列表，保留A1地址，避免将稀疏坐标填充成巨型网格。正文/缓存是原件中的值，不保证新鲜度；公式无缓存逐格提示，空字符串缓存与无缓存区分。数字/日期序列按原始值显示，样式、图表、合并布局和计算保真不承诺；不加入搜索/编辑/Agent可读范围，仅资料级位置。

预算：源16MiB；ZIP仅单卷常规目录、≤1024条目/目录256KiB，先检查真实目录数量再构造ZipFile；全部声明解压≤32MiB，单部件≤8MiB；读取部件按实际字节再验大小/CRC，不信任清单；XML累计≤100000节点/深度64，拒绝DTD/实体/样式声明（含UTF-16空字节变体）；≤10表/10000单元格/10000共享字符串、单值≤4096字符、结果UTF-8 JSON≤2MiB，超限整体明确拒绝、原件保留。拒绝重复/越根/歧义路径、加密/特殊文件、宏/嵌入活动对象与外部关系；ZIP64、Strict OOXML、加密/旧XLS等当前不支持，不能默默当空表。

公式/共享字符串/表关系依据Microsoft官方Open XML说明：[公式缓存](https://github.com/OfficeDev/open-xml-docs/blob/main/docs/spreadsheet/working-with-formulas.md)、[共享字符串](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-the-shared-string-table)、[包结构](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document)。先用自建ZIP/XML样本覆盖多表、富文本共享串、inlineStr、数字/布尔/错误、缓存缺失及坏包/预算/外链/原件保持，再接资源API与Flutter组件；当前文本回归版本和XLSX实施后回归分列。

## 2026-11-05 实现与复核

新增spreadsheet_view.py，由document_view_worker的xlsx模式调用，保留既有20秒期限/2并发/无窗口进程策略；资源API返回spreadsheet及稀疏cells、源hash，renderer_version=xlsx-values-v1。DocumentPage接SpreadsheetView，懒加载单元格列表、表选择/隐藏表标识、公式缓存及缺失提示；复用layout.page保存表序号，不存正文。原生选择器增加.xlsx，工作副本/原文行锚点仍拒绝XLSX；仅资料级标记。UTF-8文本和XLSX均未扩展Agent/搜索授权。

本批自审覆盖共享串索引/富文本及拼音注音不混正文、稀疏XFD1048576不扩成网格、空字符串缓存区别缺缓存、未知类型/坐标/重复关系/重复ZIP/CRC/DTD/UTF-16声明/宏/外链/深度与字节预算。ZIP预检在ZipFile构造前限制真实目录，包内父关系规范化后仍须留在根内；实际读取受限且无提取、网络、Office引擎或公式求值。输出逐格计费，最终序列化再核对2MiB。测试样本固定ZIP时间戳，保留精确字节断言，避免文件头时钟造成随机失败。

自审另发现资料级链接若复用已打开XLSX会保留第二表，容易被误认为书签记录了表位置。现显式跳到首表/顶部；普通重启仍恢复已选表，新增两种入口回归。此修复发生在141项Flutter/Windows-02之后，末轮重新验证，结果另列。自审非独立人工审查，未取得窗口/用户/阶段验收。

Office能力矩阵沿用既有引擎：DOCX结构视图/可选静态PDF、PPTX仅可选静态PDF；组件缺失、动态对象/外链拒绝、FakeRuntime故障在全套回归覆盖；真实第三方版式/字体、组件安装/干净机仍待验。旧DOC/PPT/XLS未新增支持，Strict/ZIP64/加密XLSX明确拒绝，不冒充Excel保真编辑。未新增运行或测试依赖。

### 当批命令与结果

环境沿用前述P/D/F，独立冻结Q=.local/release-venv/Scripts/python.exe（CPython3.13.17）。日志统一artifacts/lw06-20261105/；全部为后台自动化，无窗口操作。Windows与Flutter SDK缓存、真实junction回归使用获准扩展权限。

| 实际命令 | 退出码/结果 | 产物 |
|---|---|---|
| P -m pytest backend/tests -q --basetemp=.local/lw06-backend-20261105-01 --junitxml=artifacts/lw06-20261105/backend-01.xml | 0，350通过，211.99秒；文本切片、未含XLSX | backend-01.log/xml |
| D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw06-flutter-20261105-01 | 0，138通过；文本切片 | flutter-01.log |
| D F --suppress-analytics build windows --release --no-pub --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw09-window/data | 0，54.4秒；文本切片 | windows-01.log |
| P -m pytest backend/tests/test_spreadsheet_view.py -q --basetemp=.local/lw06-xlsx-20261105-01 --junitxml=artifacts/lw06-20261105/xlsx-01.xml | 1，20通过/1失败：inlineStr公式无缓存先走缺缓存分支，未拒绝非法类型组合 | xlsx-01.log/xml |
| 同一专项，basetemp/junit改为xlsx-20261105-02/xlsx-02 | 0，22通过，7.94秒；类型先校验，保留原断言 | xlsx-02.log/xml |
| 同一专项，basetemp/junit改为xlsx-20261105-03/xlsx-03 | 0，30通过，8.44秒；扩展损坏与注音样本 | xlsx-03.log/xml |
| 同一专项，basetemp/junit改为xlsx-20261105-04/xlsx-04 | 0，30通过，8.12秒；固定样本时间戳后复验 | xlsx-04.log/xml |
| D F --suppress-analytics test --no-pub test/spreadsheet_view_test.dart test/learning_marks_test.dart | 0，14通过；实际组件，不是实际窗口 | flutter-xlsx-01.log |
| P -m pytest backend/tests -q --basetemp=.local/lw06-backend-20261105-02 --junitxml=artifacts/lw06-20261105/backend-02.xml | 0，380通过，215.48秒；包含XLSX | backend-02.log/xml |
| D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw06-flutter-20261105-02 | 0，141通过；资料链接首页修复前 | flutter-02.log |
| D F --suppress-analytics analyze --no-pub | 0，No issues found；两次分别76.8/8.3秒 | analyze-xlsx-01/02.log |
| D F --suppress-analytics build windows --release --no-pub --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw09-window/data | 0，49.5秒；资料链接首页修复前 | windows-02.log |
| P -m ruff check backend tools | 0 | ruff-02/03.log |
| Q -m PyInstaller --noconfirm --clean --distpath artifacts/lw06-20261105/frozen/dist --workpath artifacts/lw06-20261105/frozen/build artifacts/lw06-20261105/frozen/spec/study_backend.spec | 0，约133.8秒；新目录先验不存在，复用原spec的依赖/metadata配置并将entry改绝对路径，collect_submodules包含新模块 | frozen-01.log，spec保留于原始产物 |
| P tools/check_learning_workbench.py --exe artifacts/lw06-20261105/frozen/dist/study_backend/study_backend.exe --test-root .local/lw06-frozen-20261105-01 --media-fixture artifacts/lw09-20261104/fixture.webm | 1，JSON样本write_text在Windows将LF转CRLF，精确原文断言失败；未改产品或弱化断言 | frozen-flow-01.log |
| 同命令，test-root改.local/lw06-frozen-20261105-02 | 0，fixture改write_bytes；真实冻结API验证JSON/XLSX多表/缓存、重启、整库备份恢复、源文件hash及SQLite摘要相同，媒体仅导入 | frozen-flow-02.log、隔离root/result.json |

analyze-xlsx-01命令前一次从apps/desktop错误使用根目录相对Python路径，lint未执行，随后在根目录单独复验ruff通过；该错误未当成lint通过。旧Starlette/anyio及CMake CMP0175警告继续保留。所有重复测试使用新basetemp，不清理原失败现场。

冻结/Windows候选均为隔离开发测试产物；没有替换原dist、安装包、个人默认配置或旧window-bundle。不等于原默认profile/M0、安装/干净机或实际播放通过。下一步完成末轮前端修复复验、真实第三方Office/XLSX矩阵和LW-09窗口验收；LW-06继续进行中，未提交/推送/PR/合并/发行。

### 末轮收尾

资料级链接回首表修复后，D F test使用同上完整参数但隔离数据改.local/lw06-flutter-20261105-03，退出0、142通过（flutter-03.log）；D F analyze --no-pub退出0、8.1秒无问题（analyze-xlsx-03.log）；D F build windows --release --no-pub及同一STUDY_DATA_DIR退出0、45.1秒（windows-03.log）。这三项顺序执行，任一失败不会把后续未执行项记通过。后端代码未再改，380全套/30专项和frozen-flow-02继续是该后端实际结果。

末轮前端Release排除其旧backend目录后复制到全新artifacts/lw06-20261105/window-bundle，搭配本批冻结后端；复制前要求目标不存在，无删除/覆盖旧包。exe/app.so/backend SHA256及编译数据目录记录在window-bundle-hashes.json；源文件摘要见source-sha256.json。这个候选固定读取.local/lw09-window/data（及其隔离相邻配置），不是普通发行包，未再次调用Computer Use启动。新格式隔离材料另在.local/lw06-frozen-20261105-02/materials，可供以后真实添加/阅读验证。

用户授权恢复前台操作已生效，窗口缺口目前是helper启动超时，非用户授权待批。后续应先恢复可选测试窗口再完成真实交互，不将142个组件测试或冻结HTTP闭环替代它；任务及原历史失败继续保留。

末轮文档/源检查（根目录）：P artifacts/lw06-20261105/check_docs.py退出0，49份Markdown/238本地链接/7锚点，114受保护旧文件hash保持、13报告；P tools/export_question_schema.py --check、P -m ruff check backend tools、git -c core.safecrlf=false diff --check均退出0，分别留docs-final.log/schema-final.log/ruff-final.log/diff-final.log。git check-ignore确认新候选hash清单及隔离result.json仍忽略；git rev-parse --short HEAD仍29f23d3，所有本批改动未提交。

## 后续轮：真实引擎格式矩阵与字符串兼容

本轮继续原任务，原始产物artifacts/lw06-matrix-20261105/，不重复建立报告。P tools/check_office_previews.py --exe artifacts/lw06-20261105/frozen/dist/study_backend/study_backend.exe --test-root .local/lw06-office-matrix-20261105-01 --runtime .local/release-tools/libreoffice-26.8.1 --docx .local/r3-office-samples-repro/中文公式.docx --pptx .local/r3-office-samples-repro/中文图表.pptx，退出0。用既有锁定26.8.1离线组件及项目自编样本，DOCX/PPTX各2页（67520/46266字节PDF），原件不变、真实取消/重试/缓存/重启及XML预算拒绝通过；公式文字/图表标签另有断言。检查脚本旧版把迁移head写死0012，本轮在运行前改为从当前迁移脚本读取head，保留严格相等判断。

实际查看docx-page1.png与pptx-page1.png，中文/公式/表格/图表未见明显缺失；这是生成页图检查，不是应用窗口操作，未检查的第二页及第三方任意版式不补写通过。完整PNG保留在隔离root，未整批转evidence。

新增tools/check_spreadsheet_samples.py，仅将脚本自建FODS通过既有受控无窗口Job/独立profile转换为XLSX，再调用source/frozen查看器；不接受用户Office文件执行公式，不成为产品XLSX依赖。过滤器依据[LibreOffice官方清单](https://help.libreoffice.org/latest/zh-CN/text/shared/guide/convertfilters.html)。P tools/check_spreadsheet_samples.py --runtime .local/release-tools/libreoffice-26.8.1 --test-root .local/lw06-calc-matrix-20261105-01 --exe artifacts/lw06-20261105/frozen/dist/study_backend/study_backend.exe退出1（calc-01.log），误把生产者导出的无样式布尔当成t=b；实际XML为t=n、v=1，查看器原始值正确。保留失败，校正测试为严格核对源XML类型/值及显示值，未把1和TRUE宽松等价；t=b仍由原专项验证。相同命令改新root .local/lw06-calc-matrix-20261105-02退出0（calc-02.log）：两表11单元格、中文富文本、合计公式缓存175、日期原始序列46331、字面script、原件不变。运行时fingerprint为147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca，样本XLSX SHA256为aa49c140254eacc923edc9e4620252515ad2984fd70eed86cfa4e9be9d9eadfb。

另按微软[ST_Xstring规范说明](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/bd0aa042-434a-4ca7-b25f-4e1fd25a954d)补解码：单次_xHHHH_、受保护的字面下划线、UTF-16代理对，拒绝不完整代理对；按解码字符执行4096预算，仍不解释HTML或公式、不改源字节。新增5项，XLSX专项累计35项；与LW-07初轮传输47项一起执行P -m pytest backend/tests/test_spreadsheet_view.py backend/tests/test_media_download_http.py -q --basetemp=.local/lw06-lw07-20261105-01 --junitxml=artifacts/lw06-matrix-20261105/combined-01.xml退出0，82通过，9.79秒。此兼容修补发生于上述Calc冻结验证之后，新版本完整回归/冻结跟随LW-07，不把旧冻结包当成修补后版本。

本轮样本均自编/项目生成，真实第三方复杂Office、应用窗口/用户/阶段与干净机仍待验；没有因此将LW-06销项。后续迁移与备份改动属于LW-07，命令和失败继续对应报告，不在本报告复制整份流水账。


统一添加预检补丁：explorer.inspect_source原先仍称TXT/JSON及新增只读格式不支持，已按实际能力返回TXT/Markdown/JSON/CSV/LOG/VTT/SRT/XLSX说明与有界预算提示；xlsx核PK签名，超过文本1MiB/XLSX16MiB仍可保留原件但明确超查看预算。新增7项，不冒充格式完整验证。P -m pytest backend/tests/test_readonly_text.py -q（完整运行参数见本聊天工具记录，日志/JUnit为inspect-01）退出0，14通过，5.25秒；后与test_resource_inspections.py合跑18通过，7.66秒（inspect-02日志/XML）。此7项在LW-07的442完整回归之后，后续全量计数见LW-08报告，不能直接称LW-07全量449已测。


## 最终0016冻结包真实格式复核：新增失败，保持阻塞

授权/审核最终后端完成后，再用实际当前包复核既有真实格式引擎；这不是重复沿用0014旧包成功。工作目录仓库根，P=.venv/Scripts/python.exe、PYTHONIOENCODING=utf-8：

- P tools/check_office_previews.py --exe artifacts/lw08-20261105/frozen-review-final/dist/study_backend/study_backend.exe --test-root .local/lw06-office-final-20261105-01 --runtime .local/release-tools/libreoffice-26.8.1 --docx .local/r3-office-samples-repro/中文公式.docx --pptx .local/r3-office-samples-repro/中文图表.pptx：子命令退出1，office-final-01.log。当前0016启动/受管导入、恶意XML预算拒绝、显式取消已经过，随后DOCX任务failed，“转换未生成有效大小的PDF，原件保留”；脚本因此停止，PPTX本次未执行，不能登记失败或通过。原自编DOCX/hash未替换，失败任务/字节留隔离root。
- P tools/check_spreadsheet_samples.py --runtime .local/release-tools/libreoffice-26.8.1 --test-root .local/lw06-calc-final-20261105-01 --exe artifacts/lw08-20261105/frozen-review-final/dist/study_backend/study_backend.exe：子命令退出1，calc-final-01.log。runtime.verify在实际转换前拒绝“离线转换包含未登记文件”，没有忽略或放宽清单。两个命令的PowerShell驱动最后输出退出码字符串，驱动最终0不代表两个子命令通过。

只读差异检查发现唯一未登记文件program/c144e3c4-093a-4871-8406-1c85c0cfa3f7.dmp，144731字节，前4字节确为MDMP；元数据记录runtime-final-difference.json和runtime-final-dump.json。仅检查名称/大小/头，不展示转储内存。转储在本次DOCX执行后出现，提示原生组件崩溃；根因未定位，不能推断为模型、DLL路径或应用业务代码故障。当前runtime-lock指纹仍147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca，但目录不再通过完整清单校验；原运行时和转储都未删除/移动/重新登记，无组件白名单例外，无新依赖。

上文0014冻结包真实Office/Calc成功、当前XLSX源码/冻结JSON单元格查看成功、全部历史失败均继续保留；它们不抵销本次0016组件集成失败。此项当前为阻塞，LW-06保持进行中，不补造第二页检查或当前Office通过。授权/人工候选后端双Python各468、Flutter153及冻结业务闭环的独立结果见[LW-08报告](../2026-11-05-lw08-authorization-review/report.md)，也不能抵销本项。

下一步保留转储后，在新隔离目录重建同一已核版本的组件，对比源/冻结最小DOCX与子进程环境，定位崩溃并重新验证Office/Calc；不清理原运行时、不绕过清单。实际应用窗口、复杂第三方Office/用户/阶段/安装验收继续待验。本轮没有继续尝试窗口，也未接模型。


## 2026-11-06 PR后继续：冻结进程DLL边界设计

当前版本已按用户授权创建[草稿PR #4](https://github.com/surface-user/StudyWorkbench/pull/4)，以#3为基线，未合并。继续同一LW-06任务，不另开失败重试报告。只读解析既有MDMP的异常/模块目录：异常0xe06d7363、抛出位置KERNELBASE.dll，共132模块，LibreOffice实际加载了冻结包_internal下VCRUNTIME140.dll与VCRUNTIME140_1.dll；不输出栈内存/正文，摘要artifacts/lw06-native-20261106/minidump-summary.json。这支持冻结进程DLL搜索路径污染的判断，仍须修补前后实际引擎验证，不能只凭猜测销项。

[PyInstaller官方说明](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)与[Microsoft SetDllDirectory](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setdlldirectorya)明确：冻结进程设置的DLL目录由其外部子进程继承，单独清理PATH不足。当前Office直接在主后端线程启动，不能为修补而全局更改并发后端的DLL搜索状态。

最小修补设计：仅冻结Office转换增加短命内部--launch-office入口，由原Windows Job在挂起态持有该helper；helper校验固定任务source.docx/pptx、已核运行时入口和配置，清理自身DLL目录后执行固定LibreOffice命令，不接受任意命令，不创建业务库/令牌。自身/soffice.com/soffice.bin均继承同一Job，原取消/90秒/资源预算不变；主后端不改全局DLL状态，普通源进程沿用现路径。仍完整校验每次转换运行时，不将dmp登记或忽略。

为重现实验，保留原组件/转储，以原runtime-lock固定hash147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca逐文件校验并复制全部19417个已登记文件到新.local组件目录，重新完整verify；这是恢复已核测试组件，不改变产品校验规则，不覆盖旧目录。随后按需求/设计补针对helper边界与Job所有权的测试、源/冻结真实Office/Calc矩阵及图像检查，完成后才更新状态。


### 诊断修正：DLL边界与深目录是两项问题

内部helper首轮定向17通过；开发/发行完整各472通过（256.88/236.42秒，backend-01/release-01 XML）；frozen-01构建退出0，133.4秒。重建组件逐19417文件验证，锁文件指纹不变，原组件及原c144转储不动；calc-01通过两表11格/缓存公式/日期序列和原件保持。然而office-01仍DOCX缺PDF，产生新的252e转储，PPTX未到达，不能将“DLL清理完成”当成崩溃修好。

第二个转储只读模块比较确认_internal依赖已经消失，异常仍0xe06d7363，来自mergedlo.dll的WrappedTargetRuntimeException；类名解码仅作诊断，依据[Microsoft异常参数说明](https://devblogs.microsoft.com/oldnewthing/20100730-00/?p=13273/)，不把该实现细节纳入产品。原件/栈内存未进入Git，原始转储保持，摘要exception-class.json。source-debug在独立短目录、未冻结、空DLL目录中同DOCX生成67520字节PDF；short-helper以真实冻结helper在短目录也生成相同大小PDF，Job峰值446685184，仍受1GiB限制。外层Job默认/沙箱外对照均无额外内存上限（outer-job-*.json）；沙箱外office-elevated-01仍失败，排除仅靠权限环境放行的做法。

unfrozen-deep在160字符物理输出路径重现缺PDF（deep-source-result.json），说明不只是冻结本身。仅在同长度目录中把本次Native命令/CWD/临时profile参数替换为GetShortPathNameW取得的同目录别名，os.path.samefile确认同一目录，native输出路径变103字符并生成67520字节PDF（short-alias-result.json）；源码/文件位置不搬动、宏和输入/Job/时限不放宽。既有成功包与首次失败包Office模块规范化code hash、PROFILE hash分别完全相等（old-runtime-code-comparison.json），因此不能归因于本轮业务代码改了原Office配置。

诊断副本中每轮新生成的dmp被按单文件Move-Item归档到artifacts/lw06-native-20261106，同一workspace下显式路径核对、前后SHA256一致；未删除字节、未触碰原组件原c144转储，不在生产校验中忽略/登记dmp。恢复后仍每次完整验证清单，未把诊断实验当正式集成通过。

补丁现在同时处理：主后端不改DLL状态、冻结helper清理自身继承DLL目录；Windows外部Office只使用经samefile校验的任务短路径作为CWD/输入/输出/profile与环境目录，数据库、原件和返回PDF路径保留原长路径。短路径API失败/缓冲区不足时保持原路径，不截断，不允许别名指向另一目录；无短名卷/其他极端路径仍待验。内建安全配置在helper内按输入门禁复核，stdin/out/err不传业务令牌；原件/宏外链拒绝、90秒/1GiB/4进程和Job清理全部保留。

原Windows Job用例已加强为父/孙两层，正常close和所有者os._exit都必须结束两层，原断言保持；descendants-01为17通过23.50秒。短路径API不可用/溢出/错目标等新增4项；alias-01日志/XML记录本次21项定向结果，完整重建/引擎/全量另记。修补仍在本地验证，PR #4当前54ad12b的CI已独立全绿，未把本轮Office代码冒充已送审版本。


### 修补后的实际引擎与完整回归

本轮P=.venv/Scripts/python.exe（3.12.7）、Q=.local/release-venv/Scripts/python.exe（3.13.17），日志统一artifacts/lw06-native-20261106/。以下均使用新隔离目录，不覆盖旧包、失败库或原始c144转储。

| 实际命令 | 结果/退出码 | 日志/产物 |
|---|---|---|
| P -m pytest backend/tests/test_office_launcher.py backend/tests/test_office_previews.py -q（隔离参数见当批工具调用，JUnit为alias-01.xml） | 0，21通过，23.39秒 | alias-01.log/xml |
| P -m pytest backend/tests -q --basetemp=.local/lw06-backend-20261106-02 --junitxml=artifacts/lw06-native-20261106/backend-02.xml | 476通过，255.48秒；JUnit无失败/错误/跳过，会话退出码因上下文截断未收取 | backend-02.log/xml |
| Q -m pytest backend/tests -q --basetemp=.local/lw06-release-20261106-02 --junitxml=artifacts/lw06-native-20261106/release-02.xml | 476通过，234.97秒；同上退出码未收取，不补记0 | release-02.log/xml |
| Q -m PyInstaller --noconfirm --clean --distpath artifacts/lw06-native-20261106/frozen-alias/dist --workpath artifacts/lw06-native-20261106/frozen-alias/build artifacts/lw08-20261105/frozen/spec/study_backend.spec | 日志明确Build complete，133.4秒；同上会话退出码未收取 | frozen-02.log |
| P tools/check_office_previews.py --exe artifacts/lw06-native-20261106/frozen-alias/dist/study_backend/study_backend.exe --test-root .local/lw06-final-中文-20261106-01 --runtime .local/release-tools/libreoffice-26.8.1-recovered-20261106 --docx .local/r3-office-samples-repro/中文公式.docx --pptx .local/r3-office-samples-repro/中文图表.pptx | 0，DOCX/PPTX各2页，PDF67520/46266字节，原件hash、XML预算拒绝、显式取消/重试、缓存/重启、SQLite0016/FK/完整性通过 | office-final-01.log；隔离root四页PNG |
| P tools/check_spreadsheet_samples.py --runtime .local/release-tools/libreoffice-26.8.1-recovered-20261106 --test-root .local/lw06-calc-final-20261106-01 --exe同上 | 0，2表11格，公式缓存/日期/字面值及源字节保持 | calc-final-01.log、隔离root/result.json |
| P tools/check_resource_explorer.py --exe同上 --test-root .local/lw06-ci-resource-20261106-01 --documents | 0，严格schema0016/5节点/原件去重/历史/文档/移除保持/重启 | resource-final-01.log |
| TEMP/TMP=.local/lw06-lifecycle-alias-20261106-01（junction指向本批新real目录）；P tools/check_backend_lifecycle.py --exe同上 | 0，原CI生命周期整链，独占锁/鉴权/Origin/中文作答/EOF/崩溃/迁移及父EOF取消 | lifecycle-final-01.log |
| P tools/check_document_workers.py --exe同上 | 0，真实DOCX/PDF离线文字/图片/公式/页/分题 | document-workers-final-01.log |
| P tools/check_learning_workbench.py --exe同上 --test-root .local/lw06-workbench-final-20261106-01 --media-fixture artifacts/lw09-20261104/fixture.webm | 0，笔记/标记/搜索/JSON/XLSX、授权候选审核与失败收据、重启、整库备份恢复及源hash保持 | workbench-final-01.log、隔离root/result.json |
| Q tools/check_rN_blackbox.py .local/lw06-rN-20261106-01，N顺序1至5，任一步失败即退出 | 0，68/24/42/37/50项公开HTTP断言全部通过 | r1至r5-final-01.log |

上述Office矩阵是修补后新冻结包实际HTTP流程，已不再沿用旧包成功；Calc的XLSX SHA256为c690a23a76211f35405ecc973ae390afa2a54e8ccf0ac434aae19d923123d4b2。实际查看新DOCX/PPTX的首尾四页PNG：中文、DOCX公式/表格、PPTX图表标签及第二页公式未见明显缺失；页图检查不等于应用窗口或普通用户验收。恢复组件本轮未产生额外dmp，完整清单继续通过。原污染组件仍保留原转储，仍不能视为可用组件。

自审覆盖convert调用方office_previews、固定source和输出身份、两种入口、profile精确复核、独立DLL状态、Job全部后代与取消/异常退出、短名缺失/溢出/错目标、环境白名单及源/派生hash。没有新依赖/任意命令入口/HTTP接口/Agent工具；OPTIONS v3不变，因为输入门禁、渲染配置和PDF语义未变化。规范只补架构/组件实际启动约束，不复制测试计数。后端已有Starlette/anyio弃用警告保留。

新exe SHA256 a541135a5299e8cbea5b5c4c4e75ebf6f72d3fdbee5fad8a355edf5bff5026ce；五项改动源码hash和两份完整JUnit统计见final-validation-snapshot.json。Ruff/schema/文档保护及diff检查均退出0；52份Markdown/253本地链接/7锚点、114受保护旧文件均保持。Flutter界面未改，沿用PR #4的54ad12b已实查153/Windows/COM/冻结CI结果，不将其冒称Office修补后的远端CI。

本次具体DOCX深目录故障已在同一引擎/同样本/新冻结API中复验消除，LW-06仍进行中：任意复杂第三方文件、无8.3短名卷/其他极端路径、真实窗口、独立人审/用户/阶段/安装与干净机未验。继续同一PR #4送审，推送后必须实查新head CI；不合并/发行、不接模型，旧失败与原始转储全部保留。
