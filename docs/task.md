# 当前任务与交付状态

更新日期：2026-11-14。本表分开实现、自动化、审查、人工及交付；自动化数字属于各报告的当时版本，不代表本轮重跑或当前全产品通过。历史完整清单见[迁移前快照](../dev/archive/baseline-20261030/docs/task.md)，默认无需读取。

## 当前安排

**2026-11-06用户指令：取消人工测试及Computer Use/实际窗口测试，不再作为退出或继续开发门禁。以下历史未验不改记通过；未实现功能、自动化失败、代码审查和当前head CI仍须处理。产品内的用户授权/候选审核功能保留，模型继续暂不接入。规则见[ADR0013](adr/0013-cancel-manual-testing-and-bound-artifacts.md)。**

**2026-11-10最新指令：本批代码审查暂缓至全部本批任务完成后集中处理，人工测试/Computer Use继续暂停，不等待此前测试包反馈。每个小任务独立提交草稿PR；实现、相关自动化、文档与当前head CI继续，传递许可/漏洞/二进制完整性检查不跳过。旧审查、失败、人工清单与PR依赖保留，暂缓不记通过。冲突的旧门禁按[ADR0014](adr/0014-defer-review-and-deliver-small-prs.md)执行，不授权合并或发行。**

2026-11-10用户明确要求当前Release exe自行人工测试并汇报；仅启动本轮[人工测试清单](../dev/records/2026-11-06-learning-workbench-delivery/manual-test-20261110.md)，用户反馈待收取，不恢复全项目人工门禁，Agent不执行窗口验收。当前产品基线#18/2a884fe，[独立草稿PR #19](https://github.com/surface-user/StudyWorkbench/pull/19)在codex/manual-release-handoff补CI短期构建产物出口；37a8d55构建CI #113三组44步成功，基础安装器/免安装包及独立Office扩展已在本地生成，1304文件门禁、43冻结模块及真实资源/恢复/Office探针通过。整包Office集成的Java桥接依赖仍阻断，未跳过门禁；最终记录head CI、包路径/hash与交付结论见PR实时记录，未核实前待交付，不合并或公开发行。

2026-11-03用户已审阅并采纳通用学习工作台方向，并要求继续推进。LW-00已形成[契约](learning-workbench-contracts.md)和[ADR0012](adr/0012-learning-notes-anchors-and-backup.md)，设计复核待验；**LW-01自由笔记、LW-02位置书签与备注、LW-03内部链接及LW-04集中查找已本地实现，人工测试已取消，阶段未补记通过**，LW-05完整备份恢复已实现并通过自动化验证；LW-09冻结进程闭环通过，人工窗口测试已取消，工具旧超时保留历史；LW-06文本/XLSX只读切片已本地实现，最终0016包Office故障已定位并本地修补，DOCX/PPTX各两页及Calc矩阵复验通过，旧转储/失败保留，复杂文件自动化矩阵继续扩展，人工窗口测试已取消；LW-07直接下载切片已本地实现/冻结验证，11-12源码/冻结公网下载与整库恢复已通过，真实Range及重定向已由DL-01b/#38补齐；LW-08按用户11-05要求只完善授权/审核，已本地实现无模型候选流程，双Python回归/桌面构建/冻结闭环通过，人工测试已取消。完整备份设计已纳入LW-00，其余拟议表/API不列为已实现。

R1–R5、资料删除和统一导入已有实现继续保留；R6授权切片/PR #3继续交付跟进，模型等新增能力按LW-08后排。人工测试已取消；历史M0故障、失败证据与PR/当前head CI义务不取消。用户11-06明确授权当前版本提交/推送并创建PR后继续任务；[草稿PR #4](https://github.com/surface-user/StudyWorkbench/pull/4)已创建，base为未合并#3，两轮路径/schema探针失败保留，Office修补代码head 4cd157a已全CI通过（54ad12b前批绿灯及两轮红灯均保留）；文档/精选证据补交跟进同PR，当前head检查以PR实时状态为准；本批送审覆盖旧窗口前置顺序，人工测试已按最新指令取消，不授权合并或发行。批次交付与当前head CI见[交付报告](../dev/records/2026-11-06-learning-workbench-delivery/report.md)。

本轮开发维护：已清理重复产物并启用通过测试的临时目录自动回收，项目27.19→4.91GiB；相关21项及全量476通过，见[DOC-01报告](../dev/records/2026-10-30-documentation/report.md)。本轮维护提交的当前head CI另核，未合并/发行。

本轮远端核对（2026-11-10）：#2–#13均打开且未合并，各自当前head的PR CI通过，base/head依赖连续；#8依赖#7，纯核心原head冻结漏包失败已修补，API/UI另由#9/#10实现，05d/e/f容量统计分别#11/#12/#13，不重复开发。#13最终edf8350的CI #83成功，仅有明确标注的自审，无独立批准；CI通过不计作独立审查通过。具体head/运行/失败继续记M2-05原报告，后续远端变化以实时状态为准。

## 2026-11-12 并行调度

用户已明确要求主 Agent 调度三个子 Agent，持续推进剩余已授权任务。现行任务入口为 docs/task.md；目标中 doc/TASK.md、doc/tasks.md 指本表，不新增平行目录。READY 表示实施前置已满足；IN_PROGRESS 表示已领取；REVIEW 表示实现完成、等待主 Agent 核对自动化与退出证据；DONE 仅表示该有限任务开发交付完成，仍保留审查暂缓、人工取消、未合并/发行状态。BLOCKED 必须保留具体依赖，依赖满足后再转 READY；不把未知测试记为通过。

调度基线为 #22 的 ae4ecf5，沿用全部原任务和报告。父任务可以包含已交付子项，子项 DONE 不使整个父任务自动完成。三个子 Agent 使用独立源码副本/分支，主 Agent 检查结果并维护交付状态；本轮授权覆盖此前不创建子 Agent 的默认约束。状态变化继续原任务报告，实际交付分别创建草稿 PR 并核对最终 head CI。

| 任务 | 调度状态 | 依赖判断与下一步 |
|---|---|---|
| PLAN-06 并行调度登记 | DONE | 主Agent已核[草稿PR #23](https://github.com/surface-user/StudyWorkbench/pull/23)最终2645366的[CI #133](https://github.com/surface-user/StudyWorkbench/actions/runs/43057985634)成功；本轮继续维护原表和独立PR，不代表功能全部完成 |
| OFF-01 | DONE | #22诊断开发交付已完成；本轮另核该head CI，OFF-02缺口仍保留 |
| OFF-02 | IN_PROGRESS | Java/CRT固定组合、配置隔离及保守加载域已交付；本批纳#48后剩145未知，完整Python/托管/x86加载及最终发行继续，不安装系统Java、不绕过门禁 |
| OFF-02a 固定Java组件准备 | DONE | 主Agent已核37×2专项、315文件及关键PE/hash；[草稿PR #28](https://github.com/surface-user/StudyWorkbench/pull/28)最终2187fec的[CI #153](https://github.com/surface-user/StudyWorkbench/actions/runs/43065303373)成功；固定准备工具已纳本轮候选，整包OFF-02继续 |
| REL-03a 源锁文件漏洞查询 | DONE | 主Agent已核42×2专项/实际135包查询和原始证据hash；[草稿PR #32](https://github.com/surface-user/StudyWorkbench/pull/32)最终89f0d77的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43071363779)成功；原2包12公告/6CVE由REL-03b/c分别修复复验，Git/SDK/数据库快照/最终包仍不完整，父REL-03不销项 |
| INT-01 首批组合回归 | DONE | 主Agent已核[草稿PR #31](https://github.com/surface-user/StudyWorkbench/pull/31)最终b8d534a的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43069606085)三组成功；本地760及77子测试通过，已交付有限首批组合；报告继续[批次记录](../dev/records/2026-11-12-parallel-batch/report.md) |
| OFF-02b Office配套Java/CRT组合 | DONE | 主Agent已核38×2专项、19742文件/原生框架及源码/新冻结转换；[草稿PR #33](https://github.com/surface-user/StudyWorkbench/pull/33)最终e0a3fcf的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43072881498)三组44步成功；有限组合运行时开发交付完成，完整加载域/发行仍在OFF-02c及REL任务继续 |
| OFF-02c PE加载域门禁 | DONE | 主Agent核双Python各84、实际351 PE/277未知及严格拒绝；[草稿PR #36](https://github.com/surface-user/StudyWorkbench/pull/36)最终fbbc847的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43092944364)第二次三组44步通过，原上传失败保留；已纳本组合，完整OFF-02仍未闭合 |
| OFF-02d 固定UNO注册加载域 | DONE | 主Agent核双Python各102、固定53入口/新增54覆盖/223未知及5负例；[草稿PR #39](https://github.com/surface-user/StudyWorkbench/pull/39)最终2da4306的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43359332568)三组44步成功，已纳本组合，未知仍阻断发行 |
| OFF-02e 受控Office配置来源 | DONE | 主Agent核44×2及override拒绝1×2、源码/新冻结各3页和8次真实子进程argv/env摘要，[草稿PR #44](https://github.com/surface-user/StudyWorkbench/pull/44)最终f473abc的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43367142676)三组44步成功。该功能已纳本组合，OFF-02剩余加载域继续，不新增扫描支持或豁免TWAIN |
| OFF-02f 固定JRE DLL加载域 | DONE | 主Agent核[PR #48](https://github.com/surface-user/StudyWorkbench/pull/48)最终c1877b7的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43570645325)成功、115×2专项及89原件；86 DLL根/新增78覆盖/剩145，本批纳其原代码，不替代完整OFF-02 |
| OFF-02g 固定Python启动器模板来源与角色 | DONE | 主Agent核[PR #51](https://github.com/surface-user/StudyWorkbench/pull/51)最终6f38309的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43576310542)三组45步成功及1011×2/专项142×2；667文件/14模板/2producer来源相符，仍unclassified且145未知。本批纳证据工具，不作运行域豁免 |
| OFF-02h 固定JRE启动器保守域 | DONE | 主Agent核[PR #55](https://github.com/surface-user/StudyWorkbench/pull/55)最终6d1078f的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43583174480)成功，双1188/Flutter203/44模块新冻结及既定链通过；相关123×2、19743原件及99 Java根/仅12 EXE新增覆盖已核，133未知仍阻断发行，有限DONE不代表实际调用/全Office通过 |
| REL-03b pytest漏洞修复 | DONE | 主Agent已核独立环境/原失败复验、SBOM及OSV旧新版本对照；[草稿PR #35](https://github.com/surface-user/StudyWorkbench/pull/35)最终a73bedd的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43092294564)三组通过，本组合锁为9.0.3 |
| REL-03c Starlette漏洞修复 | DONE | 主Agent核双Python各828及77子测试、89专项/23兼容组合与实际冻结/135包查询；[草稿PR #40](https://github.com/surface-user/StudyWorkbench/pull/40)最终b48b711的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43359261755)三组44步成功，本组合已纳1.3.1；原发现/在线覆盖未知保留 |
| INT-02 第二批组合回归 | DONE | 主Agent核[草稿PR #37](https://github.com/surface-user/StudyWorkbench/pull/37)最终54d26ec及[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43093356970)第二次三组44步通过；原上传失败保留，本地882及77子测试/Flutter200，见[批次报告](../dev/records/2026-11-12-parallel-batch/report.md) |
| INT-03 第三批组合回归 | DONE | 主Agent已核[草稿PR #43](https://github.com/surface-user/StudyWorkbench/pull/43)最终c666db9的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43365961531)三组45步成功、双Python各971及全部冻结链；本地971及77子测试/Flutter203，见[批次报告](../dev/records/2026-11-12-parallel-batch/report.md)。当前有限组合开发交付完成，正式发行父项保留 |
| INT-04 第四批组合回归 | DONE | 主Agent核[PR #49](https://github.com/surface-user/StudyWorkbench/pull/49)最终68eaabd的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43574318173)三组46步全部成功，含源码/冻结公网续传重定向；本地1063及77子测试/Flutter203、新冻结44模块及Office链通过。原报告保留全部边界，完整发行父项继续 |
| INT-05 第五批来源与加载域组合 | DONE | 主Agent核[PR #53](https://github.com/surface-user/StudyWorkbench/pull/53)最终b09da16的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43580584516)成功：双后端完整1180×2、Flutter203、44模块新冻结及既定链通过；46步45成功、原分支限定公网探针1跳过且不补记公网通过。497文件/真实来源与145未知有限验收，见[批次报告](../dev/records/2026-11-12-parallel-batch/report.md) |
| M3-03d 学习记录规模回归 | REVIEW | [PR #56](https://github.com/surface-user/StudyWorkbench/pull/56)已交付源码/既有#49冻结两端1k/10k/100k六档自动化，修正测试TEMP后均通过，保留旧stub/权限/溢写失败；当前head CI/主Agent核证待完成，独立工具未纳本候选 |
| REL-01a 源码锁文件标准SBOM | DONE | 主Agent已核双Python专项各35、136源码包/8个SDK未知、官方Schema；[草稿PR #25](https://github.com/surface-user/StudyWorkbench/pull/25)最终1b52eb3的[CI #141](https://github.com/surface-user/StudyWorkbench/actions/runs/43060243273)成功；仅源码范围，父REL-01仍未完成 |
| REL-01b 冻结后端SBOM | DONE | 主Agent核969实体hash/15metadata/2721PYZ与140×2专项，[草稿PR #42](https://github.com/surface-user/StudyWorkbench/pull/42)最终fb5b7a2的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43366003202)三组44步成功。工具已纳本组合；剩余2678模块/103PYD/非PE数据归属等由REL-01c映射，不据物理覆盖宣称完整身份 |
| REL-01c 冻结Python本地来源映射 | DONE | 主Agent核[PR #47](https://github.com/surface-user/StudyWorkbench/pull/47)最终d6bef38的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43570337629)成功、918×2/专项38×2；55包2358模块861实体，本批纳工具，与REL-01d共同追溯，不等于官方归档认证 |
| REL-01d 固定CPython及项目来源映射 | DONE | 主Agent核[PR #50](https://github.com/surface-user/StudyWorkbench/pull/50)最终0e295a7的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43575980520)三组44步成功、957×2及最终专项39×2；新增311 PYZ/154 ZIP代码/62实体/11启动代码来源与独立探针相符，58组件Schema通过；44 CRT/外层bootloader等仍未闭合，本批纳工具 |
| REL-01e 原生CRT与bootloader来源 | DONE | 主Agent核[PR #54](https://github.com/surface-user/StudyWorkbench/pull/54)最终24405f0的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43581479380)三组44步成功/双1000及43模块旧冻结；只读重核969实体/44本地CRT/5节与精确DEBUG差异/58组件Schema。工具未纳本候选，官方CRT/完整PE认证仍未知 |
| REL-01 完整源码与发行包SBOM | IN_PROGRESS | 先交付01a；最终覆盖仍依赖OFF-02及所有实际组件/安装器payload，不能据源锁文件或环境包表销项 |
| REL-02 | BLOCKED | 完整发行传递许可依赖REL-01实际组件清单；源锁与固定Office/Java就绪，已有范围可单独先核，整体不记完成 |
| REL-02a 锁定源码许可证据映射 | DONE | 主Agent核双Python各57、136包/246原文引用/182文本及缺文退出2；[草稿PR #41](https://github.com/surface-user/StudyWorkbench/pull/41)最终218cfc2的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43359882156)三组44步通过，工具已纳本组合。归档/内嵌声明/最终义务仍未闭合，不是完整REL-02通过 |
| REL-02b 源包许可补全 | IN_PROGRESS | latex2mathml3.81.1官方wheel/sdist缺项目LICENSE，固定tag另有MIT原文，内嵌unimathsymbols.txt声明LPPL且有vendor修改；需分别核来源/原文/通知及修改条件，不将全包标为单一MIT，完整REL-02继续 |
| REL-02b1 固定上游许可原文及内嵌声明 | DONE | 主Agent核72×2/136包248原文引用184文本及九文件来源，[草稿PR #46](https://github.com/surface-user/StudyWorkbench/pull/46)最终8bebad8的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43569063314)三组45步成功，当前已纳本组合。原分发缺文/LPPL原Work和vendor修改条件仍保留，CLI退出2，父REL-02b/02未完成 |
| REL-03 | IN_PROGRESS | 03a查询与03b/c两项修复已交付；已修复源锁135包无返回公告仅代表本次在线查询，数据库覆盖/最终组件和完整复扫仍依赖REL-01 |
| REL-04 | BLOCKED | 依赖REL-01至03；真实签名另缺发行身份，配置/篡改拒绝自动化不代表已签 |
| REL-05 | BLOCKED | 依赖OFF-02与REL-01至04；候选组装完成后仍需REV-01，发布/合并未授权 |
| FMT-01 | DONE | 主Agent已核复杂矩阵76×2、源码/新冻结DOCX/PPTX各3页及XLSX2表15格、有限无短名目录；[草稿PR #30](https://github.com/surface-user/StudyWorkbench/pull/30)最终c352424的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43067590610)成功；不代表任意文档保真/整卷禁用8.3，见[原报告](../dev/records/2026-11-04-lw06-formats/report.md) |
| PAR-01 | DONE | 主Agent已核双Python专项各30及12项环境失败的原生复验，原失败保留；[草稿PR #26](https://github.com/surface-user/StudyWorkbench/pull/26)最终1d103f3的[CI #149](https://github.com/surface-user/StudyWorkbench/actions/runs/43061041645)成功；限定显式题号/共享材料候选范围，见[报告](../dev/records/2026-11-12-complex-question-splitting/report.md) |
| PAR-02、PAR-03 | READY | 设计工作可先行；OCR实施依赖固定离线组件/语言资源评估，分块实施依赖预算/取消/重启契约，禁止直接放宽保护 |
| DL-01 | DONE | 主Agent结合已验收#24核#38真实Range/同域与跨域重定向及未注入冻结恢复，原DL-01证据范围已完成；LW-07站点提取/转码等后续保留 |
| DL-01a 公网下载与恢复证据 | DONE | 主Agent已核源码/冻结公网下载、独立摘要、重启/整库恢复及无强ETag拒绝；[草稿PR #24](https://github.com/surface-user/StudyWorkbench/pull/24)最终91db704的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43059706025)成功；该切片当时未覆盖的真实Range/重定向已由#38补齐，父DL-01已DONE |
| DL-01b 公网Range与重定向 | DONE | 主Agent已核[草稿PR #38](https://github.com/surface-user/StudyWorkbench/pull/38)最终842b19d的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43362970857)三组46步成功及原始摘要；真实源码206与冻结恢复结果通过，旧DNS/MIME/探针失败保留。诊断工具已纳本组合，产品下载代码未变 |
| DL-02 | IN_PROGRESS | 用户已选B站、抖音、爱奇艺，B站先行；#45共同设计已交付，DL-02b有限元数据/质量预览先实施，真实传输与DL-03格式交接后续继续，不以预览代替整个下载目标 |
| DL-02a 站点提取共同设计 | DONE | 主Agent核[草稿PR #45](https://github.com/surface-user/StudyWorkbench/pull/45)最终517bcd4的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43367244690)三组成功及4文档/82引用/6锚点；规划契约已纳本组合，三站真实提取与组件采用仍未完成 |
| DL-02b1 B站受控格式预览 | BLOCKED | [PR #52](https://github.com/surface-user/StudyWorkbench/pull/52) v2/b293449的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43581781896)源码与冻结均公开page/HTTP412，前两次失败保留；离线通过不代替公网正向，尚未纳本候选，三站与真实下载继续 |
| DL-03 | BLOCKED | 依赖明确的格式/轨道交接及FFmpeg实际二进制/许可选择，不要求整个DL-02完成，避免与DASH/HLS支持循环等待 |
| LW-04a | DONE | 主Agent已核58×2专项、Flutter19/全量200及失败保留；[草稿PR #29](https://github.com/surface-user/StudyWorkbench/pull/29)最终9027508的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43066543568)成功；有界TXT全文/原文行回跳已纳本轮候选 |
| LW-07a | DONE | 主Agent已核双Python专项各11、Flutter专项6/全量196及静态检查；[草稿PR #27](https://github.com/surface-user/StudyWorkbench/pull/27)最终6af0360的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43060817695)成功；50条历史分页/刷新/迟到响应开发交付完成，审查暂缓，见[原报告](../dev/records/2026-11-05-lw07-downloads/report.md) |
| UPD-01 | BLOCKED | 完整升级回滚流程依赖稳定发行产物和签名方案；保留旧库保护，未授权发布更新 |
| API-01 | DONE | 主Agent按原退出条件核API-01a兼容结构/脱敏/关联ID及调用方与冻结实证；[草稿PR #34](https://github.com/surface-user/StudyWorkbench/pull/34)最终8b29a27的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43091834219)三组45步通过，API-01/a有限开发交付完成，已纳本组合；历史Office偶发失败保留 |
| M2-05i | READY | 05g/h巡检及完整备份已实现；先设计身份/来源/附件关系与显式确认，不自动恢复或删除 |
| M2-05j | BLOCKED | 依赖05i的关系设计；容量报告已实现，实际清理另需具体授权 |
| M3-03a、M3-03b、M3-03c | READY | 富内容、知识关系、复习评价分别先明确契约；M3-03d已单列REVIEW，不把规模回归当作算法效果通过 |
| WEB-01、MED-01 | READY | 既有隔离WebView/媒体服务可用于自动化矩阵；模拟/HTTP不冒充实际解码或硬件证据 |
| R6-01 | IN_PROGRESS | 现有临时grant和普通资料接口可复用；先由R6-01a落实明确资料/笔记/书签、位置/用途/版本/预算与撤销边界，再分API/UI实施；不接模型/凭据或扩大旧analyze_attempts授权 |
| R6-01a 通用资料受控读取契约 | DONE | 主Agent核[PR #58](https://github.com/surface-user/StudyWorkbench/pull/58)最终13f4163的[CI](https://github.com/surface-user/StudyWorkbench/actions/runs/43585526915)成功、双1188/203/44新冻结与499原blob；只完成设计，b/c/d/e另行落地，见原报告 |
| R6-01b 封闭授权与文本读取API | REVIEW | 基于#58实现封闭purpose/选择、共享配额与元数据/版本绑定文本/旧笔记/标记；双1216+77子测试、源码/新冻结HTTP各57、45冻结模块核源和只读库回归已过，旧grant兼容；独立PR/当前CI待交付，无模型/迁移，见原报告 |
| R6-01c 资料范围确认与撤销UI | BLOCKED | 依赖b明确接口；普通UI逐项/版本/正文确认，保留草稿、撤销/到期与迟到响应，不向外站WebView提供桥或令牌 |
| R6-01d 无模型组合回归 | BLOCKED | 依赖b/c；源码/冻结、旧grant/候选采用、空间与源变更/重启/全库不恢复grant分别自动化，不接模型，不以设计替代功能完成 |
| R6-01e 其他格式正文提供器 | IN_PROGRESS | 首批仅设计原PDF或ready Office派生PDF的一个明确页文字层，正文尚未实现；e1/e2/e3分开交付，其他格式/结构正文/OCR/网页/转写及模型继续保留，不以元数据或设计代替整个e完成 |
| R6-01e1 PDF及Office页文字层契约 | REVIEW | 基于#63已实现文本API，单页/源与派生hash/精确页级引用、共享预算和严格取字/子进程边界已设计，见[Agent规划契约](agent-design.md#pdf及office派生页文字层规划中r6-01e1)及[原报告](../dev/records/2026-11-14-resource-read/report.md)；仅三文档，父#63 CI及本设计独立PR/当前head CI待核，未实现provider |
| R6-01e2 PDF页文字提供器实现 | BLOCKED | 依赖b和e1有限交付；封闭表示/单页/版本、源与派生有界读取、专用PDFium worker与严格Unicode/共享16MiB/20秒/128KiB输出及负例，保留旧用途/文本；不得自动Office转换或返回截断前缀 |
| R6-01e3 单页确认及无模型组合 | BLOCKED | 依赖e2及c普通资料UI；明确原件/派生版本和页码、正文另选、撤销/到期/迟到响应；源码/新冻结核源及旧grant/普通查看/学习库保持，不接模型或自动OCR |
| R6-02 | BLOCKED | 待用户明确模型提供方/远端范围/候选场景，并依赖R6-01；继续无模型/无凭据 |
| REV-01 | BLOCKED | 依ADR0014等待本批已确定开发/自动化切片完成后集中审查；本轮REVIEW只指主Agent核验交付证据，不冒充独立代码审查 |
| M0-08及统一导入历史自动化 | READY | 可继续只读/隔离启动恢复和原生COM回归；原失败/个人库保持，不恢复人工门禁 |
| M0/M1硬件交互、人工安装/干净机、真实站点/硬件人工项 | 暂停 | 依用户取消/暂停人工测试安排，不调度Computer Use；暂停不记DONE或测试通过 |

M2-03由已交付LW-05承接；M2-04由PAR/FMT、M2-05由既有a–h及后续i/j、M3-03由a–d、M4由DL/WEB/MED、R6由R6-01/02承接，父条目继续保留。LW-06/07/08整体及正式发行仍未完成。PLAN-03/05和已交付学习功能不重复实施。

## 当前任务

| 任务 | 实现 | 自动化 | 审查 | 人工/阶段 | 报告及PR交付状态 |
|---|---|---|---|---|---|
| DOC-01 文档治理 | 本地整理完成；11-04消除doc平行入口、路线/记录归位并补齐dev索引 | 旧819证据/16快照等结果保留；本次文档/引用及历史文件保持检查见原报告，不重跑业务测试 | 本次结构自审完成，非独立人工批准 | 人工测试已取消（用户11-06）；不补记阶段通过 | [原报告](../dev/records/2026-10-30-documentation/report.md)持续记录；文档改动纳入本批阶段PR；原报告持续记录，不冒充用户文档批准 |
| R1 资源目录/受管添加 | 已实现 | 当批双Python各154、Flutter66、Windows及冻结专项；另有HTTP黑盒 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [实施](../dev/archive/reports/r1-validation.md)、[黑盒](../dev/archive/reports/r1-blackbox-2026-10-29.md)；PR见下方集成说明 |
| R2 资源身份标签/layout兼容 | 已实现 | 当批后端156/发行定向38、Flutter68、Windows；另有HTTP黑盒 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [实施](../dev/archive/reports/resource-continuation-2026-10-26.md)、[黑盒](../dev/archive/reports/r2-blackbox-2026-10-29.md) |
| R3 查看器/工作副本/Office静态预览 | 受限范围已实现 | 当批双Python各176及最终专项各13、Flutter75、原生/冻结；另有黑盒 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [Office交付](../dev/archive/reports/r3-office-validation-2026-10-26.md)、[黑盒](../dev/archive/reports/r3-blackbox-2026-10-29.md) |
| R4 QuestionFile/不可变确认版 | 已实现 | 当批串行双Python各205、Flutter82、Windows/冻结；并发owner启动超时失败保留 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [交付](../dev/archive/reports/r4-validation-2026-10-26.md)、[黑盒](../dev/archive/reports/r4-blackbox-2026-10-29.md) |
| R5 学习事件/笔记/知识点投影 | 已实现 | 当批双Python各208、Flutter83（2跳过）、Windows/Release/冻结 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [交付](../dev/archive/reports/r5-completion-2026-10-29.md)、[黑盒](../dev/archive/reports/r5-blackbox-2026-10-29.md) |
| 资料树删除/0012 | 已实现，保留原件历史 | 当批后端212、Flutter86、Windows1、Release/冻结 | 当批完成 | 人工测试已取消（用户11-06）；不补记阶段通过 | [报告](../dev/records/2026-10-30-resource-removal/report.md)；已随PR #2提交的历史记录见统一导入跟进 |
| 统一添加/导航/搜索/原件复用 | 已实现，含PR竞态修复 | PR跟进记载Flutter91、静态/原生COM自检通过；自建样本Windows集成被单实例锁阻断，不能记通过 | 当批自审已记录，非独立人工批准 | 人工测试已取消（用户11-06）；不补记阶段通过 | [报告](../dev/records/2026-10-30-unified-resource-import/report.md)、[PR跟进](../dev/records/2026-10-30-unified-resource-import/pr-review.md)；11-10核对[PR #2](https://github.com/surface-user/StudyWorkbench/pull/2)的29f23d3当前head CI #16成功、仍打开未合并；保留原被阻断集成，不据CI销项 |
| R6 可选Agent（原M5-AI） | 原临时授权/摘要切片已实现；新增正文范围及人工候选审核见LW-08；模型/凭据等未实施 | API定向10项（前批）；本批Flutter93项、定向6项、静态分析及Windows Release通过；首构失败保留 | 本批自审完成；严格确认校验已修 | 人工测试已取消（用户11-06）；不补记阶段通过 | [设计](agent-design.md)、[报告](../dev/records/2026-11-03-r6-agent-access/report.md)；已接授权UI，无模型/凭据；[PR #3](https://github.com/surface-user/StudyWorkbench/pull/3)已创建，依赖#2；原报告保留head 7aa8251 CI运行中快照；11-06已核对该head CI全通过，仍未合并/发布，用户/完整阶段待验 |

R1–R5集成交付：保留PR #1的CI临时目录与路径别名失败、修复及复测记录，见[历史任务快照](../dev/archive/baseline-20261030/docs/task.md)与[黑盒总报告](../dev/archive/reports/blackbox-review-2026-10-29.md)。本地PR #2报告记载main已含该集成，远程最终状态本轮未核验；取消人工测试不补造历史通过。

## 接下来的开发任务（LW路线）

LW-00设计已形成，LW-01至05本地实现与验证见各任务报告，人工测试已取消，文档复核不阻塞继续开发；LW-09冻结进程闭环及LW-06文本/XLSX已测；11-06用户已取消人工窗口测试，不再重试Computer Use。LW-06已补真实离线Office/Calc样本，字符串兼容修补继续回归；LW-07传输/队列/UI已本地实现并通过当批442后端/145Flutter与冻结闭环，11-12同一公开源的DNS预检、源码/冻结下载和整库恢复通过，真实Range/重定向已由#38补齐，人工窗口测试已取消；LW-08授权/人工候选审核已实施，默认摘要兼容、正文另选、独立MD采用与恢复，无模型接入，自动化/自审继续。详细范围及退出目标见[路线第5节](learning-workbench-roadmap.md#5-已确定的任务顺序与实施范围)及[契约](learning-workbench-contracts.md)。先设计再实现，不把路线名称当作现有接口；所有任务退出仍执行本页统一条件。

| 编号/优先级 | 任务与依赖 | 当前状态、下一步与关键退出证据 |
|---|---|---|
| PLAN-02 / 本轮文档 | 采纳方向与排期 | 本地文档完成、自审完成，链接/状态检查见[报告](../dev/records/2026-11-03-learning-workbench-direction/report.md)；用户文档复核不阻塞继续开发；已纳入PR #4 |
| LW-00 / P0，设计待验 | 普通学习流程、笔记权威、位置/链接、格式等级和备份契约设计 | 本地设计/课程桌面走查/自审完成，文档自动检查见报告；无新增业务实现，用户文档复核/人工测试已取消；[契约](learning-workbench-contracts.md)、[ADR0012](adr/0012-learning-notes-anchors-and-backup.md)、[报告](../dev/records/2026-11-03-lw00-contracts/report.md)；已纳入PR #4，不再以人工测试阻塞 |
| LW-01 / P0，已交付 | 自由新建/编辑笔记；依赖00设计 | 已实现0013/幂等收据/创建恢复/目录与资料媒体入口/已有MD选择；旧notes保留。后端229、Flutter全套99/末轮笔记6、静态及Windows Release通过，首轮失败与限制见[报告](../dev/records/2026-11-03-lw01-notes/report.md)；本批自审完成、非独立批准；人工测试已取消，不补记阶段通过。纳入本批阶段PR；未合并/发行 |
| LW-02 / P0，已交付 | 位置书签与备注；依赖00/01 | 已实现0014/版本锚点/命名备注/修订与笔记关系；PDF与Office分页、MD/TXT原文行、媒体时间、失效提示及来源回跳。后端全套239、末轮专项10、Flutter全套112、静态及Windows Release通过；失败与边界见[报告](../dev/records/2026-11-04-lw02-marks/report.md)。本批自审完成，非独立批准；真实窗口/播放定位/用户人工测试已取消，阶段未补记通过。纳入本批阶段PR；未合并/发行 |
| LW-03 / P1，已交付 | 内部超链接；依赖02 | 已实现严格v1 URI/受控resolve、资源/书签/旧笔记复制、MD插入跟随及运行时往返；后端269、Flutter121、静态及Windows Release通过。本批自审完成、非独立批准；真实窗口/剪贴板/WebView/用户人工测试已取消，阶段未补记通过；[报告](../dev/records/2026-11-04-lw03-links/report.md)。纳入本批阶段PR；未合并/发行 |
| LW-04 / P1，已交付 | 学习记录集中查找；依赖01至03 | 已实现MD当前正文/旧笔记/书签备注有界搜索、稳定分页/截断、结果版本重验；后端281、Flutter127、静态及Windows Release通过。本批自审完成、非独立批准；人工测试已取消，不补记阶段通过；[报告](../dev/records/2026-11-04-lw04-search/report.md)。纳入本批阶段PR；未合并/发行 |
| LW-05 / P1，已交付，设计前置到00 | 完整学习库备份恢复；依赖01至04的数据覆盖 | 离线整库快照/ZIP校验、新空目录恢复、SQLite表/文件/关系核对、普通UI/取消/配置激活已实现；后端全套343、后补专项16、Flutter136、分析/Windows Release通过，LW-09后补全套137。自审完成，人工测试已取消；发行未授权；M2-03完整备份实现已由本任务承接；[报告](../dev/records/2026-11-04-lw05-backup/report.md)。纳入本批阶段PR |
| LW-09 / 自动化集成已交付 | 无Agent学习流程集成；依赖01至05 | 冻结真实后端串联导入→笔记/标记→链接/搜索→重启/整库恢复，源hash及SQLite摘要一致；11-05扩展JSON/XLSX闭环通过，媒体仅导入、实际播放未验证。11-04Flutter137/分析/隔离构建结果保留；11-05用户允许恢复操作后Computer Use启动两次超时，人工测试已取消，旧窗口失败仅保留历史。自审及限制见[报告](../dev/records/2026-11-04-lw09-integration/report.md)；纳入本批阶段PR，自动化集成交付完成 |
| LW-06 / P2，进行中 | 格式支持矩阵与扩展；依赖00 | UTF-8文本与XLSX多表只读单元格/公式缓存/资源级标记已本地实现；后端全套380、专项30、末轮Flutter142、静态/Windows Release及冻结真实进程恢复通过，失败保留见[报告](../dev/records/2026-11-04-lw06-formats/report.md)。本批自审完成；复杂Office/XLSX自动化矩阵仍可扩展，人工测试已取消，旧DOC/PPT/XLS与保真编辑未扩展。纳入本批阶段PR；未合并/发行；最后0016冻结包失败现场和转储完整保留；11-06修补冻结DLL继承与深目录兼容，双Python各476、DOCX/PPTX各两页、Calc及冻结业务/CI探针通过，页图四页已检查；本轮自审完成，人工测试已取消，无短名卷自动化仍待补，代码head 4cd157a全CI通过，文档补交CI见PR实时检查，见原报告 |
| LW-07 / P2，进行中 | 视频获取/下载；依赖00、既有媒体，批量使用前接入05 | 首批公网IPv4 HTTPS/443原始媒体、0015队列/幂等/暂停/恢复/受管入库与普通UI已本地实现；当批后端442、Flutter145、analyze/Windows/冻结通过，详见[报告](../dev/records/2026-11-05-lw07-downloads/report.md)。Commons真实来源测试因DNS返回禁止网段而失败，未放宽边界；11-12同一源的源码/冻结下载、独立hash及整库恢复通过；原源缺强ETag的拒绝保留，DL-01b已补另一公开样本的真实续传和重定向；人工测试已取消，发行未授权。未引入yt-dlp/FFmpeg、无登录/DRM/转码；纳入本批阶段PR；未合并/发行 |
| LW-08 / P3，进行中 | R6剩余授权/受控读取/审核；依赖00至05及格式提取 | 用户11-05明确先授权/审核、暂不接模型。0016外部候选/修订、默认摘要与另选作答正文/历史确认版、普通UI独立采用MD已本地实现；双Python全量各468、Flutter153、静态/Windows/冻结闭环通过；本地自审完成，独立人审未执行，失败修正见[报告](../dev/records/2026-11-05-lw08-authorization-review/report.md)。授权/审核切片待验，LW-08整体仍进行中。不接模型/凭据，不下载模型；人工测试已取消，阶段未补记通过。其他资料工具/候选场景继续规划，不冒充整个R6完成；原PR #3交付义务保留，本批纳入阶段PR，未合并/发行 |

交付规则：LW-00复核待验，LW-01至04本地交付/人工测试已取消；其余任务实施前明确报告、提交/PR、审查与当前head CI要求。本批已授权推送/PR，未授权合并/发行。所有新增数据从首个迁移即备份、校验、保留旧数据；完整恢复能力是首轮学习流程交付门槛。外部目录原地工作区、完整代码IDE、Office等价编辑和未确认Agent场景不自动加入实现。

## 本批任务拆分（2026-11-10）

以PR #19最终197a276为分析基线，其当前head [CI #115](https://github.com/surface-user/StudyWorkbench/actions/runs/42794594783)本轮查询为success；这是父基线结果，不代替下列新PR的CI。原根仍为#7，不能据旧checkout重复开发#8–#19能力。所有子项继承各自父任务并保留原条目；下列除PLAN-03外均为待实施/待设计，未登记已完成。分析、影响范围与命令见[发行原报告](../dev/records/2026-11-10-release-integrity/report.md)。

| 编号/顺序 | 小任务及依赖 | 当前状态与退出证据 |
|---|---|---|
| PLAN-03 / 首项 | 现状分析、拆分及新安排落地 | 文档自动化通过；已提交[独立草稿PR #20](https://github.com/surface-user/StudyWorkbench/pull/20)，依赖#19，最终head CI与开发交付结论见该PR实时记录；代码审查暂缓、人工暂停，本项不实现以下功能 |
| OFF-01 / P0，诊断已完成、待交付，属R3/发行 | Office Java/原生加载闭合诊断与分发方案；先于整包发行 | 11-11已核19417文件/244个PE、4条延迟导入及程序目录递归图；两种自编文件各2页，Job内加载采样确认System32 CRT和Office Python/Java框架，Bean加载预期失败126。采样错误/动态分支限制保留，未安装Java/改组件/放宽门禁；[原报告及精选证据](../dev/records/2026-11-10-release-integrity/report.md)；已提交[独立草稿PR #22](https://github.com/surface-user/StudyWorkbench/pull/22)，依赖#21，最终head CI与诊断交付结论见该PR实时记录，代码审查/人工暂缓，OFF-02整包仍未闭合 |
| OFF-02 / P0，依赖OFF-01 | 落实固定离线Java/CRT运行时及加载方案 | 11-12用户委托技术判断后主Agent选择项目内Temurin 21.0.13+9 x64 JRE，由OFF-02a先准备固定包/许可/清单；OFF-02b已实现固定组合及进程专用Java配置，源码/新冻结转换与Office框架/JVM/桥接包内加载有有限证据；OFF-02c完整PE加载域/延迟导入门禁及最终发行组合继续。保留原组件清单，新增组件/布局另锁定，冻结转换/源hash/取消重启和无开发依赖自动化复验；不只补jawt.dll、不依赖开发机System32，不删DLL/白名单绕过，整包仍未完成 |
| REL-01 / P0，属M0-02/M1-04 | 标准SBOM与源码/最终包对照；最终版依赖OFF-02及所选可选组件 | 进行中；REL-01a源码锁文件切片经主Agent核验已DONE，证据见上方调度及[原报告](../dev/records/2026-11-10-release-integrity/report.md)。Python冻结/native、Flutter/Dart SDK、NuGet、CRT/WebView2、Office/Java及安装器payload仍未覆盖；未知组件显式列出，不把源锁文件或构建环境列表当全产品SBOM |
| REL-02 / P0，依赖REL-01 | 完整传递许可与来源义务 | 进行中；REL-02a本地源锁许可原文映射已由#41交付，当前组合已纳工具；latex2mathml缺项目原文且内嵌LPPL另由02b补全。最终组件/归档来源/内嵌通知/源码提供义务/实际构建配置继续核，未知或缺文不记通过，完整父项仍依赖REL-01 |
| REL-03 / P0，依赖REL-01 | 漏洞检查与修复复验 | 进行中；REL-03a原2包12公告/6CVE保留，pytest9.0.3与Starlette1.3.1修复由#35/#40交付并纳本组合。#40本次135源包在线查询无返回公告；数据库覆盖/快照未知和最终组件复扫仍未闭合，见上方调度及[原报告](../dev/records/2026-11-10-release-integrity/report.md) |
| REL-04 / P1，依赖REL-01至03 | 签名准备与验签；实际签名需发行身份 | 待实施；签名服务/身份未指定，不声称无证书或已签；先实现显式配置/缺失拒绝/篡改失败，真实SHA256签名与时间戳后更新清单；第三方签名不冒充项目签名 |
| REL-05 / P1，依赖OFF-02、REL-01至04 | 发行候选组装与可追溯准备 | 待实施；配套前后端、签名后payload清单/SBOM、许可、扫描结果、安装器签名与外置最终hash/构建来源、当前head CI一致；自动化验证升级/卸载数据保护；人工/干净机暂停，合并/正式发布另授权 |
| FMT-01 / P1，属LW-06/R3 | 扩展复杂DOCX/PPTX/XLSX安全/版式矩阵 | DONE，有限矩阵开发交付完成；76×2专项、源码/新冻结3页DOCX/PPTX和2表15格XLSX、有限无短名目录及#30最终head CI均经主Agent核验，见上方调度和[LW-06报告](../dev/records/2026-11-04-lw06-formats/report.md)。损坏压缩流异常已修，旧失败保留；不认证任意保真/整卷无短名/极端路径；审查暂缓、人工取消，未合并/发行 |
| PAR-01 / P1，属M2-04 | 复杂题号/共享材料确定性候选 | DONE，有限题号/显式范围候选交付完成，双Python专项各30、原生复验及#26最终head CI已由主Agent核验，见上方调度和[原报告](../dev/records/2026-11-12-complex-question-splitting/report.md)。跨页原图/区域随MD保留，缺号/重号/乱序不关联，原件/旧确认版不变；OCR、多栏、任意编号不在本切片，审查暂缓、人工取消，未合并/发行 |
| PAR-02 / P2，属M2-04，依赖样本/组件评估 | 多栏与离线OCR分开切片设计/实现 | 待设计；固定离线组件/语言资源/许可/预算后分别PR，多栏阅读顺序/OCR置信提示/拒绝/超时/重启有自动化；不自动下载模型或上传资料 |
| PAR-03 / P2，属M2-04 | 更大文档/分块任务 | 待设计；原件/页区间/进度与取消/重启/幂等/预算契约先行，不直接放宽25秒/20页等原保护；旧小文件回归保持 |
| DL-01 / P1，属LW-07 | 当前直接HTTPS下载公网证据补齐 | DONE；#24已核同一CC0源的源码/冻结TLS下载、独立hash、入库、重启/完整恢复；#38已核真实源码Range/If-Range/206、同域/跨域302与未注入冻结恢复，并通过当前head CI。冻结206由严格产品校验和最终文件结果推断，原DNS及探针失败保留，见[原报告](../dev/records/2026-11-05-lw07-downloads/report.md)及#38最终核验；不扩展站点/转码，不放宽网络门禁 |
| DL-02 / P2，属M4/LW-07，依赖来源/组件设计 | 站点提取与质量选择；传输/UI可再拆PR | 用户已选B站/抖音/爱奇艺，先B站；#45共同受控设计已DONE，B站有限元数据/质量预览实施先行。实际来源/授权样本、原子候选确认、直链headers与分轨交接/合流、实际固定组件许可及Windows验证继续，不能用预览代替完整下载目标 |
| DL-03 / P2，属M4，依赖格式/轨道交接及二进制选择 | FFmpeg合流/转码与入库 | 待设计；审查实际构建开关/来源及LGPL/GPL/nonfree义务，命令参数受控、超时/取消/失败原件保留、磁盘预算与备份覆盖；不得据本机生成样本假称可分发 |
| PLAN-04 / 后续，属既有规划 | M2-05恢复策略、M3-03、WebView/媒体矩阵、R6剩余 | 继续保留原任务；M2-05不重复#8–#15，恢复/清理需先定身份/关系与同意边界；R6维持无模型，新增场景/凭据另明确。各项先定有限切片再实施/分别PR；不把“其他功能”视为无限授权 |

先交付PLAN-03；开发优先顺序为OFF-01/02与REL-01至03，随后REL-04准备及FMT-01/PAR-01、DL-01，再逐项细化OCR/分块/站点/转码和PLAN-04。最终REL-05在实际纳入发行的组件与功能稳定后收口；未进入候选包的规划不得冒充发行已支持。每个实现切片分别PR/当前head CI，不把整表塞成一次大PR。

## 遗漏补登与PLAN-04细化（2026-11-10）

用户在本批补漏检查后明确选择“补齐任务表并交付PR”。本轮交付仅为PLAN-05文档补齐；下表功能/设计项均未实施，继承原LW/M任务，不因列入表格视为已确认全部产品细节。原PLAN-04保留为汇总入口，执行时使用下列有限切片。核对依据、边界和本轮校验续记[原分析报告](../dev/records/2026-11-10-release-integrity/report.md)。每个后续实施切片仍独立PR、相关自动化及当前head CI；代码审查和人工测试依ADR0014暂缓。

| 编号/归属 | 任务、依赖与范围 | 当前状态及退出证据 |
|---|---|---|
| PLAN-05 / PLAN-03补漏 | 补登遗漏、细化PLAN-04及集中审查收尾 | 文档补齐与校验已完成；已提交[独立草稿PR #21](https://github.com/surface-user/StudyWorkbench/pull/21)，依赖#20，最终head CI及开发交付结论见该PR实时记录；原条目/历史报告保留，代码审查/人工暂停，本项不实现下列功能 |
| LW-04a / 集中检索后续 | TXT资料全文检索；依赖LW-04及现有TXT只读能力，共同文件/字节预算、原文行/版本契约见[契约第6节](learning-workbench-contracts.md) | DONE，有限范围开发交付完成；严格UTF-8原件全文、中文/casefold、同空间/墓碑、稳定分页/截断、正文行与名称资源级跳转、源版本变化拒绝旧行已接UI。双Python搜索/位置/链接各58通过，Flutter专项19/完整200及静态检查通过；[原报告](../dev/records/2026-11-04-lw04-search/report.md)保留实际命令与首轮超时。[独立草稿PR #29](https://github.com/surface-user/StudyWorkbench/pull/29)最终9027508的[CI43066543568](https://github.com/surface-user/StudyWorkbench/actions/runs/43066543568)三job/44步全成功，主Agent已核验并批准登记DONE；代码审查暂缓、人工取消，未合并/发行；不含其他格式全文/OCR/索引 |
| LW-07a / 下载历史 | 完整下载历史分页界面 | DONE，50条分页/稳定排序与上界、轮询/失败保留/重试/迟到响应保护已交付；专项11×2、Flutter6/全量196、#27最终head CI由主Agent核验，见上方调度和[原报告](../dev/records/2026-11-05-lw07-downloads/report.md)。默认活动排序保持；时间上界非事务快照，不清除任务/attempt；审查暂缓、人工取消，未合并/发行 |
| UPD-01 / 发行长期规划 | 自动升级与完整回滚产品流程；依赖稳定发行产物/签名方案及现有备份保护，方案先行 | 待设计、未实施；依据[打包指南](packaging-windows.md#规划中)。明确更新来源、版本/来源校验、前后端/组件配套、失败回退和配置/旧库保留；分别形成升级与回滚切片/故障自动化，不执行破坏性数据库降级。REL-05的安装升级/卸载验证继续保留，不能代替本项产品流程；发布更新另授权 |
| API-01 / 公共接口规划 | 统一error.code/message/request_id错误响应契约 | DONE，原契约要求的detail兼容、422脱敏、关联ID与幂等ID分离及桌面/冻结调用回归已由[草稿PR #34](https://github.com/surface-user/StudyWorkbench/pull/34)交付，主Agent核当前head CI通过；当前已纳本组合，见[API原报告](../dev/records/2026-11-12-api-errors/report.md)。不把未要求的进一步细分错误码作为原任务退出条件；审查暂缓、人工取消、未合并/发行 |
| M2-05i / PLAN-04恢复设计 | 旧提取题目及其他派生候选的恢复/重新登记；依赖05g/h巡检、已有恢复点和完整备份 | 待设计、未实施；先确定恢复目标身份、附件/题目/来源关系、原件hash、显式确认与幂等收据。形成新位置恢复/失败/重试/重启/跨空间等自动化要求；不从目录存在或无引用推断可恢复/可弃，不重复05a–h，不自动改写或删除 |
| M2-05j / PLAN-04留存设计 | 失败副本与派生文件留存/清理策略；依赖05d/e/f容量报告及i的关系设计 | 待设计、未实施；先明确引用判定、保护清单、预览/用户同意和中断恢复规则，原件/确认版/学习历史/失败证据保留。逻辑长度不当作可回收容量，当前报告不增加删除建议；实际清理须另获具体授权 |
| M3-03a / 作答扩展 | 富内容作答扩展；依赖既有题目协议/不可变确认版/追加记录 | 待设计、未实施；先明确本切片输入格式、附件归属和编辑/展示范围，再验证七类/缺答案兼容、旧作答/评分/确认版保持及备份恢复；不擅自增加未确认题型或猜答案 |
| M3-03b / 知识体系 | 科目知识点体系与关系；依赖现有知识点/事件投影和同空间资源 | 待设计、未实施；先定用户自定义分类/关系/修订契约，形成跨空间拒绝、改名移动/删除语义、旧数据迁移与备份回归；不硬编码408/数学等科目，不提前建新表 |
| M3-03c / 复习算法 | 复习策略与算法校准；依赖真实作答/最新人工评分及追加复习事件 | 待设计、未实施；先定确定性输入、评价指标/基线和验证范围，再做离线重复运行、边界/旧历史兼容及效果评估；不把读取性能或单次错误解释为学习效果/长期掌握证明 |
| M3-03d / 规模回归 | 较大规模学习记录、事件/关系读取和投影性能；依赖已确定的数据范围 | 待设计、未实施；先定可重复生成样本、数据量/机器环境、延迟/内存阈值与分页一致性，再给基线/回归结果和限制；不拿现有分页用例代替规模证据，不读取个人库 |
| WEB-01 / PLAN-04网页 | WebView安全/生命周期可自动化矩阵；依赖当前隔离WebView实现 | 待细化、未实施；覆盖导航/重定向/子资源、DNS重绑定时序、弹窗/权限/下载、profile与释放/异常退出；保留业务令牌/文件桥隔离。实际窗口/登录/验证码/DRM/硬件项继续暂停或待范围确认，不以模拟或HTTP测试补记通过 |
| MED-01 / PLAN-04媒体 | 媒体容器/音轨/编码/字幕及状态恢复可自动化矩阵；依赖当前播放器与受控媒体服务 | 待细化、未实施；列明样本来源、实际编码/解码环境与是否真实解码，覆盖时长/续播/倍速/字幕/重启/失败降级及capability；仅导入或后缀正确不证明可播放，真实硬件/休眠人工项继续暂停 |
| R6-01 / LW-08受控读取 | 通用资料/笔记/标记受控读取；依赖明确的格式提供器 | 进行中；R6-01a规划契约已形成，API/UI及无模型组合回归分别b/c/d，其他格式正文e。首批API已增用途隔离的资料读取，普通资料确认UI及其他格式正文仍待实施；链接/关系不扩权、默认元数据/正文另选、版本/预算/撤销及引用条件见[Agent设计](agent-design.md#通用资料受控读取契约r6-01)，不接模型/凭据 |
| R6-02 / LW-08后排设计 | 模型/安全凭据及其他候选场景分别评估；依赖用户明确选定提供方/场景和R6-01范围 | 待范围确认、未实施；先形成指定资料、远端授权/出境范围、Windows凭据保护、无配置/断网降级和来源验证设计；识题/知识关联/计划/分析/变式分别确认与拆PR，不把候选方向全部当实施授权，不下载或接入模型 |
| REV-01 / 本批集中收尾 | 全部本批已确定开发/自动化切片完成后集中代码审查；当前依ADR0014暂缓 | 待触发、未执行；汇总实际交付head/依赖、审查发现、修复PR和对应head CI后给出结论，自审/独立审查/批准分开。REL-05可先完成候选组装自动检查，正式发行准备再依赖本项，避免把正式发布或本项自身设成前置循环；人工测试不自动恢复 |

排期：补漏文档交付后仍优先原OFF-01/02与REL-01至03，LW-04a/LW-07a等后续开发先明确契约再排期，不因此挤掉现有失败/发行任务。UPD-01/API-01是规划登记，未决定的协议/产品流程不在本次改写。M3/恢复/R6等各切片在原父任务报告持续记录；只有实际独立功能开始时才按dev规则建立对应报告。

明确后排候选：单空间备份合并、精细选区标注、外部目录原地工作区/监听依现行契约仍不在本批实施范围，先另立设计；其未实现状态保留，不与上述补登混算完成。当前根checkout较旧，开发以各独立PR的明确base/head为准，不自动切分支、合并或覆盖旧工作区。

## 保留的未完成项

| 编号/来源 | 未完成内容 | 下一步及退出证据 |
|---|---|---|
| M0-08 / M0、M1历史 | 原默认目录历史mkdir/500故障记录保留，人工现场测试已取消 | 继续自动化启动/恢复回归，不操作个人旧库；见[默认启动记录](../dev/archive/reports/default-startup-2026-10-25.md) |
| M0/M1硬件与交互 | 中文IME、浏览器回退最终URL、最终原生退出、原生焦点快捷键、真实DPI/性能、无障碍 | 人工硬件/交互测试已取消；可自动化部分继续覆盖，旧工具失败保留 |
| M0-02 / M1-04发行 | setup实际安装/自选路径/升级/卸载保留、无Python/无WebView2干净机、签名、SBOM/传递许可/漏洞 | 人工安装/干净机测试已取消，发行未授权；集合/hash/编译前门禁见[草稿PR #16](https://github.com/surface-user/StudyWorkbench/pull/16)，x64关键PE门禁见[草稿PR #17](https://github.com/surface-user/StudyWorkbench/pull/17)，96678f4最终head CI #103三组43步通过，只有自审。后续许可复制目标边界已实现，双Python相关各53项、真实本地许可CLI、Ruff/Schema通过，旧失败保留；自审完成，无独立审查。独立分支codex/license-copy-boundary基于#17，已创建[独立草稿PR #18](https://github.com/surface-user/StudyWorkbench/pull/18)，最终head CI及本切片交付结论见PR描述/实时检查，未核实前待交付；完整Office集成因officebean.dll缺jawt.dll受阻，默认基础包已通过原门禁并编译，独立Office分页已实测但Java桥接未支持，详见#19原交付记录；SBOM/完整传递许可/签名等整体仍进行中；[原报告](../dev/records/2026-11-10-release-integrity/report.md) |
| M2-03 / 数据保护（由LW-05承接） | 完整作答/任务/媒体/事件/关系备份恢复，ZIP整包重导 | 还原后逐项一致性与故障回滚；现有export v1/v2仍非完整恢复包 |
| M2-04 / R3/R4 | OCR、多栏/复杂编号、自动共享材料归组、更大原件/分块/格式保真、复杂表格/图表编辑 | 自编真实格式矩阵；旧提取MD与QuestionFile明确区别；版本编辑仅覆盖显式转换后的QuestionFile，不冒充全部旧编辑器完成 |
| M2-05 / R3/R4，进行中 | 完整性/孤立派生巡检、保存恢复点与故障保护；三方合并等后续 | 原巡检及保存恢复点浏览已交付[草稿PR #5](https://github.com/surface-user/StudyWorkbench/pull/5)、[草稿PR #6](https://github.com/surface-user/StudyWorkbench/pull/6)，当时最终head CI均通过、未合并，原计数/失败保留于[同报告](../dev/records/2026-11-06-library-integrity/report.md)。11-09缺失工作文件的恢复点另存独立笔记已实现；创建/保存响应丢失同请求重试、改后副本不覆盖、源字节及重启保持已验证，双Python各526、Flutter167、静态/冻结检查通过，自审完成，已提交[草稿PR #7](https://github.com/surface-user/StudyWorkbench/pull/7)，依赖#6，最终head CI及切片交付结论以PR实时检查为准，未合并/发行。不接模型/人工测试，不自动修复原路径或删除；三方合并分为下方M2-05a/b/c切片；其他派生恢复与失败副本容量治理仍未完成，不将切片冒充全部恢复完成 |
| M2-05a / 三方合并核心，自动化/自审交付 | 已实现有界、无副作用的保守行区间合并核心；该PR仅纯核心，API/UI见b/c | 本轮Linux Python3.12.14专项8项及77子测试、ruff通过，自审完成。已创建[草稿PR #8](https://github.com/surface-user/StudyWorkbench/pull/8)，依赖#7，原head e3dfed4的CI #48在冻结源码检查发现漏包；11-09已修补收集路径并本地干净构建核对42模块，核心8项/77子测试及全量Ruff通过，最终ac9cd02的CI #58全部通过，自审完成、无独立批准（见PR实时描述）；[原报告](../dev/records/2026-11-06-library-integrity/report.md)记录边界与交付链接。基线hash/空间校验的只读预览接口见下项，UI确认载入草稿后续独立开发；不宣称编辑器已有三方合并，不自动保存/发布，未合并/发行 |
| M2-05b / 只读合并预览API，实现/自审完成 | 已实现同节点原件/恢复点基线、空间及当前hash核验；该PR仅API，UI见c | 双Python全量各557项及77子测试、Ruff/Schema、42模块干净冻结构建与真实HTTP只读/陈旧保存/冲突及原巡检链通过，自审完成，独立审查未执行；人工测试已取消。独立分支codex/markdown-merge-preview-api依赖#8的ac9cd02，[独立草稿PR #9](https://github.com/surface-user/StudyWorkbench/pull/9)已创建；最终head CI及切片退出结论见PR描述/实时检查，过程继续[原报告](../dev/records/2026-11-06-library-integrity/report.md)。预览不写文件/草稿/索引/确认版，不自动保存/发布；UI确认载入及原保存由05c承接，M2-05整体未退出 |
| M2-05c / 桌面三方合并，实现/自审完成 | 已实现匹配草稿基线的原件/恢复点选择、字面候选/冲突、确认前重验、仅载入草稿及原expected-hash保存 | Flutter全量193、分析/格式、后端API/核心31及77子测试通过；关闭动画重复确认竞态先失败后通过，旧失败保留。自审完成、独立批准未取得；[独立草稿PR #10](https://github.com/surface-user/StudyWorkbench/pull/10)已创建，最终head全CI及切片退出结论见PR描述/实时检查，过程继续[原报告](../dev/records/2026-11-06-library-integrity/report.md)；分支codex/markdown-merge-desktop基于#9的37fa76e。不自动保存或改原件/确认版/历史，取消与迟到响应保留草稿；人工测试已取消，未合并/发行，M2-05整体仍进行中 |
| M2-05d / 恢复副本容量只读报告，实现/自审完成 | 已实现全部空间working/question-files的current/before/pending及未登记文件逻辑长度；离线显式确认、持锁、只读元数据与有界扫描 | 双Python全量各583及77子测试、最终专项26、静态/Schema、43模块干净冻结构建与原恢复/资源巡检链通过，版本边界见报告；自审完成，无独立批准。[独立草稿PR #11](https://github.com/surface-user/StudyWorkbench/pull/11)已创建，分支codex/recovery-storage-report依赖#10的af6fec7；最终head CI及切片交付结论见PR描述/实时检查，未确认前保持待交付；命令/旧失败继续[原报告](../dev/records/2026-11-06-library-integrity/report.md)。不含Office/下载等其他失败字节，不提供删除/覆盖或清理策略；人工测试已取消，未合并/发行，M2-05整体仍进行中 |
| M2-05e / Office预览容量只读报告，实现/自审完成 | 已实现全部空间previews目录按六种持久任务状态/未登记分类；元数据、有界、独立离线CLI，不读正文或启动Office | 双Python最终全量各605及77子测试、专项48项（Office22/原Markdown26）、Ruff/Schema、43模块干净冻结构建、新Office与原恢复/合并/巡检及资源/文档/重启探针通过，旧夹具失败保留。分支codex/office-preview-storage-report依赖#11的bd9b4dd；自审完成，无独立批准。[独立草稿PR #12](https://github.com/surface-user/StudyWorkbench/pull/12)已创建，最终head CI及切片退出结论见PR描述/实时检查，未核实前待交付；命令/限制继续[原报告](../dev/records/2026-11-06-library-integrity/report.md)。ready缺PDF标不完整，其他状态缺PDF单计；profile/tmp/源副本均保留。不含下载，不提供删除/覆盖策略；人工测试已取消，未合并/发行，M2-05整体仍进行中 |
| M2-05f / 下载attempt与媒体引用容量只读报告，实现/自审完成 | 已实现downloads固定范围、媒体声明路径优先及当前/低编号/其他文件互斥计长；无正文/URL列读取或清理建议 | 双Python最终全量各636及77子测试、容量专项79（新31+原48）、Ruff/Schema、43模块干净冻结及原恢复/Office/导入/文档/重启和新增引用探针通过；旧失败保留，自审完成，无独立批准。[独立草稿PR #13](https://github.com/surface-user/StudyWorkbench/pull/13)已创建，最终head CI及切片退出结论见PR描述/实时检查，未核实前待交付；命令/限制继续[原报告](../dev/records/2026-11-06-library-integrity/report.md)，分支codex/download-storage-report依赖#12的f141770。旧编号不证明历史状态，无媒体引用不代表可弃；不改下载/入库/恢复/原件或建议清理。人工测试已取消，不接模型，未合并/发行，M2-05/task.md整体未完成 |
| M2-05g / 旧提取题目孤立目录巡检，实现/自动化/自审完成 | 补齐question-markdown-spec明确遗留的questions目录漏检；沿用现有候选警告、索引归属和只读保护 | 双Python全量各640项及77子测试、专项43、Ruff/Schema、43模块干净冻结与新增巡检/原恢复/导入/文档/重启探针通过；初轮夹具和权限失败保留。独立分支codex/extracted-question-integrity基于#13的edf8350，已创建[独立草稿PR #14](https://github.com/surface-user/StudyWorkbench/pull/14)，最终head CI及本项交付结论见PR实时描述/检查；实现/测试报告已随实现提交，用户11-10已明确授权补交含项目路径/测试命令的原报告及PR跟进；9336d2f的最终head CI #88三组43步骤通过，旧拒绝保留原报告；只有自审，独立审查未取得，不销项。只补已有巡检缺口，不增加容量统计或自动恢复语义；人工测试已取消，未合并/发行，过程续[原报告](../dev/records/2026-11-06-library-integrity/report.md) |
| M2-05h / 旧提取题目图片副本核验，实现/自动化/自审完成 | 已补齐已登记questions题目assets副本缺失/损坏的完整性漏报；依赖#14 | 双Python全量各654项及77子测试、组合专项57（新增14）、Ruff/Schema、43模块干净冻结及新增真实副本/原恢复/导入/文档/重启探针通过，先红14项及损坏现场保留。独立分支codex/extracted-question-assets-integrity基于#14最终9336d2f；已创建[独立草稿PR #15](https://github.com/surface-user/StudyWorkbench/pull/15)，最终head全CI及交付结论见PR描述/实时检查；d2c98e4的最终head CI #93三组43步骤通过，只有自审、独立审查未取得，不销项。沿用同空间资源大小/hash、只读路径及预算，不增加恢复/删除语义；人工测试已取消，未合并/发行，续[原报告](../dev/records/2026-11-06-library-integrity/report.md) |
| M3-03 / R5 | 富内容作答扩展、科目知识体系、复习算法校准、更广规模性能综合回归 | 旧历史分页已有实现；规模读取回归不等于百万记录性能/学习效果验证 |
| M4（由LW-07承接） | yt-dlp/FFmpeg下载队列、质量选择、取消/重试/断点恢复、转码、自动入库 | 依赖/许可/固定二进制审查及授权来源真实流程；本地媒体上传/播放不抵销此项 |
| M4 / WebView媒体 | 音轨/编码矩阵、外站登录/DRM/休眠、安全导航/子资源/弹窗/下载/DNS/profile矩阵 | 实际站点/硬件及负面测试；容器后缀不证明解码能力 |
| R3 / Office | 复杂第三方字体版式、完整转换安全/性能及独立组件安装/许可/干净机 | 受限静态DOCX/PPTX已实现；旧DOC/PPT与动态对象未支持，不冒充全格式完成 |
| 统一导入 | 实际Explorer拖放/取消、多屏DPI/提权差异、自建样本Windows集成重跑 | 人工鼠标/多屏测试已取消；原生COM与自动回调回归继续 |
| R6 / 原M5-AI（由LW-08承接剩余能力） | 授权分析、草稿确认、AI变式来源/验证、知识关联和无模型回归 | 先设计实施，再自动化与代码审查；人工测试已取消 |

历史M0-01/03/04/05/06/07/09/10/11、M1-01/02/03、M2-01/02和M5标签UI已有实现/自动化记录，不因换R编号消失；其人工测试已取消，阶段未补记通过统一保留在上述交互、数据和发行项中。R0方向方案已获确认，详细比较进入归档，不代表产品验收。完整标签需求见[用户规范](editor-tabs-spec.md)。

## 任务退出条件

每项退出前必须记录：

1. 实现完成，相关调用方/兼容/配置/文档均更新。
2. 相关自动化测试通过，失败保留，覆盖边界明确。
3. 本批代码审查按用户2026-11-10指令暂缓，单独标记，不阻塞已测切片开发交付；全部本批任务完成后集中处理，正式发行准备仍保留该项。旧审查记录不改写。
4. 人工测试/Computer Use按最新指令暂停，不等待既有清单/反馈；取消/暂停不作为测试通过。
5. 对应report.md更新实际命令、退出码、限制、版本和下一步。
6. 本批每个小任务必须独立提交草稿PR并核当前head CI；依赖未合并分支注明base/head，未知/失败保持待交付，代码审查暂缓，不擅自合并/发布。

不适用项须写具体原因；提交了代码不能代替任一条件。退出后保留完成摘要及报告/PR链接，详细过程才迁archive；未完成项不得从清单直接删除。

## 已退出任务

LW-01至05及LW-09自动化集成已交付，条目和报告仍保留在上表。人工测试按用户指令取消，未因此补记历史测试或阶段通过；LW-06/07/08未覆盖的实现和自动化继续推进。
