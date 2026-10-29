# M1 后台续测（2026-10-24）

用户要求“先只做后台测试”。本批未启动或操作桌面应用窗口、安装器或系统安全提示，未创建子 Agent，未提交或发布。人工与阶段验收仍未完成。

## 修复

- 连续迁移会覆盖已复制的 migration-receipt.json，新清单却包含该文件的旧哈希。回归测试首先失败；现在以独占创建写入新名称，旧回执原样保留，清单不再自相矛盾。
- 原先只能在整个文件/数据库操作完成后取消。现在扫描、每1MiB哈希/复制块、SQLite backup每256页、逐行内容比较均检查父进程取消信号。实际多块文件中途故障测试确认目标只写入部分内容，旧文件哈希及配置不变，锁释放，失败现场保留。阻塞I/O、完整性检查和应用校验期间仍非实时取消。
- 生命周期检查增加真实CLI连续迁移两次、回执原文与文件哈希、重启后作答数量断言；不降低原有EOF退出时限。
- 本地目录校验原先只拒绝UNC，漏过映射网络盘符；新增Windows GetDriveTypeW检查。模拟DRIVE_REMOTE回归先失败，再确认拒绝；本机D盘路径仍通过，不声称使用过真实网络盘。
- 冻结退出偶发超时的诊断构建在第4次复现，捕获Proactor连接重置回调的WinError10054及事件循环等待栈（m1-eof-stack-4.log）。Windows后端改用标准库Selector循环，stdin仍为专用线程；当前后端只用本地TCP，不使用asyncio子进程/管道。新增真实SO_LINGER连接重置后立即EOF断言，保持10秒上限。未来若后台业务使用asyncio Windows子进程，需要重新评估循环能力；未替换主技术栈或依赖。

## 命令与证据

命令在仓库根执行，Python TEMP/TMP 为 `.local/tmp`；Flutter cwd 为 `apps/desktop`，使用既有 prepare-windows 脚本和项目 NuGet。完整日志保存在同名 artifacts 文件，并复制到 `docs/evidence/m1-background-20261024`。

| 命令 | 退出码 / 结果 |
|---|---|
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests/test_data_root.py -k repeated -q` | 1；复现回执哈希错误，m1-repeat-migration-first.log |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests/test_data_root.py -k failure_preserves -q` | 1；4个内部取消点未响应，m1-migration-cancel-first.log |
| `.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/m1-background-312-65.xml` | 0；65 passed，Python3.12.7 |
| `.local/release-venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/m1-background-313-65.xml` | 0；65 passed，独立Python3.13.17 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 0；All checks passed |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/dart-service-isolation` | 0；19 passed，循环修复后再次执行；真实Dart→源码后端→迁移→重开，无桌面窗口，m1-background-selector-components.log |
| `packaging/windows/build-backend.ps1` | 0；独立CPython冻结，m1-background-freeze.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe --seed-db C:/Users/陈俊豪/AppData/Local/StudyWorkbench/m0/study.db` | 0；鉴权、Origin、锁、EOF、重启、强杀恢复、迁移父退出取消；只读快照保留7条历史，原库未改 |
| `.venv/Scripts/python.exe tools/check_backend_lifecycle.py` 和发行Python同命令 | 均0；循环修复后增加连接重置和连续迁移的完整流程通过，m1-background-reset-source312/313.log |
| `python tools/check_backend_lifecycle.py --exe dist/StudyWorkbench-M1-20261024-background/backend/study_backend.exe --seed-db C:/Users/陈俊豪/AppData/Local/StudyWorkbench/m0/study.db` | 两次1：首次普通服务EOF等待10秒超时；后续诊断重跑0，完整连续迁移通过。失败保留为 m1-background-frozen-eof-timeout.log 和 m1-background-repeat-frozen-retry.log，成功不能证明偶发超时根因已解决 |
| `python tools/release_inventory.py --stage dist/StudyWorkbench-M1-20261024-background` / `python tools/check_release.py dist/StudyWorkbench-M1-20261024-background` | 均0；334文件哈希、Python313、无个人DB、PE依赖检查 |
| `.local/release-tools/inno7/ISCC.exe --quiet --define=BuildRoot=<上述完整staging> --define=WebViewInstaller=<项目官方离线Runtime> --define=AppVersion=1.0.0 packaging/windows/setup.iss` | 0；仅编译，未执行安装器 |

最终配套目录为 `dist/StudyWorkbench-M1-20261024-background-fixed`，独立后端再次冻结成功；334文件清单及PE检查退出0（m1-background-fixed-release-check.log）。上表background目录为循环修复前批次，保留作对照。安装器再次编译退出0，仍为 `dist/StudyWorkbench-M1-setup.exe`，最终SHA256：`5417CEE4A7DA36908C2E74811168941EDEC93020A36ED761970F4AD1AA8ED485`。旧090800、background目录和runner/Release后端属于此前批次，不能混用证据。

## 尚未解决与下一步

冻结退出问题最初两次超时，随后普通重跑连续3次通过仍未视为解决；继续加栈诊断后第4次复现了Proactor异常。调整循环后的冻结后端，真实连接RST→EOF、连续两次迁移、重启/强杀恢复、旧库快照保留7条历史的完整流程连续5次退出0（m1-background-reset-frozen-1至5.log），未放宽10秒断言。捕获到的故障路径已有修复与回归，不能据此保证所有网络/系统条件均无故障。诊断计时/线程栈仅位于忽略目录临时构建，不进入最终安装包。

M0原默认目录普通启动/作答、最终原生退出回调、安装/升级/卸载、干净机、显示器DPI与人工验收仍待完成；本批后台结果不代替这些门禁。没有远程CI通过结论。下一步在用户允许窗口操作后补这些流程；后台自动化继续保留RST、迁移与进程退出回归。
