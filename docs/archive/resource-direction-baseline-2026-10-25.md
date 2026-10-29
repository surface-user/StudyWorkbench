# 资源中心方向修正前的文档基线

保存日期：2026-10-25。本文件仅为审查前历史快照，不是最新产品约束。当前要求见原路径文档，历史自动化和未验收状态仍然保留。快照中相对链接按各原文件所在的docs目录解释，正文保持原样。


---

## 原文件：docs/requirements.md

# 需求与阶段验收基线

2026-10-25 M5 Editor Tab Bar：按task.md的Tab UI Specification v1.0实现连续紧凑标签、溢出/动效/快捷键、草稿关闭确认及页面实例保留。自动化与限制见[UI交付记录](editor-tabs-validation-2026-10-25.md)；人工和阶段验收仍待统一执行。

2026-10-25用户调整：首次启动自动使用Windows用户默认数据位置，无需先指定数据库目录；数据位置修改保留在设置和启动错误恢复中。已有保存位置/旧库优先保留，拒写时不静默切换空库。进程完整性与Known Folder定位规则见ADR0006；普通业务不要求管理员权限。

用户 2026-10-23 的启动规范是需求来源。Windows 桌面软件，不以 Agent 或聊天记录为组织中心。

2026-10-25用户澄清：题目主要由用户自定义文档导入。PDF和Word同等优先，识别每题后裁切/提取，一题一个Markdown文件，汇入本地知识库。保留公式、图表/图片、原件和来源位置；没有答案也可作为独立题目资料入库，不虚构答案或强迫补齐答题协议。下一步优先打通两种格式的识别拆题、MD预览及确认入库，既有题目版本编辑暂后置。PDF按原版面裁图并附可提取文字；Word按文档内容顺序提取为MD，真实分页裁图另行验证。

| 编号 | 需求 | 阶段 / 验收 |
|---|---|---|
| WS | 创建/重命名/删除工作空间，独立索引、笔记、任务、设置；侧栏导航，多类标签页 | M1：重启恢复、跨空间隔离、删除确认 |
| Q | 统一富内容题目，公式、图片、图表、表格、附件，七类题型，阅读材料共享，来源及变式关系，多次作答 | M0 协议；M2 渲染/附件；M3 完整业务 |
| STUDY | 408 四科、数学一三科、英语一各题型、政治；筛选组卷、历史、判分、待批改、错题、知识点、任务、复习、统计 | M3：客观题规则、主观待批改，掌握度和到期复习决定选题，避免稳定掌握题反复出现 |
| IMPORT | 独立导入入口；Word/PDF/HTML/Markdown/视频/链接/手动题和笔记；提取、拆分、预览、去重、保存 | M2：保留原件、哈希、来源、解析版本、失败记录；未经确认不写正式题库 |
| MEDIA | 有权保存的视频链接、格式/质量/目录、进度/取消/重试/恢复、自动入库、本地导入、HTML5 播放/跳转/倍速/字幕/续播 | M4：中断恢复与 Range，格式失败提示及后备策略 |
| WEB | WebView2，多标签、URL、前后导航/刷新、外部浏览器回退 | M0 插件试验；M4 完整安全/站点验收 |
| AI | 可选；授权记录→薄弱点统计→模型→总结草稿→用户确认→笔记 | M5：无 API 时所有普通业务可用；AI 题保留验证状态 |
| DATA | 自选数据目录、校验迁移/回滚/旧数据保护；安装目录分离；卸载保留数据 | M1 起，发行前故障注入验收 |
| PKG | 自选安装位置 setup.exe；包含 Python；不要求用户装开发环境 | M0 风险与脚手架；M1 干净 Windows 虚拟机验证 |

M0 阶段门禁：文档/ADR、锁定依赖、运行原型、自动化检查、Windows WebView/播放人工证据、待验证清单。任何未完成项不得以代码存在代替通过。
后续阶段必须在 task.md 给出自己的自动化与人工验收记录，不一次性开发全部功能。

2026-10-24 后续授权（ADR 0005）：继续按任务顺序开发并执行自动测试/审查，task.md 任务完成后统一人工验收。各阶段的人工和阶段验收保留待验；该授权不表示既有失败已修复。

2026-10-24 例外：用户明确授权暂时忽略 M0 问题、提前开发 M1（ADR 0003）。本次先实现 M1-01/02 的工作空间与动态标签垂直切片；M0 遗留项仍未通过，不能转写为阶段验收成功。


---

## 原文件：docs/architecture.md

# 系统架构

2026-10-25 M5标签改造：EditorTabBar独立管理紧凑视觉/溢出/动画；WorkspaceLayout与WorkspaceShell统一身份、导航、快捷键、关闭确认和串行保存。PageHost以直接带Key的Offstage承载惰性页面，修复当前Flutter IndexedStack无Key包装导致关闭兄弟页重建的问题；业务页通过PageActivityChanged报告运行时加载/错误/标题，持久化layout协议不变。详情及原生证据见[UI交付记录](editor-tabs-validation-2026-10-25.md)。

2026-10-25默认启动调整（ADR0006）：Windows原生storageRoot通道按本进程TokenIntegrityLevel选择LocalAppData或LocalAppDataLow，settingsRoot统一定位LocalAppDataLow配置。Dart异步读取Known Folder和旧配置，首次直接启动默认目录，不再打开选择框；目录选择/迁移保留在设置，失败页可明确选择默认位置。Python继续负责数据锁和业务文件写入，拒写错误指明目录并保留原库，不改ACL或提升权限。

2026-10-25启动修复：普通启动的配置目录会话锁/原子设置写入I/O失败，允许在禁止写该配置的条件下保留所选数据位置、继续取得数据锁，并通过握手startup_warning在UI显示位置未记住。配置锁忙、数据锁/数据目录失败不降级；迁移仍必须取得配置锁并成功提交配置。不会自动换数据目录、修改ACL或提权。证据与未验证的普通入口见[startup-config-fix-2026-10-25.md](startup-config-fix-2026-10-25.md)。

2026-10-25 M2/M4续开发：draft_editing.py通过候选摘要控制合并/分割/共享材料，PDF重裁源为完整页图，原件不改；手工裁切无逐字定位时子题仅保留图像。NoteEditor通过ResourcePicker调用资源API，不直接读库。media_library.py流式保存媒体、启动恢复失败记录、提供限定单媒体的临时能力URL及独立播放器，不将业务Bearer交给网页；Alembic0006保存空间内媒体和播放状态。完整备份恢复、下载队列和转码未实现。详见[m2/m4记录](m2-m4-continuation-2026-10-25.md)，下文未接入描述保留为历史。

2026-10-25用户澄清后的M2主线：PDF/Word导入生成按题候选，Python保存原件/提取资源，Flutter逐题预览和选择；确认接口将每题MD及相对图片目录落盘，Alembic0005新增独立markdown_questions索引，文件仍经Resource哈希校验。它与需要标准答案的QuestionDocument分开，既有作答/评分不变。PDF保留区域原貌裁图/跨页，Word按内容顺序提取；OCR、多栏和裁切边界编辑尚未接入。见question-markdown-spec.md。

2026-10-25 M2编辑续开发：NoteEditor以独立深复制草稿编辑Content分段，资源引用及未修改字段原样保留；Dart复用现有单题Schema的Content约束，Python PUT notes继续负责版本冲突/附件归属及校验写入。保存失败留在编辑框，不自动重放；未增加数据库访问或依赖。AuthorDialog仅生成新内容导入预览。

2026-10-25 M3性能续开发：学习页通过attempt-history按ID游标分批读取作答，只加载本页正文和评分修订；完整历史兼容接口按attempt_id归并修订。study_rows以轻量作答列和最新修订流式计算连续掌握/到期，不加载全部response/feedback；任务完成进度按题号聚合最近作答时间。未更改数据库或学习规则，不将这批有界读取回归视为完整大库性能验收。

2026-10-24续开发：documents.py在受限子进程执行离线DOCX/PDF解析；原件和parsing任务先持久化，解析不占SQLite写锁，重启将中断任务标为可重试失败。library.py提供空间内巡检/显式恢复、预览重解析、预算导出和带版本校验的笔记编辑。learning.py统一判分、追加评分修订、计算到期/掌握并保存学习任务；Alembic 0004保留旧作答，新增版本/幂等编号和修订/任务表。Flutter新增StudyPage与AuthorDialog，仍只调用受控API。M4/M5未接入，人工/阶段验收待统一执行。

2026-10-24 M2 首批（ADR 0005）：imports.py 接收所选原件字节，Python 保存原件与解析预览，确认事务再写入题目/共享文章/笔记；Flutter 不直接访问 SQLite。RequestLimits 累计实际 ASGI 帧，资源按 ID 鉴权读取，不向 WebView 传递路径/令牌。Alembic 0003 新增资源/任务/文章/笔记，升级备份目标动态读取 head。当前实现和限制见 [M2记录](m2-validation.md)，下方 M0/M1 描述保留历史边界。

2026-10-24 后续已实施 ADR 0004：data_root.py 管理离线校验迁移、OS 数据锁和原子启动配置；SQLite 业务写入用 BEGIN IMMEDIATE 先锁定再检查名称/归档/活动状态。桌面首次位置选择、设置迁移、后端异常恢复和 Windows 单实例已接入，冻结采用独立 CPython。下文 M0/首批“尚未实施”的字样为历史边界，最新状态见 m1-completion-2026-10-24.md；没有新增 Agent 任意命令入口。

采用 Monorepo + 模块化单体。`apps/desktop` 是 Flutter 窗口、导航、交互和渲染；`backend/study_workbench` 是本地业务/持久化；`contracts` 为协议样例；`packaging/windows` 为发行脚手架；`tools` 为开发验证；`docs/adr` 为决策。

Flutter → 受保护 HTTP API → Python 应用服务 → SQLAlchemy → SQLite。文件处理服务通过资源 ID 访问数据根目录，原文件不放 BLOB。导入、学习、媒体、AI 将按业务模块拆分，M0 不建立空抽象层。

桌面父进程启动后端，stdin 交接随机令牌；后端预绑定 127.0.0.1:0，stdout 只返回实际端口；不会扫描或复用未知服务。Dart 请求均带 Bearer。关闭时终止自有后端；后端也监测 stdin EOF 防止孤儿。M0 不处理多实例，M1 要采用独立会话或带身份的单实例协调。

外部网页无主机桥、无令牌；本地播放器仅获得专用媒体能力令牌，不能调用业务。不同 WebView 生命周期与页面状态分开，玻璃容器不覆盖视频绘图区，避免原生视图合成问题。

M0 仅建立示例题、健康检查与持久化作答链路。工作空间、导入、下载任务、AI 均未实现。数据库 schema 由 Alembic 管理，禁止生产启动时 create_all 或静默删除重建。

M1 首批在用户授权下提前实施（ADR 0003）：`workspaces.py` 管理工作空间和布局的受控接口，`migrate.py` 在升级前备份并事务迁移；题目/作答按 workspace_id 隔离。Flutter 的 WorkspaceShell 管理侧栏、动态标签与串行自动保存；页面只调用 API。标签按需创建，切换保留已创建页面，关闭销毁；WebView profile 位于工作空间/标签独立路径。正常关闭等待布局写入，失败取消退出；强杀/崩溃与多实例尚属 M1-04。M1-03 数据根配置与迁移尚未实施，本批预览显式使用隔离目录。


---

## 原文件：docs/data-model.md

# 数据实体与关系

2026-10-25：0005已建立独立markdown_questions索引（工作空间、原件/导入任务、MD资源、来源元数据），不要求标准答案。0006新增media_entries：id、workspace_id、title、relative_path、mime、size、sha256、status及playback JSON；播放状态保存position/speed/subtitle，不保存能力URL或业务令牌。媒体位于数据目录，独立于原资料Resource；当前ZIP资料导出不构成媒体备份。迁移保留旧库/文件，不提供删除学习数据的降级。

2026-10-24续开发：Alembic 0004增加attempts.question_revision/request_id（旧作答保留null，空间+提交编号唯一）；attempt_reviews追加评分/说明/时间，历史展示有效修订而原作答和分数不变；study_tasks保存空间、标题、题目ID和时间，进度由创建后的追加作答推导。notes读取增加内容版本摘要，编辑需expected_revision匹配，原件不改。布局kind增加study。原件巡检和中断恢复已经接入；下方“留M2-05”为首批历史。

M2 Alembic 0003 已新增 resources（同空间SHA256唯一）、import_jobs（原件、解析版本、状态/错误/预览）、passages（文章ID与空间复合主键）、notes（确认后写入，关联原件）。确认事务与0002→0003备份回归见 [M2记录](m2-validation.md)。原件写入与SQLite不是跨介质原子事务；提交前崩溃可能留下孤立原件，不自动删除，恢复巡检留M2-05。以下后续实体表为早期规划，已实施表以上述0003为准。

M2布局仍为v1，kind在原question/web/player之外增加import，恢复时读取该空间导入记录；import标签不保存URL或题目草稿。

M0 实际迁移：`questions(id, content JSON)` 与 `attempts(id, question_id FK, response JSON, status, score nullable, created_at)`；一题多次追加作答。数据库开启外键。示例题为明确标注的人工演示题。

M1 Alembic 0002 已实现：`workspaces(id, name, archived, created_at, layout JSON)` 与 `desktop_state(id=1, active_workspace_id FK)`；题目主键为 `(id, workspace_id)`，作答含 workspace_id 且通过 `(workspace_id, question_id)` 复合外键检查归属。旧 M0 记录原样归入 default，作答 ID、文本和成绩保留；不修改原题标准答案。已有库升级前使用 SQLite backup API 写入 `backups/study-before-0002-<uuid>.db` 并 integrity_check，DDL 显式包裹事务，失败回滚、不自动删除旧数据或备份。不提供丢弃工作空间信息的破坏性 downgrade，应由人工控制恢复备份。

布局协议 v1 含 tabs（最多16）、closed_tabs（最多10）、active_tab_id，标签 id 唯一且安全路径格式，kind 为 question/web/player。question 草稿最多16000字符；web 仅保存无凭据的公网 HTTPS 地址，重新访问仍做 Dart DNS/URL 校验；player 不存媒体能力 URL。服务端写入前校验版本、引用、长度与字段白名单。移除空间只归档；恢复后布局、题目及作答仍在，最后一个活动空间不可移除。题库索引、笔记、任务和完整设置仍随后续业务模块按 workspace_id 建立，当前不冒充已实现。

后续设计实体（尚无对应表）：

| 实体 | 关系及约束 |
|---|---|
| resource / attachment | 工作空间、相对路径、SHA256、MIME、字节数、来源；不接受任意文件路径 |
| import_job / extraction | 原 resource、解析器版本、状态、错误、预览、去重指纹；确认后提交 |
| passage / question | 共享文章，多题引用；question protocol_version/content/source/verification |
| question_relation | parent/variant、生成模型和草稿/人工验证/拒绝状态 |
| attempt / grading | 独立作答；题目版本快照、提交时间、客观得分或待批改；人工评分保留历史 |
| knowledge_point / question_knowledge | 科目树、多对多关联；不从一次错误推断永远薄弱 |
| mastery / review / task | 作答证据、掌握稳定性、到期时间、每日计划；允许用户覆盖建议 |
| note | 资料/题目/知识点关联，AI 草稿必须确认后保存 |
| download / media / playback | 下载状态机、源、格式、目标、续传元数据；视频资源、字幕、进度 |
| settings / migration_journal | 配置分层与路径迁移事务日志；API 密钥不存普通 SQLite |

M1 工作空间设计需先加入迁移和隔离测试；M3 前冻结题目快照与答案修订机制，避免修改答案改变历史成绩。
# 2026-10-25 逐题Markdown索引补充

Alembic0005新增markdown_questions：独立题目id、workspace_id、import_job_id、候选ordinal、source_resource_id、markdown_resource_id、title、content（块、source_pages、regions）。import_job_id+ordinal唯一，保证重复确认不会新增同题；与需标准答案的questions/attempts不混写。resources额外记录text/markdown的实际相对文件路径/大小/SHA256，原件仍保留。升级沿用动态head备份和事务迁移，旧0002/0003数据保持断言不降低。


---

## 原文件：docs/agent-design.md

# 可选 AI / Agent 权限

M0 不接入模型。M5 的第一个闭环必须是：用户选择工作空间和作答记录→授权读取→本地统计薄弱点→可配置模型分析→总结草稿→人工确认→保存笔记。

工具只允许受控业务请求：读取已授权作答/知识点、创建分析草稿、生成未验证变式题。权限以工作空间、记录集合、有效期为边界，记录数据出境范围和模型提供方。标准答案变更、数据删除、任意 shell、原始文件任意读取不在工具集中。

模型输出不可信，须 schema/大小/来源校验，不能变成工具授权。AI 题保持 ai_generated/unverified；不把模型自评作为真题或验证证据。无密钥、断网、拒绝授权时普通学习功能正常。凭据使用 Windows 安全凭据存储（M5 实现），日志脱敏。
