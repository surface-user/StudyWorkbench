# LW-05 完整学习库备份恢复

2026-11-04，接续持续开发授权。按AGENTS及LW-00契约推进，无子Agent/新依赖；本批仅本地，不要求提交/新PR，人工/阶段待验，不推送/合并/发行。当前export/relocate不是完整恢复，此任务保持未完成。

## 设计与拆分

1. 先实现只读ZIP/manifest/payload校验：严格版本、预算、重复JSON键、Windows路径/名称/大小写与规范化碰撞、符号链接/重解析点、加密/未知压缩、未列文件、大小及逐字节SHA256。无解压、激活、数据库执行或配置修改。
2. 后续离线备份：普通UI列出含归档的全部空间及未加密隐私范围，协调全部草稿/布局，停止Office/导入并退出后端；独占数据锁下SQLite backup、一致性/表行摘要及全文件manifest。精确排除workspaces/{id}/resource/{tab_id}、web/{tab_id}、player/{tab_id}和link-web运行profile，以及根锁/WAL，不凭后缀排除附件。
3. 后续恢复：普通启动恢复入口选择包及新空目录，锁住目标及外部配置session；安全流式落唯一pending、逐块磁盘/取消/哈希检查、SQLite只读完整性/关系/表摘要、当前schema或保留包内旧库后迁移。所有确认资产、当前/失败工作字节、书签/关系、布局草稿和媒体状态核对后再激活配置；不覆盖旧库或已有目标，故障留现场。
4. 子进程通过现有parent-pipe取消机制，不把后台任务持有锁时的在线relocate当产品恢复。不新增HTTP任意路径接口；普通UI系统文件选择不开放给WebView或Agent。完整恢复实际执行、重启及窗口验收属于后续必需门槛。

初始先做第1步读取核心，随后继续实现离线快照、恢复和普通UI；各切片实绩追加如下，不把只读检查等同实际恢复或产品验收。原始产物artifacts/lw05-20261104/，同任务重试继续本报告。


## 实施与审查

基于HEAD29f23d3558740545a950a51ca04398f9420088fd及既有未提交树继续，无新schema（0014）、第三方运行依赖或Agent权限。backup_archive.py先预检ZIP/ZIP64中央目录实际条数与64MiB元数据预算，再验证严格JSON、NFC/Windows路径/重复与父子文件冲突、普通文件/已知压缩与ZIP64扩展、逐字节大小/SHA；只读检查不执行SQLite或激活。格式依据[PKWARE APPNOTE](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT)第4.3节及[Python zipfile](https://docs.python.org/3/library/zipfile.html)，未复制外部实现。

backup_store.py实现离线DataLock、SQLite backup合并WAL、typed JSONL表摘要、全文件/原件/工作副本/确认资产/派生PDF核对、磁盘/大小预算、源变更重验。新空目录恢复经唯一pending、只读SQLite integrity/FK/表摘要、旧库保留迁移及旧列行保持后独占提升，再核验才原子写外部配置；原库不改。失败保留现场，成功只清理本次独占创建并已验证提升的暂存副本，清理失败另报cleanup_pending。未知普通文件与旧备份保留，单值64MiB/不支持虚拟表明确限制。

UI设置和启动失败页均接入口；列全空间/归档及未加密范围，明确保留页面草稿、不提交作答，flush失败不停止服务；释放WebView并停服后调用固定参数离线进程，进度和协作取消走parent-pipe，不给网页/Agent业务桥或任意路径HTTP。子进程结果不明时先核对实际配置，防止重启原库覆盖已经激活的目录；Windows路径比较用目录身份，测试隔离配置可在整窗重启后保留恢复选择。

自审补强：发布/提升每块空间检查与取消、源库/包/文件变更、目标外部写入及xb防覆盖；未来schema/未知配置拒绝覆盖；工作副本外部冲突按原字节保留、不拿indexed hash覆盖。查历史M0源码`git show e9a8402:apps/desktop/lib/main.dart`确认根web-profile/player-profile，加入精确排除，连同当前workspace profile及根运行锁/WAL排除，不凭后缀删文件。全部为开发自审，非独立人工批准。

## 命令与验证

P=.venv/Scripts/python.exe，仓库根；Flutter在apps/desktop，D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F=D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot，入口D F --suppress-analytics。进程级TEMP/TMP=.local/tmp、NUGET_SCRATCH=.local/nuget-scratch，关闭Flutter/Dart分析上报；SDK缓存/Windows junction测试使用获准扩展权限。全部原始产物artifacts/lw05-20261104/，未整包晋升evidence。

| 实际命令 | 退出码/结果 | 产物 |
|---|---|---|
| P -m ruff check backend tools | 0 | ruff-final-15.log |
| P -m pytest backend/tests/test_backup_archive.py -q --basetemp=.local/lw05-archive-final-04 --junitxml=artifacts/lw05-20261104/archive-final-04.xml | 0，46通过，3.01秒 | archive-final-04.log/xml |
| P -m pytest backend/tests -q --basetemp=.local/lw05-backend-final-15 --junitxml=artifacts/lw05-20261104/backend-final-15.xml | 0，343通过，203.78秒 | backend-final-15.log/xml |
| P -m pytest backend/tests/test_backup_store.py -q --basetemp=.local/lw05-store-final-16 --junitxml=artifacts/lw05-20261104/store-final-16.xml | 0，16通过，26.53秒；全套后补M0旧profile排除再验 | store-final-16.log/xml |
| D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw05-flutter-full-15 | 0，136通过 | flutter-full-15.log |
| D F --suppress-analytics analyze --no-pub | 0，No issues found | analyze-15.log |
| D F --suppress-analytics build windows --release --no-pub | 0，60.9秒，含原生备份选择器 | windows-release-15.log |
| D F --suppress-analytics test --no-pub test/backup_dialog_test.dart test/backend_process_test.dart test/backend_learning_timeout_test.dart --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw05-flutter-process-11 | 0，11通过 | flutter-process-11.log |

后续LW-09追加隔离配置持久选择用例，Flutter全套137/分析/隔离Windows构建通过，详见[LW-09](../2026-11-04-lw09-integration/report.md)，不复制另一本流水账。学习位置解析/搜索请求可达文件工作预算，将前端超时匹配60秒；真实loopback延迟6秒测试证明不再被普通5秒期限过早中止。

后端实绩覆盖全空间/归档、原件/当前MD与草稿、书签修订关系、旧作答、不可变题目/附件、旧Office分页、媒体续播/倍速/字幕与旧cap失效、未知失败字节、0006→0014旧列保持、迁移备份、ZIP64/坏包/伪造表摘要/大小预算、真实junction、磁盘不足/配置拒写/取消/外部目标写入/ADS与设备名。Office使用FakeRuntime生成PDF、媒体元数据样本不是完整编码验收；UI6项及真实子进程支持普通控制流程，不能代替窗口/IME/DPI/断电/干净机。

中间失败原样保留：archive-01为43通过/1失败，ZIP64结束记录可在普通字段未溢出时仍出现，读取器已修；archive-02为44通过，增加head/未知扩展后46通过。store-06为1通过/9失败，样本复用演示题ID被防覆盖规则拒绝，改独立ID后store-07为10通过。扩展store-12/13分别12/15通过、各1失败，PNG fixture通用add默认MIME为octet-stream，与明确PNG附件契约不符；改准确样本MIME，保持原断言，store-14及末轮16通过。analyze-ui-09的13处花括号info按单文件dart fix修复，末轮分析0；旧warning（Starlette/anyio、CMake CMP0175）保留。

## 交付与下一步

本地实现、相关自动化及本批自审完成，任务保持待验收，M2-03/LW-05同一未完成验收项不删除。真实窗口、复杂真实库、断电/全故障矩阵、用户人工/阶段、安装/干净机/签名/许可审查仍待验；已有配置格式损坏或较新时拒绝覆盖，须先保留排查。默认profile历史M0故障未据隔离通过销项。未提交/推送/PR/合并/发行；LW-09仅新建配套测试包，不覆盖原dist或安装器，不冒充完整发行组合验收。

继续LW-09集成；用户使用电脑期间暂停所有Computer Use/前台交互，仅后台开发与自动化。完整窗口/用户验收与后续格式、下载、模型能力继续保留各自门槛。
