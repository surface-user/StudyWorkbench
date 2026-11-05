# 资源中心方向：现有架构审查与最小调整方案

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

2026-10-26续开发：用户已授权从R1核查后按R1–R6顺序继续。R2与R3首批实际实现/测试见[续开发记录](resource-continuation-2026-10-26.md)；下方R0/R1授权措辞保留为历史，不能据此要求重复许可，也不表示后续阶段已实现或验收。

日期：2026-10-25（R0审查原记录）。用户随后已确认此最小方案，并仅授权实施R1；进展见[R1设计](r1-design.md)和[验证记录](r1-validation.md)。**下文“本轮不实现/待确认”均指当时R0边界，不表示R2–R6已获本轮实施授权。**

## 结论与差异

保留Flutter + Python模块化单体；当前最需要补的是资源目录/稳定身份、资源标签分派以及题目文件与作答版本的显式关联。现有编辑器式标签外观可复用，但尚不等于文件工作区。

| 审查点 | 代码实情 | 最小调整 |
|---|---|---|
| 工作区组织 | `workspace_shell.dart:415`侧栏为空间列表及学习/导入/媒体总览，无文件树 | 增加资源目录视图，统一添加入口；旧业务视图改为辅助/兼容入口 |
| 标签身份 | `workspace_layout.dart:3`仅id/kind/url/draft，`:76`按kind选单例；shell`:663`按五类页面分派 | 保留tab_id/顺序/关闭历史，增加资源身份和受控viewer，按ID打开具体文件 |
| 生命周期 | `page_host.dart`已用稳定Key的Offstage保留页并关闭释放 | 直接复用，避免重写标签动效/缓存 |
| 资源 | `db.py:76`为固定hash/路径的原件记录；`:127`媒体另表 | 先建轻量目录身份适配层，不强行合表/搬所有字节 |
| 普通MD编辑 | `imports.py:154`将Markdown当纯文本，`:97`读取校验固定hash | 新建可编辑工作文件流程，保留原件；检测外部变更/冲突，不能放宽原件校验 |
| 题目文件 | `markdown_questions.py:35`确认后生成MD；`:75`来源JSON未写题目ID | 新文件内嵌稳定ID和版本格式，旧文件显式确认升级；保留已有MD资源/索引 |
| 可作答题 | `db.py:36/115`的Question/MarkdownQuestion两条链没有映射；MD详情在ImportPage模态预览 | 以ID建立文件映射，复用QuestionDocument作为确认缓存和现有判分器 |
| 历史 | `app.py:122`追加作答含revision，但没有完整不可变题目版本；`learning.py:71`按题目当前内容计算知识点/掌握 | 新作答绑定确认快照，旧记录标记版本未知；追加自评/错误注记，反向导航资源 |
| 解析/播放器 | DOCX/PDF子进程、候选审核、媒体范围/状态/专用播放器已存在 | 改入口/接资源身份；不重复实现后端 |
| Agent | `agent-design.md`原先仅规划总结闭环，无实际模型/工具运行实现 | 扩展为资源范围授权、候选提取/建议/变式草稿；确定性操作仍由普通程序负责 |

审查包括db.py、0001–0006迁移、migrate.py、imports/library/documents/markdown_questions/learning/media_library/workspaces/app，以及Flutter标签/宿主/导入/题目/学习/媒体/WebView调用链、锁文件、PyInstaller与setup脚本。没有读取个人数据库。

## 需要复用与重构的边界

| 模块 | 处理 |
|---|---|
| EditorTabBar / PageHost / 页面活动状态 | 复用视觉、键盘、开关动效、实例和释放测试 |
| WorkspaceLayout / WorkspaceShell / 后端Tab模型 | 增量重构资源身份、树/辅助面板、v1→v2布局兼容；前后端同时变更 |
| ImportPage | 预览/确认UI可拆出复用；总览及独立入口不能继续承担全部资料打开 |
| MediaPage / WebPage | 后端和WebView安全边界复用；把媒体库选择与“打开某媒体”分开，由资源标签传ID |
| QuestionPage / StudyPage | 演示页不是通用题目文件查看器；复用内容块/题目表单，计划统计移为辅助视图 |
| NoteEditor | 复用块编辑和版本冲突规则；它不等于Markdown编辑器，笔记文件化需显式适配 |
| Resource / ImportJob / 拆题编辑 / 读取与导出 | 复用原件、hash、确认/幂等、预算；补资源树、派生来源、编辑保存，不替换整个服务 |
| QuestionDocument / grade / Attempt / AttemptReview | 复用协议和追加评分，补MD适配/确认版本/历史反向链接 |
| data_root / migrate / 打包 | 复用锁、备份、校验与失败保留；转换器须单独证明冻结/干净机可用 |

不提前建立插件框架、通用事件总线、微服务或“AI专属资源库”。拟议结构与兼容步骤见[data-model.md](../../../docs/data-model.md)，按实际阶段落表。

## Word/PPT 转换与打包核查

### 实际环境与探针

- 应用锁定docling-slim 2.142.1/core 2.104.0、python-docx 1.2.0、pypdfium2 5.14.0。开发与发行venv均无python-pptx；虽有Docling PowerPoint后端源码，但其导入守卫提示缺format-pptx依赖。产品documents.py只接DOCX/PDF。不能凭上游格式列表宣称PPT已可用。
- 两个常用Program Files路径与PATH未发现LibreOffice/soffice（不等于穷举整机所有目录）。本机WINWORD/POWERPNT均为16.0.20430.20182，COM调用返回16.0。
- 使用Bundled Python的python-docx/python-pptx生成自编中文样本，仅写`.local/resource-architecture-audit/fixtures/中文路径`；产品venv和锁文件未加依赖。Word/PPT探针在现有Office用户会话存在时跳过，不附加或关闭其文档；本轮两者均实际执行。只调用隐藏的本次实例，关闭自编文件，不发布。
- `Word.Document.ExportAsFixedFormat(...,17)`得到1页PDF；`PowerPoint.Presentation.SaveAs(...,32)`得到2页PDF。PDFium打开/渲染均成功，中文标题/正文可提取，Word表格文字保留。两份DOCX/PPTX源SHA256前后相同。样本是少量中文/英文/公式文本/表格，不包含真实OMML、复杂图表、动画或嵌入媒体的保真矩阵。
- 既有`convert_document`处理同一自编DOCX，得到note/3块并明确无可靠题号，不虚构题目/答案。这验证现有内容提取可以复用，不能证明分页布局。

证据：`evidence/resource-architecture-20261025/word-office-02.json`、`powerpoint-office-02.json`、`pdf-validation.json`。原件/输出PDF/渲染PNG均留忽略的.local，不把导入原件放Git。

### 候选取舍（不是已接入依赖）

| 路径 | 可行性/维护一手依据 | 建议与发行条件 |
|---|---|---|
| 既有Docling + PDFium | [Docling格式](https://docling-project.github.io/docling/usage/supported_formats/)列Office输入与HTML/Markdown输出；本地版本/后端已核，DOCX/PDF有代码 | 首选复用结构提取和PDF渲染；HTML须离线受控适配，不是产品已提供。python-pptx额外依赖和新格式仍待锁定/测试，结构提取不等于分页/幻灯片 |
| 本机Office桌面导出 | [Word导出](https://learn.microsoft.com/en-us/office/vba/api/word.document.exportasfixedformat)、[PowerPoint SaveAs枚举](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.ppsaveasfiletype)支持PDF；本机双格式探针通过 | 可作用户显式触发、已装Office的可选桌面适配。Microsoft对[无人值守/非交互自动化](https://support.microsoft.com/en-gb/visio/considerations-for-server-side-automation-of-office)有明确不支持说明；据此不把它当FastAPI后台/干净机的默认方案，也不把Office随应用分发 |
| LibreOffice独立转换进程 | 官方[命令行](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)支持Windows soffice.com、headless/convert-to/outdir及独立profile | 作为无Office的本地转换候选；本机未发现，未下载、未安装、未实测，未选定版本。需中文/公式/图表/多页/旧DOC/PPT、超时/取消、离线包/体积实证后才能采用 |
| 用户先转PDF/外部打开 | 不新增运行依赖 | 能力缺失时明确后备，不能计作应用内Word/PPT预览已完成 |

新LibreOffice分发的许可不能只写一个标签：官方[许可页](https://www.libreoffice.org/licenses/)说明MPL2.0及组合组件，应按选定版本实际LICENSE/二进制清单审查；体积、维护更新、字体、Windows最低版本与安装策略均待锁定。本轮未作法律合规认证，未把新二进制纳入开发包。

当前PyInstaller仅收集现有Python后端/迁移/内置播放器和元数据，setup仅打包staging与WebView2安装器；没有Office、LibreOffice或外置转换运行时。结论：**已有Office下的转换→既有PDFium可行；无需Office的随包Word/PPT完整预览仍未验证，属于R3进入完成状态前的门槛。**

若采用转换器：有限参数的独立worker，只接服务端解析的资源ID，独立临时目录/profile、明确超时/取消、禁宏/外链策略和缓存来源；转换结束验证PDF实际可读/页数/大小及源hash，不仅看进程退出0。缺组件/加密/损坏/超时留失败记录和原件，离线不上传云端。

## 题目文件设计边界

未来QuestionFile格式有独立的`question_file_version`，不随意把已有QuestionDocument.schema_version改号。建议文件元数据含`question_id`、内容revision、题型、可选科目/知识点、来源资源/定位、原题/变式关系、验证状态；正文是普通Markdown题干/选项/答案/解析，相对图片/附件可迁移。精确语法在R4用可往返样例冻结，不能把本轮建议字段当成已实现解析器。

内容和答案只保留一份权威表示，禁止同时在可见正文与隐藏JSON写两套不同答案。结构化区段可用受限Markdown约定/可读代码块表达，普通环境可阅读；仅校验成功/用户确认的内容编译为QuestionDocument。保留未知元数据，拒绝执行HTML/脚本/宏/任意文件链接。普通阅读保留原内容，不因不能交互而丢弃文件。

既有无答案MD继续可读，不能要求先填答案才登记资源；缺答案的作答路径须扩展当前严格协议并默认待批改，不能绕过标准答案验证。MD外部改动使确认缓存过期，在版本冲突解决前不接受按旧答案的新提交；旧作答和其确认快照仍可读。

## 兼容性风险与最小控制

1. 原Resource哈希保护与可编辑文件存在语义冲突：保留原件，不直接改原文件/hash；新工作文件写入单独做expected hash和恢复对账。
2. Question/MarkdownQuestion目前各自有ID和导入来源：不按标题合并、不删除旧索引；缺ID旧文件需显式升级，冲突进入待处理。
3. attempts复合FK指向questions：先保留现有行/ID/FK，再增加映射和新版本引用；不能先把Question表删除再补救历史。
4. revision并非内容快照：旧记录标记未知，新记录绑定不可变确认版；历史分数不自动重算，知识点取当时版本或标明旧数据缺项。
5. 文件与DB提交不原子：原子文件替换不等于整个操作原子；需可重放的小范围保存记录、保留旧版本与故障注入。
6. 新资源标签不能直接覆盖旧layout：兼容v1/旧utility，缺失/未知占位；现有草稿、网页profile、媒体播放状态要保留。

## 本轮实际命令与验证边界

| 命令/动作 | 退出码/结果 |
|---|---|
| Get-Content/rg检查指定文档、源码、0001–0006迁移、锁文件、打包脚本 | 成功读取；缺少候选工具的命令查询不当作转换通过 |
| Python importlib.metadata/find_spec检查开发及发行venv | 各0；版本如上，python-pptx/win32com未在产品环境安装 |
| Bundled Python生成自编DOCX/PPTX | 0；不改产品依赖 |
| powershell.exe -STA -File .local/resource-architecture-audit/office-probe.ps1 -Kind word/powerpoint | 两个子脚本各1：继承的模块路径下Get-FileHash不可用，未启动Office；首次JSON保留为*-office-01.json，编排器返回0不能视为测试通过 |
| 改用已有pwsh.exe -NoProfile -STA执行同一探针，Start-Process -WindowStyle Hidden，逐个WaitForExit(45000) | 两个子脚本各0，*-office-02.json；没有遇到超时，没有附加用户已有Office会话 |
| 既有venv的PDFium页数/中文/渲染断言 + convert_document(DOCX) | 0；pdf-validation.json。源SHA256保留在转换JSON |
| 原始文档快照 | 已保存requirements/architecture/data-model/agent-design原文到archive，不删除历史证据 |
| 非文档源码/配置/迁移/样本哈希与文档链接检查；git -c core.safecrlf=false diff --check | 均0；124文件hash未变，10份当前文档的67条本地链接无缺失，代码围栏成对；document-review-checks.json、diff-check.log |

探针脚本仅在.local，Office输出/能力证据不代表新应用实现。本轮不执行新DB迁移、不读写个人库、不安装转换器、不运行/重建StudyWorkbench或替换开发包；不以此前UI的61项结果宣称新的资源架构通过。R1–R6方案与验收详见[task.md](../../../docs/task.md)，实现/自动化/人工/阶段状态分别标记。

## 待确认的具体方案

建议批准：受管复制导入与轻量资源目录适配、资源身份标签、复用查看器基础、题目MD确认版本/SQLite历史桥接，依次实现R1–R6。Word先复用结构提取，Office仅可选桌面路径，无Office的转换包在R3单独做受控验证和依赖评审。本轮停在方案审查，不依据旧持续开发授权开始R1。
