# 选定数据目录后仍因配置目录拒写而退出

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

用户报错：已选择`D:\computer_work\data`，冻结后端却在创建`%LOCALAPPDATA%\StudyWorkbench\session`时WinError5退出。本批沿用ponytail技能的小范围修复，不改系统ACL、不提权、不迁移个人数据、不增加依赖，没有提交/推送/发布。

## 原因与修复

业务数据位置和启动配置位置是两个目录。此前`__main__.py`无条件先取得配置目录会话锁，再取得数据锁；前者无法创建时，后者即使可写也没有机会使用。

现在普通启动遇到配置目录I/O错误时保留用户选择的数据位置，停止写该配置，但继续取得数据锁、打开业务库。配置原子写入失败同样保留旧配置并返回警告。握手增加可空`startup_warning`，Flutter显示持续提示和当前数据目录，允许复制位置；下次可能仍用旧配置或要求重选，不能把“没有记住位置”误当作“学习数据没有保存”。有警告时UI暂停迁移入口。已被其他实例持有的配置锁依然拒绝启动，数据锁及数据读写权限错误依然失败，不自动创建替代知识库。

迁移不使用这个降级路径：仍须取得配置锁并完成原子配置提交；失败保留源数据和原配置。原有迁移故障测试继续运行。

## 实测边界

同一旧开发包的冻结后端在真实`C:/Users/陈俊豪/AppData/Local/StudyWorkbench/`下独立诊断配置子目录复现拒写，见frozen-before-02.log。新冻结程序在相同路径下，两次启动/健康检查/作答/重启保留/EOF退出通过，警告存在且未创建/改写配置；另在可写配置路径下两次启动通过、位置正常保存且无警告。

当前工具启动进程观察到Low Mandatory Level，且LocalAppData访问存在打包应用路径映射；普通Python3.12/3.13与冻结程序均被拒写。因此不能认定是Python版本或单个PyInstaller可执行文件独有错误，也不能仅凭ACL中用户名FullControl断言进程实际能写。这些是当前工具环境证据，不证明用户从资源管理器启动时也有同样令牌。

对用户选定`D:/computer_work/data`只尝试创建唯一诊断临时文件，也被当前工具环境拒绝（selected-data-write.log）；没有打开个人数据库或写入原件。**修复配置阻断不能绕过数据目录权限**。普通用户从资源管理器打开新版、选择该数据目录的实际启动仍待复验。若配置仍不可写而数据可写，新版可在显示警告的情况下正常学习；若数据目录本身不可写，仍应停止，不更改权限或另建空库冒充恢复。

## 命令、退出码及证据

证据目录`docs/evidence/startup-config-20261025/`，Python的TEMP/TMP为`.local/tmp`、PYTHONUTF8=1；pytest使用独立basetemp，失败日志未删除。

| 实际命令 | 退出码/结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests/test_startup_settings.py -q --basetemp=.local/startup-config-first --junitxml=docs/evidence/startup-config-20261025/first.xml` | 1，2失败/2通过，先复现配置锁拒写与原子写入失败使启动中断 |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_startup_settings.py backend/tests/test_data_root.py -q --basetemp=.local/startup-config-fixed --junitxml=docs/evidence/startup-config-20261025/fixed.xml` | 0，20通过 |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/startup-config-full312 --junitxml=docs/evidence/startup-config-20261025/backend312.xml` | 0，126通过 |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/startup-config-full313 --junitxml=docs/evidence/startup-config-20261025/backend313.xml` | 0，126通过 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 最终0，ruff-final.log；早期两个未使用导入修复，旧日志保留 |
| `dart format lib/backend.dart lib/main.dart test/backend_process_test.dart`；`flutter analyze --no-pub` | 均0，format.log、analyze.log |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/startup-config-dart-02` | 0，50通过，flutter-02.log；第一次因Windows路径分隔符文本断言失败，改为两侧规范化后仍检查相同配置路径/实际作答保留，未删断言 |
| `powershell -ExecutionPolicy Bypass -File packaging/windows/build-backend.ps1` | 两次1，旧Windows PowerShell原生命令传参丢失引号，frozen-build.log、frozen-build-02.log；非后端业务回归失败 |
| `& ./packaging/windows/build-backend.ps1`（当前PowerShell） | 0，frozen-build-03.log，153.8秒 |
| `flutter build windows --release --no-pub` | 0，windows-release.log，46.2秒；既有插件CMake警告保留 |
| `.local/release-venv/Scripts/python.exe tools/check_startup_config.py --exe dist/StudyWorkbench-M2-M4-dev-20261025-b3a02497/backend/study_backend.exe --config C:/Users/陈俊豪/AppData/Local/StudyWorkbench/startup-regression-20261025/settings.json --data-dir .local/startup-config-old-frozen-02 --expect-warning` | 1，旧程序真实拒写，frozen-before-02.log |
| 同工具`--exe dist/study_backend/study_backend.exe --config <同上路径> --data-dir .local/startup-config-new-frozen --expect-warning` | 0，frozen-after.log，启动/作答/重启、原配置不变 |
| 同工具`--exe dist/study_backend/study_backend.exe --config <仓库绝对路径>/.local/startup-config-writable-profile/settings.json --data-dir .local/startup-config-writable-data` | 0，frozen-writable.log，正常配置保存 |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | 0，frozen-lifecycle.log，鉴权/空间、作答/原件/拆题MD/媒体、重启/崩溃/两次迁移、EOF/RST等既有回归保留 |
| `tools/release_inventory.py --stage <新开发目录>`；`git diff --check` | 均0，inventory.log、stage-check.log、diff-check.log |

Flutter命令在`apps/desktop`通过既有SDK`D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe`执行`flutter_tools.snapshot`，未更换工具链；构建复用`.local/bin`及`.local/nuget-scratch`。

## 开发产物与状态

新目录`dist/StudyWorkbench-startup-fixed-20261025-2af3c1f0`，入口`study_workbench.exe`；包含本批前端及冻结后端，exe/app.so/backend哈希与输出一致，必须保留同目录data/backend/DLL/licenses。旧开发目录保留作失败对照。请用Windows文件资源管理器打开该目录并双击程序，选择原`D:\computer_work\data`，观察实际普通启动结果。

状态：配置阻断修复已实现，自动化通过；受限工具环境的D盘个人数据目录启动未验证成功，用户普通启动/真实窗口警告/人工验收待验。M0历史默认目录mkdir/500及完整M1安装、干净机、人工/阶段验收仍不标为通过；新报告只解决已复现的配置目录强制依赖。没有新安装包。
