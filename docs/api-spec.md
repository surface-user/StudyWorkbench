# API v0 / M0

2026-10-26 R3分页增量（[ADR0009](adr/0009-offline-office-previews.md)；覆盖下方首批能力说明）：

- 以下均位于同空间 /api/workspaces/{workspace_id}/nodes/{resource_item_id}，沿用Bearer/Origin/Host校验。GET /document 对DOCX/PPTX增加preview_capability及当前源hash对应的最新preview；读取不启动转换。DOCX≤8MiB仍返回word结构，较大DOCX/PPTX返回office说明；旧DOC/PPT仍unsupported。
- POST /previews仅接受expected_source_sha256（64位小写hex），拒绝额外字段。需要已核可选组件；同节点待办返回原任务，ready缓存校验后复用。源版本/队列/组件冲突409，空间不足507，格式/大小422/413。失败缓存保留原任务，显式重试创建新任务。
- GET /previews/{id}查询状态/可追溯摘要；POST /previews/{id}/cancel请求取消。状态queued/running/ready/failed/cancelled/interrupted；摘要含来源ID/hash、运行时/选项指纹、转换器版本、PDF hash/大小/页数、错误及取消标记，不返回磁盘路径。最多4个待办、单worker，重启中断、不自动恢复。
- GET /previews/{id}/page?page=1核对当前源及派生PDF后，经PDFium返回PNG页图（同现有阅读预算）。缓存丢失/篡改/源变化409，坏PDF/超时422。令牌不交给文档或外部页面。
- document_state增加representation=original/paginated，默认original；不持久化任务能力URL或页图。

2026-10-26资源主线新增（Bearer/Origin/同空间校验保持）：

- layout支持v1/v2。v2资源标签含resource_item_id、view_kind(document/web/media)、resource_name；document可含draft_base_sha256、至多1MiB UTF-8草稿及document_state(version=1,page=1..2000,zoom=.25..4,scroll=0..1e7,mode=read/edit)。题目草稿仍16000字符。已知类型额外字段拒绝；未知kind最多64KiB惰性透传，不执行；同开资源身份唯一，现存跨空间ID拒绝，缺失ID留占位。layout实际请求32MiB，文档PUT8MiB（正文仍1MiB），其余旧上限不变。
- 以下在`/api/workspaces/{workspace_id}/nodes/{resource_item_id}`下：`GET /document`返回类型/当前hash/来源hash、工作副本与外部变化状态及对应文本/页数/图片/Word结构；`GET /document-page?page=1`按页返回PNG base64、来源hash及渲染器版本；`GET /relative-image?path=...`只解析同空间逻辑相对路径，不接磁盘路径/网络地址。DOC/PPT/PPTX当前返回明确unsupported说明，不能视为渲染成功。
- `POST /working-copy`：expected_sha256；仅MD显式创建，可重试，不修改原件。`PUT /document`：expected_sha256/text，冲突409，UTF-8字节超限413；保存收据在替换前提交，重启按hash对账。`GET`不创建工作副本或改写题目。
- 查看读取/渲染最多并发2份，忙时429。PDF阅读128MiB/2000页/逐页2048像素，与旧拆题预算分开；PNG/JPEG16MiB/1600万像素，DOCX结构沿用8MiB。页图/转换失败422、文件冲突409，原件及草稿保持。

2026-10-25 M2/M4补充（业务接口仍需Bearer/Origin/空间校验）：

- `POST /api/workspaces/{workspace_id}/imports/{job_id}/question-drafts/edit`：expected_revision、action（merge_next/split_block/split_region/share/rename）、index及对应position/text_offset/cut/title/targets/source_blocks；返回更新后的导入预览和摘要。陈旧摘要409，已入库任务拒绝编辑，原件不改。
- `POST /api/workspaces/{workspace_id}/media/import?filename=...`：MP4/WebM/M4A原始字节流，最大512MiB，实际帧计数，保留成功/失败记录；`GET /api/workspaces/{workspace_id}/media?offset=0&limit=50`分页列表。
- `GET /api/workspaces/{workspace_id}/media/{id}/player`：完整哈希检查后发放仅供该媒体的临时播放器URL（可能需要较长读取时间）。不返回原始磁盘路径。
- 播放器专用`/media/library/{id}/player|content|state?cap=...`：content支持GET/HEAD/Range；state支持GET/POST，字段仅position、speed、subtitle。能力仅对应该媒体，不能作业务Bearer，归档空间/失效/篡改文件拒绝；后端重启后重新获取。播放器不暴露业务桥或令牌。

2026-10-25新增逐题MD知识库接口（同Bearer/Origin/工作空间边界）：

- DOCX/PDF导入详情附`preview.question_drafts`、`draft_revision`和`question_markdown`，无候选时保留整篇资料并告警。
- `POST /api/workspaces/{workspace_id}/imports/{job_id}/question-markdown`：expected_revision为预览SHA256，selected为不重复的严格整数候选下标，confirm=true；确认后按题落盘，原件保留。重复同组返回原记录，另一组选题409；错误/陈旧摘要拒绝，不覆盖既有内容。
- `GET /api/workspaces/{workspace_id}/question-markdown?search=&offset=0&limit=50`：标题检索、分页独立题目摘要。
- `GET /api/workspaces/{workspace_id}/question-markdown/{id}`：原题块、Markdown文件内容及来源/MD资源ID。它不是判分题，没有推断标准答案。
- 资料导出增加Markdown题目索引及便携`questions/<id>/question.md`与相对图片；含副本的实际资源导出预算仍为128MiB。

格式/范围见[逐题MD协议](question-markdown-spec.md)。

2026-10-25 M3新增：`GET /api/workspaces/{workspace_id}/attempt-history?limit=50&before_id=<上页末条id>` 返回作答ID倒序列表，limit为1..100、before_id为正整数且严格小于该ID。每条仍包含原始response及全部评分修订，分数使用最新修订（包括零分）。空页表示没有更早记录；新增作答不挤动旧页，刷新才读取最新页。沿用Bearer、Origin拒绝、工作空间存在/未归档检查。旧`/attempts`列表保持原有升序/不分页兼容行为，学习页改用新接口；统计不以已加载历史条数计算总数。

2026-10-24 M2/M3新增（均位于`/api/workspaces/{workspace_id}`且沿用Bearer/Origin/空间边界）：

| 方法 | 后缀 | 行为 |
|---|---|---|
| GET | /resources | 原件/提取附件元数据，limit/offset分页 |
| GET | /export | ZIP含题目、笔记、原件和哈希；128MiB原件/32MiB元数据预算，不是整库恢复包 |
| GET / POST | /recovery | 巡检孤立原件 / 按resource_id和filename显式登记，不删除或自动入正式库 |
| POST | /imports/{id}/retry | 未确认任务重新解析；失败保留旧预览；已确认/正在解析409 |
| PUT | /notes/{id} | expected_revision、title、content；冲突409，不修改导入原件 |
| GET | /study | subject/knowledge_point/kind/mode（due/wrong/all）/limit/offset筛选，规则选题 |
| GET | /statistics | 作答、错题、到期、掌握、待批改及知识点统计 |
| POST | /attempts | 新增可选question_revision/request_id，服务器统一判分；冲突409 |
| POST | /attempts/{id}/reviews | score（0..1）、feedback、confirm=true，追加人工评分修订 |
| GET / POST | /study-tasks | 查询进度 / 以标题、题数和筛选条件保存组卷任务 |

确认入库仍只接受可解释预览；parsing任务须等待，进程中断后重启标failed可重试。DOCX/PDF/笔记JSON/URL导入均走原件管线；不自动抓取链接。完整命令、失败与限制见m2-m3-continuation-2026-10-24.md。旧M0兼容路由不随UI活动空间改变，新增学习业务不依赖LLM。

M2 首批导入 API、请求上限与错误语义见 [M2 验证与接口记录](m2-validation.md)。沿用私有 Bearer、Origin 拒绝与工作空间隔离。

M1 首批新增以下接口，沿用同一私有会话鉴权。M0 的 `/api/questions/demo`、`/api/attempts` 固定指向 default，不接受 query/body 改变作用域；不会随 UI 当前工作空间变化。

| 方法 | 路径 | 请求 / 行为 |
|---|---|---|
| GET | /api/workbench | 活动/归档工作空间元数据、上次选中的空间 |
| POST | /api/workspaces | name；创建并选择，含两个独立演示题 |
| PATCH | /api/workspaces/{id} | name；重命名，活动空间名称不可重复 |
| DELETE | /api/workspaces/{id} | confirm_name 必须精确匹配；仅归档并保留数据，不能移除最后一个活动空间 |
| POST | /api/workspaces/{id}/restore | 恢复归档空间，数据不清空 |
| PUT | /api/active-workspace | workspace_id；必须存在且未归档 |
| GET/PUT | /api/workspaces/{id}/layout | 版本化布局，见 data-model.md；校验后整体保存 |
| GET | /api/workspaces/{id}/questions/demo | 当前空间的演示题 |
| GET/POST | /api/workspaces/{id}/attempts | 仅当前空间的作答列表/追加提交 |

归档/不存在空间的业务路由返回404；名称冲突、确认名称不符、最后空间保护返回409。为容纳受限数量的中文草稿，layout 请求上限2 MiB，其余请求仍64 KiB；模型的标签数量、草稿长度、URL和引用约束仍执行。令牌和媒体 capability 不能作为布局字段保存。完整 error.code/request_id、并发多实例冲突与分页仍待后续实现，本批为单桌面实例的串行保存。

HTTP 地址由后端启动握手返回，固定绑定 127.0.0.1 随机端口。除专用媒体路由外均需 `Authorization: Bearer <session>`；不启用 CORS；带 Origin 的 API 请求拒绝；Host 仅允许 127.0.0.1。令牌不打印、不持久化、不进入 URL。

| 方法 | 路径 | 结果 |
|---|---|---|
| GET | /api/health | api_version、status、SQLite 可用性 |
| GET | /api/questions/demo | 公开展示题目与解析，非考试保密 API |
| POST | /api/attempts | question_id、response；返回 id/status/score |
| GET | /api/attempts | 演示作答列表，用于验证重启持久化 |
| GET | /api/player | 可信 HTML，内含独立只读媒体 capability |
| GET/HEAD | /media/demo?cap=... | 单个指定视频，支持 Starlette FileResponse Range |

错误：401 鉴权，403 Origin/能力错误，404 未知题/媒体，422 请求或选项不合法。M0 使用 FastAPI 统一错误结构；M1 定义稳定 error.code/message/request_id 和分页/幂等策略。

启动协议：stdin 第一行 JSON {token}（>=32 字符），stdout 一行 {port,api_version}；后端 stderr 为日志，stdin EOF 退出。不允许命令行传密钥。启动超时/版本不符在 Flutter 显示错误，不能静默接入任意端口。

## R1 资源管理器增量

均沿用loopback随机端口、Bearer鉴权、拒绝Origin及工作空间隔离；`resource_item_id`是逻辑节点ID，区别旧`resource_id`原件ID。旧API保持兼容。

- `GET /api/workspaces/{workspace_id}/nodes?offset=0&limit=100`：可选parent_id指定文件夹，省略为根级，limit 1–200。根级读取将兼容工具中新产生但未登记的原件/媒体各至多200项适配到树；更大积压可继续刷新。节点返回kind/name/parent_id、互斥resource_id/media_id/url、size/hash及状态。列表只检查可读路径/存在/大小，完整hash检查见详情。
- `GET .../nodes/{resource_item_id}`：详情及流式hash验证，缺失/冲突保留身份与关系。
- `POST .../nodes`：`{parent_id?,name,kind:folder|link,url?}`。同级重名自动编号，链接只接外部HTTPS且无凭证；文件夹不可带URL。
- `PATCH .../nodes/{resource_item_id}`：`{parent_id:null|string,name}`，同时改名/移动，稳定ID不变；同名409、跨空间404、非文件夹父级422、成环409。无删除接口。
- `POST .../resource-add-jobs`：`{parent_id?,source_path}`，仅由桌面用户选中的本地绝对路径发起。单worker、最多4个排队/运行任务；不接受UNC/映射网络盘/设备路径/重解析点，不接受与数据目录交叠的来源。复制不解析，不访问网络。
- `GET .../resource-add-jobs?offset=0`：按创建顺序倒序，每页20；`GET .../resource-add-jobs/{job_id}`：查询单任务。结果含状态、取消标记、逐项added/renamed/duplicate/failed/cancelled/interrupted结果及copied_path收据；来源绝对路径不返回、不写日志。
- `POST .../resource-add-jobs/{job_id}/cancel`：请求分块取消；保留已完成节点、结果和字节。queued/running重启后变interrupted，保留复制路径，不自动续读外部来源。

每任务1000节点/32层/1GiB；普通文件128MiB，既有MP4/WebM/M4A媒体512MiB。每MiB检查取消与预算，复制前后校验来源元数据，fsync后登记。媒体复用既有容器校验和播放器；编码兼容未扩展。复制失败/重复留下的额外副本保留并列入收据，不自动清理。下载未实现。旧解析的8MiB/20页限制未放宽，R1保存大原件不等于可解析/预览它。

## R4题目文件与确认版（已实施）

以下均在 /api/workspaces/{workspace_id} 下，沿用loopback/令牌/Origin边界，无任意文件或命令接口：

- GET /nodes/{node_id}/question-file：只检查；返回当前hash、题目/材料、警告、confirmed_version_id、confirmed及status。已映射当前文件无效时返回invalid_current及最后确认快照，不能确认；未映射非法文件仍拒绝。
- POST /nodes/{node_id}/question-file/confirm：expected_sha256、必须存在但可空的expected_version_id、字面布尔confirm=true；额外字段拒绝，变化409。MD/附件落盘回读后发布，确认版重复请求幂等。
- GET /question-versions/{id}：同空间不可变编译内容、hash/revision/时间；GET /question-versions/{id}/assets/{resource_id}：受保护且核对hash的PNG/JPEG，返回image_base64。
- GET /questions/{id}/file-preview 和 /question-markdown/{id}/file-preview：旧内容转换预览；POST 对应 /file：expected_source_sha256、expected_preview_sha256、confirm=true，显式创建新编辑文件，尚未发布。已建立映射返回同一节点。
- 已映射GET /questions/{id}附confirmed_version_id/resource_item_id；POST /attempts需携当时当前确认ID并校验快照及全部资产。旧未映射JSON提交保持兼容；同request_id/答案/版本重试先返回原记录，新版本不能篡改旧作答。attempt DTO附可空question_version_id，旧值未知。
- 资源document_state.mode新增question，question_draft独立保存JSON字符串，上限64000字符。关闭保存草稿不提交。
- 含文件映射的导出manifest与缓存包标记version=2，附question-files及确认快照；不作为旧v1导入/完整恢复包。

协议预算/限制见[QuestionFile](question-file-spec.md)，实际命令/错误证据见[R4记录](r4-validation-2026-10-26.md)。

## R5首批记录接口（2026-10-29）

GET /api/workspaces/{workspace_id}/attempts/{attempt_id}/record 支持limit=1..100及before_id，返回version_status、当时knowledge_points（旧空版本为null）、当前resource_item_id、source_resource_item_ids、事件页及next_before_id。POST对应/events接收request_id、kind(annotation/reviewed)、非空note及可选error_type/self_rating(again/hard/good/easy)，同内容幂等、不同内容409，额外字段拒绝。鉴权/Origin和空间归属检查不变，无修改/删除接口。自评/复习事件不重判旧作答。R5整体仍进行中，见[R5首批](r5-records-2026-10-29.md)。

## R5完成批载荷及投影

/events增加note_id（必须同空间，最多关联100个不同笔记）和knowledge_points（可空列表，最多100项，每项非空独立且不超过500字符）。省略/null不修订，[]明确清除记录标签；旧请求null/省略幂等兼容。/record增加effective_knowledge_points、related_notes(id/title/available)、reviewed_count及knowledge_projection_algorithm=latest-explicit-annotation-v1；原knowledge_points仍是当时快照值。投影基于全流，不受当前before_id页限制。GET .../attempts/{id}/notes/{note_id}再次检查空间、作答、事件关系和笔记存在性后返回当前笔记内容；缺失404保留事件。掌握算法attempt-review-streak-v1不因注记/自评而改分。详见[R5完成记录](r5-completion-2026-10-29.md)。
