# R4：题目Markdown与确认版本交付记录

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

2026-10-26开始，2026-10-27完成本批开发、自动化及审查。用户已授权R1→R6按序继续；人工、普通用户/干净机及阶段验收仍待统一进行。本批使用隔离测试库/自编样例，不读取个人库，不创建子Agent，不提交/发布/合并，不替换dist/StudyWorkbench-current。

## 实际行为

- 独立QuestionFile v1以MD保存稳定ID、文本/公式、全部旧富内容块、七类题型、相对附件和未知根元数据。旧JSON协议保持严格；新文件显式缺答案待批改，不编造标准答案。结构块完整记录与可读投影必须一致，未知格式/核心字段拒绝。
- 旧JSON/提取MD先预览、显式创建新编辑文件，再另行确认。旧行/原件/ID与提取来源信息保留；重复ID拒绝合并。普通保存只改工作副本。
- 0010追加映射、不可变确认版本和attempt可空版本ID。确认冻结MD、标题、编译题目/材料、附件及hash，落盘回读后发布；提交核对当前版本及全部快照资产，损坏拒绝判分。旧attempt新列为null/版本未知，不补造历史。
- 原request_id/答案/版本重试保持幂等，新确认版不改旧分数。文件移动、外部修改、当前附件丢失不影响已确认快照；当前文件无效时明确警告，不允许发布。
- 文档页内检查/确认/作答，文件编辑与作答草稿分别保存。关闭保存不提交答案，重新打开恢复同一版本/request_id；旧版本草稿需要显式舍弃才能开始新版本。隐藏视图复用PageHost隔离焦点。旧学习入口双读当前确认版。
- 含映射的资源导出标记v2，携当前MD/相对附件、全部确认版和旧缓存；无映射沿用v1。v2不冒充旧导入包或完整数据库恢复。

设计、协议及决策：[R4设计](r4-design.md)、[QuestionFile](../../../docs/question-file-spec.md)、[ADR0010](../../../docs/adr/0010-question-files-and-confirmed-versions.md)。

## 实际命令与证据

所有路径相对仓库；各命令均在本机执行。证据目录为[本批目录](../../../artifacts/legacy-evidence/r4-20261026)。开发Python3.12用.venv，发行Python3.13用.local/release-venv。Flutter命令实际使用固定SDK的dart.exe调用flutter_tools.snapshot；Windows命令先运行tools/prepare-windows.ps1并将.local/bin加入本进程PATH。

| 命令 | 退出码与证据 |
|---|---|
| .venv/Scripts/python.exe tools/make_question_file_samples.py --output contracts/samples/question-files-v1 | 0；自编有答案/待批改MD、PNG，生成时协议往返自检 |
| .venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r4-py312-sequential --junitxml=docs/evidence/r4-20261026/backend312-sequential.xml | 0；205通过，144.34秒；backend312-sequential.log/xml |
| .local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r4-py313-sequential --junitxml=docs/evidence/r4-20261026/backend313-sequential.xml | 0；205通过，112.46秒；backend313-sequential.log/xml |
| .venv/Scripts/python.exe -m pytest backend/tests/test_question_files.py -q -x --tb=short | 0；28通过，13.90秒；targeted-final.log |
| flutter test --no-pub | 0；82通过/2跳过；flutter-final.log。跳过项不计通过 |
| flutter analyze --no-pub | 0；No issues found；analyze-final02.log |
| flutter test integration_test/question_files_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r4-native03 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/r4-20261026 | 0；Windows真实1通过；windows-final.log。补强移动后检查和截图的同命令将目录改为.local/r4-native04，见windows-final02.log及下方最终复核 |
| flutter build windows --release --no-pub | 0；58.0秒；windows-release.log。源码编译不等于安装器/完整组合包验收 |
| .local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath .local/r4-frozen/dist --workpath .local/r4-frozen/build .local/r4-frozen/study_backend.spec | 0；freeze.log；复用既有收集配置，新独立目录，不覆盖旧包 |
| .venv/Scripts/python.exe tools/check_question_files.py --test-root .local/r4-loopback-source-final | 0；loopback-source-final.log，真实source loopback |
| .local/release-venv/Scripts/python.exe tools/check_question_files.py --exe .local/r4-frozen/dist/study_backend/study_backend.exe --test-root .local/r4-loopback-frozen-final | 0；loopback-frozen-final.log，PATH仅System32、移除PYTHONPATH/PYTHONHOME、cwd隔离目录；4确认版/3作答、旧分数、重试/重启、独立图片快照、缺答案、导出及草稿 |
| .local/release-venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/r4-frozen/dist/study_backend/study_backend.exe --test-root .local/r4-resource-frozen-final --documents --without-office | 0；frozen-without-office.log，0010/旧作答/树/MD冲突/布局/原件/重启及缺组件回退 |
| .local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe .local/r4-frozen/dist/study_backend/study_backend.exe | 0；frozen-lifecycle.log，数据锁/鉴权/Origin/EOF/重启/崩溃/资料与媒体迁移保留；未传seed-db |
| .venv/Scripts/python.exe -m ruff check backend tools | 0；ruff-final.log |
| .venv/Scripts/python.exe tools/export_question_schema.py --check | 0；新旧三份协议与Dart assets一致 |
| git diff --check | 0；仅现有文件LF/CRLF提示，无空白错误 |

28项R4测试包含七类×空/有答案往返、CRLF/实体/全部块/未知字段/重复元数据/结构投影、旧JSON与旧提取MD显式转换、来源降权、重复ID/同空间、快照篡改、空答案全部待批改、版本/幂等/旧分数、0009升级失败精确回滚和旧行列保持、迁移备份、跨空间DB绑定触发器、严格确认值/额外命令/鉴权/Origin、快照写坏时旧缓存保持与失败收据。携MD/图片的v2导出再添加到另一空间会重新绑定实际Resource ID，不信任旧库ID。

## 审查、失败与限制

逐项检查协议→旧内容转换→相对资源→工作副本→确认收据/落盘→缓存/快照→提交/幂等→UI草稿/关闭→导出及迁移触发器。source-before.json为改动前SHA；final-review.json复核0001–0009及旧question_protocol.py完全不变、本地文档链接和验收边界。使用现有依赖，未新增产品依赖；固定玻璃库和旧判分规则不改。

保留的失败均在证据目录，不删测试、不降低断言：

- first.log/xml：16通过7失败，夹具重复Resource hash违反已有唯一约束；改为不同MD字节但同题ID，继续验证ID冲突。
- second.log/xml：79通过2失败，旧断言仍期待head/备份0009；升级到0010预期，并逐表逐列验证旧值保持，新attempt列只允许null。
- assets.log/xml：23通过3失败，新增测试少json/hashlib导入；assets02后26通过，最终R4已28通过。
- windows-first.log：点击位于滚动区域外的“开始新一次作答”失败；统一ensureVisible后点击，并启用致命命中警告，windows-second/final通过。
- analyze-first/second/third/final.log：新增测试单行if格式提示，补大括号后analyze-final02无问题。
- backend312-final与backend313-final：各204通过、1失败，旧Office abrupt-owner测试子进程marker等待10秒超时。当时两套全量与冻结构建并发；未据此断言一定为负载原因。原测试独立执行 -k owned_process -vv -s --basetemp=.local/r4-owner-diagnostic，退出0、两项通过（owner-diagnostic.log）；终止断言与超时均未放宽，随后分别串行全量复核，结果分开保留。测试仍有固定启动时间窗口这一限制。

截图：[确认版公式/图片及评分](../../../artifacts/legacy-evidence/r4-20261026/question-file-graded.png)、[缺答案待批改](../../../artifacts/legacy-evidence/r4-20261026/question-file-pending.png)。仅自编数据，不含个人资料。

首版复杂块需类型记录与可读投影一致；不提供通用Markdown AST/所见即所得编辑。单独移动MD会破坏当前相对附件关系，仍可使用确认快照；不能据此宣称路径自动修复。导出v2不是完整恢复包；旧版本未知保持。未重复R3完整LibreOffice实机转换（Office执行路径本批未改），保留R3的字体/复杂文件和完整OS沙箱限制。安装器、普通用户/干净机、完整发行许可/SBOM/签名及人工/阶段验收待统一进行，M0旧失败、下载队列及完整备份恢复继续保留。下一顺序R5学习记录、追加事件和资源反向关联，R6尚未实施。

最终复核：windows-final02.log退出0、1通过、11秒交互（Windows编译31.3秒）；明确断言移动MD后的当前相对附件检查失败、无发布按钮、保留确认快照及作答草稿，截图已滚动到可见评分/待批改结果并人工查看图像。双Python串行全量分别205通过；并发失败不删除、不改判通过。235个本地文档链接和0001–0009/旧协议SHA核对通过，review-links-migrations.log与final-review.json保留机器可读结果。CMake仍有既有inappwebview CMP0175开发提示，构建退出0；Starlette测试仍有BlockingPortal弃用提示，不作为安装/运行兼容结论。

最终补充命令：固定dart.exe执行 format --output=none --set-exit-if-changed，覆盖本批14个Dart调用方/测试文件，退出0（format-final.log）；Schema检查与git diff --check最终日志分别为schema-final.log/git-diff-check.log，均退出0。
