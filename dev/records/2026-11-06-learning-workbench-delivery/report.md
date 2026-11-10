# 通用学习工作台阶段PR交付

2026-11-06用户明确授权“这一版先提交pr，提交完之后继续推进task.md任务”。本批允许提交、推送新分支并创建PR，覆盖此前本地积累的LW-00至09及文档治理；不等同人工/阶段验收，不授权合并、发布、删除数据或接模型。旧真实窗口后才PR的顺序针对本次送审由用户新指令覆盖，原窗口待验义务仍保留。

## 基线与范围

远端实际核验：PR #2 open/draft、head 29f23d3558740545a950a51ca04398f9420088fd，base main；PR #3 open/非draft、未合并，head 7aa8251561c548df9d34163f326980bde20200cd，base codex/unified-resource-import。本批独立分支codex/learning-workbench-20261106以#3 head为parent、以已验本地完整源码快照为tree，避免重复R6并保留#2/#3依赖，不改写两个旧分支。

送审内容：自由MD笔记、位置书签/备注、内部链接、集中查找、离线整库备份恢复、受限UTF-8文本/XLSX查看、直接HTTPS媒体队列、无模型本地授权及外部候选人工审核；0013–0016迁移、桌面入口和测试；docs现行规范与dev历史/证据分离。普通业务离线、原件/旧学习数据保留。依用户偏好不接模型/凭据。

.vscode本机设置保留在工作区而不提交；artifacts/.local、个人库、模型、导入原件和下载视频不入库。旧归档/共享证据迁移在提交树中作为保留内容检查，不丢历史失败。

## 已有验证及送审边界

开发/发行Python各468通过，Flutter153通过、静态/Windows Release/冻结学习及人工候选闭环通过，详见[LW-08原报告](../2026-11-05-lw08-authorization-review/report.md)。这是11-05末轮同源码结果，本次未重跑全部测试；实际重算109运行源码/工具SHA256均不变，记录artifacts/pr-workbench-20261106/source-verification.json。

必须保留阻塞：最终Office DOCX未生成PDF并产生MDMP转储，Calc因组件多出未登记文件被完整性门禁拒绝，PPTX末轮未执行，见[LW-06原报告](../2026-11-04-lw06-formats/report.md)；下载公网源受当前DNS负面门禁阻断，见[LW-07报告](../2026-11-05-lw07-downloads/report.md)；Computer Use启动超时、实际窗口/用户/阶段/安装与干净机待验，见[LW-09报告](../2026-11-04-lw09-integration/report.md)。PR采用draft，不请求合并。

## 送审步骤与后续

先验证保护文件/链接、源码hash、暂存范围与敏感文件，再以当前完整源码树生成以#3为parent的单一阶段提交，推送新分支并由GitHub连接器建PR。实际命令/退出码、commit/tree/PR和当前head CI结果在本报告追加。提交完成后优先继续LW-06组件崩溃定位：保留原转储，在新隔离组件目录对照源/冻结进程，不降低校验、不修改个人库；其他任务仍依task与现行契约推进。

送审前实测：git fetch origin codex/r6-local-agent-access退出0；.vscode仅本机路径配置，未暂存。git -c core.safecrlf=false add -A -- .gitattributes AGENTS.md README.md apps backend contracts docs dev tools及暂存diff --check退出0。暂存树412文件/4743126字节、相对#3为235项变化；模式扫描未发现真实密钥样式或长Bearer，禁止路径/数据库/媒体/可执行包断言均通过。运行保护文档检查第一次因LW-01改成用户已授权PR送审状态而失败；仅按用户新授权转换该交付措辞，保留其余原单元格全文相等检查，未豁免失败/验收信息。Ruff/schema检查退出0，运行源码仍109项一致。


实际创建：git write-tree得到ffdd0a1c4924b6a54afcef88c1bb26c77b63c9fb；git commit-tree该tree -p 7aa8251561c548df9d34163f326980bde20200cd -F artifacts/pr-workbench-20261106/commit-message.txt得到c7dc5dddd58ed73dbacd306d0c9e7f59b5c11891；git update-ref以不存在旧ref的零SHA保护创建codex/learning-workbench-20261106，git switch及git push -u origin同名分支均退出0。只剩.vscode未跟踪，无丢失/覆盖继承改动。通过GitHub连接器创建[PR #4](https://github.com/surface-user/StudyWorkbench/pull/4)，draft/open，以#3为base，235变更文件、1阶段提交，未合并/发行。

首head c7dc5dd的PR CI [run 42061516523](https://github.com/surface-user/StudyWorkbench/actions/runs/42061516523)实查进行中：双Python已过Ruff且在pytest，桌面已过格式且在analyze；不是最终通过。提交后的工作继续LW-06，定位到LibreOffice从冻结包继承VCRUNTIME，设计/修补/验证继续[LW-06原报告](../2026-11-04-lw06-formats/report.md)。新增修补验证后跟进同PR，不自动合并。


## 首轮CI失败与路径修补

run42061516523最终双后端job均success（含pytest和R1–R5 HTTP黑盒），desktop失败于Flutter测试：152通过1失败，后续Windows/冻结步骤未执行。日志保留artifacts/pr-workbench-20261106/desktop-ci-first.log。唯一失败backend_process_test.dart首项“isolated restored settings remain selected on a fresh application start”，第13行期望true实际false：仅testData转正斜杠，repository未规范化；CI Resolve-Path给反斜杠，本地前批给正斜杠，导致错误前缀比较。不是后端业务失败，CI缺口确由本地未原样复现参数造成。

用户询问原因后继续按已授权task/PR交付工作使用gh-fix-ci排查流程，通过GitHub连接器取实际job日志。修补只规范化同一个断言两边的路径，不删除“必须在仓库.local中”的保护，不改CI参数或跳过测试。按CI同样的$taskRoot=(Resolve-Path ../..).Path，D F --suppress-analytics test --no-pub --dart-define="STUDY_ROOT=$taskRoot" --dart-define="STUDY_DATA_DIR=$taskRoot/.local/ci-path-before-20261106" test/backend_process_test.dart --plain-name 'isolated restored settings remain selected on a fresh application start'先退出1复现（ci-path-before.log）；改after新profile后退出0（ci-path-after.log）。全量同参数改ci-path-full-20261106退出0，153通过45秒（flutter-full-path.log）；analyze退出0无问题，77.7秒（analyze-path.log，组件复制并行带来机器负载，不降低断言/超时）。当时的静态核对误判未发现硬编码漂移；实际输出截断漏看了check_resource_explorer.py第172行，下一轮CI证实这一遗漏，不能把静态核对当作执行完CI命令链。只提交该测试及交付状态；Office修补仍在工作区验证，不混入此CI修补提交。推送后的当前head CI仍需实际等待。


## 第二轮CI：冻结探针旧schema常量

路径修补提交f0a34e3714e618ed95cf3b4f9ab6f8623c3c97ed已推送。PR run42064343519双后端成功；desktop通过153测试、Windows Release、原生COM和冻结打包，随后Frozen unified resource import and document regression失败：tools/check_resource_explorer.py第172行仍严格断言0012，而当前应用正确升级0016；同脚本末尾汇报字段也写死0012。原日志desktop-ci-second.log保留。这里是探针未随迁移维护，不是把旧库未升级当作通过；先前静态核对遗漏由本报告明确纠正。

保留原整数/关系/hash断言，以Alembic ScriptDirectory读取源码唯一current head，SQLite仍须严格相等，报告revision随实际已核head，不使用>=或放宽列表。复用先前已验、与PR后端代码一致的frozen-review-final包，避免混入尚在验证的Office修改。

P tools/check_resource_explorer.py --exe artifacts/lw08-20261105/frozen-review-final/dist/study_backend/study_backend.exe --test-root .local/pr4-resource-before-20261106 --documents退出1复现原schema断言（resource-before.log）；修补后改独立root .local/pr4-resource-after-20261106，退出0（resource-after.log），验证5节点/原件去重/文档/墓碑/布局/历史/重启/SQLite完整性和FK，schema0016。

完整执行该失败步骤及其后CI命令：新建项目.local/pr4-lifecycle-real-20261106和指向它的pr4-lifecycle-alias-20261106 junction，将TEMP/TMP设alias；P tools/check_backend_lifecycle.py --exe同一冻结包退出0（lifecycle-after.log），独占锁、鉴权/Origin、中文主观与客观题、EOF、重启/崩溃恢复和迁移父EOF取消通过。P tools/check_document_workers.py --exe同一包退出0（document-workers-after.log），DOCX/PDF真实离线worker、文字/图片/公式/页及编号/跨页拆分通过。驱动实际收取resource_exit=0/lifecycle_exit=0/workers_exit=0，不仅查看日志。Ruff与暂存diff检查另做后才推送；不改工作流、不跳测试、不更新尚未验证的Office运行代码。新的PR head须再实查全CI，保留两轮红灯及本地先红后绿。

当前已送审head 54ad12b51b0d5bc2c8d2e4d71e42926ab4e86135的PR run42068871152三个job全部success，GitHub实查确认；两轮失败保留。PR描述已据此更新，不改commit/不合并。Office新试验尚未提交，不能混称该head已包含或解决组件问题。


## PR后继续：Office隔离启动与深目录修补

按用户原授权继续LW-06，已在原任务报告记录两项原因及最小修补：冻结组件DLL继承由独立受控helper清理自身，外部组件深profile路径使用samefile确认的短名。修补后双Python各476通过，新冻结包真实DOCX/PPTX各2页、Calc、四页页图、完整CI冻结三项探针、R1–R5 HTTP及授权审核/整库恢复闭环通过，实际命令和退出码收取边界见[LW-06原报告](../2026-11-04-lw06-formats/report.md)。没有将54ad12b的绿灯套用到新代码；本次推送后的当前head CI仍需GitHub实际核对。旧Office失败、原组件转储、两次红CI和窗口/人工/安装待验保持，不合并/发行、不接模型。


本轮Office修补提交4cd157a870d557eb82d57204431b8642bf295ffd已git commit/push，均退出0；PR run42078193435跟进中，当前双后端success、desktop已通过Flutter测试并构建Release。PR描述标明新代码CI进行中，未套用54ad12b结果。实际窗口新包一次launch_app超时、匹配0，继续原LW-09报告；公网DNS只读复核仍拒绝，继续原LW-07报告。

并行核对旧PR：#2当前29f23d3/run40928912483与#3当前7aa8251/run41559301426均completed/success；#2历史自审确有已修复竞态/样本问题，#3/#4当前reviews为空，未发现自动审查服务故障证据。#3原报告与描述补实时CI结果，不改原分支或验收状态。

R6原报告追加时，文档保护初检退出1：该活动报告处于旧快照保护集合，首次写入也将CRLF归一化。已恢复全部原始CRLF字节，原正文prefix的SHA256严格等于旧保护值e153ad11f8ac574f18d9b9071eec0d43daae606af48fc66ed1e698cec38a6409，仅尾部追加本轮PR交付状态。ad hoc保护检查保留其余113文件完整hash严格相等，并单独断言该报告原字节prefix未变，未修改旧checksum/归档/失败内容；复验退出0，52份Markdown/254本地链接/7锚点、113整文件及1原报告原字节均保持。此检查调整只在忽略的artifacts脚本，不删或减弱产品测试。


### Office代码提交CI结果与文档收尾

4cd157a的[run42078193435](https://github.com/surface-user/StudyWorkbench/actions/runs/42078193435)已completed/success：双Python及desktop全部通过，Release/COM/冻结三项整链均success。通过GitHub再次核对运行与job，不依据本地成功推断。当前修补功能已送审，仍为draft，未合并/发行；窗口、真实公网、人工/阶段/安装以及无短名卷仍待验。

随后仅补PR状态、窗口/网络工具限制与四张精选派生页图说明，没有再改产品/测试代码。文档保护复验退出0：53份Markdown、260本地链接、7锚点、113整文件与1活动报告原字节保持；R6报告的旧失败/原始前缀不动。文档提交后的当前head仍需远端检查，结果以PR实时页面为准，不把代码head绿灯套成未来提交成功，也不为写自身SHA反复提交文档。


## 用户取消人工测试后的维护提交

用户明确取消人工测试并要求继续开发/治理近30GB占用；不再执行Computer Use或把人工窗口测试作为阻塞。现行规则由ADR0013覆盖旧延后安排，产品内用户授权与候选审核确认仍保留。清理及防复发实现继续[原DOC-01报告](../2026-10-30-documentation/report.md)，不新增清理报告：238项已核生成目录移除，27.190→4.912GiB，保留当前后端与一份可用组件并核验hash。pytest内置failed策略启用，相关21项及全量476通过；故意失败探针用于核验现场保留，非产品失败。本轮修改的CI须按新head查询，不能沿用1e22cd2绿灯；不重建人工测试包、不合并/发行。

## 2026-11-10 用户领取当前Release构建进行人工测试

用户明确要求“给个目前的正式版exe我人工测试一下，列出待测试的内容，我人工做汇报”。本轮生成Release模式本地交付包及[人工测试清单/反馈模板](manual-test-20261110.md)，由用户自行执行并反馈；只覆盖此次安排，不恢复所有任务人工门禁，不把旧取消或当前CI算成人工通过。仍不执行Agent窗口/Computer Use、不接模型、不合并/公开发行。产品代码基线#18最终2a884fe4f665b3ce50152914e32ee60314af60c9，CI #108三组43步成功已再核，独立审查没有；原根#7和原两份未提交改动保留。

先检查旧包：原根dist/StudyWorkbench-M1-setup.exe为10-24旧产物，不能冒充当前版本。固定CPython3.13.17、Flutter3.47.1/Dart3.13.1、签名Valid的NuGet6.14/Inno7.1/WebView2离线安装器、固定Office26.8.1及28.4GB剩余空间已核。只在.local/markdown-merge-followup-src写新生成文件；原安装目录/数据目录未操作。Get-CimInstance只读进程查询权限不可用，未重试该接口，后续未依靠它执行操作；flutter --version无输出阻塞后只中止本代理查询，版本改由已观察SDK缓存元数据核实，未启动用户应用。

本机首次原build-release命令使用已验证工具与-OfficeRuntime，退出1，Flutter的NuGet依赖target报MSB3073，尚未生成新安装器/完整stage。只读nuget help暴露默认TEMP/NuGetScratch对项目.local/NuGet.Config的锁不可用；未删除该锁、未改全局NuGet配置。用新项目私有TEMP/NUGET_SCRATCH运行带20秒超时help诊断，退出0；据此仅进行一次私有scratch的本机构建复验，仍退出1于同一NuGet依赖步骤，停止这条构建操作，不再反复尝试或降低原门禁。两轮构建日志、help输出、诊断JSON和驱动副本保留artifacts/manual-*；不能从help成功推断install或构建通过。

本地实际命令（cwd=隔离源码）：packaging/windows/build-release.ps1 -Iscc <原根固定ISCC.exe> -WebViewInstaller <原根固定安装器> -OfficeRuntime <原根固定Office目录>，退出1（manual-release-build01.log）；artifacts/manual-release-driver02.ps1同参数，退出1（manual-release-build02.log）。第二驱动仅改脚本副本的源根与进程私有scratch，保留原Flutter/冻结/许可/hash/PE/Office/ISCC全部门禁，原生产脚本无变化。artifacts/manual-nuget-diagnostic01.json记录私有目录help退出0。原CIM权限失败不参与构建通过证明。

已通过的现行GitHub CI环境可以正常编译该产品基线，但desktop job原先没有可领取的构建产物。本切片只在现有全部桌面/冻结/worker检查之后复用已采用的actions/upload-artifact@v4，保留Release前端、配套冻结后端及该次NuGet包目录三天；排除仅供COM检查的resource_drop_check.exe，不上传测试profile、学习数据库、用户原件、会话令牌或源码工作区。此为仓库内短期构建交付，不创建GitHub Release或公开发行。已有所有检查及失败行为不变，无新运行依赖/产品逻辑。

独立分支codex/manual-release-handoff基于#18；本轮四份明确文件（工作流、task、原批次报告及一份清单），修改前副本在artifacts/manual-handoff-base。不把新的清单另当一份交付报告，后续用户反馈继续本原报告。本地校验会核YAML可解析、旧全部steps原样保留、仅增加末尾产物步骤、限定路径/三天保留/缺文件报错、文档链接/UTF-8/空白及其余父基线保持。无需为纯工作流出口另写镜像断言单元测试；当前head完整CI仍须通过并实查新artifact。

待该构建成功后，仅下载指定运行的构建ZIP并核artifact来源/摘要，安全解压到全新本地目录；组装app-local已签名CRT和已核Office组件，运行现有release_inventory/check_release与冻结源码/业务/Office探针，再用原ISCC编译本地安装器。产品版本1.0.0+1，不注入开发STUDY_ROOT或固定个人数据路径，不启动真实用户库/窗口。实际退出码、运行/下载来源、最终包路径/hash、构建元数据和交付结论在本PR描述及交付目录build-info.json记录，不把尚未执行项目记通过。当前仍待构建/PR及最终head CI核实；自审与独立审查分开，用户人工结果待反馈。旧题目目录恢复继续规划，不修改原目录，保留全部旧失败证据。

实际交付跟进：[独立草稿PR #19](https://github.com/surface-user/StudyWorkbench/pull/19)，分支codex/manual-release-handoff，基于#18最终2a884fe，实现6806a70ecdcb9538cf96d5a8444d49fc24e9e0a7。四份规范文本上传并核Git blob SHA，远端实现差异仅四份；首次推进ref网络异常导致创建PR返回422无差异，先只读核分支仍为父head且PR未创建，再仅重试一次expected_sha推进并创建成功；非权限绕过，无强推或重复PR。task/原报告补实际链接，文档最终差异与远端回读继续核实；最终head/全部CI步骤、artifact来源/下载校验、本地组装/打包/探针实际命令退出码与包hash在PR描述及交付build-info.json记录，不循环提交自身SHA。当前包/最终head CI尚未交付，不先记成功；自审完成，独立审查未取得，用户人工结果待反馈，不合并或公开发行。

### 本轮实际构建、打包结果与交付限制

37a8d553e56c34ea901269a01e3022d934215d45的CI #113（42788216714）三job/44步骤全部success，双后端各707、Flutter193/格式/分析、Windows Release/COM、43模块冻结、原资源/文档/恢复/合并/容量/生命周期/worker及新artifact步骤通过。四份远端文本回读匹配规范blob SHA，自审COMMENT锚定该head，无独立批准/线程。构建产物windows-release-inputs-37a8d55...，artifact ID13750752076，96017537字节；SHA256=928460703ec9ae29e5989b62a57b1db88fb9b69a7232c9c84d8da78b213b0ec7。本地流式下载逐字节匹配GitHub digest，先拒绝越界/重复大小写路径、符号链接和超预算ZIP再安全解压，1151个条目。没有下载/上传个人学习库或原件。只将CI生成的三个NuGet目录放入当前隔离源码的空构建目录，未改上游缓存或安装版本。

以下Q为D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe，cwd为隔离源码；stage=.local/manual-delivery-output01/app。相同可选Office组件先通过19417文件源/目标清单与hash核验。首个暂存进程无输出且未生成组件目录，停止后使用真实Q路径/构建权限进行一次原命令，退出0；未删除或修改组件/清单。首个空日志和第二次日志保留，不把中止记作通过。

| 实际命令/步骤 | 退出及结果 | artifacts/日志 |
|---|---|---|
| Q tools/stage_office_runtime.py --runtime <原根已锁Office26.8.1目录> --stage stage | 0；19417文件完整核验并复制，源保持 | manual-office-stage02.log |
| Q tools/check_frozen_sources.py --exe stage/backend/study_backend.exe | 0；43模块/嵌套代码/常量匹配当前产品源码 | manual-frozen-sources01.log |
| Q tools/check_resource_explorer.py --exe stage/backend/study_backend.exe --test-root .local/manual-package-resources01 --documents --without-office | 0；导入/文档/布局/作答/删除/重启/0016保持，无组件分支 | manual-package-resources01.log |
| Q tools/check_library_integrity.py --exe stage/backend/study_backend.exe --test-root .local/manual-package-library01 | 0；锁/健康/孤立/只读/恢复另存/合并/三类容量及旧题图片核验等原链保持 | manual-package-library01.log |
| Q tools/check_office_previews.py --exe stage/backend/study_backend.exe --test-root .local/manual-package-office01 --runtime stage/converters/libreoffice --docx <交付自编中文公式.docx> --pptx <交付自编中文图表.pptx> | 0；DOCX/PPTX各2页、PDF67520/46266字节，原件hash/取消重试/缓存/重启/XML预算/公式图表通过 | manual-package-office01.log |
| Q tools/release_inventory.py --stage stage，随后Q tools/check_release.py stage（整包Office） | 生成0/20722文件，门禁1；officebean.dll导入jawt.dll缺失。此失败保留，不运行该分支的ISCC，不清除或忽略DLL | manual-release-inventory01.log；manual-check-release01.log |
| 将完整已核Office目录移至同一新交付根optional/libreoffice；Q tools/release_inventory.py --stage stage；Q tools/check_release.py stage | 均0；基础包1304文件集合/hash、x64/PE导入/CRT/CPython/无.db均通过。没有改检查器或Office固定清单 | manual-release-inventory02.log；manual-check-release02.log |
| 原ISCC.exe --define=BuildRoot=<stage绝对路径> --define=WebViewInstaller=<固定已签名离线安装器> --define=AppVersion=1.0.0 packaging/windows/setup.iss | 0；95.094秒，生成新的274385377字节安装器。只编译，未执行安装/卸载 | manual-installer-compile02.log |
| Q tools/check_office_previews.py同上，--test-root .local/manual-package-office02，--runtime .local/manual-delivery-output01/optional/libreoffice | 0；独立组件新位置同样DOCX/PPTX各2页，取消/重试/源hash/缓存/重启/预算全部保持 | manual-package-office02.log |

Java桥接缺口仅阻断完整Office并入基础安装器；不据真实Word/PPTX成功推断所有Office子库依赖闭合。按项目默认分发方式交付基础安装器，保留未经裁剪的独立Office组件与仅对子进程设置STUDY_OFFICE_RUNTIME的“启用Office分页.cmd”。未引入Java，不删officebean.dll、不改runtime-lock或放宽PE断言；基础包的完整门禁照常通过。扩展入口运行免安装版，先退出已有实例，Java桥接不在支持测试范围。完整Office整包依赖/SBOM/发行仍未完成，已在task保留。

最终本地目录为D:/computer_work/project/StudyWorkbench/dist/StudyWorkbench-Release-20261110-37a8d55/，含setup.exe、app/study_workbench.exe、optional/libreoffice、启用Office分页.cmd、自编测试样本、人工测试清单、启动说明、build-info.json及SHA256SUMS.txt。仅移动本代理新建暂存目录/新安装器，移动前逐项解析绝对路径并核在预期workspace/dist/暂存范围，目标存在则拒绝，不覆盖旧10-24安装器或个人数据；用户可填写的清单/样本先行复制，后续不覆盖其反馈。

安装器SHA256=a57847b7a9b99fafd7f123296b26cb21664bd994329eebdfe6a1f5a1a84f0361；主exe SHA256=873f7c560bb9b0a302ca99c370ddc20ce87772e9527a8c4fde8f4a0d2330e44f，版本1.0.0+1/Release。编译器、NuGet、app-local CRT和离线WebView安装器签名已核；本项目主exe/新安装器未签名，不称签名正式发行。基础安装包不含独立Office，免安装入口需系统已有WebView2，缺少时先使用安装版。build-info记录产物/源码/CI/artifact/实测退出码、失败和人工待反馈状态；原日志/JUnit/隔离库不进Git。

已向用户提供当前安装器和清单链接；用户人工结果尚未收取，没有代替用户启动应用、选择/迁移个人库、安装或窗口验收。产品代码仍为#18基线；本次后续提交只补task/本原报告的真实结果和未闭合项，不替换已交付二进制，打包输入继续明确标为37a8d55/CI #113。最终文档head仍需完整CI，构建来源CI和最终记录CI分别说明；自审与独立审查分开，未合并/公开发行，旧题目目录恢复仍规划。
