# M2/M3 续开发与自动测试（2026-10-24）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

用户授权继续task.md任务、暂不验收，完成后统一验收（ADR 0005）。已完整阅读AGENTS.md、requirements、architecture、question-content-spec和task；使用ponytail技能，未创建子Agent。保留所有既有未提交改动与历史失败，没有提交、推送、发布、合并或删除个人数据。

## 实现

- M2：空间内ZIP资料导出，含原件、SHA256清单、题目/文章与笔记；最多10000资源、128MiB原件、32MiB元数据。它不是作答/任务备份，也尚不能整包重新导入。增加资源列表、孤立原件巡检及用户显式登记恢复；不删除原件。失败可重解析，已确认内容不可覆盖；失败保留旧预览。
- 导入先持久化原件与parsing任务，再在写事务外解析，避免25秒解析占用SQLite写锁。读取/解析放到工作线程，不阻塞ASGI事件循环；重启把中断任务标为failed，可重试。提取图片按空间和内容哈希复用，正式引用仍检查归属/MIME/文件校验。
- 自编真实DOCX/PDF位于contracts/samples，由compare_document_parsers.py生成，含文字、公式、表格、图片和两页内容，均非真题/个人资料。两候选实际输出与测量在parser-comparison.json及四份Markdown。选用Docling slim Word后端，保留中文、OMML公式和提取图片；PDFium逐页提取文字并生成原貌图，保留扫描图形与页码。PDF样本不含中文，不将对应false指标当成中文能力结论。
- 文档在可抛弃子进程中离线处理：8MiB原件、25秒超时、PDF最多20页，Word解压64MiB/2000项，图片尺寸/总量限制；拒绝Word宏、嵌入对象、外部引用、复杂图表及非PNG/JPEG媒体，保留原件并提示转换PDF。不加载模型、不联网抓取资料，不调用Office/LibreOffice。
- 手动表单覆盖七类题目和阅读共享材料，仍须预览确认；支持笔记JSON、纯文本笔记编辑及HTTPS链接记录。笔记编辑检查内容版本摘要，冲突409，导入原件不变。富内容笔记不进入纯文本编辑器，防止丢失图片/公式/表格。
- Dart离线使用Python同步导出的两份Schema，并检查答案、来源、表格、公式、共享文章/来源链；真实API读题及导入预览调用检查。Python继续负责最终写入与资源权限。Schema资产纳入漂移检查，无新增Pub依赖。
- M3：新增真实题库学习页（新建标签页→题库与学习计划），按科目/题型/知识点/错题/到期筛选，保存组卷任务并按作答推导进度，显示知识点与错题统计。稳定掌握需连续3次全对，复习间隔为1/3/7/14/30天；待批改题不重复进入到期列表。这是待校准规则，不是学习效果证明。
- 判分集中在Python：多选精确集合，填空逐空exact/trim匹配并按正确比例计分，阅读按response_kind；计算/证明/主观默认待批改。question_revision防陈旧提交，request_id防同一答案重试重复保存；有意再次作答需“开始新一次作答”。人工评分另表追加修订，保留原始作答/分数和全部修订。
- Alembic 0004新增可空版本/提交编号、评分修订与任务表；0002→head与0003→head均验证备份/保留，旧版本断言更新到0004，没有删除测试或降低数据保持断言。

## 实际命令、退出码与证据

仓库根D:/computer_work/project/StudyWorkbench，分支codex/m1-workspaces-tabs。Python命令使用PYTHONUTF8=1、TEMP/TMP=.local/tmp；每次pytest使用新basetemp，历史失败不清除。Flutter在apps/desktop运行，TEMP/TMP同上，Windows构建PATH增加.local/bin且NUGET_SCRATCH=.local/nuget-scratch。实际Flutter启动器为SDK内`dart.exe flutter_tools.snapshot`（D:/computer_work/Tools_work/flutter/bin/cache），避免批处理启动器阻塞；读取SDK锁文件需要沙箱外工具链权限，自动审批允许执行，无需用户人工验收。

证据目录：[m2-followup-20261024](../../../artifacts/legacy-evidence/m2-followup-20261024)。

| 实际命令/过程 | 退出码与结果 | 日志 |
|---|---|---|
| `.local/release-venv/Scripts/python.exe -m venv .local/parser-benchmark`，随后尝试安装 | 1；ensurepip失败、隔离环境无pip | parser-install.log，原终端错误保留；后用已有pip的--python选择目标环境 |
| `.venv/Scripts/python.exe -m pip --python .local/parser-benchmark/Scripts/python.exe install "markitdown[docx,pdf]==0.1.9" "docling-slim==2.142.1"`，再安装python-docx/rtree/pylatexenc | 0；仅候选环境 | parser-install-02.log、parser-extras-01.log |
| `.local/parser-benchmark/Scripts/python.exe tools/compare_document_parsers.py`，HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1 | 0；四组真实转换 | parser-comparison-01.log/json及四份md |
| 两运行环境安装锁定Docling/PDFium/Word/Pillow依赖 | 0；版本/许可另见dependencies.md及parser-dependencies.json | runtime-install-01.log、release-runtime-install-01.log |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_library.py -q --basetemp=.local/m2-library-01 ...` | 0；初始3项通过 | library-01.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_documents.py -q --basetemp=.local/m2-documents-01 ...` | 1；3通过、PDF失败 | documents-01.log/xml；PdfTextPage不支持with，修为try/finally close |
| 同文档测试，basetemp=.local/m2-documents-02 | 0；4通过 | documents-02.log/xml |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m3-final312-04 --junitxml=docs/evidence/m2-followup-20261024/backend-04.xml` | 0；107通过 | backend-04.log/xml |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m3-final313-05 --junitxml=docs/evidence/m2-followup-20261024/backend-05.xml` | 0；107通过 | backend-05.log/xml |
| `.venv/Scripts/python.exe -m ruff check backend tools --fix`（初次与后续） | 初次修2项导入排序，最终0且无更改 | ruff-02/03.log |
| SDK dart.exe `format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test` | 0；29文件无更改 | format-final-02.log，之前format-final.log保留 |
| Flutter `analyze --no-pub` | 首次1（SDK锁权限）；后续1（格式提示）；最终0，No issues found | analyze-01/02/03.log、analyze-final.log、analyze-final-02/03.log |
| Flutter `test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m3-pipe-tests` | 0；32通过，含真实管道/迁移、七类Dart协议、录入表单、多选和幂等重试 | flutter-tests-final-02.log；此前31项flutter-tests-02/final.log及定向9项flutter-targeted-01.log保留 |
| Flutter `build windows --release --no-pub` | 0；最后录题表单修复后78.9秒 | windows-build-01/02/03.log，原插件CMP0175警告保留 |
| `packaging/windows/build-backend.ps1` | 0；最终冻结149秒；包含必要包元数据 | frozen-build-01/02.log |
| `.local/release-venv/Scripts/python.exe tools/check_document_workers.py --exe dist/study_backend/study_backend.exe` | 0；受限PATH、无开发Python，DOCX中文/公式/图片与PDF页数/图片断言通过 | frozen-documents-01/02.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | 首次1（忘记仓库TEMP，沙箱C盘临时目录拒绝访问）；设置TEMP后0；最终0 | frozen-lifecycle-01/02/03.log |
| 独立新建`dist/StudyWorkbench-M3-dev-20261024-200157`，复制当前Release桌面（排除旧backend）和当前冻结后端；`.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage <该目录>` | 0；1267文件哈希清单、71个构建环境包，含PDFium许可目录 | release-inventory-01.log、dev-stage.txt及目录内build-inventory.json；构建包清单不等于实际模块SBOM |
| `git diff --check` | 0 | diff-check-final.log |

首次`dart.bat format`在工具链受限环境阻塞，已中断自有会话（退出1）；后续只用SDK dart.exe。它不作为格式通过证据。pytest持续有Starlette/AnyIO弃用警告，未隐藏。最终CI新增冻结文档子进程检查，但未推送/未触发远程Actions。

## 审查、剩余任务与验收边界

自查并补测：提取图片没有import_job时再上传的去重分支；确认时检查笔记附件；失败/中断原件恢复；元数据导出预算；评分跨空间隔离及不可变原作答；幂等提交冲突和陈旧版本；旧0003笔记/作答迁移；采集PDFium BUILD_LICENSES，避免只按LICENSE文件名收集。

最终自查给录题文本框增加按字段标签区分的Key，避免切换题型复用原选项内容为填空答案。新增真实控件切换回归，32项完整Flutter测试通过。最后构建完成后更新独立开发目录，重新生成清单（release-inventory-final.log）；stage-check-final.log验证桌面exe、data/app.so及冻结后端均与当前构建/清单哈希一致，并检查18份PDFium许可文件。前一次复制可能早于编译结束，所以最终另行等待完成再复制/校验，不以中间快照交付。

仍待开发：Word实际分页/复杂表格和图片位置保真、富内容笔记及既有题目的版本编辑、分块大原件与更广样本回归；科目知识体系、富内容作答和历史/统计大库性能；M4下载/媒体完整链路、M5可选授权AI闭环。yt-dlp预备安装不算M4实现。未将这些任务标为完成。

人工、阶段验收、真实文件选择/保存对话框、DPI/性能、默认用户目录启动、安装/升级/卸载、干净机均未执行；M0/M1历史失败不因上述通过而清除。没有启动产品窗口让用户验收，没有将源码、组件或隔离冻结结果冒充普通入口成功。

Windows编译与冻结产物均为本地开发证据。若dev-stage.txt记录了本轮独立开发目录，目录内匹配当前桌面与后端并生成许可/哈希清单；它不是正式setup或已验收发行。旧M1/M2安装包保留，不将其改名冒充本轮完整产品。继续按task.md未完成项开发，完成后再统一人工验收。
