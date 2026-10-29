# R3 Word/PPT分页续开发记录（2026-10-26）

用户允许继续下一步；按R1–R6授权继续实现、自动化和审查，人工及阶段验收统一待验。本批完成受限DOCX/PPTX分页范围，旧DOC/PPT、动态对象、任意复杂版式和完整发行/干净机不据此销项。不创建子Agent、不读个人库、不发布或替换StudyWorkbench-current，保留此前未提交内容。

## 实现与范围

- 固定LibreOffice26.8.1 Windows x64为可选离线运行时；官方MSI SHA256 c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312，374870016字节、Authenticode Valid/The Document Foundation。管理镜像解包退出0，不注册系统安装/文件关联。清单19417文件、1577045386字节（约1.47GiB，不含MSI/清单），完整许可保留，默认安装包不带。
- DOCX/PPTX显式生成派生PDF，复用PDFium分页/缩放；DOCX原结构预览保留。界面轮询/取消/重试、结构与分页切换，标签记录representation/页码/缩放而非页图/令牌。关闭标签停止轮询，后台任务继续，取消单独操作。
- 0009仅追加document_previews，保存同空间来源和可追溯收据。一个worker、最多4待办；缓存按源hash/运行时/选项匹配，源或产物篡改拒绝，重试留新任务；重启标中断、不自动重跑，失败字节不删除。
- 输入32MiB，解压合计128MiB/4096条目/一层静态XLSX；XML单部件8MiB、总计20万节点、深度128，增量解析命中即停止。外部关系（含编码）、宏/XLM/OLE/ActiveX、DTD/实体、拆分DDE字段、外部公式/图片拒绝。图表嵌入工作簿不执行公式/定义名称。转换独立profile，无shell；宏/Python脚本/Windows OLE Automation关闭，链接Never。Job挂起加入再运行，1GiB/4进程，90秒执行限时，取消/后端退出结束本次进程树。
- 实测ActiveContent总禁用会使内部图表变占位、OMML公式消失。现仅在通过门禁且包含内部chart/OMML时启用内部渲染；宏/OLE/外部入口仍拒绝。选项v3防止旧错误产物命中当前缓存；新增真实PDF内容断言，检查Word x²和图表坐标标签。修复前证据保留。

方案和安全边界见[设计](r3-office-design.md)、[ADR0009](adr/0009-offline-office-previews.md)、[依赖](dependencies.md)。输入与Job/profile控制不是完整OS文件/网络沙箱。

## 实际命令与证据

工作目录为仓库根；日志在 docs/evidence/r3-office-20261026。所有pytest均使用独立新basetemp，PYTHONUTF8=1；本机TestClient在受限执行环境会挂起，改在自动审批允许的普通测试进程执行，未删断言。下表路径为实际参数；Windows Flutter命令通过固定SDK dart.exe/flutter_tools.snapshot调用，并运行tools/prepare-windows.ps1加入.local/bin。

| 实际命令 | 退出码与结果 |
|---|---|
| .venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r3-office-all312-final --junitxml=docs/evidence/r3-office-20261026/backend312-final.xml | 0；176通过，90.01秒；backend312-final.log |
| .local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r3-office-all313 --junitxml=docs/evidence/r3-office-20261026/backend313.xml | 0；176通过，91.16秒；backend313.log |
| .venv/Scripts/python.exe -m pytest backend/tests/test_office_previews.py -q --basetemp=.local/r3-office-v3-312 --junitxml=docs/evidence/r3-office-20261026/office312-v3.xml | 0；最终公式/图表与打包改动12项通过，17.67秒 |
| .local/release-venv/Scripts/python.exe -m pytest backend/tests/test_office_previews.py -q --basetemp=.local/r3-office-v3-313 --junitxml=docs/evidence/r3-office-20261026/office313-v3.xml | 0；最终同范围12项通过，16.32秒；不把定向重跑当第二轮全量 |
| flutter test --no-pub（apps/desktop） | 0；74通过，2个非Windows组件用例按既有规则跳过；flutter-tests02.log |
| flutter analyze --no-pub（apps/desktop，最终） | 0；无问题；flutter-analyze-final.log |
| dart format --output=none --set-exit-if-changed lib/document_page.dart lib/backend.dart lib/workspace_layout.dart test/document_page_test.dart integration_test/office_previews_test.dart | 0；format-final02.log |
| .venv/Scripts/python.exe -m ruff check backend tools | 0；ruff-final02.log |
| flutter test integration_test/office_previews_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r3-office-native03 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/r3-office-20261026 | 0；最终原生1项通过，4分52秒；windows-office03.log。显式生成、Word结构/分页、PPT第二页、切标签位置保留及真实截图 |
| .local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath .local/r3-office-frozen/dist02 --workpath .local/r3-office-frozen/build .local/r3-office-frozen/study_backend_v3.spec | 0；最终独立后端study_backend_v3，冻结到新目录；frozen-build03.log |
| .local/release-venv/Scripts/python.exe tools/stage_office_runtime.py --runtime .local/release-tools/libreoffice-26.8.1 --stage .local/r3-office-frozen/dist02 | 0；19417文件复制前后hash/许可清单相同；office-stage.log |
| .local/release-venv/Scripts/python.exe tools/check_office_previews.py --exe .local/r3-office-frozen/dist02/study_backend_v3/study_backend.exe --test-root .local/r3-office-frozen-final --docx .local/r3-office/samples/中文公式.docx --pptx .local/r3-office/samples/中文图表.pptx | 0；默认定位随包组件，PATH仅System32、无开发PYTHONPATH、cwd新目录。Word/PPT各2页，公式/图表内容、原件hash、取消/重试、缓存和重启通过；loopback-frozen-final.log |
| .local/release-venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/r3-office-frozen/dist02/study_backend_v3/study_backend.exe --test-root .local/r3-office-frozen-without --documents --without-office | 0；实际缺组件时Word结构、其他文档、MD工作副本、旧作答/标签/源文件及重启通过；frozen-without-office.log |
| .local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe .local/r3-office-frozen/dist02/study_backend_v3/study_backend.exe | 0；数据锁/鉴权/Origin、追加/重启/崩溃、两次迁移与旧收据/源文件保持；frozen-lifecycle-final.log |
| .venv/Scripts/python.exe tools/check_office_process_cleanup.py --runtime .local/release-tools/libreoffice-26.8.1 --source .local/r3-office/samples/中文公式.docx --test-root .local/r3-office-native-cleanup01 | 0；真实引擎短超时和取消，所属进程句柄确认已结束、源字节不变；native-cleanup.log。探针先完整验证一次运行时，复用该已验证实例仅测结束时序；生产每次仍完整验证 |
| flutter build windows --release --no-pub | 0；42.1秒，windows-release.log；仅证明Release源码编译，不等于完整安装/干净机或该输出目录的组合包验收 |

最后审查增量（不重复扩大无关测试）：双Python分别运行同一Office专项，--basetemp=.local/r3-office-xml312/.local/r3-office-xml313、--junitxml=docs/evidence/r3-office-20261026/office312-xml.xml及office313-xml.xml，均退出0、各13通过（15.31/14.94秒）；最终XML单部件/节点/深度预算覆盖在内。此后用相同PyInstaller参数冻结study_backend_v4.spec，COLLECT目录study_backend_v4，frozen-build04.log退出0。最终 tools/check_office_previews.py 命令把exe改为.local/r3-office-frozen/dist02/study_backend_v4/study_backend.exe、test-root改为.local/r3-office-frozen-xml-final，其余参数不变；loopback-frozen-xml-final.log退出0：恶意深层XML拒绝，Word/PPT各2页、真实公式/图表、取消重试、缓存、重启及原件hash通过。

补齐“转换仍在运行时关闭文档页会停止轮询”的断言后，再运行同一flutter test --no-pub，退出0、75通过/2跳过，flutter-tests-final.log。不是以已取消任务没有计时器来代替运行中释放测试。前表74项为上一次成功回归，最终以75项为准。

原生截图回归另运行相同命令，仅测试目录改为.local/r3-office-native04，等待分页加载结束再取图；windows-office04.log退出0、1通过、2分02秒。之前native03为4分52秒，说明运行时完整校验和机器负载会影响总耗时。此后只加强后端XML门禁，UI行为不变，门禁通过双Python专项及新冻结流程验证。

真实自编输入生成逻辑已归档为tools/make_office_preview_samples.py：Word复用仓库自编OMML/中文/表格/图片样本，PPT含中文表格、静态嵌入XLSX柱状图和第二页公式文字。桌面捆绑Python执行该工具 --output .local/r3-office-samples-repro 退出0；作者工具python-pptx为1.0.2，仅作夹具生成，不新增运行依赖或随产品分发。首轮以同逻辑在.local/r3-office/samples生成的样本用于本批转换。单次原生总时间4分52秒；运行时完整校验另占耗时，90秒限制只计算引擎执行，不应误导成整个任务90秒完成。

## 审查与保留的失败

逐项检查了Office输入→受控工作目录→固定进程→PDF验证→收据→受保护页图→文档页/标签及关闭轮询调用链，以及旧迁移、布局、缓存和可选打包调用方。后端边界包括同空间、额外命令字段拒绝、源/产物篡改、预算、队列、取消/关闭、重启和0008升级/失败备份回滚；未修改历史迁移、未删除失败用例。对照审查前baseline确认0001–0006逐文件hash不变、0008与前批交付hash不变；95个本地文档链接检查通过，证据review-links-migrations.log。prepare-office-runtime.ps1语法解析及错误包hash在解包前拒绝的自检通过；未重复运行完整安装器构建。

- 下载首轮EOF：保留部分文件与日志，续传后完整SHA/签名通过才运行。
- baseline.log/api01.log：受限进程TestClient挂起；api-diagnostic.log在普通本机上下文通过原有测试，终止的仅是本次确切测试进程。
- targeted02.log：28通过、1失败，崩溃测试辅助进程误用系统Python缺项目依赖；改为sys.executable，随后双版本测试通过，断言不变。
- flutter-tests01.log：73通过、1失败、2跳过，新夹具少assets字段；补齐真实返回结构后74通过，未改产品断言。
- direct-probe02.log：打印机设置BIN被保守门禁误拒；仅放行固定printersettings路径，其余BIN/OLE仍拒绝。
- failed-chart-disabled.png、loopback-source01/02.log：原先仅页数/输出成功不足以覆盖实际图表/公式，修复前结果不充当最终保真证明。最终依据v3冻结内容断言与页图。
- math-probe01.log：探针误传pdf渲染模式，转换/公式文字检查已通过，页图参数报422；改用既有pdf-page后math-inspect02.log通过。
- format-final.log：新增截图代码未格式化；format-final02.log通过。失败日志均保留。

## 截图、限制与下一步

[原生Word分页](evidence/r3-office-20261026/office-1.png)、[原生PPT图表](evidence/r3-office-20261026/office-chart.png)、[PPT第二页](evidence/r3-office-20261026/office-2.png)。冻结页图在同目录pdf-word-formula.png及pdf-ppt-chart.png；只包含自编数据。

目前支持受限DOCX/PPTX静态派生阅读。旧DOC/PPT、外部超链接/外链图、宏/OLE、某些旧图片或复杂部件及带公式的嵌入工作簿会拒绝，原件可留存或外部转PDF后再添加。复杂排版/字体、动画/视频和任意第三方文件保真没有承诺。

人工作业、普通用户/干净机、完整发行许可/SBOM/漏洞/签名、安装升级卸载和全阶段验收仍待统一进行；M0历史缺项、完整备份恢复和下载队列不因此清除。下一顺序为R4题目Markdown与已确认版本权威链，继续复用旧Question/Attempt和旧协议，不能自动覆盖答案或伪造旧作答版本。
