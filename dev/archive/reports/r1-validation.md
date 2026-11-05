# R1 交付与验证记录（2026-10-25起）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

实现完成，自动化通过，代码审查完成；人工与阶段验收待验。用户本轮仅授权R1，R2–R6未展开。开工完整阅读AGENTS及指定七份文档，检查当前代码/未提交内容；保留当前`codex/m1-workspaces-tabs`上的前序改动，没有提交、推送、发布或替换`dist/StudyWorkbench-current`。个人学习库未读取、未迁移。没有创建子Agent。

## 实现与审查结论

- 0007追加逻辑资源树与复制任务，复合FK隔离父子/原件/媒体，互斥载荷与兄弟规范名称唯一。旧0001–0006迁移未改；适配旧原件/媒体时只生成新目录身份，不改原ID、路径、hash或学习行。具体DDL与兼容决策见[r1-design.md](r1-design.md)、[ADR0007](../../../docs/adr/0007-resource-explorer.md)。
- 左侧资源树支持分页展开、文件夹/链接创建、详情、改名/移动；同资源移动保留ID。统一添加文件、文件夹、本地媒体、HTTPS链接；媒体复用容器校验/MediaEntry与原播放器。导入预览、学习计划及媒体总览为辅助工具。
- Python流式受管复制、保留层级，不解析题目。Windows名称/大小写、同空间父级/无环、路径/重解析点/映射网络盘、数量/深度/大小预算、取消、来源变化和失败结果都有针对性回归。映射网络盘在首次lstat前拒绝。逐文件fsync后登记；中断/取消/登记失败保留节点、字节及复制路径收据，重启标记interrupted而不自动重读来源。
- 新库默认“我的学习空间”，新空间为空v1布局，从资源添加开始。仅数据库原先不存在时初始化默认名称/布局；现有名称、旧标签/关闭历史/草稿不重置。标签协议与PageHost保持，未实施资源标签或查看器。
- 审查覆盖目录路由及调用方、原件读取、媒体校验调用方、前端状态/失败恢复、迁移/备份与旧测试夹具。修复旧响应覆盖新树的竞态、详情窗口关闭动画期间过早释放控制器、旧原件损坏时错误复用。没有削弱历史数据保留断言，没有新增依赖。

## 实际命令、退出码与证据

工作目录为仓库根，Flutter命令在`apps/desktop`执行。日志目录为`docs/evidence/r1-20261025`。后端运行前设置`TEMP`/`TMP`为项目`.local/tmp`，`PYTHONUTF8=1`。Python 3.12.7为现有Anaconda开发环境；冻结仅用独立CPython 3.13.17。所有pytest basetemp和真实进程数据均为新生成的`.local/r1-*`隔离目录。

Flutter使用已有快照（以下以`flutter-snapshot`缩写完整前缀）：

```powershell
& 'D:\computer_work\Tools_work\flutter\bin\cache\dart-sdk\bin\dart.exe' 'D:\computer_work\Tools_work\flutter\bin\cache\flutter_tools.snapshot' <参数>
```

| 实际命令 | 退出码 / 结果与日志 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q --basetemp=.local/r1-full312-final04 --junitxml=docs/evidence/r1-20261025/backend312-final04.xml` | 0，154项，无跳过；backend312-final04.log |
| `.local/release-venv/Scripts/python.exe -m pytest -q --basetemp=.local/r1-full313-final04 --junitxml=docs/evidence/r1-20261025/backend313-final04.xml` | 0，154项，无跳过；backend313-final04.log |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 0；ruff-final04.log |
| `flutter-snapshot test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r1-flutter-pipe-final` | 0，66项，含真实后端管道；flutter-full-final.log |
| `dart.exe analyze lib test integration_test` | 0，No issues found；analyze-final02.log |
| `dart.exe format lib test integration_test` | 0，47文件无变化；format-final03.log；最终另执行不写入格式检查 |
| `. ../../tools/prepare-windows.ps1`，将项目`.local/bin`加入本进程PATH；`flutter-snapshot test integration_test/resource_explorer_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r1-native-final --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/r1-20261025` | 0，真实Windows流程1项；windows-native-final.log、native-results.json和运行截图 |
| 同上Windows准备；`flutter-snapshot build windows --release --no-pub` | 0；windows-release.log。普通Release入口，未复制到旧开发包 |
| 独立CPython PyInstaller初建，详见下方完整参数；再执行`.local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath .local/r1-frozen/dist --workpath .local/r1-frozen/build .local/r1-frozen/study_backend.spec` | 0；frozen-build-02.log、frozen-build-final02.log。新冻结目录，不覆盖原dist |
| `.venv/Scripts/python.exe tools/check_resource_explorer.py --test-root .local/r1-real-source-final04` | 0；source-explorer-final04.log，真实loopback复制/去重身份/改名/作答/草稿/重启 |
| `.local/release-venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/r1-frozen/dist/study_backend/study_backend.exe --test-root .local/r1-real-frozen-final03` | 0；frozen-explorer-final03.log，同一专项在无源码cwd、移除Python环境及开发PATH后通过 |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe .local/r1-frozen/dist/study_backend/study_backend.exe` | 0；frozen-lifecycle-final02.log，EOF/异常重启、数据锁、作答、旧导入/拆题/媒体及两次迁移回归 |
| `git -c core.safecrlf=false diff --check`；文档本地链接及新增源码/证据检查 | 最终0，见final-review-checks.json、diff-check-final.log；首次EOF多空行失败另留diff-check-first.log |

PyInstaller首次完整参数（PowerShell在仓库根展开`$PWD`，仅路径变量）：

```powershell
& .local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --onedir --name study_backend --distpath .local/r1-frozen/dist --workpath .local/r1-frozen/build --specpath .local/r1-frozen --paths "$PWD/backend" --collect-submodules study_workbench --copy-metadata docling-slim --copy-metadata docling-core --copy-metadata doclang --copy-metadata pypdfium2 --copy-metadata python-docx --copy-metadata pylatexenc --add-data "$PWD/backend/migrations;migrations" --add-data "$PWD/backend/study_workbench/player.html;study_workbench" --add-data "$PWD/backend/study_workbench/library_player.html;study_workbench" tools/frozen_entry.py
```

隔离0001–0006升级均保留原列值；0006夹具含作答/追加评分/笔记/候选草稿/MD/计划/归档空间及任意旧layout原文，比较全部旧表完整行。备份完整性/还原再升级、0007 DDL后注入失败回滚、原件hash、FK/完整性、重复启动均通过。没有用当前题目内容补造历史快照。

Windows运行截图：[资源树与空工作区](../../../artifacts/legacy-evidence/r1-20261025/resource-explorer-windows.png)。实际验证复制4个节点、树展开、详情hash状态、经UI添加网页、原文保持及v1布局保持。原生选择器方法有组件替身回归及Windows编译证据；没有把选择器替身称为人工系统对话框验收。

## 失败保留与修复

- explorer-01：17通过/2失败，目录联接创建被受限环境拒绝；0006夹具漏建演示题，启动种子导致行值比较差异。补齐真实旧库夹具后，在隔离目录授权创建联接验证，explorer-02的19项、后续explorer-03的21项通过。
- backend312-01：144通过/2失败，旧备份文件名/head断言写死0006；更新为新精确head 0007，旧行保留断言不变。final02双环境各152通过/1失败，归档测试仍写死旧新库名；更新为“我的学习空间”，并保留最后空间禁止归档的准确确认名断言。final03双环境各153通过；最终审查补映射网络盘拒绝与读取前断言，final04双环境各154通过。
- flutter-targeted-01：详情对话框退场时控制器提前dispose；改为表单自身管理输入。02为测试点击屏外加载按钮，改为实际滚动到可命中位置。后续全量通过。analyze-01/final首轮包含格式提示、旧测试局部变量重名及新测试缺Completer导入，最终全部清零。
- frozen-build.log：1，spec放入隔离目录后，相对add-data被解释到spec目录；改绝对源路径，02/final为0。没有放宽冻结检查。
- source-explorer.log/source-explorer-final.log及frozen-explorer-final.log：检查脚本先后错误比较未规范化的layout请求、误用attempt_id；改为比较PUT返回的完整持久化布局及既有id字段，保留精确重启断言，最终source-final03/frozen-final02为0。
- Windows构建有既有插件CMP0175警告；PyInstaller有未采用数据库驱动等可选hidden import警告。未修改上游库或缓存，不把构建警告隐藏为依赖验证通过。pytest保留既有Starlette/anyio弃用警告。

## 限制与下一步

人工/阶段仍待验；历史M0默认启动、原生焦点/DPI、干净机、安装升级/卸载等遗留未清除。没有运行个人默认数据位置测试，也没有替换/发布开发包或installer；Flutter Release构建、源码后端Windows交互、冻结后端CLI是分开的证据，未验收新的组合安装包。

R1只做受管逻辑树及复制；不附加任意外部目录、不监听/原地修改、不做资源标签或文件查看器、不实现下载。点击文件当前打开详情/组织窗口，链接保存在树中，后续具体查看器/独立资源标签留R2/R3。旧演示页仅兼容入口。

每任务1000节点/32层/1GiB，普通文件128MiB、MP4/WebM/M4A 512MiB；大原件可保存不代表旧8MiB/20页解析器已放宽。相同字节保留独立逻辑ID，可复用原件索引；复制产生的额外重复/失败字节保留且不自动清理，会增加磁盘占用。媒体仅沿用已支持容器，未扩大编码矩阵。取消不能中断操作系统阻塞I/O或瞬间终止校验读取。

文件/SQLite无跨介质原子性；失败与中断收据能追溯保留副本，重新选择来源是新任务，不自动恢复半文件为完整资源。任务/树均分页，兼容工具产生的未登记资源在根级刷新时每类至多适配200条；大积压需继续刷新。最终审查未遗留阻断R1已授权范围的问题。下一步保留R1人工/阶段待验，R2–R6等待用户另行安排。
