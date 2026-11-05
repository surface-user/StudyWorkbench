# M1 持续开发与 M0 回测（2026-10-24）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

最新补充：用户要求“先只做后台测试”后的修复与65项后端/19项无窗口组件结果，见 [后台续测](m1-background-2026-10-24.md)。最新配套产物为 background-fixed 目录；下方090800、58项及安装包哈希属于此前批次。后台续测包含冻结退出超时的失败证据，不以成功重跑抹去。

用户要求继续开发、测试，完成 M1 后回查 M0。本轮完成 M1 剩余主体实现和打包构建，发现并修复并发缺陷；**M1 阶段仍未验收通过**。实现、自动化、人工和阶段验收分别记录，不以自动化代替人工。

检出目录：`D:/computer_work/project/StudyWorkbench`；分支：`codex/m1-workspaces-tabs`。保留全部此前 M0/M1 未提交修改和失败现场；未提交、推送、发布、合并或创建子 Agent。设计见 [ADR 0004](../../../docs/adr/0004-data-root-and-lifecycle.md)，首批工作空间/标签证据见 [原 M1 报告](m1-validation.md)。

## 已实现

- 首次数据位置选择与 Windows 原生目录选择器；无效配置/启动失败可重新选择；默认检测已有 M0 数据。
- 设置迁移：保存页面、释放 WebView、停止后端、空目标/空间/路径/链接检查、SQLite 一致性备份、逻辑内容与外键检查、原件 SHA256、验证后切换配置、重启。失败保留旧目录/原配置和目标现场。
- OS 数据/配置锁、Windows 单实例 mutex、SQLite 写事务，避免两个请求创建同名空间或同时移除最后的空间。
- 后端正常 EOF 退出与异常退出提示；保存内存页面草稿后重启恢复；迁移子进程检查父进程管道，配置切换前取消。
- 标签鼠标拖动排序并持久化；先前的创建、关闭、重开、切换与草稿恢复保留。
- 独立 CPython 冻结、UTF-8 管道、配套 Release 目录、setup 编译；自选安装路径、WebView2 检测/缺失时离线安装入口、VC++ app-local DLL。原生页面缺少 Runtime 时可重试或打开官方安装页。
- 可复现工具准备脚本、签名/哈希验证、Python/Dart/Flutter/native 许可收集、文件清单与 PE 导入检查。构建环境依赖列表不是完整 SPDX SBOM 或漏洞认证。

## 本地预览产物

普通 Release 及完整依赖：`dist/StudyWorkbench-M1-20261024-090800/study_workbench.exe`，不能仅复制 exe；同目录 backend/DLL/data/licenses 必须保留。`apps/desktop/build/windows/x64/runner/Release` 的前后端也已配套更新，旧后端保存在忽略目录 `.local/previous-release-backend-*`。

安装器：`dist/StudyWorkbench-M1-setup.exe`。仅本地预览，未发布、未签名、未通过干净机安装/升级/卸载验收。完整哈希见 [最终安装包记录](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-setup-final-hash.log)。首次普通 Release 已显示位置选择页，随后系统“打开文件—安全警告”阻挡 UI；未自动点击、解除文件标记或关闭安全防护。安装 smoke 的系统启动请求也尚未取得正常安装日志/退出码，不能记为安装成功。

首次普通入口的 [受阻截图](../../../artifacts/legacy-evidence/m1-followup-20261024/release-security-block.png)来自较早的 084711 staging；最终预览为上面的 090800，不能把截图称为最终安装验收。

当前系统提示需要用户手动处理。Computer Use 规则禁止操作 Windows 安全应用或绕过安全屏障，见本机 `computer-use/docs/guidance.md`；普通测试代码、组件/管道和后端检查继续运行。此限制与自动批准工具的拒绝不是同一件事，本轮没有收到自动批准拒绝。

## 实际命令和结果

Python 命令在仓库根目录执行，TEMP/TMP 为 `.local/tmp`；Flutter 命令在 `apps/desktop` 执行，先运行 `tools/prepare-windows.ps1`，PATH 加 `.local/bin`。没有修改系统环境或上游依赖。

| 命令 | 退出码 / 证据 | 实际范围 |
|---|---|---|
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=artifacts/m1-backend-58.xml` | **0；58 passed**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-backend-58.log)、[XML](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-backend-58.xml) | 保留 M0 协议/接口与 M1 空间/布局断言；增加迁移、复制/校验/配置失败、磁盘空间、锁、并发约束；独立 CPython 3.13.17 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | **0** | 不降低规则 |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/dart-service-isolation` | **0；19 passed**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-components-real-process-final.log) | 全部组件及真实 Dart→Python→迁移工作进程→重开后历史；无桌面窗口。默认不带 ROOT 的组件命令会跳过这一独立进程用例，本命令实际执行了它 |
| `flutter analyze --no-pub` | **0；No issues found**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-analyze-clean.log) | 先前 lint 失败保留，均补大括号，不关闭 lint |
| `dart format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test` | **0；0 changed** | 21 个 Dart 文件；最后只补风格大括号，未改变打包逻辑 |
| `flutter test integration_test/m1_test.dart -d windows ...` | **0；1 passed**；[冻结原生日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-frozen-native-2.log) | 真正冻结后端、两空间、作答、草稿、重启、归档/恢复、拖动标签、创建 WebView 后迁移、旧原件保留、强杀后恢复。此轮之后增加了管道取消/并发事务和退出回调断言；最终追加的原生退出断言尚未重跑，不伪称最终版本全量原生通过 |
| `flutter test integration_test/m0_test.dart -d windows ...` | **0；1 passed**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m0-frozen-final-1.log) | 冻结后端客观/主观题、真实 WebView DOM、VP9 解码、倍速/跳转、中文 WebVTT、关闭重开；不是编码矩阵和外站兼容验收 |
| `python tools/check_backend_lifecycle.py --exe dist/StudyWorkbench-M1-20261024-090800/backend/study_backend.exe --seed-db C:/Users/陈俊豪/AppData/Local/StudyWorkbench/m0/study.db` | **0**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-frozen-lifecycle-final.log) | 在临时目录对原库只读快照测试，原 7 条作答保留；追加两类作答、重复实例拒绝、鉴权/Origin、正常 EOF、重启/强杀恢复、迁移父 EOF 取消。冻结进程 PATH 只保留 System32、移除 PYTHONHOME/PYTHONPATH，cwd 不在源码；不等于无开发环境干净机 |
| `.local/check_cross_volume.py` | **0**；[真实跨卷日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-cross-volume-writable.log) | D→C 的全新测试目录，哈希/SQLite/切配置/旧数据保留。第一次 C Temp 目标被运行环境拒绝，日志也保留；之后使用明确允许的 C 盘工作目录，无系统权限修改 |
| `packaging/windows/prepare-tools.ps1` | **0**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-tools-complete.log) | 固定 SHA256、核对 Python PSF / Inno Pyrsys / Runtime Microsoft 签名、便携工具和锁定 Python 包 |
| `packaging/windows/build-release.ps1` | **0**；[最终普通构建](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-release-build-3.log) | Flutter Release、独立 CPython 冻结、CRT 验签、全新 staging、Inno 编译。之后补许可文件/输入框间距与读取快照修复，同步 staging 后重新编译 setup，见下一行 |
| `ISCC.exe --quiet --define=BuildRoot=.../dist/StudyWorkbench-M1-20261024-090800 --define=WebViewInstaller=.../MicrosoftEdgeWebView2RuntimeInstallerX64.exe --define=AppVersion=1.0.0 packaging/windows/setup.iss` | **0**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-setup-final.log) | 最终安装包；没有实际安装或卸载通过结论 |
| `python tools/check_release.py dist/StudyWorkbench-M1-20261024-090800` | **0；334 个文件**；[日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-release-check-final.log) | 清单 SHA256、CPython DLL 版本、无个人 db、PE 依赖可用、CRT 已随包。不能证明所有运行时动态加载项或干净机兼容 |
| `git diff --check` | **0** | LF/CRLF 提示单列，不影响结果 |

原生测试参数与首批一致，但不传 STUDY_ROOT，确保使用 runner/Debug/backend 冻结程序；M1 用 `.local/m1-frozen-native-2`，M0 用 `.local/m0-frozen-final-1`，媒体 `.local/sample.webm`，截图写入 `artifacts/m1-m0-final`。后续完整原生测试应使用新的隔离数据目录，并保持 Windows 构建串行。

## 修复与失败保留

- 首轮迁移数据库文件移动报 WinError32：sqlite3 connection 上下文只提交/回滚，不关闭连接。迁移和 schema 备份都改为显式 closing；未改数据或减断言。
- 首次 C++ 编译因中文源码编码触发常量换行错误：只给自有 runner 加 `/utf-8`，未改第三方 CMake。
- 首次迁移失败提示带整个 traceback，遮挡设置按钮：改为有界最后一行，增加关闭提示；重新跑真实迁移通过。
- 冻结 stderr 不遵守 PYTHONUTF8 环境变量：冻结入口显式 UTF-8，真实冻结进程复测通过。
- 并发同名创建最初得到 `[200,200]`，保留 [失败日志](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-concurrency-first.log)；写事务先 `BEGIN IMMEDIATE`，全 58 项重新通过，不仅修改 UI 按钮。
- GET workbench 在读取期间并发创建空间，最初返回了不在列表里的活动 ID，见 [快照失败](../../../artifacts/legacy-evidence/m1-followup-20261024/m1-snapshot-first.log)。增加真实 SQLite 读事务后，列表与活动 ID 保持同一快照；两版本 Python 的58项后端测试通过，重新冻结并同步最终产物。
- [原生截图复查](../../../artifacts/legacy-evidence/m1-followup-20261024/m0-question-before-spacing.png)发现主观题说明与浮动标签挤在一起，增加12像素间距，重新构建普通 Release并同步 staging；原图保留为修复前证据，不冒充修复后截图。
- 新 Dart 管道测试首轮把不同路径分隔符当成不同位置，保留失败；改为检查 OS 文件实体相同，仍检查原库、目标位置和作答原文，全部 19 项通过。
- C Temp 迁移因运行环境权限失败；安全停止且旧目录保留。没有修系统 ACL，也未以删除数据“修复”。Inno 工具普通安装的注册表写入失败后使用其官方 portable 模式，工具安装成功不代表本产品安装成功。

## M0 与阶段状态

M0 的失败恢复、中文菜单、作答结果与历史分离、网页外开失败反馈继续保留。新冻结构建和原库快照未复现先前 HTTP500；旧冻结程序对只读副本追加作答也成功，不能据此编造原始根因。**用户原默认目录的完整普通启动/作答，仍需安全提示处理后的实际流程复测**；新目录选择和失败重选已实现，原库未强制迁移。

M1-01/02/03 主要实现和自动化已具备；M1-04 的进程/冻结/配套 Release/setup 主体已实现。仍缺实际安装/升级/卸载保留数据、干净 Windows 无 Python/无 WebView2、原生焦点快捷键、真实显示器 DPI/性能及用户人工验收。新加的最终原生退出回调断言待跑；迁移父退出为检查点取消，不保证单个超大文件立即停止。

没有现成的干净 Windows 虚拟机镜像，当前 VMware_data 未发现可直接使用的 VMX/ISO。没有把开发机清单检查当干净机，也没有自动修改安全设置。**M1 与 M0 阶段均不标为全部通过**。下一步是用户手动处理系统提示、完成普通入口/原生退出和安装流程，再继续干净机及人工验收。

CI 已补充 Python 3.12/3.13.17 矩阵、19项完整组件/真实管道命令、独立 CPython 冻结和冻结生命周期 smoke；未推送、未触发或读取远程 CI，因此没有“远程 CI 已通过”结论。PowerShell 脚本语法解析通过，既有 WebView CMake CMP0175 开发警告仍保留。后端源码 CPython/Anaconda3.12.7 同样58通过，日志为 m1-source312-58.log；本轮最终 Python ruff 和 Dart 格式检查通过。
