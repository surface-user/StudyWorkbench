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
