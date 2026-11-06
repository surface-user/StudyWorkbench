# 测试与验收指南

## 自动化运行

仓库根使用既有.venv；TEMP/TMP可按tools/prepare-windows.ps1设置到项目内，避免受限系统TEMP。每轮使用新的隔离profile/basetemp，不指向个人学习目录，通过测试的tmp_path自动清理，失败现场保留；不再永久留存每轮完整测试副本。原始产物写artifacts/<运行批次>/；报告和精选共享证据见[记录规则](../dev/README.md)。

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/<新测试目录> --junitxml=artifacts/<本批>/backend.xml
.venv/Scripts/python.exe -m ruff check backend tools
.venv/Scripts/python.exe tools/export_question_schema.py --check
# 在apps/desktop运行，STUDY_ROOT须为仓库绝对路径，STUDY_DATA_DIR须为新隔离目录
flutter analyze --no-pub
flutter test --no-pub --dart-define=STUDY_ROOT=<仓库绝对路径> --dart-define=STUDY_DATA_DIR=<新隔离目录>
flutter build windows --release --no-pub
```

先创建本批产物目录。R1–R5真实HTTP回归使用tools/check_r1_blackbox.py至check_r5_blackbox.py，各带新隔离根；源码/冻结检查见tools/check_resource_explorer.py、check_question_files.py、check_backend_lifecycle.py、check_document_workers.py。Windows构建/原生集成串行，避免共享生成资源覆盖；按范围补原生与冻结检查，按用户11-06指令不再要求或执行真实窗口/人工测试。具体CI范围见[check.yml](../.github/workflows/check.yml)，存在工作流不代表远程已通过。

STUDY_EVIDENCE_DIR是沿用的历史参数名，原生自动截图应将其值指定为artifacts/<本批>/，不因变量名自动晋升为evidence。M0默认截图现写artifacts/m0/。

只读备份包检查核心可在`backend/`工作目录运行`../.venv/Scripts/python.exe -m study_workbench --inspect-backup "<备份ZIP绝对路径>"`。仅检查manifest与payload字节，不执行包内SQLite、不解压/激活或切换数据目录；输出的`database_semantics_checked=false`和`data_activated=false`不能忽略。完整备份/恢复由设置菜单及启动失败恢复入口执行，不用该检查命令代替恢复验收；冻结发行组合仍须另验。

临时目录策略使用pytest内置failed：用例执行失败时保留tmp_path，成功用例清理；setup/teardown异常以JUnit和错误日志留证，需完整现场时显式使用`-o tmp_path_retention_policy=all`，诊断后只保留最小复现，避免永久累积整轮副本。

## 已取消的人工测试范围（历史参考）

用户2026-11-06明确取消人工测试，以下矩阵仅保留历史范围，不再执行、不再作为退出门禁，也不记为通过。详见[ADR0013](adr/0013-cancel-manual-testing-and-bound-artifacts.md)。产品中的用户确认/候选人工审核功能仍保留。

| 范围 | 必要场景 |
|---|---|
| 默认启动/数据 | 普通Explorer、原保存位置、失败恢复、数据锁/迁移/回滚、重启保持；M0旧现场不被隔离通过替代 |
| R1/删除/统一添加 | 原生多选、真实跨窗口拖放、去重/取消/部分失败重试、目录层级、删除确认/重启不复活/原件历史保留 |
| R2/标签 | 5种资源、连续切换/关闭/重开、文件和作答草稿、原生焦点快捷键、多屏DPI/性能/无障碍；[完整规范](editor-tabs-spec.md) |
| R3/内容 | MD冲突、PDF/图片缩放、DOCX结构和可选PPTX派生、缺组件/坏文件/源变更/取消，真实公式图表内容 |
| R4/R5 | 七类及缺答案作答、确认新版本不改旧分数、相对附件丢失/快照、笔记关联、事件分页/全流投影、版本未知 |
| LW-01/02 | 空目录自由笔记、来源关联失败重试；PDF/Office旧分页/原文行/真实媒体时间、多条备注与回跳；改名移动/内容变化/移除/重启及草稿保护 |
| LW-03/04 | 真实剪贴板与MD插入/点击/往返、外部HTTPS隔离；搜索中文/大小写/分页/截断，正文变更重验、失效来源备注可读；跨空间不跳转或泄露 |
| LW-05（本地实现，人工待验） | 实际全库恢复、确认版/关系/工作字节/草稿/媒体状态一致、磁盘不足/坏包/取消/激活失败旧库保持；只读检查不替代 |
| 媒体/WebView | 音轨/编码/字幕/续播/倍速、外站导航/浏览器最终URL/登录/DRM/休眠、权限和子资源负面矩阵 |
| 安装/发行 | 无Python/无WebView2干净机、自选目录、升级/卸载保留、前后端配套/签名/实际二进制许可 |
| R6授权/人工候选审核；模型路径规划 | 本地范围/到期/撤销/预算、历史版本、修订/hash与独立采用、失败/恢复/备份及原数据保持；模型实施后另验出境/提示注入/降级和AI来源 |

记录OS/Runtime、样本来源与编码、应用/后端版本或hash、实际行为与截图。Agent自动窗口交互和用户人工验收分开，回调注入不证明Explorer真实拖放。失败测试/断言不删除不降低，旧head绿灯不代表新head。任务完成按[退出条件](task.md#任务退出条件)，人工测试按用户指令已取消。


## 离线只读巡检自动化

`python -m study_workbench --data-dir <已有隔离库绝对路径> --check-library --confirm-all-workspaces`（backend工作目录）。测试缺失/损坏字节、索引冲突、未登记派生目录、空目录、已登记失败任务、创建/保存收据、重解析点、范围/预算和锁冲突，并比对业务数据库和学习文件前后字节一致。CLI也纳入冻结包CI，在已停止的统一导入样本库上执行；不以源进程通过代替冻结入口。
