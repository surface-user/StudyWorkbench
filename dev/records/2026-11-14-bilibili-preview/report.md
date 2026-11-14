# DL-02b1：B站受控格式预览

当前交付基线是#46的8bebad8896da83db4ac45ea6f7f4aa41142901cd，最新实现为v2公开页面纯JSON→nav→playurl。下列原#45、旧HTML原型和v1 API-only记录保留失败沿革，不代表当前实现。草稿PR#52的d17/be316两次CI公网失败完整保留；be316源码/冻结精确定位view HTTP412后，对照固定源标准起点实施v2，当前IN_PROGRESS，新head公网正向仍待核，不推断登录/权限原因。完整DL-02仍未完成。代码审查按用户要求暂缓，人工测试已取消，未合并、未发行。

## 问题、基线与完整目标

用户已选择B站、抖音、爱奇艺并要求持续推进。DL-02a/#45的517bcd479fad45f559c85a9ce75548783260052a、tree f2563a250c13c1ea86189d29cb58f6c67a02c366已由主Agent核当前CI43367244690三组成功。本切片逐Git blob复制451份源码到独立bili-preview目录，不改变根旧checkout、#45或其他任务。读取AGENTS、requirements、architecture、question-content-spec、task及下载/API/数据边界后登记IN_PROGRESS。

当前仅直链下载，普通B站页面不能预览格式。先增加B站普通单视频的受控元数据/真实返回格式预览与短期候选；后续候选确认及来源持久化/固定headers传输由下一实现切片接入原持久队列，DASH/HLS轨道和合流由DL-03，抖音/爱奇艺分别验证。完成预览不代表完整DL-02或视频下载已完成，不减少原三站目标。

## 最小设计与影响范围

requirements/architecture没有将yt-dlp采纳为硬性运行依赖，dependencies明确仍是候选。首个有限B站适配使用现有CPython标准库及parse_url/resolve/PinnedHTTPS，不引入整套工具/插件/脚本或第二份持久下载队列。固定适配版本bilibili-preview-v1。WBI排列/签名及站点字段参考yt-dlp固定f264a6cbd1f630894da0f368df00f8aae50140e0，来源为Unlicense；不是clean-room。源码只读资料及哈希保存旧设计副本artifacts/dl02b-fixed-source，未执行其程序或安装包。

所有页面/API/短链和重定向经过单一受控标准库入口：仅精确允许域、HTTPS443、全部公网IPv4预检、固定地址连接和原域TLS/SNI；固定Referer/Origin，不接用户headers/业务令牌/代理/cookies。只读__INITIAL_STATE__的JSON和固定匿名nav/播放接口，不执行页面JavaScript，不请求缩略图、评论、字幕、章节或外部程序。WBI仅普通静态参数；风险挑战受控失败。拒绝番剧/直播/列表/互动、付费/登录/试看，不自动变更质量或回退其他提取器。

首批明确预算：I/O10秒、总45秒、取消2秒后结束本任务子进程；全流程10次请求含重定向、每链3跳；单响应2MiB、累计8MiB、响应头32KiB、仅identity编码；最多64格式，IPC结果128KiB，标题512字符。复用既有WindowsProcessJob的1GiB总内存/4进程/kill-on-close保护；输入在归属设置后才交给固定worker。短期内存条目最多32、并发2、10分钟有效，重启失效，不新增表或迁移。

API继承鉴权/Host/Origin和空间状态；只接受URL/严格权利确认/幂等request_id。启动、状态、取消在内存中绑定同空间和固定版本。普通响应只有纯文本信息和格式元数据/限制，不携下载URL/query/headers；内部URL候选不传客户端。原下载入口/任务身份/512MiB与15分钟/旧attempt/媒体原件及备份不变。

界面在原下载入口提供单独B站预览：手动确认后才联网，支持取消/关闭和迟到结果保护，显示实际返回的质量/轨道及未知大小；尚未接入下载的格式明确显示暂不支持下载。测试覆盖网络闭合、源字段漂移/付费试看/超限、权利/空间/幂等、取消/阻塞DNS/重启、旧下载与恢复；双Python、Flutter及源码/新冻结验证后独立草稿PR/当前head CI。真实正向使用能核原作者公开许可或用户许可的样本，不把上游testURL自动当授权，也不以离线夹具冒充真实站点。

## 实际准备

2026-11-14，根辅助逐451份Git blob核对/复制退出0。尚未执行产品测试。设计已由主Agent明确允许继续实施；原#45文档/历史失败保留。代码审查暂缓、人工测试取消，未合并或发行。


## 基线校正与保留的初轮证据

主Agent指出#45继承旧Starlette/pytest锁，冻结/发布前必须采用已修复版本。已保留整个原bili-preview及日志/失败，另从#46最终8bebad8896da83db4ac45ea6f7f4aa41142901cd/tree a3c3ea71b40e7196e58a9c0d038861b63ff23084逐478个Git blob核对建立bili-preview-current。#46当前head CI已由主Agent核三组45步成功/后端986×2。后续本任务实际源码与发布基线为#46，#45仅设计输入，不以旧基线测试冒充当前组合通过。

根rebase_bili_feature.py先对app、__main__、OfficeRuntime的最小attach接口和桌面入口进行带上下文补丁检查/应用，退出0，原#33 Java组合逻辑保留，未复制旧OfficeRuntime整文件。新增8份功能/测试/报告原字节复制。#45契约/依赖统一补丁在新dependencies前言的上下文变化处保守失败1，未部分应用该文档补丁；resume_bili_rebase.py按唯一现行相邻段落插入已采纳契约/候选评估并纠正旧“队列未实现”描述，保留新依赖/OSV/许可条目和现行前言，不整文件覆盖。该恢复命令退出0。

初轮原bili-preview：新增解析测试先因模块缺失退出2（预期红灯）；实现后30通过，再含同页格式/权限失败不换入口等35及API/实际子进程10合计45通过，使用IQ40，但当时副本锁旧，不能作为当前基线锁一致的交付证据。Ruff初轮两处导入排序退出1，规范排序后通过。Dart三个新/改文件格式化退出0；普通权限Flutter因固定SDK cache lockfile拒绝，退出-1073741816，没有算组件测试通过。

许可样本只读调研找到BV1gi4y1V7Xx的Big Buck Bunny页面摘要，声明CC-BY3.0并链接Blender原作；原作者peach.blender.org/about搜索结果亦说明CC-BY3.0。web直取分别失败412/获取器402，不能将缓存摘要冒充已取回页面或媒体对应校验。直接源码只读元数据调用在现有DNS公网守卫拒绝，退出1，public-metadata-01.json保留；未关闭证书/改DNS/代理或向任意视频伪造媒体许可。真实正向仍待受控环境与可核来源。


## 最终主路径与已验证的中间结果

主Agent允许比较并采纳固定f264a6c已使用的HTTPS WBI view/detail作为唯一主元数据路径。当前实现为nav→view/detail→playurl；普通BV/av链接仅取ID，不请求HTML，b23只解析受控HTTP重定向到该类链接。删除未发布HTML赋值解析/同页playinfo实现分支，原字段漂移/付费/试看/多P/超限/权限拒绝断言按相同语义迁移到API JSON夹具，没有删去仍适用的失败断言。固定兼容UA为Mozilla/5.0 (Windows NT 10.0; Win64; x64) StudyWorkbench/1.0，不在拒绝后切换通道或会话。WBI/字段参考与Unlicense原文范围在packaging/licenses/bilibili-preview保存，不宣称整套yt-dlp采用或clean-room。

当前约63个新边界/探针测试包含声明的API-only路径、nav拒绝不再请求、JSON字段与身份一致、既有全部DNS地址拒绝、重定向/计数/字节/JSON/格式预算、Dolby/FLAC不漏列、短期幂等/空间/到期回收、真实固定worker环境与模拟阻塞自有子进程终止；实际计数以最终JUnit为准，不把计划值当通过。

保留中间证据：原HTML轮Q全量1043+77子测试、第二API轮1048+77子测试均退出0；第二轮之后又补nav显式拒绝语义/一例测试，故这两次不作为最终当前源版本的全量证明。冻结01/02各构建退出0并核47模块，但最终nav保护变更后需重新冻结；old-frozen-identity.json保留首候选hash，依产物规则只留一份当前冻结目录，没有把旧exe当新主路径。IP第二轮151专项退出0，其后nav测试同样另核。

Flutter：当前完整211项退出0，1分41秒；新界面8专项（含100/200/300%模拟DPI）退出0。首轮4过1失败系延迟POST测试夹具的Map/Future条件表达式类型推断，错误被正常UI显示；改为显式await异步夹具后原取消/迟到断言与新增“仍在获取”断言全部保持，旧flutter-current01/02失败保留。后续只修正原直链说明，避免与新预览入口相矛盾；最终格式/分析/相关组件复验另记。

原冻结01的真实HTTP探针已到新增worker并由原DNS守卫明确拒绝，失败JSON只含公开状态/固定错误，不含URL/query。没有放宽网络或把失败算正向。新的check_bilibili_previews固定CC候选、显式--allow-public-fixture、只请求元数据、复核同空间幂等/跨空间拒绝/取消/重启失效及无下载/媒体记录；普通CI离线测试与codex/bilibili-preview分支的源码/冻结公网步骤分开。原作者许可/镜像摘要的来源关系仍记录，media_byte_correspondence_verified=false，不做媒体请求、发布或许可认证。

## d17cd3e候选的本地交付证据

以下命令均在bili-preview-current独立副本执行，PYTHONPATH=backend、PYTHONDONTWRITEBYTECODE=1；IQ为Python3.13.17的starlette-q-isolated，IP为Python3.12.7的starlette-p-isolated，锁内Starlette1.3.1/pytest9.0.3，未修改共用环境和两份锁。原始stdout/JUnit保存在忽略的artifacts/dl02b，筛选摘要见[evidence/local-summary.json](evidence/local-summary.json)。Windows链接测试及固定Flutter SDK缓存访问使用原生权限，没有修改系统Developer Mode。

| 命令/范围 | 退出码与结果 | 原始记录 |
| --- | --- | --- |
| IQ `-X utf8 -m pytest -q --basetemp=.local/bili-full-q03 --junitxml=artifacts/dl02b/full-q03.xml` | 0；1049项及77子测试通过，3条原警告；JUnit1126、零失败/错误/跳过 | full-q03.txt/xml |
| IP `-X utf8 -m pytest -q`，三个新增测试文件及原media_download_http/media_downloads/Office预览/Java整包专项，独立basetemp及JUnit | 0；152项通过 | final-target-p03.txt/xml |
| 固定Flutter `test`全量；随后两个下载对话框专项 | 0；全量211、最终专项14（新预览8、原下载6）；模拟100/200/300% DPI | flutter-full01.txt；flutter-focused-final01.txt |
| 固定Dart `format --output=none --set-exit-if-changed lib test`；Flutter `analyze --no-pub`；Ruff `check backend tools` | 均0；90文件无变更、No issues、All checks passed | dart-format-final01；flutter-analyze-final02；ruff-final01 |
| `./packaging/windows/build-backend.ps1 -Python .venv/Scripts/python.exe` | 0；最终API-only路径47业务模块内嵌code/constants一致 | frozen-build03.txt |
| IQ `tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/bili-frozen-api01` | 0；34检查/18错误ID，重启、收据、媒体Range保留 | frozen-api01.txt |
| IQ `tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | 0；Host/Origin、EOF、两轮CLI迁移、原件/笔记/文档/下载等回归通过 | frozen-lifecycle01.txt |
| IQ `tools/check_bilibili_previews.py --allow-public-fixture --exe dist/study_backend/study_backend.exe --test-root .local/bili-frozen-public02` | **1**；原公网IPv4/DNS守卫拒绝，未取得站点格式正向结果 | frozen-public02.txt；该test-root/failed-preview.json |

最终exe为22602465字节，SHA256 `65d63cf5c8cddc4549c217ca105abaca3c67421be37a525915dd128d2849f518`；没有提交二进制/profile/影片/原始日志。冻结之后业务Python未改。Flutter最终analyze第一次因新控件两处缺少if大括号退出1，补齐后final02通过，原失败保留；未降低断言。早期冻结build01/02及full-q01/02均只作沿革，不替代上表最终证据。

当前状态REVIEW：已实现受控普通B站格式预览、取消及短期候选；未实现确认下载、轨道合流、多P/互动/付费内容、抖音/爱奇艺。后续DL-02b候选确认需复用持久队列/来源身份/固定headers逐跳守卫，DL-03仅依赖格式交接与二进制方案，不循环依赖完整DL-02。网站字段变化会受控失败，固定源版本只保证可追溯，不承诺永久适配。PR/current-head CI和固定CC样本的真实源码/冻结公网结果待核，不标DONE。源码/冻结公网诊断在同一CI步骤各自执行并合并退出码，源码失败也不掩盖冻结结果。

## d17cd3e真实CI失败与精确诊断补丁

[PR#52](https://github.com/surface-user/StudyWorkbench/pull/52)初候选head d17cd3eeb116ec92e7fd5ca656d4775006c66e50/tree a77e2b9b701342192e0b7d435296d33603751622、[CI43576361155](https://github.com/surface-user/StudyWorkbench/actions/runs/43576361155)已逐head核对，completed/failure。两后端job成功，各1049项/3警告，Ruff与R1–R5通过；desktop的211组件、格式/分析、Windows Release、COM、新冻结47模块及全部既有冻结回归成功。47步中44success、1failure、2skipped：新增公网步骤失败，依赖失败跳过发行输入上传和setup-python post，诊断上传成功。不是完整CI通过。

源码与冻结在同一受控主路径各自产生失败JSON，均error“该视频暂不可预览，可能需要权限或访问限制”、result=null；此固定文本仅在HTTP非200返回，但旧版没有阶段/具体状态，不能据此断言412、登录授权、外部权限或用户网络环境。原d17代码、报告、本机DNS失败和远端HTTP非200是不同证据，全部保留。artifact [14107451115](https://github.com/surface-user/StudyWorkbench/actions/runs/43576361155/artifacts/14107451115)已取回，ZIP795字节SHA256 `19638cd3f662e4116dcba964a8f5d611f2bd952e8f349df6d8cc7d82f06616be`；仅两份脱敏failed-preview.json，原zip及CI筛选摘要保存在忽略的artifacts/dl02b，未把全文日志/profile入Git。远端491个blob、26变更、两锁和原许可文本均核对；169本地Markdown引用无缺失。

主Agent依调度规则退回IN_PROGRESS并要求先定位普通实现细节。已核实际PinnedHTTPS.__init__保留域名给HTTPConnection，connect只将固定IP传给socket.create_connection，TLS仍用self.host的SNI/证书校验。CPython putrequest默认Host由self.host生成，尚不能仅凭读代码代替线缆证明；新增真实http.client请求的捕获socket回归明确核Host为api.bilibili.com、socket目标为批准IP:443、TLS server_hostname为域名且CERT_REQUIRED/check_hostname开启，六个固定公开头无Cookie/Authorization。WBI urlencode后的path/query原样进入请求，百分号不重复编码，中文/斜杠/空格/加号/百分号查询值可还原。短链每实际跳仍重走DNS和固定连接，API重定向只同域同原path，普通BV/av不请求HTML。

最小诊断方案经主Agent明确批准：仅原非200分支抛PreviewHTTPError，附固定stage四枚举shortlink/nav/view/playurl与严格整数http_status100–599；worker IPC父进程只接收这两个键，布尔/字符串状态、越界、未知stage、附加字段均拒绝，不反射远端文本。鉴权API可选error_diagnostic只携此二字段；普通UI仍显示原error文本。开发探针在失败前复核无私有字段，只打印此诊断并保存原脱敏JSON。不新增请求或回退、不改UA/公开头/入口/TLS/DNS/请求预算，不跳过公网步骤。JSON业务code、DNS/格式错误不伪造HTTP状态。

首轮专项：IQ `-X utf8 -m pytest -q backend/tests/test_bilibili_preview.py backend/tests/test_media_site_previews.py backend/tests/test_bilibili_probe.py backend/tests/test_media_download_http.py --basetemp=.local/bili-diagnostic-q01 --junitxml=artifacts/dl02b/diagnostic-q01.xml`，退出0、135项；IP相同四文件、独立p01 basetemp/JUnit，退出0、135项。Ruff check backend tools退出0。真实固定worker的原取消/隔离测试、真实IPC可选诊断的父进程白名单/固定普通错误/取消清空，以及所有旧非200断言保持。后续仅收紧查询值还原断言，最终核验及新冻结/CI另记，不拿旧exe替代新代码。

最终IQ同四文件专项（q02独立basetemp/JUnit）退出0、135项；IP对新增查询值还原断言的 `backend/tests/test_bilibili_preview.py::test_actual_http_client_keeps_domain_host_sni_and_encoded_target`（wire-p02独立basetemp/JUnit）复验退出0、1项，配合其135项完整专项。最终Ruff check backend tools退出0；没有Dart/UI源变化，普通错误文本由API专项明确断言，Flutter全量另随新head CI执行。

`./packaging/windows/build-backend.ps1 -Python .venv/Scripts/python.exe` 再次退出0，新47业务模块内嵌code/constants与当前源码一致；新exe22603563字节，SHA256 `74085005353f9087563adc5cd0e0b6088055c683180337104b4cdfd26562f78a`，覆盖的旧exe身份/失败证据仍由原摘要与日志保留。IQ `tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/bili-frozen-api-diagnostic01` 退出0，34检查/18错误ID；冻结和源码分别运行 `tools/check_bilibili_previews.py --allow-public-fixture`，使用各自source/frozen-diagnostic01新test-root，均退出1且仍为本机原DNS公网守卫拒绝，error_diagnostic=null，未取得HTTP响应，不伪造阶段/状态。原始记录为artifacts/dl02b/{diagnostic-q02,diagnostic-p01,wire-p02,ruff-diagnostic02,frozen-build-diagnostic01,frozen-api-diagnostic01,public-source-diagnostic01,public-frozen-diagnostic01}对应txt/xml；精选[http-diagnostic-summary.json](evidence/http-diagnostic-summary.json)保存最终JUnit/模块/exe的hash及边界，SHA256 `4c1132e79273279b9f0ae251555775019cb536410dd95f024465743f11de56d9`。

当前IN_PROGRESS：同PR推送新的受限诊断补丁后，核新head CI的真实源码/冻结阶段和状态，再根据事实定位普通请求兼容问题；尚不宣称外部权限阻塞，也不改入口、UA、网络门禁或公网退出条件。审查暂缓、人工取消、未合并或发行。

## v1精确view412与标准公开页面v2

be3169917b79ff4abfa865ac260bed48df0670d2/tree514d76d6227d467f916ed42c9ec9c7bd9fbf643b的[CI43578909355](https://github.com/surface-user/StudyWorkbench/actions/runs/43578909355) completed/failure：两后端各1073、Flutter211、Windows/COM/47模块冻结及既有离线回归成功；源码与冻结均stage=view/http_status=412。可由控制流确认nav成功返回WBI键，playurl尚未请求，不能归因其cid/play参数或推断具体权限原因。artifact [14108250440](https://github.com/surface-user/StudyWorkbench/actions/runs/43578909355/artifacts/14108250440)两份失败JSON已下载核验，875字节ZIP SHA256 `d83b3e8bdeeefcfe8e42719daa3e225eb33a0c0b02dcffa827881e1a2d4a25eb`，原d17和be316代码/失败zip/日志保留。

固定f264a6c文件SHA b99ad995a016b11097cdadfb64bc6da55cd64129b76e7914eafbc7e45685ec33逐段对照：134–167的WBI图文件名拼接/64项置换/前32字符、按键排序、五字符!'()*过滤、round(time.time())严格整数和MD5(query+key)一致；view参数为platform=web+bvid或aid，playurl另有bvid/cid/fnval4048与上游dm_params/try_look差异。离线compare_fixed_wbi.py仅解析上游AST常量，没有执行上游程序；BV/av/play及五字符/中文/百分号四个固定向量和线缆query均一致，退出0，筛选比对保留在忽略的artifacts/dl02b/fixed-wbi-comparison.json。未在view412后补尚未请求的游客指纹/试看参数。

已证实现依据差异在上游723–735：普通提取先正常GET公开页面及__INITIAL_STATE__，view/detail只在状态缺失时辅助查redirect_url，不能据该备用用法证明独立匿名元数据主路径。主Agent批准调整实现选择，唯一预声明链改为公开page→nav→playurl，仍是3次正常请求；不是收到拒绝后的自动备用切换。版本升bilibili-preview-v2，stage改为shortlink/page/nav/playurl；v1/view历史含义保持在原证据，不覆盖旧失败。

旧HTML原型全页面regex可匹配注释/字符串伪锚点，raw_decode丢弃结束索引且只取第一赋值，存在数据来源歧义；它没有eval，未宣称这是已证RCE。v2不照搬：标准库HTMLParser只看无src且类型匹配的inline script，排除HTML注释/属性、模板/noscript/文本惰性区域；赋值须从脚本开头固定window.__INITIAL_STATE__开始。JSONDecoder严格重复字段/NaN/深度64/节点50000保护保留，raw_decode结束后只能是分号+空白；未知IIFE/尾表达式/第二赋值均拒绝，不猜测或执行尾部。最多128脚本并保留原2MiB单响应/8MiB累计/10次请求/3重定向/10秒I/O/45秒/Job1GiB4进程等预算，未加cookie、JS、图片/轨道请求或UA变更。AV→BV正常跳转仍检查原aid，所有身份/rights/单P/试看拒绝保持；不恢复__playinfo__备用分支。

v2实际验证：IQ四文件专项沿用上节命令，独立 `.local/bili-v2-q02` basetemp/JUnit，退出0、160项；IP同四文件v2-p01退出0、160项；Ruff check backend tools退出0。新增注释/属性/src/JSON字符串/惰性区域伪锚点、多候选、重复字段、NaN、尾表达式、未知IIFE、脚本计数、AV原身份冲突及嵌入playinfo不回退断言，旧限制断言按相同语义迁移未删除。实际http.client全链捕获证明page/nav/play的三次域名Host/TLS-SNI、证书校验与批准IP连接，另有原编码值还原检查；仅离线捕获，不冒充站点正向。

`build-backend.ps1 -Python .venv/Scripts/python.exe` 新v2冻结退出0、47模块内嵌code/constants一致；exe22605386字节/SHA256 `ab076dd690c4f2c2ece1544498f50777fd68b3ebbb4c1a71dc7a5b30b18f7fc3`。新冻结API检查34/18错误ID退出0，源码/冻结限定CC元数据探针分别新v201 test-root均退出1，仍为本机原DNS公网守卫拒绝，HTTP诊断null、版本v2；未将旧v1 exe或成功摘要当v2证据。原始txt/xml保存在artifacts/dl02b的v2-q02/v2-p01/ruff-v202/frozen-build-v201/frozen-api-v201/public-source-v201/public-frozen-v201。精选[v2-summary.json](evidence/v2-summary.json)与前两版摘要分别保留。

office_1114正式性能窗口期间本任务暂停重构建/测试/大hash；其明确暂停后才执行约十余秒专项及78秒新冻结，全部结束后通知释放本机，后续只做文本/PR与远端CI。当前IN_PROGRESS，同PR新head公网仍必需；公开页面若非200或受限如实保留局部阻塞，后续独立DL-03格式/轨道交接继续，不重复打请求或降低门槛。任务详细DL-03旧“依赖整个DL-02”标签已与概览/契约统一为格式/轨道交接及二进制选择，避免循环依赖。
