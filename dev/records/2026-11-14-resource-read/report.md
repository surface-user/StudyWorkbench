# R6-01 通用资料受控读取

## 来源与范围

本任务承接task中READY的R6-01，先交付R6-01a设计，不接模型、凭据或远端服务。基于已验收#55 6d1078f8eca2923bb0d77a76136f0b8f5e921738/tree49028e80314a23c9b7fc3ecfcfc4ca6084636691，将498个blob逐一复制校验到独立resource-read-contract副本，保留旧根checkout/用户原件。#55当前CI43583174480成功是父项证据，不冒充本设计重跑。

按AGENTS及requirements/architecture/question-content-spec/task、agent-design/API/学习契约/数据模型核范围，读取实际agent_access、markdown_notes、learning_marks、learning_search、db.Note及library.NoteEdit。现有analyze_attempts只读指定作答；自由MD是资源节点，旧notes是富内容JSON，标记/关系另有稳定身份/版本。假设database.py/notes.py/annotations.py/main.py的只读搜索返回不存在后，已改按实际文件清单核对。首次文档patch因旧段落上下文不完全一致失败，无产品变更；改用完整标题/旧语句唯一锚点更新，保留错误事实。

## R6-01a设计与后续

唯一现行契约归docs/agent-design.md“规划中，R6-01”章节，不把本报告再作平行规范。read_resources与analyze_attempts用途隔离、共享进程配额/期限/撤销；resource_node/legacy_note/learning_mark封闭选择默认元数据，正文单独明确已保存版本，原件/工作副本/旧富内容不混权威。首批纯文本/Markdown/旧笔记/标记，其余格式元数据及后续provider条件单列；关联/内部URI/附件不扩权。

预算沿旧授权64KiB单正文/1MiB规范上下文及既有TEXT_LIMIT/富内容深度16，累计文件I/O16*TEXT_LIMIT含核验重读；全量失败不静默截断。服务端版本/指纹与空间/状态读前后重验，不回读任意路径/URL或执行外部处理，不缓存进库/备份或远端传输。撤销不删持久候选；临时grant不恢复。当前旧API/模型/备份格式均未改变。

后续API/封闭提供器、普通UI确认/撤销、源码/冻结/整库无模型回归分别拆小PR；未支持格式另列依赖，不把有限文本读取当全格式或R6整体通过。父任务保持IN_PROGRESS，未选模型/语义场景不纳入本项。

## 验证与交付

本切片仅四文档：agent-design、task、dev索引和本报告。没有产品/测试/依赖/迁移/API修改，不以镜像实现的测试替代文档核对。提交前核全部498基线/仅四文档、两锁/其他原blob、Markdown引用/锚点、任务ID/依赖和Git空白，再执行Schema漂移检查；实际结果及独立PR/current-head CI另记，未执行前不写通过。

R6-01a REVIEW，当前独立草稿PR与head CI待交付；代码审查暂缓、人工取消、未合并/发行。无模型/远端工具或全格式支持结论；后续本任务实现/重复测试/PR跟进继续本报告。


### R6-01a 实际文档检查

2026-11-14，工作目录为独立resource-read-contract：共享Python执行tools/export_question_schema.py --check，退出0，现行题目Schema无漂移。根执行artifacts/goal-20261112/check_resource_read_contract.py，退出0：499文件/仅四文档变更、495原blob保持，115本地引用/4锚点/61唯一调度行通过，Git空白、旧两锁/当前API/架构/数据模型保持。最初任务链接标题少“受控”二字，在提交前改为精确当前标题锚点后核通过；无业务或测试断言修改。

任务表同步已独立有限验收的#54/#55、#52 v2公网失败BLOCKED及#56待CI的REVIEW，不把其他PR工具合并到本分支；M3-03d从通用READY分组拆出但保留其单独条目，避免与现行状态矛盾。R6父项仍IN_PROGRESS，a转REVIEW，b/c/d/e按各自前置保留BLOCKED，不记实现完成或人工通过。

本切片没有运行新的本地产品/模型/窗口测试，具体原因是仅定义规划契约、产品源和全部测试保持父#55原blob；本head完整CI仍必须运行。独立草稿PR/current head CI待提交核验，不以父项绿灯代替。

## R6-01b 封闭授权与首批文本API

R6-01a已由主Agent核#58最终13f4163b0cdf01d1dc916d560969243d19671577/tree4faa168c6128309decb6fdd1cfbe5d65998062b5、CI43585526915及499原blob，有限设计DONE。本实现从该精确499文件复制到独立resource-read-api，不修改旧根checkout/用户原件；原报告完整前缀保留。必读现行开发约束、需求/架构/题目协议/task，并核Agent/API/模型、实际agent_access、db、imports、document_files、learning_marks、learning_search、markdown_notes及现有授权/候选测试。

沿既有AgentAccess路由/锁/内存grant增加封闭read_resources，与analyze_attempts共享100配额/期限/撤销且用途隔离；旧输入/返回及候选接口保留，新授权不能用于作答候选。创建即核固定投影指纹，读取重核同范围/版本/空间/到期；不存正文镜像、授权、模型、配置或新表，不新增依赖/迁移。新resource_grants仅复用既有身份/版本/富内容投影和受管路径守卫；未支持格式只允许元数据。元数据取数据库安全字段，不打开正文/工作文件/附件；文件存在/hash不在元数据校验声明内。

纯文本明确原件或已保存MD工作文件，严格hash，MD/TXT可选现行LF原文行；不保存草稿或默认为最新。旧笔记先核结构字节预算，再按已有Content验证和note_text投影；标记只读本条当前备注/位置，不读creation_content或目标，位置始终未验证。缺失/墓碑/跨空间、未知结构、超限、非法路径、非普通打开描述符和读中变化整体拒绝，保留资料；不宣称全局原子文件系统快照。64KiB正文/1MiB最终JSON/1MiB源文件/16MiB累计文件I/O含重读共享预算，别名不重置预算，超限不截断。

调用范围包括AgentAccess判别输入/旧调用者、封闭提供器、新自动化测试、现有check_api_errors真实源码/冻结HTTP探针及API/Agent/架构/数据模型/task。复用既有CI的Frozen API步骤，无新工作流。没有Flutter产品修改或普通资料确认界面，R6-01c/d和其他格式e继续分别交付，不把本项当整体R6完成。

### 实际命令与原失败

工作目录resource-read-api；Q=`../starlette-fix/.local/starlette-q-isolated/Scripts/python.exe`（3.13.17），P为同位置starlette-p-isolated（3.12.7），工具解释器=`../../release-venv/Scripts/python.exe`。测试设置PYTHONDONTWRITEBYTECODE=1、PYTHONPATH=backend，原始文本/JUnit/自建数据均在artifacts/r601b或.local，Git忽略。以下所有真实路径由本任务自建；链接测试经原生权限执行，不修改系统设置。

- 旧test_agent_access.py/test_analysis_context.py先跑10通过。首次resources-q01为16通过/4测试样本失败：3个新fixture在Session关闭后读取过期ORM id，另1个重复Resource违反既有workspace/hash唯一约束。捕获id并用多个节点别名引用同一Resource，保留唯一约束和原断言；不改产品数据模型。q02为22通过，q03含旧授权35通过。
- q04/p04把既有test_analysis_review.py误写复数，pytest退出4、未收集；按rg实际清单纠正，q05/p05各48通过。首次Ruff发现两个新测试未用import，删除或实际使用后通过。上述失败原记录保留，未删除测试/降低断言。
- 添加真实os.pipe打开描述符负例和无阻塞/不跟随的可用平台open标志后，Q执行`-X utf8 -m pytest backend/tests/test_resource_grants.py backend/tests/test_agent_access.py backend/tests/test_analysis_context.py backend/tests/test_analysis_review.py -q --basetemp=.local/resources-q06 --junitxml=artifacts/r601b/resources-q06.xml`，退出0：49通过/2既有弃用警告，含28新增用例和实际目录联接。完整双版本回归另列最终结果，不以此替代。
- Q执行`-X utf8 tools/check_api_errors.py --test-root .local/resource-http-source01`，退出0：57项/31独立错误ID，真实HTTP、元数据/正文、错用途、额外字段、鉴权/Origin、撤销、重启授权不恢复及旧媒体/收据保持。
- 首次误用Python执行build-backend.ps1，SyntaxError退出1，未构建；改原生PowerShell执行`./packaging/windows/build-backend.ps1 -Python <Q>`，退出0。新生成包经check_frozen_sources：45个业务模块及嵌套代码/常量等于本次源码。
- Q执行`-X utf8 tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/resource-http-frozen01`，退出0：同57项/31错误ID及重启授权不恢复，frozen=true；不是旧包冒充。Ruff检查本项四个Python文件退出0。
- 探索中数次猜测旧文件名/检查脚本相对目录错误返回不存在，未改产品；均改用rg清单及根绝对目录。原始输出保留，不将不存在命令写成成功。

当前实现已形成；完整回归、源码包指纹、文档检查、独立草稿PR和当前head CI完成前保持IN_PROGRESS/待交付。代码审查按用户暂缓，人工测试已取消；不合并/发行，不接模型或凭据。

### R6-01b 最终本地结果

Q/P分别执行`-X utf8 -m pytest -q --basetemp=.local/full-q01`或`full-p01`，带各自artifacts/r601b/full-*.xml：均退出0，各1216通过/77子测试通过/4警告（Q478.90秒、P504.06秒），无跳过/失败。4警告为既有httpx/BlockingPortal弃用和两个重复ZIP负例。新增28测试均执行；未把历史样本失败删除或改记通过。

工具解释器执行`tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/resource-library-frozen01`退出0：真实冻结数据锁/损坏与孤立字节检测、原件/持久业务数据保持、只读恢复预览、旧保存/合并冲突、Markdown/Office/下载容量报告均保持，不修复/删除。`tools/export_question_schema.py --check`及`-m ruff check backend tools`退出0。Flutter产品/测试及依赖锁未改，本地不重复无关联Flutter构建；当前head CI仍必须执行全部既定检查。

本次实际新study_backend.exe为22589083字节，SHA256=c66a0be1f525c1b1a6e822ce09186e9bacbf9e3a70b27df4bb2a35d0a984ca9c；45模块核源和frozen HTTP57对应该包。不是旧#49/#53包，不宣称已组合后续其他平行PR、完整SBOM/签名或发行。当前task转REVIEW，独立草稿PR及当前head CI继续核验，c/d仍不冒充已完成。

根执行`artifacts/goal-20261112/check_resource_read_api.py`退出0：501文件/10变更/491原blob保持，135本地引用/7锚点、61唯一调度行和48任务前缀集合保持；旧报告完整前缀、两依赖锁/工作流保持，Git diff --no-index --check逐变更文件通过。发布仅这10个源码/测试/现行文档/原报告，生成包、日志、样本库和临时grant不上传。全部原工作区未提交文件保持。独立PR只交付本API，不组合平行Office/下载/SBOM任务。

## R6-01e1 PDF及Office派生页文字层设计

### 基线与只读调查

主Agent批准先设计原PDF或已ready Office派生PDF的单明确页文字层。本切片先只读#58最终13f4163/tree4faa168的精确499文件副本resource-read-formats-plan，完整读取AGENTS、requirements/architecture/question-content-spec/task和Agent契约、学习锚点、API/数据模型及相关源码。随后按主Agent要求改用刚发布[PR #63](https://github.com/surface-user/StudyWorkbench/pull/63)最终ca61a8da28c87c90236217d7c1d57b8c0582c4de/tree1c911618af5dd3359e17e4932ca1abdc54ca9331，逐501原blob新建resource-read-pdf-plan；旧副本/根/父API工作目录均保留，不覆盖其他任务。父#63当前CI43594836585当时仍运行，不能先记b DONE或用父绿灯代替本项CI。

新基线AGENTS/requirements/question-content-spec与已完整读取的#58逐字节相同；新architecture/agent-design完整重读，task/API/模型及父报告所有变化逐项重读。API/架构/数据模型保持#63首批资料文本API已实现状态，不将本设计的拟议字段写成现有接口。agent-design开头两句继承的“通用资料未实现/旧笔记标记未入grant”与其正文及#63代码不符，在本次同一现行契约内收敛为已实现首批文本API、其余UI/格式仍规划中。

实际调查入口：documents.py、document_view_worker.py、document_files.py、office_previews.py、learning_marks.py、imports.read_resource、db.DocumentPreview及父#63 resource_grants。PDF普通查看仅页数/位图；拆题提取会整篇扫描、生成图片/候选，不具备授权单页正文/引用边界；DOCX结构没有可信原页码。Office read_pdf核源/派生hash但按普通阅读上限读取，无授权共享16MiB预算；不能未经适配直接当正文提供器。LearningAnchor v1已有pdf_page和office_pdf_page，后者明确源hash/派生hash/preview_id，不需要伪造行/区域或改变书签协议。

只读搜索最初猜resource_access.py不存在，改用实际resource_grants.py；无源码/断言变更。稳定版pypdfium2在线文档显示5.15.2，不能当已锁5.14.0；另核已安装5.14.0的textpage.py原始源码及[同版本官方源码](https://raw.githubusercontent.com/pypdfium2-team/pypdfium2/5.14.0/src/pypdfium2/_helpers/textpage.py)：get_text_range仅UCS-2、默认ignore且可能增删字符，GetBoundedText为先计数/后UTF-16分配。故设计要求预算内精确分配/严格解码，不直接复用默认丢字符或无上限辅助函数；PDFium取字不提供布局/阅读顺序分析，不承诺视觉保真。

### 设计范围及触点

单一现行规划契约写agent-design的R6-01e1小节，task拆e1/e2/e3，本报告只记录依据/命令与限制。批准最小三文档，无新报告或dev索引重写；已有索引已指本原报告。原b报告完整保留，所有产品/测试、锁、工作流、API/架构/数据模型原blob保持，不新增依赖、迁移、持久正文或授权记录。

设计固定每节点一页、原PDF或原件/ready派生版本、原生页级引用、提取版本/文字hash及空文字状态；允许读取所选二进制源但不返回/读取附件，不能用附件false掩盖PDF源已读。保留64KiB单正文/1MiB上下文/共享16MiB含重读，8MiB组合上限不逐选择重置；实际打开/增长、子进程剩余deadline及有界stdout均须后续实现证明。单页严格Unicode、无文字/失败不自动OCR、无Office自动转换或latest替换，其他格式仍保留。具体字段/预算/负例仅见现行契约，不在报告维护另一份平行规范。

后续e2触点为#63封闭选择/共享读取预算适配、新PDFium取字worker及固定内部CLI分派、版本/引用校验、API/负例；e3触点为普通资料确认UI、取消/撤销/迟到响应及源码/新冻结无模型组合。旧文本/作答授权、候选采用、普通查看/书签、数据保护和两用途隔离必须保持；本e1不实现这些产品触点，不接模型/凭据/远端，不执行用户文件、Office、OCR或实际窗口。

### 验证与交付边界

计划核三文件白名单、501基线/498未变blob、原报告完整前缀、UTF-8/LF/Git空白、本地引用/锚点、唯一任务及e1/e2/e3依赖，另运行既有Schema漂移检查。此为只定义规划的文档改动，所有产品/测试原blob不变，不另写镜像设计的测试或重复本地产品构建；当前head CI仍须完整执行。实际结果和独立草稿PR另记，未知/失败不先写通过。

R6-01e保持IN_PROGRESS，e1设计完成后REVIEW待独立PR/本head CI及主Agent有限核验；父#63也须当前CI成功后方可根验收。e2/e3和其余格式正文未实现，不把e1设计当e或整个R6完成。代码审查按用户要求暂缓、人工取消不补记通过；不合并或发行。

在resource-read-pdf-plan执行工具Python `-X utf8 artifacts/r601e1/check_changes.py`退出0：仅三文档/498原blob保持/501最终文件，90本地引用及全部被引用标题锚点、64唯一调度行、Git diff --no-index --check、UTF-8/LF、两锁及原b报告完整前缀保持均通过。IQ `-X utf8 tools/export_question_schema.py --check`退出0：Question schemas are current。没有本地产品/模型/窗口测试结论；因产品/测试/协议文件均未变，本地不重复其测试或构建，当前head完整CI另核，不能用设计检查冒充提供器实现验证。

独立草稿[PR #64](https://github.com/surface-user/StudyWorkbench/pull/64)已建立并附当前任务，分支codex/resource-pdf-read-plan依赖#63的codex/resource-read-api精确ca61a8d，首次设计提交06f06d1623030a327e80f1d87fe4d6b2a7fe95af/tree4aafe2d2559346208f24809068b632ce7753c8d7。后续文档提交只补实际PR链接；最终head/tree与该head CI记录PR正文，避免记录自身hash反复改头。e1保持REVIEW，父#63及本项当前CI/主Agent有限核验未取得前不登记DONE；e整体及e2/e3仍未完成。

## R6-01e2 单页文字提供器（2026-11-14开始，11-19恢复）

### 基线、范围及恢复点

主Agent已有限接受#63文本API及#64设计：精确38c1abebcd94c72a82740ccac9d6deafd99c1c6a/treeb477069a7f5a54445ce66f9043bb1c3821b802fb的CI43595667880三job成功，双1216/desktop203/45冻结核源/API57与501远端blob已根核。e2从该精确501文件新建resource-pdf-provider，原#64/旧根/resource-read-ui及用户资料不改；本轮恢复再次查#64仍open/draft/unmerged且头精确相同。AGENTS、requirements/architecture/question-content-spec/task及Agent契约逐字节对应已完整阅读的已接受版本，另核全部实际调用者、现有worker/路径/预算/预览收据和相关测试。

暂停时保留resource_pdf.py新模块、resource_grants和固定内部入口三项未提交改动。q01.xml原为缺测试父目录的49 setup errors；补运行目录后q02.xml实际49通过/14.690秒，恢复时从原XML确认，不把中断的工具回执当作失败或成功。CIM命令行枚举被当前环境拒绝，未据此声明没有残留或终止别人进程；后续Get-Process只读未列Python进程。初次恢复工具JavaScript括号错误没有执行系统命令；修正后继续，不修改旧失败证据。

### 实现与兼容边界

本项扩既有封闭resource_node选择，原PDF或明确ready的DOCX/PPTX派生PDF只读一个授权页。原件/预览归属/当前源及派生hash、选项、转换器/运行时、页数和提取版本绑定；不调用Office转换、拆题、OCR、网页、转写或模型。输出文字及v1页级anchor，不猜原文行/字/区域或PPT页语义；空页只报告no_extractable_text。source_binary_read=true与binary_attachments_read/links_followed=false分开，其他未覆盖格式仍只元数据。旧文本、旧作答用途/返回及100活动grant共享限额不变，临时授权/正文不落持久表或备份。

read_file复用既有作用域和末尾数据行/文件重验，扩为有界原始字节模式；纯文本1MiB不变，PDF或Office源+派生组合8MiB，所有选择实际文件读取含重读仍共享16MiB。打开前规范化archive_path并精确核workspaces/<workspace>/前缀，打开后普通文件/大小/身份/hash校验、无Python缓冲预读、按剩余额度和组合限制限长，增长/别名不重置预算。Office另核所选preview的固定派生路径，不未经适配调用普通read_pdf。根另交[PR #66](https://github.com/surface-user/StudyWorkbench/pull/66) c0bb750对旧原件/工作文件授权路径修复；后续组合须保留#66的原件/工作文件保护及e2的派生固定路径/归属校验，不能用任一方覆盖另一方。当前候选基于#64，不把#66整份实现/测试冒充已组合。

专用resource_pdf仅接已核字节和页，原生先计UTF-16容量≤16384单位再有界分配，核实际长度/严格Unicode/最终64KiB；引用带实际pypdfium2/PDFium及算法版本和文字hash。全context读取/解析以及外层规范编码/hash均受20秒总期限，既有2查看槽共用；短命子进程stdin逐块/剩余deadline，stdout按实际读出到128KiB即停止拒绝，不communicate无界缓存，终止仅使用本次Popen持有进程句柄。最小环境白名单不继承业务凭据，不冒充OS文件/网络沙箱。同步文件I/O不可即时硬中断，子进程终止后的有界清理另保留；槽位在异常清理后也释放。

Windows源venv存在redirector，直接kill它可能遗留实际Python子进程。本实现按固定CPython机制使用sys._base_executable并由服务端设置__PYVENV_LAUNCHER__保持当前venv；未改环境/缓存或安装。已核[3.13.17官方getpath](https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/getpath.py)与本机只读试探，保持原venv和pypdfium2 5.14.0而进程句柄属于实际解释器；双版本真实child专项另核。冻结包直接启动自身固定内部--read-resource-pdf入口，既有collect-submodules自动收集，不新增依赖/工作流/迁移。普通PDF页图、Office转换器和旧候选业务不改。

### 本地命令、失败与阶段结果

工作目录resource-pdf-provider。Q/P为../starlette-fix/.local/starlette-q-isolated及starlette-p-isolated/Scripts/python.exe，工具解释器为项目既有release-venv；PYTHONDONTWRITEBYTECODE=1，原始JUnit/日志/自建库及生成包均Git忽略。所有以下资料均仓库自编样本或独立测试生成，不操作个人库。

- 新test_resource_pdf初轮q03为26通过/2失败，因误用既有snapshot签名（传了client及目录）；改按现有sqlite路径签名后q04为30通过/26.65秒。后续q05含旧授权为90通过/50.30秒，q06/p06各93通过（54.00/59.59秒）；这些是各自中间版本，不冒充最终计数。Ruff初发现import排序、未用json及测试lambda，按规则修正，未删除负例/降低断言。
- IQ -X utf8 -m pytest backend/tests/test_resource_pdf.py backend/tests/test_resource_grants.py backend/tests/test_agent_access.py backend/tests/test_analysis_context.py backend/tests/test_analysis_review.py -q --basetemp=artifacts/r601e2/tmp-q07 --junitxml=artifacts/r601e2/q07.xml：无缓冲修正后的业务快照95通过/73.62秒/2既有弃用警告；随后新增真实空文字PDF专项另跑，不把95当最后新测试数。原生链接测试使用Windows权限，目录仅本任务临时样本。
- Q -m ruff check backend tools：退出0。新增反例涵盖封闭字段、单页/错源/错预览/大小/选项/跨节点、真实PDF child、Unicode/空文字/容量边界、共享读与预读/增长/末尾变更、字节管道超限/阻塞输入/畸形协议/超时、并发槽和持久数据保持；旧授权用途/版本/撤销/重启等仍由原专项执行。
- IQ tools/check_api_errors.py --test-root .local/pdf-http-source02：退出0，实际82次HTTP/36唯一错误ID，源码真实PDF及明确自造ready Office收据读取、范围/拒绝/重启/全部资源及派生hash/业务DB快照保持。首次source01因独立.local父目录未创建失败，保留事实后建运行父目录并改新source02，不改产品。
- 同工具加STUDY_OFFICE_RUNTIME=<既有固定Office+Java组合>、--convert-office、--test-root .local/pdf-http-source-office02：退出0，889次HTTP（含等待轮询）/36错误ID。真实普通受管导入→普通Office转换ready→授权单页及源/派生hash→保持DB/原件→重启后重复均通过；不是自造收据冒充转换。source-office01曾自设180秒总体等待，完整运行时校验未完即被探针停止为interrupted，只有source.docx、未进入引擎，原目录和失败保留。改沿既有check_office_previews的600秒等待完整校验；未改变产品90秒引擎或20秒Agent期限，不能将其算作放宽产品测试。
- 首次并行全量/冻结启动后补了无缓冲读取细节；该轮仅中间源码快照。首次build-backend.ps1在check_frozen_sources准确拒绝resource_grants源不等，退出1；未绕过门禁。经绝对路径核对将自己的旧build/dist及spec完整保存在artifacts/r601e2/failed-freeze01（209.84MiB），不删失败或挪别人产物。稳定源码重新执行./packaging/windows/build-backend.ps1 -Python <Q>，完整日志build02.log，退出0：46冻结模块及嵌套代码/常量等于当时业务源码。后续实测必须用该包，不能用首次差异包。

真实新冻结HTTP/普通Office转换及库保持、最终双版本回归、文档/范围检查和独立PR/当前head CI继续核验；未取得前保持e2 IN_PROGRESS。e3单页UI/总体组合和未覆盖格式仍未实现，不把本实现/单项局部通过记为e或R6整体完成；审查暂缓、人工取消，未合并或发行。

### e2 最终本地证据与交付准备

后续补强未扩大功能：子进程显式PYTHONDONTWRITEBYTECODE=1，避免源模式触碰共享环境字节码缓存；源Resource ID纳入citation及grant上下文指纹，不仅依靠hash/节点关系隐含冻结该身份。外层规范编码/hash后的deadline检查已覆盖，纯文本/作答用途保持。AgentAccess新增长import经Ruff排序，旧构建随后按既有严格代码比较拒绝AgentAccess差异；未用忽略/放宽门禁处理。build02/03/04各自当时成功仅作历史，最终以排序及身份补强后的build05和本head CI为准，自有可再生build/dist顺序复用，不复制或清理他人产物/用户数据。

- 最终Q/P执行上述五个授权相关测试文件，改用tmp-q09/tmp-p09及q09.xml/p09.xml、完整输出q09.log/p09.log：各退出0，96通过/2既有警告（119.75/130.25秒），包含47新增及49旧用例，无失败/跳过。真实空文字PDF子进程也已执行；q08仅新专项47通过/61.32秒，是此前版本记录，不替代最终96。子进程恶意输出/阻塞stdin/畸形协议用本任务自造命令，实测只终止自己持有的实际child并释放共享槽，没有终止其他进程。
- 两轮本地全量的完整XML保留：full-q01/full-p01为1261通过/77子测试/4既有警告（656.40/692.31秒）；full-q02/full-p02为1263通过/77子测试/4警告（960.58/1032.73秒）。这些运行启动于后续修正前，属于中间模块快照，不能冒充最终所有源码已经本地全量重跑；最终差异由上述96×2及本head全量CI核验，待CI取得前不作最终全量通过结论。47新增数量与最终head全量实际执行数须按当前CI日志另核。
- Q全Ruff（ruff-final02.log）及IQ tools/export_question_schema.py --check均退出0，协议无漂移。最终./packaging/windows/build-backend.ps1 -Python <Q>退出0，完整build05.log显示46业务模块/嵌套代码常量等于当前源码；最终study_backend.exe为22600069字节/SHA256 f493edc9292c85556c0b2ce5c94f29595eb5d465863990d358d5d58930f91ba0。无新增依赖/锁/迁移/工作流变化，不将开发包称为已签发行包或已组合其他平行PR。
- 最终IQ tools/check_api_errors.py --test-root .local/pdf-http-source-final01退出0：88次HTTP/36独立错误ID；加--exe dist/study_backend/study_backend.exe、--test-root .local/pdf-http-frozen-final01退出0：86次/36ID。均是当前业务源码/最终新冻结，真实受管PDF及明确自造Office ready收据、源Resource ID/页级引用/文字hash、固定范围/拒绝/重启不恢复授权与全部原件/派生hash/业务DB快照保持通过。HTTP数含受管导入轮询，不能当作88/86条互不重复的业务断言；独立错误ID数实际相同。
- 最终同工具加--convert-office、STUDY_OFFICE_RUNTIME=<既有固定Office+Java组合>、--exe dist/study_backend/study_backend.exe、--test-root .local/pdf-http-frozen-office-final01退出0，2694次HTTP含完整校验/转换等待轮询、36错误ID，office_conversion_executed=true/frozen=true。确切普通导入→普通转换ready→源与派生文件hash及Source ID绑定→授权取页→业务数据/原件保持→重启后重新普通转换/授权全部通过。源码实际普通转换已在source-office02通过；早期同类冻结frozen-office01的591次结果为旧中间包历史，最终使用本条build05包，不混用。自造收据模式与真实转换模式分别记录，不用前者代替后者。
- IQ tools/check_library_integrity.py --exe dist/study_backend/study_backend.exe --test-root .local/pdf-library-frozen-final01退出0：最终冻结真实数据锁/健康、损坏和孤立字节检测、保存恢复/另存/合并/容量只读报告全部保持，business_bytes_preserved=true/repair_performed=false，各删除授权false。完整结果library-frozen-final01.log；不修复或删除原件/历史/失败文件。

实现、最终相关自动化、源码及最终新冻结的真实HTTP/普通Office派生贯通和文档就绪，e2转REVIEW；独立草稿PR/当前head CI和主Agent有限退出核验继续，原报告保持全部阶段/失败事实。不改原#64或根UI目录，不把e2取字API等同e3界面/组合或e父项全部完成。

工具Python -X utf8 artifacts/r601e2/check_changes.py退出0：11文件白名单、492原blob保持/503最终文件、130本地引用及被引用标题锚点、64唯一调度行、UTF-8/LF/git diff --no-index --check、两锁/工作流及原#64报告完整前缀保持通过。新增仅resource_pdf模块及其47专项测试文件；其余9文件为既有授权/内部入口/真实API探针及本任务现行文档/原报告，无新平行报告或整份artifact入Git。

独立草稿[PR #74](https://github.com/surface-user/StudyWorkbench/pull/74)已建立并附当前任务：codex/resource-pdf-provider基于#64最终38c1abe，首次实现3ac57cc1827cf9d523f732761ef568daae97c6b2/tree3612c01473b712e8896457ac9adec9e8f3482d0e。文档补实际交付链接形成后续提交，最终head/tree/当前CI在PR正文记录，不为记录自身hash循环改头。e2保持REVIEW待当前CI和主Agent核验；审查暂缓/人工取消，未合并或发行，e3及父任务继续。

## R6-01f 后端授权路径组合回归（2026-11-19）

### 已交付输入与最小范围

主Agent已有限接受e2：#74最终5ab4ccdfbc3df4e80baf3022c3a7a908bb383b81/tree53e5e57ca698e0db40d8ca495ff6332483a71749，当前[CI44504052672](https://github.com/surface-user/StudyWorkbench/actions/runs/44504052672)三job成功，双1263/4既有警告、desktop203、46冻结模块核源及冻结API81次HTTP/36独立错误ID。CI使用自造ready收据，office_conversion_executed=false；本地最终新冻结真实普通Office转换后2694次含轮询HTTP/36错误ID及双版全量原记录另经主Agent核实，不混同两类证据。e2可记有限DONE，e/R6父项、UI/e3及完整发行仍保留。

#66 c0bb750605a737ec74b7a9d483d26bec68ee7f41/tree86975048accdad35833e094719b7a2869922abb5直接基于#63 ca61a8da28c87c90236217d7c1d57b8c0582c4de；其[CI44492081114](https://github.com/surface-user/StudyWorkbench/actions/runs/44492081114)成功。#74基于#64 38c1abe（父06f06d1，祖先同为ca61a8d），没有直接包含#66提交。核五文件实际差异后，#66唯一产品变化是规范化archive_path再核前两段精确workspaces/<workspace>；#74共用read_file已先规范化再核精确workspaces/<workspace>/前缀，规范路径禁止空段，两者对原件/工作文件语义等价。PDF原件沿同一保护，Office派生另核所选ready收据及固定preview路径。未通过简单合并覆盖其中任一保护，也不重复改产品代码。

主Agent授权仅补#66两项持久回归及任务/原报告。从#74精确503远端blob新建resource-backend-combo，逐Git blob核503文件；AGENTS、requirements/architecture/question-content-spec/task对应先前已完整阅读版本，现行调用者和路径契约无变化。原resource-pdf-provider/#74、#66及根UI副本保持。两例从#66实际patch提取，分别篡改持久Resource/DocumentWorkfile路径到default-other，断言已发grant读取与新正文授权均409、元数据仍200、路径解析从未调用且原件字节不变；不是只测内存选择字段。两例先在#74未改产品上独立试探Q/P各2通过，再纳现有test_resource_grants.py以免持久回归遗漏。

本项仅改该既有测试和两份任务文档，业务源码、接口/锁/工作流及原件保持。审查按ADR0014暂缓，人工按ADR0013取消；独立草稿PR/当前head CI与主Agent核验为有限交付门禁，不要求合并或发行。旧失败完整保留，未重复执行真实Office转换或新本地冻结构建；与#74产品逐字节一致及原冻结核源可以复用其自动化边界，当前CI仍需重新构建及全量验证。

### f 本地自动化及交付准备

工作目录resource-backend-combo，复用Q/P固定3.13.17/3.12.7隔离解释器，PYTHONDONTWRITEBYTECODE=1，不安装或变更环境。Q/P -X utf8 -m pytest backend/tests/test_resource_grants.py backend/tests/test_resource_pdf.py backend/tests/test_agent_access.py backend/tests/test_analysis_context.py backend/tests/test_analysis_review.py -q --basetemp=artifacts/r601f/tmp-q02或tmp-p02 --junitxml=artifacts/r601f/q02.xml或p02.xml，均退出0，各98通过/2既有警告（76.57/82.81秒）、无失败/跳过；即#74原96与本次2例。tmp-q01/p01首次各97通过/1失败，原重解析点测试创建Windows目录联接被沙箱拒绝（Access denied），原XML/日志保留。重跑仅使用已授权的本任务临时目录本机链接权限，不改测试/产品保护，不接触其他目录或进程。

Q tools/check_frozen_sources.py --exe ../resource-pdf-provider/dist/study_backend/study_backend.exe退出0，46业务模块及嵌套代码/常量匹配当前源码。业务/工具/打包/锁全部原blob保持，本项不为两例测试另复制或重建本地包。原#74新冻结f493edc9292c85556c0b2ce5c94f29595eb5d465863990d358d5d58930f91ba0仅用于源码等价与既有运行证据，不将文档/测试候选说成新的已签发行产物。

工具解释器release-venv -m ruff check backend tools及Q tools/export_question_schema.py --check均退出0。首次Q -m ruff因隔离环境只读复用ruff模块而其Scripts/ruff.exe不存在失败，改用已有工具解释器，不安装/拷贝工具；此失败与产品无关。artifacts/r601f/check_changes.py初次精确检出追加测试末尾多空行，去掉该空行后退出0：3文件白名单、500原blob保持/最终503文件、75本地引用/标题锚点、65唯一调度行、LF/UTF8/diff --check以及旧报告完整前缀保持。没有新增报告/依赖/生产行为或整份artifact入Git；R6-01f转REVIEW待独立草稿PR/当前CI及主Agent核验。

独立草稿[PR #77](https://github.com/surface-user/StudyWorkbench/pull/77)已创建并附任务，codex/resource-backend-scope-regressions基于#74最终5ab4ccd；初提交2990ac6345163a22d0a36662b01cc85b7a953f25/tree7fb77134132be1668617259d56285f641b0fcc54。补实际PR链接后仍为3文件，当前head/tree及其CI在PR正文记录，不为自引hash循环改头。R6-01f待本头CI/主Agent有限退出核验，未动旧头、合并或发行。
