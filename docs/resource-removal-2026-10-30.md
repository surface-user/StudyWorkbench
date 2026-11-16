# 工作区资料删除（2026-10-30）

用户实测资源树缺少删除入口，要求修改。需求为移除工作区资料；永久擦除个人文件和学习数据不在本批范围。

## 设计与任务拆分

1. 复用资源菜单，增加“删除”和确认对话框，明示文件夹包含全部后代；取消无请求，失败保留对话框可重试，请求期间防重复操作。
2. 受保护 DELETE `/api/workspaces/{workspace_id}/nodes/{node_id}` 仅在事务中标记节点和全部后代的 `removed_at`。工作空间归属、会话令牌、Origin规则不变；同空间存在排队/运行的添加任务时返回409，先等待完成或取消。
3. 0012仅追加可空字段，将同层名称唯一索引改为未移除节点的部分索引。沿用升级前备份、事务迁移和完整性验证；无新增依赖。
4. 列表、相对资源查找和重名检查排除移除节点。旧资源适配查询仍包含移除身份，避免刷新/重启时重新生成。允许再次添加同名资源及显式重新导入，获得新节点身份。
5. 原文件、受管原件、工作副本、题目映射/确认版、作答、事件和layout均保留。按ID访问仍受空间权限控制，已打开的编辑标签可继续读写工作副本；不强制关闭标签或丢弃草稿。学习记录不再将移除节点作为当前资源或来源入口，历史快照保留。删除相对图片节点后，当前文档可能提示引用缺失，已确认附件快照不变。

涉及：Explorer服务及SQLAlchemy模型/Alembic迁移、学习记录关联、Flutter资源菜单、后端及组件/Windows集成回归、依赖当前head的既有迁移/冻结检查。没有改变判分、技术栈、依赖或导出格式。

## 验证记录

- 首轮 `.venv/Scripts/python.exe -m pytest backend/tests/test_resource_removal.py -q`：退出1，4个setup错误，sandbox默认TEMP无法建立pytest目录，未进入业务断言。改用项目隔离TEMP及显式basetemp后复测。
- `$env:TEMP="$pwd/.local/tmp"; $env:TMP=$env:TEMP; .venv/Scripts/python.exe -m pytest backend/tests/test_resource_removal.py -q --basetemp=.local/removal-tests-01 --tb=short`：退出0，4通过。覆盖递归移除、鉴权/跨空间/Origin、幂等、同名重建、重启不复活、原件与历史保留、工作副本继续保存、活动任务阻断、注入失败事务回滚及0011升级备份。
- `dart format lib/resource_explorer.dart test/resource_explorer_test.dart`、`flutter test test/resource_explorer_test.dart`：退出0，6通过，含取消无请求、删除失败保留及重试成功刷新。
- Ruff首轮退出1（新测试局部import顺序），已修复，` .venv/Scripts/python.exe -m ruff check backend tools`复测退出0；`git diff --check`退出0。

- 首轮完整后端回归（`.local/removal-full-01`）210通过/2失败：一项sandbox拒绝创建测试Junction；另一项为旧行比较未适配新增removed_at。授权环境复测（`.local/removal-full-02`）211通过/1失败，仅剩该旧行比较。已增加“旧节点removed_at必须为NULL”并逐列比较全部旧值，保留所有旧断言；失败日志`.local/removal-backend.log`与`removal-backend-02.log`保留。
- 最终 `$env:TEMP="$pwd/.local/tmp"; $env:TMP=$env:TEMP; .venv/Scripts/python.exe -m pytest -q --basetemp=.local/removal-full-03 --tb=short`：退出0，212通过（`.local/removal-backend-03.log`）。
- `flutter analyze --no-pub`：最终退出0，无问题；首轮3条if缺大括号的lint已修复。`flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/removal-pipe-tests`：退出0，86通过，包含两项真实后端管道测试。
- `flutter test integration_test/resource_explorer_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/removal-native-data-02 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/.local/removal-native-evidence`：退出0，1通过；真实窗口完成文件夹复制、详情、链接添加、递归删除确认、树刷新与原文/layout保留。首轮NuGet临时目录失败（退出1），按现有tools/prepare-windows.ps1的进程级TEMP/TMP/NUGET_SCRATCH重试通过，未改依赖或系统设置。日志`.local/removal-native.log`和`removal-native-02.log`均保留。
- `flutter build windows --release --no-pub`：退出0（`.local/removal-release.log`），同上隔离TEMP/NUGET_SCRATCH。已有插件CMP0175开发警告保留，不修改上游缓存。
- `.local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --onedir --name study_backend --distpath .local/removal-frozen --workpath .local/removal-freeze-build --specpath .local/removal-spec --paths backend --collect-submodules study_workbench --copy-metadata docling-slim --copy-metadata docling-core --copy-metadata doclang --copy-metadata pypdfium2 --copy-metadata python-docx --copy-metadata pylatexenc --add-data 'D:/computer_work/project/StudyWorkbench/backend/migrations;migrations' --add-data 'D:/computer_work/project/StudyWorkbench/backend/study_workbench/player.html;study_workbench' --add-data 'D:/computer_work/project/StudyWorkbench/backend/study_workbench/library_player.html;study_workbench' tools/frozen_entry.py`：退出0，CPython3.13.17独立冻结。首轮specpath使相对add-data基准变化，退出1；改为绝对输入路径后成功，日志`.local/removal-freeze.log`与`removal-freeze-02.log`保留。
- `.venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/removal-frozen/study_backend/study_backend.exe --test-root .local/removal-frozen-check --documents`：退出0；实际冻结进程确认0012、删除后重启不复活、layout/作答/原件与文档保留。`.venv/Scripts/python.exe tools/check_question_files.py --exe .local/removal-frozen/study_backend/study_backend.exe --test-root .local/removal-question-frozen`：退出0，4确认版/3作答、旧分数、历史未知版本、快照附件、草稿/学习事件重启全部通过。

代码审查完成：核对所有WorkspaceNode/node_in调用、旧资源适配、事务锁与复制竞争、同空间约束、部分索引及迁移备份、已打开编辑器保存和历史关联。原迁移0001–0011不修改，当前head检查工具与测试更新至0012。人工/阶段验收仍待验。

## 新测试包

`dist/StudyWorkbench-resource-delete-test-20261030/study_workbench.exe`。全新目录组合本次Release界面与本次冻结后端，复用既有本地CRT，不覆盖旧测试包。必须保留整个目录，启动前退出旧程序以释放数据锁。没有自动启动或迁移个人学习库；普通启动时仍采用已有数据位置，升级前由迁移器保留SQLite备份。

界面data/app.so与构建来源SHA256均为`27C47EA162D9C9A1B19BFF21E6BC4319502DC4726AC96FD496B2E6AEB61229A7`；后端EXE与已验证冻结来源均为`8174561A73F0D4BF55A9A80B8D48E10B5BAAE679CE4AE41565E109BFD6470EFB`（`.local/removal-package-hashes.json`）。截图`.local/removal-native-evidence/resource-delete-confirmation.png`已目视检查，文字与确认/取消按钮完整可见。

`.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage dist/StudyWorkbench-resource-delete-test-20261030`与`.local/release-venv/Scripts/python.exe tools/check_release.py dist/StudyWorkbench-resource-delete-test-20261030`均退出0；1304文件哈希、CPython版本、无数据库及PE依赖检查通过。保留许可证与build-inventory.json；这不代表干净机或安装器验收。未提交、推送或发布。

## 限制

本批删除指从工作区资源树移除，不释放磁盘空间，也不提供回收站恢复界面。原件和学习记录保留；旧包不会自动获得新入口。安装器、干净机、用户个人库及手动验收不以自动化通过替代。
