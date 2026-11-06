# 本地业务API

基线：2026-11-04实际路由、Pydantic模型与request_limits.py。下列“当前已实现”均可在代码中找到；不是规划工具清单。本文概述契约，完整字段校验以链接源码为准；修改接口须同步调用方和测试。

## 当前已实现

### 会话与公共约定

后端仅127.0.0.1随机端口，私有stdin首行JSON {token}，stdout握手返回port/api_version等启动状态，EOF退出。令牌至少32字符，只经管道/内存传递。业务API需Bearer，Host仅loopback，带Origin拒绝，无全局CORS及公开OpenAPI/docs。默认FastAPI detail错误体，不能假定所有错误都有error.code/request_id。

除标明全路径外，下表以W=`/api/workspaces/{workspace_id}`为前缀，节点N=`W/nodes/{node_id}`。归档/不存在空间及跨空间资源拒绝。常见状态401鉴权、403 Origin/能力、404未知/隔离、409冲突、413超预算、422输入非法，具体见服务实现；不能笼统把任意4xx当作预期结果。

请求体按实际接收帧计数：layout 32MiB、document 8MiB（文本仍1MiB UTF-8）、imports 8MiB、notes编辑2MiB、其余64KiB。media/import由流式处理器自行限制512MiB。省略Content-Length不绕过预算。[实现](../backend/study_workbench/request_limits.py)

### 工作空间与布局

[实现](../backend/study_workbench/workspaces.py)

| 方法/路径 | 当前契约 |
|---|---|
| GET /api/health | api_version/status/SQLite健康 |
| GET /api/workbench | 空间列表、当前选择，同一数据库读快照 |
| POST /api/workspaces | name，创建工作空间 |
| PATCH /api/workspaces/{workspace_id} | name，重命名 |
| DELETE /api/workspaces/{workspace_id} | confirm_name精确匹配，仅归档；禁止移除最后活动空间 |
| POST /api/workspaces/{workspace_id}/restore | 恢复归档空间 |
| PUT /api/active-workspace | workspace_id，切换活动空间 |
| GET/PUT W/layout | 版本化布局，校验后整体保存 |

layout版本1/2；tabs最多16、closed_tabs最多10、active_tab_id须有效且ID唯一。旧question/web/player/import/study保留utility身份，新增resource/welcome；资源页以resource_item_id+view_kind(document/web/media)去重。现存跨空间ID拒绝，缺失ID可保存占位；未知kind最多64KiB有预算透传，不执行。MD draft及draft_base_sha256区分空草稿/未修改；MD至多1MiB UTF-8、旧题目草稿16000字符、question_draft独立JSON字符串64000字符。document_state(version=1,page=1..2000,zoom=.25..4,scroll=0..1e7,mode=read/edit/question,representation=original/paginated)。不保存令牌、能力URL或页图。

### 资源树、预检与受管复制

[实现](../backend/study_workbench/explorer.py)

| 方法/路径 | 当前契约 |
|---|---|
| POST W/resource-inspections | source_paths为1–1000个来源；只读路径/属性/32字节文件头识别，逐项返回类型/大小/warning/error，不复制、不提取题目 |
| GET W/nodes | parent_id/offset≥0/limit=1..200（默认100）；search最多200字符，非空时按NFC+casefold名称搜索同空间全部未删除非文件夹节点，不限当前目录 |
| POST W/nodes | parent_id?、name、kind=folder/link、url?；文件夹不能带url，HTTPS外部链接不得有凭证，添加重名自动编号 |
| GET N | 节点详情；原件/媒体完整hash验证，缺失/冲突明确返回状态 |
| PATCH N | parent_id（可null）及name；稳定ID不变，禁止成环/跨空间/非目录父级；重名409 |
| DELETE N | 无请求体，事务标记节点及后代removed_at；返回removed_ids；同空间有queued/running添加任务时409；重复删除返回空列表 |
| POST W/resource-add-jobs | parent_id?、source_path；显式用户选择的本地绝对路径 |
| GET W/resource-add-jobs | offset，倒序每页20 |
| GET W/resource-add-jobs/{job_id} | 状态/取消/逐项结果/error，不返回来源绝对路径 |
| POST W/resource-add-jobs/{job_id}/cancel | 分块取消，保留已完成节点、收据和字节 |

根级列表会适配既有未登记Resource/MediaEntry，每类每次最多200项；墓碑不会重新生成身份。删除不删除原件/工作副本/布局/学习历史、不释放磁盘；已开文档仍可按ID操作保留文件，当前题目/来源入口过滤墓碑。

预检不是格式完整性证明；PDF/Office/图片签名不符可留存并告警，媒体沿用容器校验，能否解码另验。来源每项最多2048字符；拒绝UNC、映射网络盘、设备路径、重解析点和数据目录交叠。复制单worker、最多4个待办，1000节点/32层/合计1GiB、普通文件128MiB/媒体512MiB；每MiB取消/大小检查，源变化拒绝，fsync后登记。失败、重复复制字节保留；重启未终结任务标interrupted，不自动续读外部路径。

### 内容导入、资料与旧提取MD

[导入](../backend/study_workbench/imports.py) / [资料](../backend/study_workbench/library.py) / [拆题](../backend/study_workbench/markdown_questions.py)

| 方法/路径 | 当前契约 |
|---|---|
| POST W/imports?filename=... | 上传原件字节，8MiB；原件先保存，解析后preview/failed，HTTP200不表示正式入库 |
| POST W/resources/{resource_id}/analyze | 同空间已有原件校验hash后复用ImportJob，不重复保存原件；不自动确认 |
| GET W/imports、GET W/imports/{job_id} | 导入历史分页、单任务预览/失败 |
| POST W/imports/{job_id}/confirm | 预览确认，正式写入题目/材料/笔记；冲突整批拒绝，幂等，不信任来源自报验证状态 |
| POST W/imports/{job_id}/retry | 未确认失败任务重解析；已确认/正在解析409，失败保留旧预览 |
| GET W/resources、GET W/resources/{resource_id} | 分页元数据、受保护原件/附件读取，禁止任意磁盘路径 |
| GET W/questions、GET W/questions/{question_id} | 分页题目/单题，映射题附确认ID/节点ID |
| GET W/passages/{passage_id}、GET W/notes | 共享材料与笔记分页 |
| PUT W/notes/{note_id} | expected_revision、title、content，冲突409，原件不变 |
| GET/POST W/recovery | 孤立原件巡检/按resource_id+filename显式登记，不删除、不猜题 |
| GET W/export | ZIP含原件/题目/笔记/hash，128MiB原件/32MiB元数据；不是整库恢复包 |
| POST W/imports/{job_id}/question-drafts/edit | expected_revision、action=merge_next/split_block/split_region/share/rename及对应字段；陈旧或已入库拒绝 |
| POST W/imports/{job_id}/question-markdown | expected_revision、selected严格不同整数下标、confirm=true；同组选题幂等，另一组409 |
| GET W/question-markdown | search标题、offset/limit分页旧MD摘要 |
| GET W/question-markdown/{id} | 原题块、MD内容、来源/资源ID，不等同可判分题 |

DOCX/PDF提取预算8MiB/20页PDF/25秒，与阅读预算不同。候选修改更新摘要，PDF手工子裁图不复制无法定位文字。附件检查空间/MIME/存在/hash；导入来源降权，HTML不执行。格式见[旧MD](question-markdown-spec.md)和[内容协议](question-content-spec.md)。

### 文件阅读、保存与Office分页

[文档](../backend/study_workbench/document_files.py) / [转换](../backend/study_workbench/office_previews.py)

LW-01自由笔记已实现（人工待验），[实现](../backend/study_workbench/markdown_notes.py)：

| 方法/路径 | 当前契约 |
|---|---|
| POST W/markdown-notes | request_id为16–100位ASCII字母/数字/_/-、parent_id可null、name为合法1–200字符Windows名称且以.md结尾；额外字段拒绝，实际请求帧仍64KiB。创建初始MD原件与可编辑工作副本，返回节点元数据/source_resource_id/初始sha256/working_copy、request_id及状态 |
| GET W/markdown-notes | offset≥0、limit1..100默认50，按节点ID返回同空间未移除的MD/MARKDOWN资源，包括文件夹内、显示名已改为无后缀的节点；按Resource.original_name判断格式，打开时另验当前正文 |
| GET W/markdown-notes/requests/{request_id} | 同空间收据，未知404；requested_name/requested_parent_id可用于重试，不返回磁盘路径 |
| GET W/markdown-notes/requests | offset≥0、limit1..100默认50，按创建ID排序；列出创建收据供重启/响应丢失后恢复，不是按时间排序 |

creation_status为prepared/ready/interrupted/conflict；status在未完成时同创建状态，完成后反映当前节点ready/missing/conflict/removed。同空间同request_id及规范名称/目录返回原节点，不同内容409；墓碑不复活，编辑后重试不覆盖工作文件。原件与工作副本独占写、fsync/回读后同事务登记；启动只把prepared标中断，显式重试才核对保留字节。文件与数据库非跨介质原子事务，失败字节保留。创建后复用N/document、layout草稿/保存/关闭确认，旧notes协议不改。来源关联另用下文learning-marks接口，不把笔记创建成功冒充关联成功。

| 方法/路径 | 当前契约 |
|---|---|
| GET N/document | 类型、当前hash/来源hash、副本/变化状态及文本/页数/图片/DOCX结构；Office附能力和当前源预览，读取不启动转换 |
| GET N/document：通用文本 | TXT/JSON/CSV/LOG/VTT/SRT返回type=text、source_format和position_kind；TXT为text_line，其余resource。≤1MiB严格UTF-8，非法编码422、超限413；原文字面显示，不自动解析题库、不执行公式/脚本，工作副本编辑仍仅MD |
| GET N/document：XLSX | type=spreadsheet、source_format=xlsx、position_kind=resource、renderer_version=xlsx-values-v1；sheets含name/state/cells（address/value/formula/cache_missing），另有cell_count。公式仅取现有缓存、无缓存提示，字符串字面显示，无编辑/计算/网络读取；源超16MiB为413，损坏/不支持/预算/20秒超时422 |
| GET N/document-page?page=1 | PDF页图PNG base64、来源hash及渲染器版本 |
| GET N/relative-image?path=... | 同空间逻辑树相对PNG/JPEG，拒绝网络/绝对/越根；允许树内父导航，目标缺失404 |
| POST N/working-copy | expected_sha256，仅MD显式创建，原件不变 |
| PUT N/document | expected_sha256、text，冲突409，文本超限413；保存收据和重启对账 |
| GET N/document-saves | 仅已有MD工作副本；offset≥0、limit1..100默认50，按随机ID升序分页（不是时间排序）。只含id/status/old_sha256/new_sha256，不读取正文、不返回磁盘路径 |
| GET N/document-saves/{save_id}?version=before或pending | 同空间/节点收据、受管路径和记录hash核对后返回id/status/version/text/sha256/current_sha256/unavailable_reason；≤1MiB严格UTF-8，缺失/损坏/归属不符409、超限413，未知收据404。只读，不修复、不消费收据 |
| POST N/previews | expected_source_sha256，拒绝额外字段；组件/源/队列冲突409、空间不足507；复用有效ready缓存或同节点待办 |
| GET N/previews/{id}、POST N/previews/{id}/cancel | queued/running/ready/failed/cancelled/interrupted及可追溯摘要；不返回磁盘路径 |
| GET N/previews/{id}/page?page=1 | 核对当前源和派生hash后PNG页图；丢失/篡改409，坏PDF/超时422 |

文档读取/渲染最多2并发，忙429；MD1MiB、预览20万字符；PDF128MiB/2000页/逐页最长边2048；PNG/JPEG16MiB/1600万像素；DOCX结构8MiB。DOCX/PPTX可选分页输入32MiB、单worker/4待办、独立profile/Job和90秒引擎执行限时（不含完整运行时验证）。旧DOC/PPT明确unsupported；动态/外链等输入拒绝，原件保留。详细预算见[架构](architecture.md)与[ADR0009](adr/0009-offline-office-previews.md)。

保存恢复点内容读取同样受2并发门禁约束，保留已移除节点的现有标签访问语义。成功保存后pending已移入当前文件，原pending不可读是正常情况，不用其他内容冒充。当前文件不可读或任意该节点保存仍prepared时，current_sha256=null并给出原因，只允许查看；不会自动重启/对账。否则current_sha256为读取时的当前文件hash，仍不授予覆盖权限。

桌面MD工作副本“保存恢复点”仅在无未保存草稿时打开，选择与字面预览后另行确认载入编辑草稿，沿用现有layout草稿及hash字段，不写正文。再次点击普通保存才执行PUT N/document，expected_sha256采用预览响应的current_sha256，后续外部修改仍409且草稿保留。没有专属恢复写接口、Agent工具或确认版发布；当前文件缺失/不可读时本切片不提供写回，三方合并另行设计。

### 位置书签、备注与笔记来源（LW-02）

[实现](../backend/study_workbench/learning_marks.py)。全部业务路由继承Bearer/Host/Origin及空间校验；写请求64KiB，未知字段拒绝。位置协议见[LearningAnchor v1](learning-workbench-contracts.md#3-位置协议-learninganchor-v1)，整数拒绝bool/浮点替代，hash由后端核对。

| 方法/路径 | 当前契约 |
|---|---|
| POST N/learning-anchor | kind及匹配的位置字段；resource无位置；pdf_page为page；office_pdf_page为page/preview_id；text_line为line；media_time为position_ms。位置捕获必须带显示版本expected_sha256，resource可省略。回读实际hash/页数/行数/时长，返回完整v1 anchor，不保存书签 |
| POST W/learning-marks | request_id（16–100位ASCII字母/数字/_/-）、anchor、非空title≤240、note≤4000默认空、targets≤100默认空；同空间同请求同规范内容幂等，不同内容409；不把多条同位置书签去重 |
| GET W/learning-marks | resource_item_id或note_resource_item_id可选过滤；offset≥0、limit1..100默认50，按ID排序；摘要含anchor、正文、revision、targets/target_details，过滤墓碑，不声明位置已验证 |
| GET W/learning-marks/{id} | 当前记录及location：valid/content_changed/missing_content/removed/out_of_range/unsupported、message及可用资源/anchor。未知版本保留原始数据，不跳转；未知/跨空间404 |
| PATCH W/learning-marks/{id} | expected_revision严格正整数及至少一项title/note/anchor，显式null拒绝。失效来源仍可改文字；重新关联须校验新anchor，限同一资源，跨资源另建标记。旧修订先保存，竞争409 |
| DELETE W/learning-marks/{id} | 请求体expected_revision；追加旧修订、推进版本并置removed_at，禁止物理删除；旧版本竞争或重复删除409，客户端刷新确认结果 |
| PUT W/learning-marks/{id}/notes | expected_revision、targets明确替换关系集合，最多100个不同目标；kind=file_note/id为MD节点，kind=legacy_note/id为旧notes ID；同空间/格式/墓碑校验，旧集合进入修订 |
| GET W/learning-marks/{id}/notes/{kind}/{target_id} | 再验空间及当前关系后返回文件节点或带revision的旧富内容笔记，关系缺失404、文件笔记已移除409 |
| GET W/learning-marks/{id}/revisions | offset≥0、limit1..100默认50，按revision倒序返回旧快照；标记移除不清除历史，数据库触发器拒绝修订更新/删除 |

记录指向稳定节点ID，改名移动不改关系；正文变化不自动重定位。Office页绑定源及派生hash/preview_id，若另有不同的新分页版本，会明确提示并打开保留的旧版；派生物损坏不回退同页码。媒体时间只按受管原件MP4/M4A mvhd或WebM Info受限元数据验证，最多4096个容器元素/一周；未知时长拒绝时间锚点，可资源级记录，不表示编码已可播放。读取/捕获/位置改写复用最多2份查看任务的并发预算；列表不批量渲染资料，详情/回跳才核验。

资料页“记笔记”先创建/选择笔记再以独立幂等请求关联资源级来源；关联失败明确提示笔记已保存并允许重试，页码/时间点由“书签与备注”记录。笔记页可按note_resource_item_id查来源并回跳。旧修订冻结的是标记与关系，不冻结所关联笔记全文；旧notes仍按原revision编辑，不修改R5事件/评分。现有export v1/v2尚不包含标记、修订、关系或自由笔记当前工作副本，不能当完整备份。

### 内部超链接（LW-03）

[实现](../backend/study_workbench/internal_links.py)。`POST W/internal-links/resolve`仅接收`{uri}`，拒绝未知字段，64KiB请求预算；v1 URI最多2048字符，严格语法及单次解码规则见[契约](learning-workbench-contracts.md#5-内部链接-v1)。所有路由继承会话、Host/Origin与活动空间校验，URI空间必须等于路由空间，否则404，不返回跨空间标题。

返回规范化`target={workspace_id,kind,id,uri}`、`status/message`；nodes返回当前`resource`，marks复用实时位置验证并返回可用`resource/anchor`及title，notes返回旧笔记的id/title/content/resource_id/revision。目标未知/跨空间/空间归档404；墓碑返回removed；文件夹unsupported；资料未就绪missing_content；标记内容变化等沿用位置状态。标记墓碑优先于位置验证，不把已移除记录定位成功。节点URI打开资源，位置须使用mark URI；无新表、路径猜测或隐式重绑定。

原生UI复制当前资源、选定书签和旧笔记链接；Markdown工作副本显式插入前验证目标，预览只在点击时跟随，坏链保留原文。往返栈仅在当前空间窗口内最多50条，存URI和受限视图/版本，不序列化正文、令牌或能力；返回也重验，失败保留记录和草稿。外部HTTPS仅交隔离WebView，其他scheme拒绝；旧富内容v1不新增内联超链接块。不注册系统协议处理器，也不接受外站调用此业务接口。

### 集中查找（LW-04）

[实现](../backend/study_workbench/learning_search.py)。`GET W/learning-search?q=...&offset=...&limit=...`：q为1–200字符且非全空白，保留输入空格作为字面匹配；offset≥0，limit1..100默认50。当前活动空间内匹配Unicode casefold后的字面子串，不执行正则、SQL通配符、Markdown或HTML。继承会话、Host/Origin与空间校验，复用最多2份文档处理任务的并发门禁。

范围为活动MD/MARKDOWN节点名及当前工作副本/无副本原文、旧notes标题/文字/公式/附件说明、未移除marks标题/备注；失效来源的书签仍可查。TXT全文、OCR及其他格式不纳入。响应含`query/items/total/offset/limit/has_more/truncated/reasons/scanned/scope`；items含kind=`file_note|legacy_note|mark`、id、title、纯文本snippet、稳定uri，文件附content_sha256，旧笔记/标记附revision。无磁盘路径、媒体能力或正文镜像。

每请求先完整扫描预算范围、按kind/id排序，再分页；total为本次已扫描范围内的匹配数。最多1000份MD、旧笔记/书签共10000条，总文字读取预算16MiB、单MD≤1MiB；坏文件字节计入，超限最多额外1字节探测；旧笔记按JSON字节预检/计费。不支持的旧块、文件缺失/损坏/非UTF-8及任何预算截断均置truncated并列原因；scanned为各类尝试条数、已计费bytes及unreadable，不承诺所有尝试均成功。无匹配且截断时只能称“已扫描范围无匹配”。

原生结果分页合并按kind/id去重，失败保留原查询和已读结果；库变化后可刷新，不承诺跨请求快照。打开文件/旧笔记结果前重验hash/revision，变化时要求刷新；书签先打开保留的记录及备注，跳到来源仍须验证位置。内部导航随后再次resolve，不因搜索结果越过空间/墓碑或扩大Agent权限。

### QuestionFile与确认版

[实现](../backend/study_workbench/question_files.py)，格式和预算见[QuestionFile](question-file-spec.md)。

| 方法/路径 | 当前契约 |
|---|---|
| GET N/question-file | 只检查，当前hash、编译内容、警告和confirmed_version_id；已映射当前文件无效返回invalid_current及最后确认版，不能发布 |
| POST N/question-file/confirm | expected_sha256、必须存在但可null的expected_version_id、字面confirm=true；额外字段拒绝，竞争409，重复确认幂等 |
| GET W/question-versions/{id} | 同空间不可变内容/hash/revision/时间 |
| GET W/question-versions/{id}/assets/{resource_id} | 核对资产hash后image_base64 |
| GET W/questions/{id}/file-preview、GET W/question-markdown/{id}/file-preview | 旧JSON/MD转换预览，不写文件 |
| POST W/questions/{id}/file、POST W/question-markdown/{id}/file | expected_source_sha256、expected_preview_sha256、confirm=true；创建编辑副本而非发布，已有映射返回同节点 |

确认冻结正文、标题、材料和附件，回读后提交；快照损坏拒绝新作答。导出存在映射时manifest/缓存version=2，附当前MD/assets与确认版，只有旧业务沿用v1；v2不能当旧bundle或完整数据库备份。

### 作答、计划与学习事件

[判分/入口](../backend/study_workbench/app.py) / [学习](../backend/study_workbench/learning.py) / [事件](../backend/study_workbench/learning_records.py)

| 方法/路径 | 当前契约 |
|---|---|
| GET/POST W/attempts | 旧升序列表/追加作答，question_id、response及可选question_revision/request_id/question_version_id；映射题要求确认ID，服务器核验快照判分 |
| GET W/attempt-history | limit1..100默认50、before_id正整数，按ID倒序；每条带全部评分修订，旧页不被新作答挤动 |
| POST W/attempts/{id}/reviews | 追加人工score/feedback，不覆盖原作答 |
| GET W/study、GET W/statistics | 科目/知识点/题型/mode=due/wrong/all及分页；统计依据完整记录 |
| GET/POST W/study-tasks | 读取/创建确定性练习计划，进度由作答推导 |
| GET W/attempts/{id}/record | limit1..100、before_id；当时版本状态/知识点、当前题目与来源、事件页、全流标签投影、相关笔记、复习数和算法版本 |
| POST W/attempts/{id}/events | request_id(16..100)、kind=annotation/reviewed、非空note≤4000，error_type?、self_rating=again/hard/good/easy?、note_id?、knowledge_points?；额外字段拒绝 |
| GET W/attempts/{id}/notes/{note_id} | 再验空间/作答/事件关系后返回当前笔记；缺失404，关系保留 |

提交同request_id/答案/版本重试返回原作答，内容冲突409；确认新版不改变旧请求或分数。主观/缺答案待批改。事件同请求同内容幂等、不同内容409，null/省略兼容；无更新/删除事件接口。知识点最多100项、每项≤500非空独立，null不修订、[]清除；每作答最多100份显式同空间笔记。unknown旧版本不补造；latest-explicit-annotation-v1遍历全事件流，attempt-review-streak-v1依真实作答/人工评分，不因注记加分。

### 媒体与旧default兼容入口

[实现](../backend/study_workbench/media_library.py)

POST W/media/import?filename=...为MP4/WebM/M4A流式导入≤512MiB；GET W/media?offset=0&limit=50；GET W/media/{id}/player核对hash后发放只绑定该媒体的临时能力。专用 `/media/library/{id}/player|content|state?cap=...`，content支持GET/HEAD/Range，state为GET/POST(position/speed/subtitle)。能力不是业务Bearer，失效/归档/文件变化拒绝，重启重新申请，不暴露主机桥。

保留 `/api/questions/demo`、`/api/attempts`（GET/POST）、W/questions/demo、`/api/player`及`/media/demo?cap=...`。旧业务入口固定default空间，不跟随当前UI空间暗改作用域；演示题展示包含答案，不是保密考试接口。

## 离线完整学习库备份恢复（LW-05）

[包校验](../backend/study_workbench/backup_archive.py)、[快照与恢复](../backend/study_workbench/backup_store.py)通过固定参数子进程提供，**没有HTTP任意路径接口**。普通入口为设置中的“备份全部学习库/从完整备份恢复到新空目录”及启动失败恢复按钮。备份先列出所有活动/归档空间并确认未加密范围；页面草稿落盘失败不离线。随后释放WebView、关闭业务后端/任务及锁，再运行独立工作进程，完成后重新启动。

- `--inspect-backup <zip>`：只读检查结构及payload字节，返回payload_integrity_verified=true、database_semantics_checked=false、data_activated=false；不执行SQLite或激活。
- `--data-dir <source> --backup-to <new.zip> --confirm-all-workspaces [--config <settings>]`：持独占数据锁，SQLite backup合并WAL，完整性/FK/表行摘要及所有受管原件/确认附件核对；未知普通文件与失败字节保留，精确排除运行profile。输出已存在则拒绝；返回file_count/total_bytes/schema_revision/source_retained=true/data_activated=false/cleanup_pending。
- `--data-dir <new-empty> --restore-backup <zip> --config <settings>`：包/目标/配置/原数据/安装目录不交叠，持目标和配置session锁，逐块校验预算/空间/字节，核对SQLite及manifest表摘要、工作文件/原件/确认资产。旧schema先保留库副本再迁移，旧列/记录不变才提升；目标用独占创建防覆盖。最终再次核对后原子更新配置，返回data_dir/schema_revision/file_count/database_semantics_checked=true/data_activated=true/cleanup_pending。已有配置格式未知/损坏时拒绝覆盖，原配置保留供排查。

UI传`--parent-pipe`，stdout仅阶段/最终结果JSON，关闭stdin表示协作取消；不通过杀进程替代正常取消，配置提交后以实际结果为准。失败保留原库/原配置和未完成字节；成功只清理本次独占创建且已验证提升的暂存副本，清理失败单独报告。若子进程结果不明，先读取实际配置确认是否已激活，不重启旧库覆盖未知的新配置。库包预算与字段见[契约](learning-workbench-contracts.md#7-完整备份恢复-v1lw-05)，源码/组件通过仍不等于安装/干净机/实际窗口验收。

## 直接媒体下载（LW-07当前本地接口）

前缀W/media-downloads，继承Bearer/Host/Origin/空间隔离。POST根路径接收url、name（合法MP4/WebM/M4A文件名）、parent_id可空、request_id（16–100字符）、严格布尔rights_confirmed=true；额外字段拒绝，不接受文件目标路径。同空间同请求同参数重试返回原任务，不同参数409；待办全库32上限429。GET根路径offset≥0、limit=1..100，优先queued/running再创建时间倒序；GET /{id}读取单项。响应含id/name/source_host/parent_id/status/attempt/progress(received,total)/can_resume/result/error/created_at，无完整URL/query、磁盘路径或ETag。

POST /{id}/pause保留字节、请求暂停；ready拒绝409。POST /{id}/retry仅mode=resume|restart，活动/完成任务不能重试；resume缺少可信断点409，实际字节/版本不符时任务失败且旧部分保留，restart换新attempt不覆盖旧文件。result为resource_item_id/media_id/deduplicated。重启queued/running转interrupted，不自动联网；任务缺失/跨空间404。HTTP创建成功表示排队，不表示下载、解码或验收通过。

源/重定向/DNS固定、TLS、字节/磁盘及超时约束见学习契约；当前源仅公网IPv4直链，源质量仅原文件。普通资源管理器提供下载入口，状态/暂停/重试/打开媒体；不暴露路径操作或Agent工具。

## 规划中

LW-00确定的markdown-notes、learning-marks及笔记关系、internal-links/resolve、learning-search已实现，见上文；离线整库恢复通过独立进程，不开放任意文件路径或网页业务桥。单空间合并仍未实现，不把资源export或只读包检查当作实际恢复结果。

本地授权和人工候选审核见下文；R6其余工具/凭据与模型接口尚未实现。通用error.code/message/request_id响应包装尚未形成完整公共契约。不得调用[Agent设计](agent-design.md)中的拟议工具名当成现有HTTP接口。

## 待验证

已有接口自动化与限定Windows混合集成证据见[任务](task.md)。真实Explorer拖放、原生焦点/硬件DPI、Office完整转换/恶意样本矩阵、安装/干净机和人工/阶段验收仍待验；API通过不证明这些行为通过。

## 本地授权与人工候选审核当前接口

均继承业务Bearer/Host/Origin校验，前缀W/agent-grants。POST根路径接收attempt_ids（1–100个独立严格正整数）、purpose=analyze_attempts、expires_in_seconds（1–900严格整数，默认300）、confirm=true、include_content（严格布尔，默认false）；额外字段拒绝。验证同空间后返回随机id、原范围/用途/有效期及transport=local_only。进程最多100份未过期授权，超限429。

DELETE /{id}撤销；POST /{id}/read-attempts读取原范围作答摘要（id/question_id/question_version_id/status/score/created_at）。未知、跨空间、已撤销或到期授权404；归档空间拒绝。只读且不联网，不返回正文/事件/笔记/评分修订。授权不落库，重启失效；这些路由由学习页本地授权弹窗调用，不能把原始分数当最新人工评分。


POST /{id}/read-analysis-context返回schema_version=1、workspace_id、scope=summary或content、attempts、question_versions、context_sha256及binary_attachments_read=false/latest_reviews_included=false。仅include_content=true含作答response和实际确认版content/attachments元数据；正文每条≤64KiB、整体UTF-8 JSON≤1MiB，超限413，读前/后复核授权。旧question_version_id=null保持历史未知；不读当前题目冒充历史，不取二进制附件、最新人工评分、事件或笔记。MD/版本元数据损坏409并保留记录。

前缀W/analysis-drafts，仅普通用户业务UI使用，无模型/Agent采用工具：

- POST根路径：grant_id、context_sha256、request_id（16–100字母数字下划线/连字符）、title（1–200）、body（1–16000字符且≤64KiB）、source_label（≤200）。保存时重读授权上下文并核hash；固定origin=external_candidate、verification=unverified，保留引用，不存grant/上下文正文镜像。同空间同请求同内容幂等；不同内容409。已有请求查询不重新读取已撤销授权；待处理最多1000条。
- GET根路径offset≥0、limit=1–100默认50；GET /{id}读取单项。返回content/payload_sha256/revision/status/adoption/result/error/rejection_reason/created_at。持久草稿不随授权撤销删除。
- PATCH /{id}：title/body/source_label及expected_revision（严格正整数）、expected_payload_sha256；仅pending且无采用收据可改。过期版本409，旧状态追加修订保留。
- POST /{id}/reject：上述修订/hash守卫及reason（≤2000），允许pending或failed，标rejected而不删除；失败采用的笔记/原收据保留，拒绝后禁止再重试采用。
- POST /{id}/adopt：修订/hash守卫、name、可选parent_id、request_id及严格confirm=true。普通UI另行核对确认，先写采用收据再经既有自由MD服务新建笔记；固定未验证，正文/引用作为字面文本，不修改答案/作答/评分。失败保留候选与已建笔记；仅同原参数可重试，其他编辑冲突409不覆盖。已采用重复请求返回同结果；重启adopting转failed并保留审计，不自动重放。采用持久草稿不再读取源、不要求旧grant仍有效。
- GET /{id}/revisions：offset/limit同列表，倒序只读历史；历史禁止更新/删除。

上述接口继承Bearer/Host/Origin及workspace隔离。桌面在退出/备份/迁移前刷新打开的候选编辑器；保存失败则保留文字并取消退出，可明确确认放弃窗口编辑。人工采用仅表示保存为笔记，不证明内容正确。

context_sha256及payload_sha256由服务端按对应上下文/候选content计算，客户端原样回传，不从UI文字重建。1MiB上下文预算包含最终校验字段。


## 离线资料完整性巡检（M2-05，当前已实现）

`--data-dir <已有库绝对路径> --check-library --confirm-all-workspaces`：先验证已有study.db与本地路径，再持独占数据锁，用SQLite只读连接巡检全部空间及归档。不启动HTTP或业务服务、不创建/迁移业务库、不写配置、不修复或清理；拒绝同时传入备份/恢复/迁移操作或config/media/parent-pipe。锁文件可创建，数据库及学习文件不写入。正在使用的库拒绝；没有桌面或Agent入口。

输出单行JSON的result：schema_version=1、checked_scope=managed_files_and_derived_directories、complete、healthy、data_modified=false、repair_performed=false、entries_checked、rows_checked、bytes_hashed、retained_preview_tasks及issues（code/severity、可选relative_path）；预算中止另含limit_reason。健康且完整退出0，发现问题/不完整退出1；参数或取锁错误非零退出。只报告相对路径与类别，不输出正文或原始SQL异常。

核对当前schema、SQLite完整性/FK、原件/就绪媒体/确认版及附件/就绪派生PDF的大小/hash，工作文件对索引变化报告警告；保留保存恢复点、创建收据和失败预览任务。working、question-files、question-versions、previews目录按数据库归属巡检，包含空目录及working旧generation；无归属只表示候选，不表示可删除。根部未完成迁移/备份/恢复暂存目录提示后不展开；运行profile排除。未知其他目录不猜测归属。

最多20000目录项、50000引用行、512MiB文件哈希、30秒协作式期限、200条问题；超限complete=false/healthy=false，不返回虚假的全库健康。healthy仅针对上述检查范围，不替代所有业务JSON/格式语义验证，数据锁不排斥外部编辑器；单次阻塞文件系统操作不保证可立即中断。旧schema只报告不支持，不借巡检自动升级。
