# LW-07 本地媒体获取与下载

2026-11-05，用户授权持续推进直到额度用尽；按路线接续LW-06/09，人工及阶段验收继续待验。无子Agent。本任务仅本地实现/测试/自审，不要求本批提交或新PR，未授权推送/合并/发行。原始产物artifacts/lw07-20261105/；同任务重试继续本报告。

## 首批需求和设计

来源限定用户有权获取的直接HTTPS媒体文件，UI须明确权利确认；源质量仅原始文件，不解析站点、不登录、不处理DRM/播放列表或转码。首批只支持MP4/WebM/M4A，复用既有512MiB媒体预算、容器头校验和媒体资源身份。固定组件为现有CPython标准库http.client/ssl/socket/ipaddress，不引入yt-dlp/FFmpeg或额外依赖，既有FFmpeg样本生成器不随产品发行。

先实施有界传输，再接持久队列和普通UI，不能把传输模块当成已交付下载能力。目标固定受管目录、文件名由业务校验/ID生成，不提供HTTP任意目标路径。未来队列单worker/有界待办，进度/取消/重试/重启恢复、媒体去重和磁盘预算均须完成；新增表时追加迁移、LW-05全库覆盖/摘要核对及旧库保留，不提前登记不存在的接口。

传输边界：仅HTTPS/443、ASCII DNS域名（路径/query可编码中文），不接受凭据/fragment/控制字符；IPv4首批，DNS结果须全部为允许公网IPv4，限制答案数并将连接固定到已核地址，TLS证书/主机名校验和SNI仍用原域名。拒绝内网/loopback/link-local/保留/多播等，重定向每跳重新校验和固定，最多3次；不读取系统代理、cookies或业务令牌。IPv6/代理网络首批不支持，不冒充任意网络可用。

逐块写入和预算检查，不以Content-Length代替实际字节限制；拒绝压缩内容、歧义长度/传输编码、错误MIME/容器头。只在强ETag、精确206 Content-Range和已存长度一致时追加恢复；服务端返回200/版本变化时停止，旧部分不覆盖。取消/失败保留字节；普通日志/错误不含完整URL及query，签名URL只进入个人库（后续UI须说明全库未加密备份范围）。网络I/O每次有10秒超时，整体期限/不可取消DNS由固定工作子进程负责，尚未接入之前不视为已有限时产品任务。

依据现有技术栈及Python官方[HTTPSConnection](https://docs.python.org/3.13/library/http.client.html)、[TLS默认校验](https://docs.python.org/3.13/library/ssl.html)、[IP分类](https://docs.python.org/3.13/library/ipaddress.html)细化实现；使用3.12/3.13共有API，不采用最新文档中3.15新增参数。真实授权来源/错误网络/Windows播放和窗口验收按实际结果分列。

## 持久队列实施设计

0015新增media_download_jobs，空间/目标父目录复合约束、空间内request_id幂等；source_url/name/parent固定，进度/ETag/部分hash、attempt及结果分列。queued/running在启动时改interrupted，不自动联网；单worker、全库最多32待办。每次尝试使用独占ID路径，最终文件直接成为受管媒体原件，不复制/移动或覆盖；同空间完整hash相同且旧媒体实际字节有效时复用媒体身份，下载副本仍作为任务历史保留，不承诺释放空间。

固定子进程接stdin配置，不在命令行/错误中暴露URL；stdout受限进度/结果，父进程15分钟硬期限、取消先关闭stdin，2秒仍未响应才终止本任务所属子进程，以处理阻塞DNS/网络。进度附前缀hash；恢复只在文件实际长度/hash、强ETag及Range全符时追加。retry明确resume或restart；restart分配新attempt文件，旧字节不删。子进程/父进程崩溃导致进度和文件不符时拒绝resume，须显式重新开始。归档/目标移除、空间不足等停止，已存部分保留。

普通UI输入直链、文件名及权利确认，列表展示进度/暂停/断点重试/保留旧部分重新开始/打开完成媒体；不显示敏感query、不自动展开外部站点。API不接受目标路径、不注册Agent下载工具。迁移、离线备份schema/新表/部分文件、重启/取消/恢复/去重/失败/跨空间均须测试；最终退出仍含真实来源/窗口与用户验收。

## 实施与当前验证

传输、固定worker、持久业务队列及资源管理器普通入口已接入。0015保留既有表与数据，后台关闭下载子进程后才能整库备份；离线支持schema同步0015，ready任务的原件/结果节点媒体关系另验，暂停/未知部分照实际字节保留。生产恢复旧schema时发现只允许study-before-0014备份名的旧守卫，已改为严格匹配当前SUPPORTED_SCHEMA，未放宽未知文件拒绝规则。下载最终文件直接由媒体引用；去重复用身份但副本留存，不删除任务或旧部分。

自审补齐可验证完整断点的本地收尾（不再从EOF请求Range）、每块前缀hash、目标目录删除/归档检查、独占新attempt、已知总量按实际剩余磁盘预留；未知长度仍按512MiB。入库hash扫描有字节上限及取消检查。worker/父进程期限、无窗口创建和只终止所属子进程已有针对性测试，不能代替真实来源或浏览器播放。普通UI显式权利确认、相同参数断连重试复用request_id、关闭不取消任务、重启需手动恢复，来源移除不打开旧媒体；当前列表最多100条且优先进行中，历史仍保存在库中。

P=.venv/Scripts/python.exe，仓库根；Flutter命令在apps/desktop执行，D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F=D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot，入口D F --suppress-analytics。原始日志均在artifacts/lw07-20261105，后续测试使用新basetemp，不覆盖初次失败。

| 实际命令 | 退出码/结果 | 产物 |
|---|---|---|
| P -m pytest backend/tests/test_media_download_http.py -q --basetemp=.local/lw07-http-20261105-01 --junitxml=artifacts/lw07-20261105/http-01.xml | 0，47通过，2.15秒；传输第一版 | http-01.log/xml |
| P -m pytest backend/tests/test_media_download_http.py backend/tests/test_media_downloads.py backend/tests/test_spreadsheet_view.py -q --basetemp=.local/lw07-queue-20261105-01 --junitxml=artifacts/lw07-20261105/queue-01.xml | 0，87通过，12.18秒；含前缀篡改拒绝 | queue-01.log/xml |
| P -m pytest backend/tests/test_media_downloads.py -q --basetemp=.local/lw07-queue-20261105-02 --junitxml=artifacts/lw07-20261105/queue-02.xml | 1，6通过/1失败：测试误写manifest字段count，实际协议为rows | queue-02.log/xml |
| P -m pytest backend/tests/test_media_downloads.py backend/tests/test_backup_archive.py -q --basetemp=.local/lw07-queue-20261105-03 --junitxml=artifacts/lw07-20261105/queue-03.xml | 0，53通过，13.33秒；改正确字段，仍严格核对2行及恢复后字节/URL/关系 | queue-03.log/xml |
| P -m pytest backend/tests -q --basetemp=.local/lw07-backend-20261105-01 --junitxml=artifacts/lw07-20261105/backend-01.xml | 1，435通过/2失败，259.03秒；未来版本fixture仍用0015、生产恢复守卫仍写死0014 | backend-01.log/xml |
| P -m pytest backend/tests/test_media_downloads.py backend/tests/test_media_download_http.py backend/tests/test_backup_store.py -q --basetemp=.local/lw07-queue-20261105-04 --junitxml=artifacts/lw07-20261105/queue-04.xml | 1，71通过/1失败，39.13秒；未扩展权限运行时Windows mklink真实junction被拒绝，未删或跳过测试 | queue-04.log/xml |
| P -m pytest backend/tests -q --basetemp=.local/lw07-backend-20261105-02 --junitxml=artifacts/lw07-20261105/backend-02.xml | 0，440通过，242.76秒；扩展权限含junction；之后补完整断点/磁盘及目标移除检查，末轮另记 | backend-02.log/xml |
| D F --suppress-analytics test --no-pub test/media_download_dialog_test.dart | 0，2通过 | flutter-download-01.log |
| D F --suppress-analytics analyze --no-pub | 1，4处花括号info/1处冗余cast warning；单文件dart fix及移除冗余cast修正，待末轮 | analyze-01.log |

旧库迁移测试中的当前head/升级备份名由0014改0015，故障注入0014本身保持，未改旧断言为宽松范围；只读包测试仍保留schema0014作为向后兼容样本，未来版本拒绝样本改0016。ruff初次仅import排序，--fix后通过。Starlette/anyio旧warning保留，无新增运行依赖。

## 真实公网来源尝试与限制

使用已核CC0公开源：[Media.webm](https://commons.wikimedia.org/wiki/File:Media.webm)，作者SounDany18，页面版本oldid=1205920199，标明CC0 1.0、6501273字节、SHA1=e0c41415959164afa4584379fda17dec95616d95；原文件直链https://upload.wikimedia.org/wikipedia/commons/0/0f/Media.webm。仅作测试下载到Git忽略的隔离库，不转发/发布。尝试前Blender官方候选页面在web工具返回402，未将该工具错误当成站点付费或下载许可证明，改用上述可核来源。

P tools/check_learning_workbench.py --test-root .local/lw07-public-20261105-01 --download-url https://upload.wikimedia.org/wikipedia/commons/0/0f/Media.webm --expected-download-sha1 e0c41415959164afa4584379fda17dec95616d95退出1（public-flow-01.log）：实际任务failed，域名未解析到允许公网IPv4。只读诊断确认1个答案、all_global=false、benchmark_fake_ip_seen=true（198.18.0.0/15测试用地址），不记录实际本机/代理地址。保留防SSRF拒绝，没有改代理/DNS/证书设置或放行私网；这是当前网络环境与首批“不使用代理”范围限制，未取得真实公网下载或播放通过，整条恢复检查也因前置下载失败未执行。

该工具只在显式传公开无query URL及独立SHA1时增加下载/恢复验证，不进入默认pytest网络依赖；成功才设置public_download_and_restore_verified。签名私有URL不可作为此CLI测试参数。下载部分、故障、用户人工/阶段、实际窗口、发行/CI仍分列，任务继续进行中，未提交/推送/合并/发布。

## 当批末轮结果

后补完整断点收尾/剩余量磁盘检查/目标删除停止后，P -m pytest backend/tests -q --basetemp=.local/lw07-backend-20261105-03 --junitxml=artifacts/lw07-20261105/backend-03.xml退出0，442通过、237.13秒；这是后补预检标签之前的全套。随后LW-06修复统一添加对TXT/JSON/CSV/LOG/VTT/SRT/XLSX“无查看器”的旧提示，保留超预算/坏签名警告，P -m pytest backend/tests/test_resource_inspections.py backend/tests/test_readonly_text.py -q --basetemp=.local/lw06-inspect-20261105-02 --junitxml=artifacts/lw06-matrix-20261105/inspect-02.xml退出0，18通过、7.66秒（其中新增7项）；不将旧442冒充449项全套重跑。

Flutter全套参数同前述STUDY_ROOT，隔离STUDY_DATA_DIR分别.local/lw07-flutter-20261105-01/-02，flutter-full-01.log退出0、144通过；补600×450测试后flutter-download-02.log为2通过/1失败（底部RenderFlex溢出85像素），改成单一CustomScrollView/sliver表单和懒加载列表，flutter-download-03.log退出0、3通过，原断言保留。末轮D F test全套退出0、145通过（flutter-full-02.log），D F analyze --no-pub退出0/10.4秒（analyze-02.log），D F build windows --release --no-pub --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw07-window/data退出0/57.0秒（windows-01.log）。组件布局不代替真实DPI/中文IME窗口验收。

Q=.local/release-venv/Scripts/python.exe；Q -m PyInstaller --noconfirm --clean --distpath artifacts/lw07-20261105/frozen/dist --workpath artifacts/lw07-20261105/frozen/build artifacts/lw07-20261105/frozen/spec/study_backend.spec退出0，约147.9秒（frozen-01.log）。先确认新目标不存在，复用上一已核spec和固定依赖/metadata，不覆盖原dist。P tools/check_learning_workbench.py --exe artifacts/lw07-20261105/frozen/dist/study_backend/study_backend.exe --test-root .local/lw07-window --media-fixture artifacts/lw09-20261104/fixture.webm退出0（frozen-flow-01.log）：0015启动、XLSX转义/代理对、固定download worker拒绝HTTP并不回显敏感query、重启/整库恢复/源hash与SQLite行摘要一致；媒体仅导入，未公网下载/窗口播放。public_download_and_restore_verified/user_acceptance/phase_acceptance明确false。

Windows前端排除其旧backend后与本批冻结后端配成全新window-bundle，编译固定库.local/lw07-window/data；SHA256及固定目录保存在window-bundle-hashes.json，不碰个人配置或旧包。Computer Use重新list_apps无目标，sky.launch_app新包仍返回computer-use request timed out: launch_app，刷新list_windows目标0；无点击/键入，window-status.json记录。授权不缺失，不再盲重试，不将helper故障写成产品窗口通过或启动失败。

本批实现与自审完成，自动化边界如上；真实无代理公网TLS下载/Range/错误网络与媒体解码、普通窗口、用户/阶段、安装/干净机、独立审查和PR/CI仍待验。用户随后选择LW-08“先完善授权和审核，暂不接模型”，后续工作保持无模型/无远端，不据默认Ollama设计自动接入。


### 2026-11-06 网络前置复核

继续任务时只读重查socket.getaddrinfo(upload.wikimedia.org,443,AF_INET,SOCK_STREAM)，退出0；仍仅1个答案、all_public=false、benchmark_fake_ip_seen=true，摘要artifacts/lw06-native-20261106/public-dns-recheck.json。不再启动必然被同一门禁拒绝的完整公网流程，不改代理/DNS/证书或放行网段；原public-flow-01失败与公网下载/窗口待验保持。新Office包的本地媒体导入、download worker负面拒绝及整库恢复已在LW-06对应闭环复验，通过范围不包含公网下载或播放。

## 2026-11-12：DL-01a，真实公网下载、重启与整库恢复

本轮只读DNS复核发现原Commons源现为1个允许公网IPv4答案，benchmark_fake_ip_seen=false；于是继续原自动化，不改代理/DNS/证书或任何拒绝网段。[原文件页](https://commons.wikimedia.org/wiki/File:Media.webm)（修订1205920199）声明作者SounDany18、CC0-1.0、6501273字节与独立SHA1 e0c41415959164afa4584379fda17dec95616d95。下载仅在新建测试目录使用，不进Git/产品包，不是播放或人工验收。

源基线为#23的2645366（与#22业务相同），隔离目录.local/goal-20261112/public-download。Q为根.local/release-venv/Scripts/python.exe、CPython3.13.17；源码运行设置PYTHONPATH指向该副本backend。以下命令均从该副本执行，原始日志在根artifacts/goal-20261112：

- Q -X utf8 tools/check_learning_workbench.py --test-root <新建dl-source-01> --download-url https://upload.wikimedia.org/wikipedia/commons/0/0f/Media.webm --expected-download-sha1 e0c41415959164afa4584379fda17dec95616d95：退出0，public_download_and_restore_verified=true；入库SHA256及备份恢复后SHA1均一致，重启、原件保持和SQLite行摘要核对通过，日志download-source-01.log。
- Q -X utf8 tools/check_frozen_sources.py --exe <原dist/StudyWorkbench-Release-20261110-37a8d55/app/backend/study_backend.exe>：退出0，43个业务模块及嵌套代码与本副本一致；exe SHA256见精选证据。没有重新构建或覆盖旧包。
- 上述check_learning_workbench加同一--exe、使用新建dl-frozen-01：退出0，冻结真实子进程公网下载、入库、重启/备份恢复通过；工具将PATH限定System32并去除PYTHONPATH/PYTHONHOME，日志download-frozen-01.log。来源文件/学习关系保持；未实际播放媒体。

额外真实传输探针Q -X utf8 artifacts/goal-20261112/check_public_range.py（根目录执行）在524288字节时主动中断后，强ETag断言失败，退出1；public-range-01.log和旧部分保留。该公开源未提供本实现允许的强ETag，不能声称Range续传通过，未降低产品拒绝规则。随后独立探针check_public_restart.py退出0：无强ETag恢复明确拒绝且旧部分逐字不变，显式新文件重新下载6501273字节，独立SHA1一致、SHA256为2ea4c1fccfbe6f37fd3e286cf6a1104b09686a7be260c772582cc5ede140737b，旧部分继续保持。重定向未测试；真实Range成功、重定向及更广错误网络仍属于DL-01未完成项。

[精选证据](evidence/public-download-20261112.json)只保留公开来源、摘要、具体结论和false边界；来源为上述两条真实流程、冻结源码核验及两个实际传输探针，不复制原始日志/数据库/profile/IP/令牌/视频。原11-05/11-06失败保持。本切片仅task、原报告和一个JSON摘要变更，无产品代码、依赖或网络保护变更；文档/JSON/差异范围校验后独立草稿PR，当前head CI未知前保持REVIEW。代码审查暂缓、人工取消；DL-01父项和LW-07整体仍进行中，不合并或发行。

## 2026-11-12：LW-07a 下载完整历史分页

任务沿主 Agent 的并行调度进入 IN_PROGRESS；以 #23 的 2645366ca4f37cced53f41119ccebd732239a123 为父基线，独立目录 .local/goal-20261112/downloads。根工作区/个人库保持，后续提交独立草稿 PR，主 Agent 核验当前 head CI 和退出条件前维持 REVIEW；此处 REVIEW 为交付证据核验，代码审查仍按 ADR0014 暂缓，人工测试取消。

原界面仅列100条；直接将活动优先列表按offset连续翻页，会因完成/暂停后的排序移动而重复或漏掉历史。本切片保留默认API兼容，显式history=true按created_at倒序、id升序，newest_id校验同空间后限定首次时间/ID上界。复用offset/limit，无数据库迁移或新增依赖；不改传输、许可、来源权限或任务数据。上界不是事务快照：系统时钟回拨而产生的较早时间新任务可能进入范围，须显式刷新重新开始浏览，不声称覆盖这一快照语义。

普通UI每页50条，取51条判定下一页。自动轮询保留当前页/上界，显式刷新、创建成功与重新打开从第一页开始；加载期间禁重复翻页，翻页失败保留原页可重试，操作递增请求代次拒绝迟到轮询。列表加载错误与操作错误分开，目标移除仍拒绝打开，完整URL/query不渲染。调用方仅现有对话框和既有下载路由，无新导出/配置；API及学习契约对应段已同步。

### 实际验证与失败保留

工作目录为独立源码，Q为根.local/release-venv/Scripts/python.exe（3.13.17），P为根.venv/Scripts/python.exe（3.12），D为已安装Flutter SDK的bin/cache/dart-sdk/bin/dart.exe，F为同SDK的bin/cache/flutter_tools.snapshot。原始结果在本目录artifacts/lw07a，未纳入Git。

- Q -m pytest backend/tests/test_media_downloads.py -q：首轮默认临时目录权限失败11 errors，backend.xml保留；加basetemp首轮遗漏.local父目录，backend-rerun.xml保留。创建独立.local父目录后进入用例。
- 新历史夹具首轮用2026-11-12日期晚于本机UTC，插入新任务落在旧范围，断言失败；改为固定2000年旧历史。下一轮重启断言选了第二页的ID却在第三页查找，保留失败后改用明确第三页ID30，不降低125项唯一/全集断言。backend-rerun02/03.xml保留。
- Q -m pytest backend/tests/test_media_downloads.py -q --basetemp=.local/lw07a-test04 --junitxml=artifacts/lw07a/backend-rerun04.xml：退出0，11通过。Q -m ruff check backend tools：退出0，全量通过。
- P -m pytest backend/tests/test_media_downloads.py -q --basetemp=.local/lw07a-p312 --junitxml=artifacts/lw07a/backend312.xml：11通过、JUnit无失败；同一命令单元后接D analyze错误相对路径使单元退出1，该路径错误不当作静态检查通过，另在apps/desktop执行检查。
- flutter pub get --offline：受SDK缓存锁文件写权限阻断，停止本任务会话后使用D F --no-version-check pub get --offline。依赖解析成功但本机插件symlink支持检查退出1；未改系统Developer Mode、上游库或锁文件，后续--no-pub组件测试实际可运行。
- D format lib/media_download_dialog.dart test/media_download_dialog_test.dart：退出0，两文件格式化。
- D F --no-version-check test --no-pub test/media_download_dialog_test.dart --reporter expanded：首轮5通过/1失败，测试ensureVisible将刷新文本贴近被裁边缘，真实tap未命中；改居中滚动等待后原断言保持，flutter-target.txt保留。第二轮退出0，6通过，flutter-target02.txt。
- 新增后端2项覆盖125条、同时间ID顺序、状态变化/新插入/重启、私有URL不出响应、跨空间/缺失/非法边界、分页预算及Origin拒绝。新增Flutter3项覆盖123条、第三页/末页/返回、失败原页保留、轮询当前页、重开/显式刷新重置、迟到轮询/关闭与重复翻页禁用。原暂停/恢复/重新开始/目标移除、600×450布局和幂等创建测试保留通过。

完整桌面/当前head CI另核，不用专项数代替；人工窗口/播放未执行。LW-07整体及DL-01公网证据是独立任务，不据历史分页交付标记整个下载能力完成。历史失败/下载原件/attempt保持。

### LW-07a 本地完整回归

D F --no-version-check analyze --no-pub：退出0，无问题，101.6秒，analyze.txt。初次完整test未传STUDY_ROOT/STUDY_DATA_DIR，188通过/5跳过/3备份对话框失败（缺测试根导致选择路径校验未完成），flutter-full.txt保留。给独立源码新建.venv目录链接至既有Q环境，不修改依赖；设PYTHONPATH为该源码backend，在apps/desktop运行D F --no-version-check test --no-pub --dart-define=STUDY_ROOT=<独立源码绝对路径> --dart-define=STUDY_DATA_DIR=<独立源码>/.local/flutter-full02 --reporter expanded：退出0，196全通过、45秒，包含真实后端备份恢复/配置/管道退出，flutter-full02.txt。未改失败测试或降低断言。

最终D format --output=none --set-exit-if-changed lib test integration_test首次指出新增居中滚动行未格式化，退出1；按原格式器修正后退出0，87文件0变化。仅空白修正，不重复功能测试；当前head CI继续执行全套。此切片仍REVIEW，等待独立PR和主Agent验收，Windows本地发行构建未重跑，由当前head CI验证。

实际交付：[独立草稿PR #27](https://github.com/surface-user/StudyWorkbench/pull/27)，分支codex/download-history-pagination，base为#23的2645366，实施提交390072640b0db6f4c5cdf831282602a4a4ee5c9f，八文件。补链接后的最终head CI以PR实时记录为准，未核实前保持REVIEW，主Agent检查后登记DONE；不以父head通过替代本项CI，未合并/发行。

### DL-01b最终验证与主Agent验收（2026-11-13）

[PR #38](https://github.com/surface-user/StudyWorkbench/pull/38)最终head `842b19df5100e55960f98269283743d37d63433b`的[PR CI43362970857](https://github.com/surface-user/StudyWorkbench/actions/runs/43362970857)三job/46步骤全部成功，公网步骤实际执行。Python3.12为745通过/433.52秒，3.13.17为745通过/386.97秒；桌面构建、新冻结44模块源码一致、既有探针与公开下载验证均成功。

源码真实持久队列写入256KiB后显式暂停，新进程以相同attempt/路径/前缀发出Range/If-Range，取得206及291914字节；WPT同域302和跨域302至固定MDN对象完成，独立重下SHA256一致。另一次真实源码暂停由未经注入的冻结exe恢复，受限PATH、相同attempt/前缀、最终大小/hash与入库通过。冻结206由严格生产范围校验、44模块一致和最终结果推断，未直接抓包；不混作直接响应观测。

源码观察器累计1665678字节，另一冻结恢复前缀262144字节，冻结实际追加291914字节，合计2219736响应体字节；不计TLS/报头。源码硬限5MiB，冻结原512MiB/15分钟保护不变，外部观察不构成5MiB硬保证。花视频SHA256 `c6f8a348953395598a9a73b9bab1676436410797bce9f398f4be1531d6e76dda`，冻结exeSHA256 `d5b706aa36d88ff597d046ce4a5665aff3f0fefc1254133693e89f1717bf9911`。

原始日志与筛选摘要保存在原独立副本`download-range/artifacts/dl01b/`，摘要`ci-public-summary-842b19d.json` SHA256 `cbdfa5cbe5211ca53dc9bcafdd707097fbfdc78c73fa6684542920cc7359fce8`。主Agent独立核对head/CI、原桌面日志和摘要hash后，在PR描述登记DL-01b DONE；结合#24已交付的原范围，父DL-01 DONE。此前失败及当时状态段落保留，LW-07后续站点/质量/转码不销项；审查暂缓、人工取消，未合并/发行。

## DL-02a：共同契约与固定组件候选评估（2026-11-13）

本项只交付设计文档。基线为#38精确head `842b19df5100e55960f98269283743d37d63433b`，451个受跟踪文件逐一校验Git blob后复制到独立`.local/goal-20261112/download-extractor-plan`，不移动#38、根工作区或共享环境。修改范围仅现有契约、依赖登记、task和本报告，无产品代码/API/DB/UI/依赖/工作流改动。

### 范围核对与最小设计

完整读取AGENTS、requirements、architecture、question-content-spec、task及现行下载/API/数据/安全约束；基线task的DL-02、路线第3节、契约第8/10节和ADR0014均未指定网站及具体授权来源。早期方向输入也只提出待定项，不能把“Seal交互参考”或上游支持列表当成站点决策。主Agent询问后，用户明确回复“B站,抖音,爱奇艺,”，按此范围先从B站推进；本版已登记三站，不再写目标站点未知。尚缺自己发布或已获准下载、无需登录的单视频样本，实际下载不得以等待超时或上游测试URL代替授权。

共同契约采用：明确发起提取→有界纯文本质量预览→用户确认→复用现有持久任务。现有直链的无特殊headers单文件条件只界定可直接复用范围；用户已选B站，公开固定Referer/Origin、WBI参数可在服务端精确域/用途白名单及逐跳校验下另作普通能力设计，不构成永久阻断。元数据预览先行；分轨/HLS/DASH依赖DL-03的传输/合流，其前置改为明确的格式交接而非整个DL-02完成，避免循环。临时匿名站点cookies与登录凭据区分，后续先定任务隔离/生命周期/域范围，本项不启用或读取浏览器会话。短期候选引用绑定空间/来源/版本/格式，重启/过期重新确认；成功创建的同幂等请求优先返回原任务。媒体传输、512MiB与15分钟、强ETag/206/前缀hash、失败字节和身份/备份规则保持。实际来源追溯与原子登记、预算、API/表结构仍在实施前设计，本项不预建协议名称或迁移。

提取器的页面/API/所有内部请求也必须执行现有公网IPv4固定地址与TLS/每跳守卫。固定源码适配是候选路径；独立进程/Job只是期限与生命周期约束，不能冒充完整OS网络沙箱。stock CLI的metadata/skip-download模式仍会联网，其配置、插件、外部进程、远程组件和默认请求处理均须纳入验证；输入/最终URL检查不足。无法证明全部实际请求受控的提取器不得纳入支持，不能用换代理、浏览器cookies或关闭TLS绕过。

### 固定官方来源与分发差异

使用GitHub连接器只读获取[2026.10.26 release](https://api.github.com/repos/yt-dlp/yt-dlp/releases/tags/2026.10.26)及[tag ref](https://api.github.com/repos/yt-dlp/yt-dlp/git/ref/tags/2026.10.26)，指向commit `f264a6cbd1f630894da0f368df00f8aae50140e0`；发布时间2026-10-26T22:25:26Z。固定commit的README、LICENSE、pyproject、THIRD_PARTY_LICENSES、YoutubeDL、networking/common与_urllib、plugins、__init__用于下述有限评估，未下载/安装/执行发行二进制。

- 官方文档将Git/PyPI源码与wheel的Unlicense，和PyInstaller成品的GPLv3+组合明确区分；release tarball另含ISC/MIT的JS代码。产品分发对象尚未选定，不能把“yt-dlp Unlicense”套到Windows exe。
- Python要求≥3.11与本项目3.12/3.13名义匹配；官方Windows x64成品声明Win10+。这不是本项目源码或冻结集成实测。release API的大小/digest见[依赖登记](../../../docs/dependencies.md#站点提取候选未采用)，只是官方元数据，未取成品字节核验。上游提供SHA2校验清单及GPG签名，但本轮没有下载验签，不称供应链通过。
- 基础Python依赖为空不等于站点能力无需可选组件。default extra含yt-dlp-ejs 0.8.0；上游说明完整YouTube支持另需EJS和JS引擎。EJS/JS运行时/浏览器仿真/FFmpeg均未选用，传递许可和实际配置未审。固定版本也不等于无漏洞，本轮未运行扫描或最终SBOM。
- `YoutubeDL.build_request_director`能够选择request handlers，默认使用已注册handlers；`urlopen`处理认证等输入，plugins具有发现/加载路径。这支持“可调查固定源码适配”的判断，不证明所有提取器仅走此入口。所选站点确定后还须检查实际提取器调用路径和禁止回退/外部程序，普通CLI参数不能代替这项证明。

补读同commit的bilibili.py、tiktok.py与iqiyi.py后，三站分别列入[依赖登记](../../../docs/dependencies.md#站点提取候选未采用)：BiliBiliIE带Referer、WBI签名及DASH/多段候选；DouyinIE缺详情时要求fresh cookies；国内IqiyiIE走HTTP并返回m3u8，国际IqIE另用PhantomJS签名。这里只观察第三方提取器，未据此确认网站官方允许调用或下载权限。普通固定headers/分轨/匿名会话分别设计，不能混同权限突破；当前不启用cookies/挑战脚本、HTTP降级、付费/DRM绕过，不将YouTube EJS或国际iq.com暗中加到用户范围。

本切片更新文档入口中的陈旧“下载队列未实现”为“标准库直链队列已实现、yt-dlp未接入”；不将候选提升为采用项。不引入依赖、不下载exe、不读取个人库、不接模型/登录/DRM。DL-02a可作为有限文档交付，父DL-02/实际DL-02b和DL-03仍未实现；审查暂缓、人工取消，未合并/发行。

### 文档验证与交付

本项无业务实现，新增行为测试不适用；完整业务回归由本PR当前head CI执行，普通CI不得因文档设计新增任意公网提取。#38限定分支公网步骤在本分支跳过，不重复宣称为本项真实站点验证；未核实前DL-02a保持REVIEW。

实际在独立目录执行`Q .local/validate_dl02a.py`：首轮退出1，仅Git全局autocrlf对LF文件的转换警告被校验器当作stderr失败；没有文档空白错误。固定该次只读diff命令为`git -c core.autocrlf=false diff --no-index --check <原文件> <新文件>`，不改全局Git配置或放宽空白检查。复验退出0：451文件中仅预期4文档变化，82处本地引用/6处锚点存在，40个原任务标识保留，原报告全文前缀不变；每个no-index命令因存在差异退出1且stdout/stderr均空，聚合校验为0。摘要保存在`artifacts/dl02a/validation.json`，本地工具/产物不进入Git。候选官方文件均通过只读GitHub连接器取得，未执行第三方程序；共享Python环境不变。后续PR/最终head CI以独立PR实时记录核对，不沿用#38绿灯替代本项。

已创建并附加[独立草稿PR #45](https://github.com/surface-user/StudyWorkbench/pull/45)，分支`codex/download-extractor-plan`，base为#38的精确842b19d，初始文档提交`bf748c80f602167f97f70e75e33a0b5bb06b74e5`。本链接补交后以PR最终head的检查为准，DL-02a待主Agent验收；不因文档完成登记实际站点下载通过，代码审查暂缓、人工取消，未合并/发行。

## 2026-11-13 DL-01b：固定公网Range与重定向探针

独立副本`.local/goal-20261112/download-range`基于PR #34最终8b29a27008e64e0cce6615a2135edda1125a435d；远端449个Git blob与本地逐项一致，未覆盖根checkout及其他任务副本。主Agent已核API-01/01a原退出条件和该head CI，任务表及原API报告同步DONE，保留旧偶发Office关闭失败，不把额外细粒度业务码强加为父项未完成条件。DL-01a源码/冻结公开下载与备份恢复由[PR #24](https://github.com/surface-user/StudyWorkbench/pull/24)交付，本切片补真实正向Range和重定向；不因文档基线较旧而重复开发下载业务。

### 范围与固定样本

- 只增加`tools/check_public_downloads.py`开发探针、离线探针测试、显式CI步骤及使用/任务/本报告；生产下载器、接口、数据库、Flutter和依赖锁未改。
- MDN [flower.webm](https://github.com/mdn/interactive-examples/blob/9991b045e1561681d3ffc66215b92f68531ec97b/live-examples/media/cc0-videos/flower.webm)，固定commit9991b045e1561681d3ffc66215b92f68531ec97b，554058字节，Git blob `5b8edf7d8384c057dfb13627073288cebfb54d74`。[该commit LICENSE](https://github.com/mdn/interactive-examples/blob/9991b045e1561681d3ffc66215b92f68531ec97b/LICENSE)为CC0-1.0。固定raw URL为传输源，独立对象身份校验必须包含Git blob头，不把Git SHA误当文件原始SHA1。
- WPT `/media/2x2-green.mp4`是3503字节的程序生成单帧样本，Git blob `157361c2ddc97fc1179006ab1dfa9639fe14950f`；[引入提交2305706](https://github.com/web-platform-tests/wpt/commit/23057064c87f42aba0615705b11570ace9cb4324)保留生成命令。[WPT LICENSE](https://github.com/web-platform-tests/wpt/blob/master/LICENSE.md)为BSD-3-Clause，版权所有web-platform-tests contributors；不把其称为CC0。只临时下载测试，不随Git/安装包/CI构建输入分发样本；部署内容变化则对象hash检查失败。
- 使用WPT现行[common/redirect.py](https://github.com/web-platform-tests/wpt/blob/master/common/redirect.py)的`location`参数分别验证同域相对跳转到green和跨域到固定MDN文件。开发日志须实际看到302/指定Location，随后生产传输再验每跳DNS/TLS和最终对象hash，仍最多3次重定向。

### 验证设计与边界

先通过产品`resolve/PinnedHTTPS`预检HEAD固定长度/强ETag、If-Range单字节206。真实源码后端用HTTP API创建持久任务，原worker和transfer实际写入首个256KiB；开发入口仅让该进度可观察并等待普通pause。暂停API/原进度处理落库后关闭进程；新源码进程显式resume，核同attempt/路径/前缀、实际Range/If-Range及206范围，独立重下核固定Git对象和SHA256。两个重定向也经过普通任务/入库，重复花视频复用媒体身份。

`--exe`再用另一份真实源码下载前缀，通过未经注入的冻结后端恢复。冻结子进程PATH仅System32，清除PYTHONPATH/PYTHONHOME，独立cwd；不需要系统Python/开发包。其206结果是结合固定冻结源码校验、产品强ETag/Content-Range拒绝逻辑与最终同attempt/前缀/hash推断，并非直接抓包观察冻结响应。源码观察器不替换DNS/TLS或响应内容，不伪造部分文件、SQL状态或服务端Range。

源码观察器限制累计响应体读取5MiB，并拒绝超过固定样本长度的响应。全流程预期约2.2MiB响应体，5MiB为探针预期总预算。冻结保持产品512MiB/15分钟原保护，外部轮询见长度偏离请求暂停并失败；不声称轮询可硬保证5MiB。汇总分别列源码读取量与冻结文件实际追加量，不将TLS报头/握手开销计入响应体。后端/工作子进程、目标文件和库均属本次新目录，不读个人资料。

公网步骤只在本证据分支`codex/public-download-range`的PR事件显式开启；普通pytest和其他分支不联网，不为触发任务合并main。[GitHub官方说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)要求workflow_dispatch工作流先位于默认分支，因此本次不依赖尚未合并的新手工工作流。CI只在控制台输出筛选过的固定公开响应元数据/摘要，不上传下载媒体/个人库。

### 本地实际命令与结果

以下在本独立源码目录执行；Q为根`.local/release-venv/Scripts/python.exe`3.13.17，P为根`.venv/Scripts/python.exe`3.12.7，共享依赖均未升级。产物为本目录`artifacts/dl01b/`。

- 首轮`Q -m pytest backend/tests/test_public_download_check.py backend/tests/test_media_download_http.py backend/tests/test_media_downloads.py -q --basetemp=.local/dl01b-target01 --junitxml=artifacts/dl01b/target01.xml`退出0：66通过，13.27秒。补冻结入口后target02同专项退出0，66通过，14.85秒。
- 补错误Range/预算停止/真实后端跨进程后，同专项Q使用target03目录与XML/log退出0：73通过，18.10秒；P使用target31201目录与XML/log退出0：73通过，20.93秒。原Starlette/anyio弃用警告保留。覆盖固定对象hash与原始SHA1区分、变长/同长损坏、逐块预算、真实transfer首块落盘/hash、不联网opt-in拒绝、旧目录保留、假206/ETag/范围/长度拒绝、超预期暂停及真实源码后端启动/关闭/重启。普通下载安全/队列既有断言全保留。
- 首次Ruff退出1，仅脚本设置自身backend搜索路径后导入的E402；按开发入口需要局部注明，不全局关闭规则。`Q -m ruff check backend tools`最终退出0，ruff01.log。初始化基线校验曾漏显式UTF-8退出1，补正确解码后449文件全相同；无源码覆盖。
- `Q tools/check_public_downloads.py --allow-public-fixtures --test-root .local/dl01b-public01`退出1，在原resolve拒绝，未发送媒体请求；首次控制台编码显示不完整。设置PYTHONUTF8=1后用全新public02再跑同命令仍退出1，public02.log保留完整错误。系统DNS实查raw.githubusercontent.com=`198.18.0.14`、wpt.live=`198.18.0.28`，dns02.json；不改hosts/代理，不放宽禁止网段，不据离线73项称公网通过。
- 无生产改动，复用PR #34既有冻结包仅作入口验证：`Q tools/check_frozen_sources.py --exe ../api-errors/dist/study_backend/study_backend.exe`退出0，44冻结模块与本源码匹配；开发探针的原冻结入口实际启动、health、空下载列表、父管道关闭退出全部通过，frozen-source01.log/frozen-entry01.log。此处没有公网Range，当前head CI将重新构建后执行完整公网探针。

实现/离线相关自动化已完成，真实公网正向Range/重定向/新冻结恢复仍等待本PR限定CI验证，DL-01b保持IN_PROGRESS，不销父DL-01。失败现场和历史Commons缺强ETag/DNS证据保留；审查暂缓、人工取消、未合并/发行，不引入站点提取/转码/模型。

交付前7文件逐项git diff --no-index --check无诊断、72处本地Markdown目标存在，delivery-validation01.log，聚合退出0；全量Ruff和Question Schema漂移检查均退出0。未修改产品/UI，不另跑本地Flutter或重建重复冻结包，当前head CI继续全套后端/桌面/新冻结与公网步骤。

已创建[独立草稿PR #38](https://github.com/surface-user/StudyWorkbench/pull/38)，分支codex/public-download-range，base为#34最终8b29a27；初始实现提交9746c207411e0e8244bbf9c06701907c4405df77，7文件。PR限定公网步骤在PR事件执行，push轮不将跳过记为通过。补交本链接后的当前head完整CI、公网结果及主Agent核验结论以PR实时记录为准，未核实前保持IN_PROGRESS，不使用父head或旧实现head绿灯代替；未合并/发行。

### 初轮公网MIME拒绝及固定托管修正

初始9746c20的[PR CI43358807604](https://github.com/surface-user/StudyWorkbench/actions/runs/43358807604)，以及链接跟进bb402e5的[PR CI43359034632](https://github.com/surface-user/StudyWorkbench/actions/runs/43359034632)，均实际连通公开IPv4；HEAD长度554058、强ETag和`bytes=0-0`的206/Content-Range全部通过。随后普通任务GET被产品拒绝“下载响应不是所选媒体格式”，两轮公网步骤退出1，未达到真实暂停/续传。初版日志没有保留Content-Type具体值，因此不补造其具体MIME；这里只确认不在产品允许集合。两份完整desktop日志保留于artifacts/dl01b/ci-<run>-desktop.log；不是DNS失败，也不能据前置206称整项通过。

bb402e5的Python3.12完整CI为740通过，357.82秒；3.13完整pytest/R1–R5同样通过，桌面Flutter/Windows构建/44模块冻结/既有冻结探针均通过，但公网失败使整个PR轮不通过。原head与新head的结果分开，不能用push跳过公网的绿灯抵销。

只修正测试来源：将传输固定为`https://mdn.github.io/shared-assets/videos/flower.webm`。[MDN官方shared-assets说明](https://github.com/mdn/shared-assets/blob/main/README.md)明确指定此托管域；其videos目录元数据为同一554058字节/Git blob `5b8edf7d8384c057dfb13627073288cebfb54d74`，保留上述固定旧commit的CC0来源及对象身份约束。托管URL可能更新，任何不同字节继续失败；不改生产MIME、DNS、TLS、Range守卫。预检现在提前验证HEAD/206的MIME，选取日志增加Content-Type，错误MIME不读媒体正文；不增加自动选源或降级绕过。

新增3项MIME拒绝用例后，Q同专项target04退出0：76通过、18.24秒；P target31202退出0：76通过、20.90秒，XML/log保留；Ruff全量退出0。新固定域本地public03实际仍在resolve被拒，退出1，mdn.github.io=`198.18.0.70`，public03.log/dns03.json保留；未绕过本机网络，等待新head CI实测。

### WPT未知长度响应与探针修正

098ba18的[PR CI43360984198](https://github.com/surface-user/StudyWorkbench/actions/runs/43360984198)中，两组后端全部成功：Python3.12为743通过/424.04秒，3.13.17为743通过/449.20秒；R1–R5/JUnit及桌面公网之前各步骤通过。公网阶段实际从MDN取得video/webm、554058字节和强ETag，源码真实首块256KiB暂停后，新进程发出`Range: bytes=262144-`与相同If-Range，返回206、291914字节、`Content-Range: bytes 262144-554057/554058`；同attempt/前缀及固定Git对象校验后进入重定向阶段。

WPT同域302实际到达目标video/mp4，但该响应没有Content-Length，生产下载器合法报告`total=None`；开发观察器把未知总长度误判为固定样本变长，抛出`Public fixture size changed`，公网步骤退出1。不是产品下载失败的修复，不据已通过源码Range把未到达的跨域/冻结步骤记为通过。完整日志ci-43360984198-desktop.log保留。

只将开发观察器的总长条件改为None或固定长度，逐块实际字节仍不得超过固定3503/554058，落盘最终长度/Git对象/SHA256检查保持。增加未知Content-Length的真实transfer自编容器成功与多1字节拒绝/保留文件两例；未改生产或降低已有断言。Q专项target05退出0：78通过/37.57秒；P target31203退出0：78通过/41.70秒，XML/log保留；两轮并发运行，Ruff全量退出0。新head继续完整CI与真实公网验证，整体保持IN_PROGRESS。

## 2026-11-14：DL-03a格式/轨道与持久队列交接设计

主Agent批准在B站真实预览局部受阻后先推进独立设计，不等待整个DL-02或三站完成。基线为已由主Agent接受的[PR#53](https://github.com/surface-user/StudyWorkbench/pull/53)最终b09da16b9ea23f4fcb81eb016f9602d84afa451c/tree c2747215a6ae9187b28706234b70662190f54252。独立media-track-contracts副本逐497个Git blob按SHA1(blob长度+原字节)核对后复制，与根旧checkout、#52和其他任务隔离；原报告全文作前缀保留。

完整阅读本基线AGENTS、requirements、architecture、question-content-spec、task；补读现行学习/站点/备份契约、API/模型下载部分及db.MediaDownloadJob、media_downloads/worker、backup_store、backup_archive、recovery_storage和dev证据规则。代码当前仍只有单文件下载，source_url/progress/result等原字段无逻辑来源快照；backup_store.check_references对ready下载用progress的partial_sha256/received校验单文件并核节点关系。不能把拟议字段写成已有API/表，或据表自动枚举称分轨恢复已覆盖。

### #52局部阻塞与保留证据

独立[PR#52](https://github.com/surface-user/StudyWorkbench/pull/52)未纳本设计源码。d17cd3e的[CI43576361155](https://github.com/surface-user/StudyWorkbench/actions/runs/43576361155)记录源码/冻结generic HTTP非200，未取具体阶段，原ZIP795字节/SHA256 19638cd3f662e4116dcba964a8f5d611f2bd952e8f349df6d8cc7d82f06616be保留；be31699的[CI43578909355](https://github.com/surface-user/StudyWorkbench/actions/runs/43578909355)取得源码/冻结view HTTP412，875字节ZIP/SHA256 d83b3e8bdeeefcfe8e42719daa3e225eb33a0c0b02dcffa827881e1a2d4a25eb保留；固定源对照后改成v2正常公开页面起点，b293449f137284d5b01823c3a704ffff6d2dfc37的[CI43581781896](https://github.com/surface-user/StudyWorkbench/actions/runs/43581781896)源码/冻结首个page请求仍HTTP412、result=null，未取得HTML或请求nav/playurl。

v2两后端各1098、Flutter211、Windows/COM/47模块冻结及既有离线回归成功，不能抵销公网步骤失败。v2 [artifact14109580343](https://github.com/surface-user/StudyWorkbench/actions/runs/43581781896/artifacts/14109580343)实际下载/解包核两份JSON均bilibili-preview-v2/page412，877字节ZIP SHA256 520fcfb4ce30b638f937c9677dc267b183a7e35264f8cd5171d2a0286aefa26b；三份原ZIP分别在bili-preview-current忽略的artifacts/dl02b/ci-public.zip、ci-http-diagnostic.zip、ci-v2-page.zip。主Agent已要求DL-02b1局部BLOCKED，不重复公开请求/换UA、cookies、入口或降门槛，不推断登录或具体权限原因。本次4文档设计CI即使通过，也不是#52公网或三站功能通过。

### 采纳范围与拆分

仅修改四个文档：学习契约新增规划交接、dependencies明确实际二进制门槛、task新增DL-03a/b/c及局部阻塞、本原报告记过程。没有新增API/表/Alembic迁移/原生程序/测试或锁文件，也没有下载FFmpeg、采纳系统PATH程序或模型/凭据。候选确认下载与元数据预览明确分离；DURL单文件、最多2轨音视频DASH、多段/HLS规划边界分开，声明容器/codec不当作实际探测。

source_snapshot明确严格版本/站点联合、字段白名单、16KiB及B站专有aid/bvid/cid，不透传任意JSON或硬塞其他站点；它与原确认一起不可变，不藏progress。每attempt/显式运行的解析记录只持久安全逻辑身份、URL指纹/validators及必要hash，最多2轨/每条8KiB；临时签名URL和认证信息仅worker内存，不入库/备份/日志。质量/逻辑身份改变要新预览确认/新Job；仅临时URL轮换可显式restart新attempt，首批不承诺跨URL透明续传，即使ETag相同也不冒充同一资源。

共用同Job每次显式运行的10次实际请求/3跳、总15分钟和512MiB网络响应体/轨道合计预算；元数据2MiB/8MiB子限额及原DNS/TLS保持，输出另512MiB，统一预留输入+输出+16MiB，不能逐轨重置。固定公共header配方按用途/目标重验，不接任意字典/cookies。原生探测/合流只本地固定路径/协议/demux/参数，实际build须无网络协议、Job/EOF/取消全树，先锁二进制才启用。

最终输出校验/去重及发布复用原MediaEntry/节点/Job，须补文件与SQL非跨介质原子的收据/崩溃/幂等对账。新版备份须用最终输出凭据而非把输入进度假装输出大小，包含来源/运行记录、全部attempt轨道、完整性与容量语义；旧库、旧直链收据、原件和失败字节保留，恢复不恢复临时URL/候选/授权。DL-03b实际组件选择和DL-03c本地探测/合流分开，不依赖完整站点提取；HLS/多段/转码及真实端到端继续，不据设计登记实现。

只读查阅FFmpeg官方[许可](https://ffmpeg.org/legal.html)、[下载](https://ffmpeg.org/download.html)、[协议](https://ffmpeg.org/ffmpeg-protocols.html)和[ffprobe](https://ffmpeg.org/ffprobe.html)文档，未选版本/供应方或下载二进制。记录其仅供源码/第三方Windows构建的区别和协议默认/裁剪事实，作为后续实际build flags及完整传递许可要求的来源，不冒充具体产品构建已核验。未放宽既有来源/许可/漏洞/签名门槛。

### 本轮文档验证与退出

基线复制由Node原生fs读写与crypto.createHash('sha1')逐497文件验证，成功；未调用根git checkout/add/reset，也未修改根旧checkout。首次插入补丁因精确锚点少“集合”二字匹配失败、未部分应用；核实际行后重试成功，不涉及业务测试失败或断言变化。专项文档范围/空白/本地引用/锚点/原报告前缀/旧任务与两锁保持检查、Question Schema漂移及独立PR/current-head CI另记。业务代码完全不变，不为文档切片重复本机构建或业务测试；CI仍执行基线完整自动化。审查按用户要求暂缓，人工取消，未合并或发行；DL-03a在当前head CI与主Agent核验前不记DONE。

最终文档检查在独立media-track-contracts目录运行 `../starlette-fix/.local/starlette-q-isolated/Scripts/python.exe .local/validate_docs.py` 退出0：497基线blob重新匹配、仅指定4文档变化/493不变，逐4文件 `git -c core.autocrlf=false diff --no-index --check` 无诊断（有差异退出1但无空白错误，聚合0），96本地Markdown目标/10锚点全部存在，65种旧任务ID/原报告完整字节前缀及两锁保持。Python3.13.17同一独立IQ环境、PYTHONPATH=backend、PYTHONDONTWRITEBYTECODE=1运行 `-X utf8 tools/export_question_schema.py --check` 退出0，Question schemas are current。检查脚本、摘要与日志仅放.local/artifacts，未把测试profile或原件入Git；此次没有新增可执行功能，未另造镜像实现的测试。DL-03a本地设计/文档自动化完成，调度REVIEW；当前head CI继续全量后端/桌面/新冻结，未执行或跳过的公网项不记通过，#52三次失败继续局部BLOCKED。


## 2026-11-14 DL-03b1：官方FFmpeg源码认证与安全准备（有限实现交付）

主Agent已有限接受DL-03a [PR#57](https://github.com/surface-user/StudyWorkbench/pull/57)最终747c0bf907d6aad8fa64b730d9112d04b0ce9026、tree d042ccfa563201468bf143b8414de623074006a6、CI43584717946三job成功；它只是共同设计。此次在全新ffmpeg-component副本逐497原blob核对，未碰根旧checkout或#52/#57旧head。DL-02b1仍是普通公开页HTTP412的局部BLOCKED，三份失败不清除。本轮b1不等待三站公网，先交可审计的认证输入/离线安全准备；b2真实native组件与CRT闭包继续，c产品源/冻结执行尚未实现。

### 输入、认证与许可范围

官方[download](https://ffmpeg.org/download.html)/[release index](https://ffmpeg.org/releases/)实际稳定9.0.2（2026-09-18），未盲升或采用PATH二进制。固定tar 12040788字节/SHA256 8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e；asc 520字节/SHA256 d617fd94ea354dadd2a8bb16243d37c44e1e9729b06b6ad58fe30bfb0fa943f2；官方公钥1709字节/SHA256 397b3becedcd5a98769967ff1ff8501ddc89f8368b8f766e4701377d7dbaabe5。正常HTTPS固定URL/禁止redirect、32MiB上限抓取仅用于开发输入获取，不是产品下载器，也没有下载媒体。原包/asc/key只在忽略的.local/upstream，未改缓存/安装。

GnuPG2.4.9在项目内全新短homedir .pgp03核官方固定指纹FCF986EA15E6E293A5644F10B4322F04D67658D8。共用参数：`--no-options --homedir <项目POSIX短路径> --batch --no-autostart --no-auto-key-retrieve --no-auto-check-trustdb --no-default-keyring --keyring <该homedir>/release-key.gpg --trust-model always --status-fd 1`；在upstream cwd依次`--dearmor --output <该keyring> ffmpeg-devel.asc`、`--with-colons --fingerprint`、`--verify ffmpeg-9.0.2.tar.xz.asc ffmpeg-9.0.2.tar.xz`，退出均0，严格仅一个VALIDSIG且完整40hex匹配；GOODSIG与unknown trust警告保留。不读写个人keyring、不启动agent、不声称web-of-trust建立；信任来源是官方固定指纹。

n9.0.2 tag object ce8f11b9fac4cd7ccfb41ca7c01bc17f5cda8cc3指向commit946fcce07b6dcd0331c8cc609192aeff5e1924f8；GitHub verified tag元数据与tar RSA认证各记范围。实际从认证tar展开的configure/fftools/ffmpeg.c/fftools/ffprobe.c/LICENSE.md与固定Git四blob逐匹配（工具常量有完整SHA），只证明这些关联，未捏造全tar等同Git全树。官方[许可](https://ffmpeg.org/legal.html)明确主体LGPL与可选GPL；原tar完整保留所有COPYING/LICENSE及源码，不把整个原包称单一LGPL，不将CLI/共享库链接或对应源码义务当法律通过。官方[安全页](https://ffmpeg.org/security.html)作维护来源，不是最终二进制/所有内嵌库漏洞认证。

### b1实施与实际自动化

新增开发工具`tools/prepare_ffmpeg_component.py`和专项`backend/tests/test_ffmpeg_component.py`，没有产品API、表迁移、UI、运行依赖、任意命令入口或二进制。工具先固定整个tar大小/hash再解析，严格拒绝链接/reparse、特殊成员/sparse、路径穿越/设备名/大小写/父子冲突，最多20000成员、单项8MiB、总展开256MiB。目标必须全新，失败不删原件或部分。每个原文件记录size/SHA256/Git blob；版本化source-lock的derived digest在payload外，preimage仅UTF-8/sort_keys/compact/非NaN payload，自身hash不参与。verify从固定原tar重建期望，再校验实际完整文件集合和所有原bytes，不能通过篡改后自重算清单逃过。

工具本身只离线展开/核证，未调用GPG/configure/外部程序；固定hash来源是上面的真实PGP核证，不声称每次工具运行都重新验PGP。手工开发构建探针只能在此前认证成功后启动。实际prepare-source/verify-source各退出0，10399原文件，canonical source snapshot SHA256 7a65ea9dcb64a778fe393c2582628c4ab339092971e0916422c63dd44833d81c。源目录保持未构建，构建尝试全部out-of-tree。

命令均在独立ffmpeg-component根：IQ=../starlette-fix/.local/starlette-q-isolated/Scripts/python.exe（3.13.17），IP=对应starlette-p-isolated（3.12.7），既有锁环境未改。

- IQ `-X utf8 tools/prepare_ffmpeg_component.py prepare-source --package .local/upstream/ffmpeg-9.0.2.tar.xz --directory .local/upstream/source`，退出0；随后同参数verify-source退出0，原记录分别artifacts/dl03b/source-prepare01.txt、source-verify01.txt。
- IQ `-X utf8 -m pytest -q backend/tests/test_ffmpeg_component.py --basetemp=.local/ffmpeg-source-q03 --junitxml=artifacts/dl03b/source-q03.xml`，退出0，26通过/1skip；IP对应p01目录/XML同命令退出0，26通过/1skip。覆盖改原包先拒/安全展开、路径/链接/特殊文件/预算/原文件缺失、额外/变更/自重签伪造、重复JSON/NaN/自包含hash等。
- skip仅因本机用户无法创建文件symlink的WinError1314，不记该用例通过；真实Windows目录junction创建成功，沿根目录reparse拒绝真实通过。文件symlink用例仍保留供具备权限环境执行，不调系统Developer Mode/权限。最初q01为25通过/1失败（fixture权限），q02为25通过/1skip/1失败（PowerShell位置参数fixture写错），全部XML/日志保留；仅修fixture引用/针对明确1314 skip，产品拒绝断言没有降低。
- 既有release-venv `-m ruff check tools/prepare_ffmpeg_component.py backend/tests/test_ffmpeg_component.py`，退出0。最终范围/文档/Question Schema与当前head全CI另记，不把本地专项当全产品验证。

### 真实构建失败与后续

只读确认Git-Bash5.2.37、GNUmake4.4.1、VS2022 17.14/MSVC14.44.35207（cl19.44.35219）、现有SDK与MinGW GCC13.2.0。未安装系统工具/语言包/NASM/额外编码器。受限执行MSYS命名对象NtCreateDirectoryObject先失败，原生同一已有工具复验成功；原失败保留，不假称工具缺失。PGP首轮D:/homedir误作相对路径失败、次轮POSIX长homedir agent socket路径失败，随后新短homedir显式公钥/no-agent模式才成功，均保留。

MSVC configure-msvc-01退出1：实际cl中文banner前缀，官方probe_cc固定grep ^Microsoft即便VSLANG=1033也不能匹配（本机只有2052资源），误用-o产生LNK1136，真实编译链接失败未绕过。原配置/错误保留，未改官方源。MinGW新独立01/02退出1分别为MSYS /tmp不可建、继承个人TEMP不可写；第03仅把TEMP/TMP和MSYS TMPDIR定到项目新目录、child环境allowlist后configure退出0，但实际生成大量decoder/filter/bsf和file以外本地协议，且既有MinGW sed有表达式警告，不符合最小能力；未执行make。没有产出/采用binary，尚未核CRT原许可/精确来源/对应源码。原config.log可能含继承环境，只留忽略artifacts/.local原件，不上传完整内容。

主Agent同意b1先有限独立交付，b2继续调查MSVC一个banner识别点的派生兼容补丁。任何派生源码须新目录、原configure/补丁/结果hash及其余原bytes证明，不伪造compiler结果、不改C实现/实际编译链接检测，不动原件/缓存/上游。真实b2仍须实际禁GPL/nonfree/version3/autodetect/network/x86asm/外部库、最小demux/mux/parser/codec、实际-protocols/PE/DLL/CRT/许可与对应源码/漏洞/供源核证，未闭合不进产品payload。

即便后续编译无HTTP等网络协议，file可触达UNC，不能称OS网络隔离；c仍要固定受管本地路径、拒UNC/设备/外链/dref/外部引用、任意参数，Job/EOF/取消/预算及源冻结执行。组件开发探针不替代产品证明；MP4/WebM/M4A stream-copy/remux/probe、DASH/三站真实下载/HLS/转码均未因b1完成。证据只选[源码准备摘要](evidence/ffmpeg-source-preparation.json)的固定输入、PGP白名单状态、原文件hash与命令结果；理由是支持认证/安全准备的有限结论，未塞tar/二进制/完整日志或环境。审查按用户要求暂缓，人工按11-06取消，未合并/发行；b1等待PR/current CI与主Agent核验，不提前DONE。

最终六文件交付检查：IQ `-X utf8 .local/validate_delivery.py` 退出0，497基线blob逐核，仅3原文档修改/494原文件不变，加3新文件；91本地引用/9锚点、68种原任务ID、原报告完整前缀、两锁/运行代码保持；逐文件no-index diff --check无空白错误。相同IQ环境Question Schema `--check`退出0。最终代码专项q04退出0（26通过/1权限skip），Ruff再核退出0；未以重复运行抹去q01/q02失败。b1进入REVIEW，PR和当前head CI仍待交付，b2/c不因此完成。

首次GitHub create_tree被自动审批拒绝，原因为project source/reports/evidence上传的精确payload与目标未核定；首次未上传/未建commit、分支或PR。随后只读核根origin为https://github.com/surface-user/StudyWorkbench.git、已接受#57同公开repo/精确base；六文件仅3既有文档+开发工具/测试/精选摘要，无上游tar/源码包、原config.log/环境、实际PGP key块、私钥/token/个人DB或媒体。PGP公开签名键只记录公开指纹/输入hash，不属私钥。逐文件SHA256/Gitblob/字节数、494不变与报告前缀已核；按用户每小项PR和主Agentb1授权，原连接器同一create_tree在证据补全后获自动审批通过（tree4f9f9f543e5d606abd603d25993150c862c41493），未换通道或规避限制。该树不是已交PR，当前CI另核。
