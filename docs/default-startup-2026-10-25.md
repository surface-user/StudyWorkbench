# 默认位置启动、D盘拒写与工程体积

用户本轮要求：解释约7GB占用；首次进入不要先选择数据库目录；解决选择D盘后创建`.study.lock`被拒绝。实施前重读开发约束/需求/架构/协议/任务，按ponytail技能限制改动范围；无子Agent，无提交/推送/发布，无系统ACL或权限提升修改。

## 体积实测与清理

初始逻辑文件总量7,904,160,063字节，即7.361GiB，非单个程序大小。扫描不跟随重解析目录，结果见`evidence/default-startup-20261025/workspace-size.json`。

| 初始目录 | 大小 | 主要内容 |
|---|---:|---|
| apps/desktop | 3.375GiB | Flutter编译缓存/测试kernel、原生插件中间产物、Debug/Release、SDK临时文件；例如flutter_windows.dll.pdb约240MiB |
| .local | 2.258GiB | 发行工具、独立Python环境、解析器比较环境、测试/诊断现场；不全是可随意删除的缓存 |
| dist | 1.292GiB | 多套历史开发包、冻结后端、旧安装包（含约205MiB的WebView2离线安装器） |
| .venv | 0.294GiB | Python开发环境 |
| 其余 | 约0.142GiB | 冻结构建、研究参考、源码/文档/测试/版本历史等 |

在全部测试/构建结束、完整开发包复制及依赖检查成功后，仅删除两处已验证的自动生成缓存：`apps/desktop/.dart_tool/flutter_build`（1,838,887,050字节）与`apps/desktop/build/test_cache/build`（965,489,000字节），合计2.612GiB。删除前核对绝对路径位于当前工作空间、不是重解析点、目录内无数据库；使用同一PowerShell的Remove-Item -LiteralPath，不通过跨shell拼接。日志见cache-cleanup.json。保留package_config、可运行产物、源码、个人数据、失败日志和测试数据现场。缓存可在后续编译时再生成。

本轮额外测试/构建和新增固定开发目录后，总量实测5,744,411,807字节（5.350GiB），不是简单用初始总量减缓存；见workspace-size-after.json。当前完整开发包161,444,089字节（154.0MiB），不含个人数据库。以后开发交付使用固定`dist/StudyWorkbench-current`，避免每次复制一套新的带日期目录。历史包尚未清理，未擅自删除旧数据/失败对照。

## 启动修复

只读核查时`D:\computer_work\data\.study.lock`根本不存在，目录也为空；所以是创建锁文件被拒绝，不是陈旧锁占用。此前当前工具进程已观察到Low Mandatory Level，D盘和LocalAppData目录对该运行环境拒写。上次修复仅解除配置目录的强制依赖，不能解除D盘数据目录本身的权限限制。

本轮按ADR0006实现Windows Known Folder定位：普通进程默认LocalAppData/StudyWorkbench/data，低完整性进程默认LocalAppDataLow/StudyWorkbench/data。启动配置统一定位LocalAppDataLow/StudyWorkbench/settings.json，已有保存位置优先，兼容此前LocalAppData设置；同profile已有m0/study.db时继续使用，空m0目录不冒充旧库。

首次直接启动已保存或默认目录，取消先弹位置选择框。设置保留迁移；错误页提供明确的“使用默认数据位置”和手动选择入口，只有用户主动选择时才改用其他目录。数据锁仍强制取得，不能通过忽略锁/自动切空库掩盖拒写；Python拒写提示增加目录和原数据保留说明。未创建或删除D盘锁文件，未修改D盘数据或ACL。

真实Windows流程不设置STUDY_DATA_DIR；最终不设置STUDY_ROOT，使用已核对SHA256的冻结后端，启动StudyApp、验证没有“选择学习数据位置”、进入工作台、健康检查、默认位置study.db和.study.lock存在且无配置警告，随后EOF关闭。没有向默认库追加测试作答。当前应用继承打包身份时Windows会映射到`AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/LocalLow/StudyWorkbench/data`；这是实际日志路径，不宣称所有启动环境均使用此映射。普通Explorer/Medium进程分支和用户人工验收仍需分别验证。

## 命令与退出码

证据目录`docs/evidence/default-startup-20261025/`。Python使用PYTHONUTF8=1、TEMP/TMP=.local/tmp；Flutter在apps/desktop，通过既有SDK dart.exe执行flutter_tools.snapshot，未更换SDK或运行依赖。

| 命令 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/default-startup-full312 --junitxml=docs/evidence/default-startup-20261025/backend312.xml` | 0，127通过，backend312.log |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests/test_data_root.py backend/tests/test_startup_settings.py -q --basetemp=.local/default-startup-target313 --junitxml=docs/evidence/default-startup-20261025/backend313-target.xml` | 0，21通过，backend313-target.log；这是3.13定向回归，不是全量 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 0，ruff-final.log |
| `dart format lib/backend.dart lib/main.dart lib/startup_failure.dart test/storage_paths_test.dart integration_test/default_startup_test.dart`及最终相关文件格式化；`flutter analyze --no-pub` | 0，format.log/format-final.log、analyze-final.log，无静态问题 |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/default-startup-dart-final` | 0，54通过，flutter-final.log；默认路径/旧m0/共享设置/无效路径/既有业务 |
| `flutter test integration_test/default_startup_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench` | 0，1通过，windows-default-native.log；真实Windows默认位置、源码后端，无数据位置覆盖 |
| `& ./packaging/windows/build-backend.ps1` | 0，frozen-build.log，87.7秒 |
| 复制冻结后端到Debug/backend并核对SHA256，再运行`flutter test integration_test/default_startup_test.dart -d windows --no-pub` | 两次0，各1通过，windows-default-frozen-native.log、windows-default-final.log；最终共享配置规则使用后者，无源码/数据目录覆盖 |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | 0，frozen-lifecycle.log；锁/鉴权、作答/导入/逐题MD/媒体、重启/强杀/两次迁移、EOF/RST等既有断言继续通过 |
| `flutter build windows --release --no-pub` | 0，windows-release.log，49.4秒；既有插件CMake开发警告保留 |
| `tools/release_inventory.py --stage dist/StudyWorkbench-current`及`tools/check_release.py dist/StudyWorkbench-current` | 首次依赖检查1，release-check.log，发现本地msvcp140.dll缺失；未削弱断言，按既有发行流程补齐微软签名Valid的14.44.35211.0 CRT并重新生成清单，最终0，1284文件哈希/无DB/PE导入检查通过，inventory-final.log、release-check-final.log、crt-signatures.log |
| `git diff --check` | 0，diff-check.log |

构建使用项目.local/bin和.local/nuget-scratch。温和CloseMainWindow关闭了停留在失败页的已知旧版窗口，没有强杀其他程序。新包入口exe、AOT app.so、backend exe与构建输出哈希一致（stage-check.log）。清理缓存发生在这些验证之后，不改变开发包文件。

## 交付与验收边界

入口`dist/StudyWorkbench-current/study_workbench.exe`，必须保留同目录backend/data/DLL/licenses。首次可直接启动；若保留的旧配置仍指向不可写D盘，点击错误页“使用默认数据位置”，原目录不变。

本批默认启动/数据锁修复已实现，并有真实Windows+冻结后端自动化证据。Release构建/依赖闭包通过不等于普通Explorer启动的人工验收或干净机认证；未编译新setup、未执行安装/卸载，M0历史默认路径HTTP500及完整阶段验收不据此清除。M2备份恢复、复杂文档识别和M4下载队列仍按原任务保留。
