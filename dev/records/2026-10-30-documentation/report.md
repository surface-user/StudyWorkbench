# DOC-01 文档治理

## 请求、设计与范围

2026-10-30用户批准正文审查方案，并要求明确report生成粒度、artifacts/evidence边界、实现/规划/待验证、archive读取规则和任务退出条件。只作本地整理；提交、PR、合并、发布不在本轮授权范围，不读取个人库、不创建子Agent。

设计：docs维护现行规范，dev/records承载独立任务/批次报告，dev/archive承载历史，artifacts承载完整原始输出，精选共享证据才放evidence。先保留原文快照/迁移清单，再整合规则、迁移并修复引用，最后核对数据和链接。未改业务模型、接口实现、依赖或测试断言。

## 实现

- 57份docs根Markdown中，14份现行文档整合；43份设计/验证材料迁入dev（3份最近开发跟进，其余归档）。标签用户规范从task完整抽出，保留原文要求；docs新增导航。
- 14份现行文档、README和AGENTS重写前原字节保存在archive/baseline-20261030；既有历史快照移入archive/snapshots。
- 819份证据按原Git纳入状态分开：47份既有共享证据归archive/evidence，772份本机原始产物归artifacts/legacy-evidence；没有整目录晋升共享证据。所有文件迁移前SHA256见[清单](../../archive/relocation-20261030.json)。
- AGENTS/dev规则明确小Bug与同任务重测更新原报告、独立功能新报告、阶段交付批次报告；归档默认不读；架构变更查相关ADR。
- 架构、数据、API、Agent文档分列当前已实现/规划中/待验证；查实际路由/模型补齐资源预检、搜索、删除、原件分析和R4/R5，R6工具保持规划。ADR注明启动、预算及Office后续替代关系。
- task保留R1–R6、近期删除/统一导入、M0/M1启动/硬件/发行和M2/M3/M4数据恢复/格式/下载等遗留；设置实现、自动化、审查、必要人工、报告和PR六项退出条件。旧完整清单留快照供追溯。
- compare_document_parsers.py输出改artifacts/parser-comparison；M0默认截图改artifacts/m0并建立父目录，沿用显式STUDY_EVIDENCE_DIR。更新.gitattributes共享证据路径；CI已使用artifacts，不修改。

## 命令、验证与审查

工作目录D:/computer_work/project/StudyWorkbench，使用既有.venv与固定Flutter SDK。以下为本轮实际执行记录，最后结果继续追加，不把历史测试计数当成本轮重跑。

- Get-Content、rg、git status --short用于只读文档/代码/引用核对。首次PowerShell误用大括号文件展开：退出1；改显式路径后定位源码。随后两份猜测源码文件不存在：rg提示错误，按rg --files定位learning_records.py/office_previews.py；不作为验证通过。
- .venv/Scripts/python.exe .local/reorganize_docs.py：退出0，863文件迁移，目标均在工作区，拒绝覆盖；证据移动时逐项hash一致。后续链接处理中两份原始Markdown被误改，复核发现后已按原SHA256恢复，再进行全量终检。
- .venv/Scripts/python.exe .local/update_docs.py、update_docs_2.py、update_docs_3.py：均退出0，仅本轮文档整合脚本，位于忽略目录，不新增产品工具/依赖。
- .venv/Scripts/python.exe .local/check_evidence.py及restore_raw_markdown.py：退出0；中间结果明确报告两份不匹配，随后恢复并以最终全量检查为准，不将脚本退出0冒充全部断言已通过。

## 状态与交付边界

实现：本地整理完成。自动化：下方定向检查通过。审查：本轮调用路径/文档契约/迁移完整性自审完成，非独立人工批准。人工：用户文档评审待验。PR：本轮仅本地修改，不提交/推送/创建PR；远程PR #1/#2最终head/CI/合并状态未查询，不补造结论。任务保留待验收，不能因为本地文件完成就退出task。

本次不运行业务全量、Windows桌面/构建/安装/干净机，也不改个人数据库、原件、历史失败或发布包。输出路径调整做定向格式/编译及目录自检，不能代替完整Windows原生流程。


## 最终检查（2026-10-30）

- .venv/Scripts/python.exe .local/verify_docs.py：退出0；819份证据SHA256与迁移前逐项相同，16份原文快照原字节保持，363条当前/报告/索引本地链接存在，四份重点文档状态分栏及用户标签规范原文一致。该检查不检查快照内按旧路径解释的历史链接，也不请求外部URL。
- .venv/Scripts/python.exe -m py_compile tools/compare_document_parsers.py：退出0。定向Ruff同文件退出0。runpy加载模块核对OUT精确指向artifacts/parser-comparison，自检退出0，未生成/覆盖样本。
- 固定SDK dart.exe format --output=none --set-exit-if-changed integration_test/m0_test.dart首轮提示需格式化（格式子命令退出1，后续分析不能覆盖此结论）；执行format退出0后复核退出0、0 changed。dart.exe analyze integration_test/m0_test.dart退出0、No issues found。格式器规范化了该文件的回调布局，既有业务断言保留。
- git diff --check：退出0；仅既有Windows LF/CRLF提示。最终按code/source核对/api/active-workspace与Submission.question_version_id，避免在整理时把概念名写成请求字段。原始日志/JUnit/图片不格式化。
- 自审核对范围：报告迁移、链接及原文快照、原始证据hash、任务历史未完成项映射、ADR替代关系、四份文档状态与实际路由/ORM、产物脚本和截图调用点。未新增依赖/迁移/业务API、未减少测试断言；保留.vscode既有未跟踪状态。

下一步为用户评审文档结构与状态表。DOC-01保持待验收；本轮不重复业务全量或Windows实机，已有人工/阶段失败与未验项继续保留。报告不是发布、合并或远程CI验收证明。

终检补充：移除已空的旧证据目录后，链接检查暴露12处指向旧目录的链接（文件级迁移映射未包含目录），verify_docs.py退出1；已按共享证据/本机产物分别修正目录链接，再次完整检查，不把空目录存在当成迁移正确。原命令文本保持历史路径。

最终目录链接修复后verify_docs.py再次退出0（819证据、16快照、363链接、0问题），git diff --check退出0。复核进一步将R6未来验收要求留在规划栏，待验证栏仅描述已有基础服务验证缺口，三方合并/派生恢复未实现项留规划栏。

## 目录职责再次归位（2026-11-04）

用户反馈doc/与dev/再次混乱。本批继续DOC-01原报告，不新建整理任务或报告，不更改LW开发进度/验收结论。检查发现：平行doc/只剩已被采纳方向取代的原评估；docs路线仍大篇幅复制原差异评估；契约混有设计自审/实施补丁；dev索引漏掉方向讨论及R6，原有日期目录没有明确对应任务。

实际整理：

- 将doc/learning-workbench-direction-gap-review-2026-11-03.md移至原方向任务目录的gap-review.md，仅重基相对链接，原评估正文及当时状态不改。初稿曾由用户指定放在doc/是历史事实，在原报告追加迁移说明；只移除迁出后的空doc目录，不删除评估材料。
- docs/learning-workbench-roadmap.md从180行精简为61行，职责限于已采纳范围、依赖及交付目标；10项LW范围/结果表逐行保持，不再复制原评估全文。当前任务/下一项查task，讨论来源查原方向任务记录。
- 契约从199行整理为186行；设计自审两段原文追加到LW-00原报告，保留当时语境；已实现API/字段指向api-spec/data-model，规划协议及安全/数据保护要求继续留在契约。删除的是重复维护入口，不是失败或验收记录。
- dev/README改为放置规则与7项任务记录索引，补齐PLAN-02/R6及原评估入口，保留日期目录和旧PR跟进文件，不为这次整理重命名全部任务目录或提前归档待验收任务。
- AGENTS与docs索引明确不再新增平行doc/、讨论输入归原任务目录、路线不维护任务流水账、同任务继续原报告。task仅更新日期和DOC-01行；其他任务行逐行保持，包括人工待验、历史失败及旧PR义务。

命令与核验（cwd=D:/computer_work/project/StudyWorkbench，PowerShell）：

- Get-Content、rg --files/rg -n、git status --short：定位必读规范、现行路线/契约、原评估、已有治理报告和引用。未把归档内容重新当成当前规范。
- 既有.venv Python内联快照命令退出0：10份本批可能修改文件原字节保存在artifacts/docs-organization-20261104/before/；114份其余dev归档/记录/共享证据建立SHA256清单，记录在protected-files.json。
- 原生PowerShell先验证移动源与目标绝对路径均在工作区、目标不存在，再Move-Item移动单文件；确认doc目录已空才非递归Remove-Item，退出0，未覆盖目标。
- `.venv/Scripts/python.exe artifacts/docs-organization-20261104/reorganize.py`退出0：链接重基、路线提炼、设计自审归位及原报告追加迁移说明，结果见reorganization.json。脚本仅本批产物，Git忽略，不新增产品工具或依赖。
- `.venv/Scripts/python.exe artifacts/docs-organization-20261104/check.py`首轮退出0：43份现行/记录Markdown、210处本地链接/5处标题锚点通过；114份保护文件hash保持，10项LW目标逐行保持，其他任务行保持，评估正文除链接外一致，设计自审原文保留，任务report仍7份。追加本节后再做最终复核，结果继续记本节。

自审：职责、输入材料归属、当前/历史入口、链接和保留断言完成；非独立人工批准。仅本地文档整理，无业务代码/数据库/依赖变更，业务单测、Flutter、Windows构建及真实窗口不适用，不能把LW-01历史229/99等数字当作本批重跑。用户文档复核仍待验；未提交、推送、新建PR、合并或发行。原始运行产物仅新增artifacts/docs-organization-20261104/，未清理任何历史失败现场或个人数据。

下一步按现有task推进LW-02；目录整理继续遵守本报告和dev规则，不按每次对话再产生一份治理报告。

最终复核：check.py再次退出0，43份Markdown/210处本地链接/5处标题锚点、114份保护文件hash、10项LW范围表及其他任务行均保持，迁移评估的链接目标与原位置语义一致；report数量仍7份。git diff --check退出0，仅AGENTS的既有LF/CRLF提示；git check-ignore退出0，本批脚本和清单均被忽略。


## 2026-11-06 用户取消人工测试与开发产物治理

用户明确取消人工测试并要求继续开发，指出项目接近30GB。已停止Computer Use/人工窗口流程；AGENTS、task、testing及ADR0013撤销该退出门禁，ADR0005注明替代关系。历史失败不改为通过；模型仍暂缓，产品中的用户授权/候选审核确认保留。LW-01至05及LW-09不再因人工测试保持待验收，自动化/审查/PR义务继续。

实测清理前27.19GiB：.local 15.335、apps 6.961、artifacts 2.303、dist 2.044GiB。主要是重复构建包、Office组件镜像、逐轮pytest成功副本及Flutter缓存。清单与原始结果保存在artifacts/storage-before-20261106.json、storage-cleanup-plan-20261106.json与storage-cleanup-result-20261106.json；未另建报告或删除源码/个人库。清理前逐个绝对路径验证在workspace内、无Git跟踪文件；遇重解析点仅移除链接自身，不跟随目标。原Office崩溃转储和原runtime-lock先复制并SHA256相等核对，保留在artifacts/lw06-native-20261106/original-runtime-diagnostics；删除的是可重建组件/旧测试副本，不是错误日志、JUnit或失败测试代码。可用Office组件与当前冻结后端各保留一份。

继续开发的防复发修补：pyproject.toml启用现有pytest9的tmp_path_retention_policy=failed，无新依赖。已核对已安装_pytest/tmpdir.py：通过测试teardown清理其tmp_path，失败保留；不会删除产品资料目录。人为构造的两例探针预期退出1：1通过/1故意失败，确认仅失败marker留存、JUnit完整；不是产品回归失败。原Office/Job回归21项退出0（24.47秒），全套回归继续记录实际结果。日志retention-probe/retention-real-20261106.log/xml；不为此重建Windows或再制作人工窗口包。

全量复核：P -m pytest backend/tests -q --basetemp=.local/retention-full-20261106 --junitxml=artifacts/retention-full-20261106.xml，退出0，476通过、264.91秒；回归后该basetemp剩43文件/10824047字节（不再每轮保留约150MiB副本）。Ruff、54份Markdown/268本地链接及git diff --check均退出0；旧Starlette/anyio弃用警告未屏蔽。

清理完成：原生PowerShell按238项明确清单操作，退出0，238项全部移除、0失败。重新遍历不跟随重解析点，目录从27.190GiB降为4.912GiB，减少22.278GiB。唯一干净Office组件恢复到默认.local/release-tools/libreoffice-26.8.1，两个绝对路径均核对在workspace且目标不存在后移动；OfficeRuntime.verify完整19417文件校验通过、指纹不变。当前冻结exe SHA256仍a541135a5299e8cbea5b5c4c4e75ebf6f72d3fdbee5fad8a355edf5bff5026ce，核验和复测命令退出0。旧窗口包、逐轮冻结dist/build、Flutter缓存、旧dist测试包及识别为pytest自动目录的副本已清理；源码、个人库、开发venv、日志/JUnit及精选证据保留。旧报告内被清理的二进制/自动副本路径仅作为历史运行位置，不再承诺永久留存。
