# 用户文档逐题Markdown首批实现（2026-10-25）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

用户澄清：题目主要来自用户自定义导入文档，识别之后裁切并以MD逐题存储，PDF/Word同等优先。已停止把既有题目版本编辑当作当前主线；本轮该方向尚未修改代码时收到澄清。已阅读AGENTS.md及四份基线文档，按ADR0005继续实现/自动测试，人工及阶段验收仍统一待验。沿用ponytail技能，不创建子Agent，不提交/推送/发布或操作个人数据，保留既有未提交改动。

## 本批结果

1. PDF与DOCX同时接入编号题目候选。PDF按单栏原版面区域裁图、附文字、保留页码/归一化区域；跨页到下一题号前归入同题。DOCX按内容顺序保留文字、OMML公式、图片及Markdown表格，支持显式题号和可恢复的自动编号。Word不是分页截图，PDF文字不冒充公式识别结果。
2. “导入资料→选择文件→检查拆题，逐题存为Markdown”逐题预览，可取消选择错误候选，再确认入库。整篇另存笔记是独立操作，不再把整篇笔记称为逐题入库。新增“本地题目知识库（Markdown）”标题检索/分页/独立打开，原来的结构化练习题入口保留兼容。
3. 每题一个`questions/<id>/question.md`与相对`assets`目录，UTF-8，包含源文件/SHA256/来源位置/未验证标记。不要求答案或题型，不虚构标准答案；Alembic0005新增独立markdown_questions索引，不修改原作答/题目。MD本身作为Resource校验，原件保留。
4. 确认校验预览摘要、严格选中下标、空间、原件和附件；相同确认幂等，不重复生成。资源API鉴权/Origin边界不变。ZIP导出带每题MD与相对图片，离开数据目录仍可打开，实际导出含副本仍受128MiB预算。
5. 自编真实样本`contracts/samples/numbered-questions.docx/pdf`由`tools/make_question_samples.py`生成，含两题、Word公式/图片/表格、PDF跨页条件；不是授权真题或个人资料。

格式、API和限制详见[逐题MD规范](../../../docs/question-markdown-spec.md)。没有新增依赖；仍使用已锁定Docling、PDFium、Pillow及python-docx。

## 实际命令与退出码

目录D:/computer_work/project/StudyWorkbench，分支codex/m1-workspaces-tabs。证据：[m2-splitting-20261025](../../../artifacts/legacy-evidence/m2-splitting-20261025)。Python设置PYTHONUTF8=1，TEMP/TMP=<仓库>/.local/tmp，每次pytest新basetemp，不清除失败。

Flutter工作目录apps/desktop，实际入口为`D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot`，下表简称flutter。SDK锁/Windows工具链所需访问由工具自动审批。

| 命令 | 退出码/结果 | 证据 |
|---|---|---|
| `.venv/Scripts/python.exe tools/make_question_samples.py` | 0，生成两种真实自编样本 | 原工具输出及样本文件 |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_documents.py -q --basetemp=.local/m2-splitting-docs-01 --junitxml=docs/evidence/m2-splitting-20261025/documents-01.xml` | 1，3通过/Word图片保持失败 | documents-01.log/xml |
| 同时跑test_documents.py/test_markdown_questions.py，basetemp=.local/m2-splitting-targeted-02、xml=targeted-02.xml | 1，7通过/Word表格测试错误假定空格格式 | targeted-02.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_markdown_questions.py -q --basetemp=.local/m2-splitting-targeted-03 --junitxml=docs/evidence/m2-splitting-20261025/targeted-03.xml` | 0，4通过 | targeted-03.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m2-splitting-full312-01 --junitxml=docs/evidence/m2-splitting-20261025/backend312-01.xml` | 0，115通过，最终自动编号补测前 | backend312-01.log/xml |
| 同全量，basetemp=.local/m2-splitting-full312-02、xml=backend312-02.xml | 0，116通过 | backend312-02.log/xml |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m2-splitting-full313-02 --junitxml=docs/evidence/m2-splitting-20261025/backend313-02.xml` | 0，116通过 | backend313-02.log/xml |
| `.venv/Scripts/python.exe -m ruff check backend tools`，前序同命令--fix | 0，均All checks passed | ruff-01/final/final-02/final-03.log及原输出 |
| SDK dart.exe format新增拆题测试，首次 | 1，多一个右括号；修正后0 | 原终端输出，format-targeted-02.log |
| `flutter test --no-pub test/question_split_dialog_test.dart test/import_page_test.dart` | 0，9通过 | flutter-targeted-01.log |
| `flutter analyze --no-pub` | 0，No issues found | analyze-01.log |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m2-splitting-pipe-tests` | 0，42通过 | flutter-all-01.log |
| 最终`flutter analyze --no-pub`及全部`flutter test --no-pub`，同根定义、DATA_DIR=.local/m2-splitting-pipe-final | 各0；静态无问题、43项通过，含真实管道及拆题入口→保存→独立题目打开 | analyze-final.log、flutter-all-final.log |
| SDK dart.exe `format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test` | 0，33文件无更改；之后新增入口测试另经format | format-final.log、format-test-final.log |
| `flutter build windows --release --no-pub`，PATH增加.local/bin、NUGET_SCRATCH=.local/nuget-scratch | 0，50.7秒 | windows-build-01.log |
| `packaging/windows/build-backend.ps1` | 0，137.5秒 | frozen-build-01.log |
| `.local/release-venv/Scripts/python.exe tools/check_document_workers.py --exe dist/study_backend/study_backend.exe` | 0；两种旧样本及两种编号样本均通过，无开发Python PATH | frozen-workers-01.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe`，首次 | 1，新增检查错误要求无图的Word第二题也含图片链接 | frozen-lifecycle-01.log |
| 同冻结生命周期命令，修正为有图则必须有链接、无图不得伪造链接 | 0，真实API拆题/MD文件、重启/崩溃/两次迁移字节保持、鉴权/EOF通过 | frozen-lifecycle-02.log |
| PowerShell新建独立dev目录，复制当前桌面（排除旧backend）及新冻结后端；`.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage <目录>`，比较exe/app.so/backend三份SHA256 | 0；1269文件清单、71构建环境包，三份哈希匹配；构建包清单不等于实际二进制SBOM | dev-stage.txt、inventory-01.log、stage-check-01.log |
| `git diff --check`，首次 | 2，data-model.md新增末尾空行；已修正，原日志保留 | diff-check-01.log |
| `git diff --check`，收尾 | 0，换行提示保留 | diff-check-final.log |

Word图片修复依据：Docling把样本图片标为INVISIBLE内容层，默认iterate_items不返回它；按内容树含所有内容层遍历后保留顺序，未修改上游/缓存。表格测试改为精确验证三行及每个单元格值，不再错误绑定列对齐空格，内容保持要求未降低。冻结生命周期检查也明确验证图片存在与MD链接一致性，原失败均保留。

旧0002/0003迁移回归将动态head/备份目标断言更新为0005；原记录、备份、外键、旧版本数据内容断言保留。Word/PDF测试验证预览零入库、逐题独立落盘、公式/图片/表格、PDF跨页和下一题不串入、相对图片实际存在、导出文件匹配、重启/重复确认/跨空间及鉴权边界。

## 验收边界与下一步

实现：本批显式题号首版完成。自动化：以上实测。人工/阶段：未验收，task.md整体仍未完成；M0/M1旧失败不因本批通过而消除。

无OCR、稳定多栏/复杂编号、共享阅读材料自动归组、可视化手动边界裁切/合并拆分、MD编辑回写、正文全文检索或自动转为判分题。题号前的卷头/共享材料未自动归题，原件/整篇预览保留并提示；错误候选目前只能取消选择。文件预算沿用8MiB/20页/25秒，不能宣称适配任意试卷。派生文件写入中断后的专门孤立目录巡检尚未完成，不自动删除它们。

本机dev目录是新的桌面+冻结后端开发产物，未制作正式setup，未实际启动产品窗口验收；默认用户目录、系统提示、干净机/安装卸载、DPI/性能仍未验。下一批继续当前主线：可调整边界与合并/拆分、共享材料关系及更广Word/PDF样本，再处理OCR和检索；既有题目版本编辑后置。

本机开发入口：`D:/computer_work/project/StudyWorkbench/dist/StudyWorkbench-MD-dev-20261025-f5c4d39e/study_workbench.exe`。同目录backend/data/DLL/licenses必须一起保留；它不是已验收发行包。新建数据目录或默认目录的实际桌面启动行为仍待人工/后续验收，冻结隔离目录通过不代替默认普通入口验收。
