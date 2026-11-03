# R6首批：本地授权及作答摘要读取

日期：2026-11-03。范围为R6基础API；整体R6未完成，人工/阶段待验。

## 需求、设计与任务

完整读取AGENTS.md、requirements、architecture、question-content-spec、task；补读agent-design、api-spec、data-model、testing及dev/README。当前R1–R5已实施，历史验收仍待完成；保留工作区已有文档治理和其他修改。使用ponytail最小实现，无子Agent、无新依赖。

本批设计：普通业务Bearer保护的显式授权创建/撤销；作用域固定同空间显式作答集合及analyze_attempts用途，仅本地读取最小摘要。进程内存保存，重启失效、单调时钟过期、总数预算100；不新增数据库迁移。先实现授权/读取及安全回归，再接普通UI和模型。调用方为新增HTTP路由及测试，目前没有Flutter调用方、模型或远端出口；既有接口不改。文档同步API/架构/模型/任务/Agent设计。

## 实现与自审

agent_access.py新增3个受控API，app.py注册既有鉴权依赖。校验独立正整数ID、用途、期限、确认及额外字段；创建和每次读取均核验空间/归属。锁串行撤销与读取，读取不扩大集合，不执行正文指令。摘要仅原始状态/分数和ID/时间，不含响应、题干、事件、笔记或评分修订。自审完成，非独立人工批准。未修改个人库或原件，无学习记录写入。

## 实际验证

工作目录均为仓库根，使用既有.venv。原始JUnit在artifacts/r6-access-20261103/，不晋升共享证据。

- 最初终端/Node读取因Windows sandbox setup refresh错误未启动，无命令退出码；恢复后读取成功。读取backend/pyproject.toml时发现不存在，随后读取根pyproject.toml。
- `.venv/Scripts/python.exe -m ruff check backend/study_workbench/agent_access.py backend/study_workbench/app.py backend/tests/test_agent_access.py --fix`：退出0，修正2处import排序。
- `.venv/Scripts/python.exe -m pytest backend/tests/test_agent_access.py backend/tests/test_learning_records.py backend/tests/test_api.py -q --basetemp=.local/r6-access-20261103 --junitxml=artifacts/r6-access-20261103/backend.xml`：退出0，9 passed。
- 同命令改basetemp为.local/r6-access-20261103-02、JUnit为backend-02.xml：退出1，1 failed/9 passed。新增预算测试使用不合法空作答，触发KeyError；同时自审发现重启断言插入位置错误，恢复到原测试后再跑，不删除断言。
- 同命令改basetemp为.local/r6-access-20261103-03、JUnit为backend-03.xml：退出0，10 passed。覆盖授权输入、隔离、鉴权/Origin、撤销、过期、重启、授权数量上限、归档拒绝、旧记录保持及既有API/学习事件回归。
- `.venv/Scripts/python.exe -m ruff check backend tools`：退出0。保留Starlette/AnyIO废弃告警。

## 交付与限制

仅本地实现，未提交、推送、创建PR、合并或发行；远程head/CI本批未查询。人工与阶段未验收。未跑全后端、Flutter、Windows构建/冻结或真实窗口；本批无Dart/原生/依赖改动，定向API回归不替代完整产品验收。既有失败保持不变。

下一步：普通UI授权选择/撤销、资源受控读取、模型与安全凭据适配、单独远端内容授权、草稿外置审核、来源校验及完整安全/离线矩阵。当前摘要不含最新人工评分，禁止当作完整薄弱点分析结果。


## 同任务继续：普通授权界面

需求/设计：学习页当前已加载历史作为候选清单，最多勾选100条；明确用途/5分钟/本地读取边界后确认，另按按钮读取摘要。授权ID不写布局/磁盘；弹窗关闭先撤销，网络/服务错误保留弹窗和授权以重试；404视作已失效。当前不接模型或远端，不扩大读取内容。任务拆分：独立弹窗、学习页入口、模拟后端组件测试、静态/组件/Windows构建、自审和文档同步。无新依赖或数据迁移。

已实现agent_access_dialog.dart与学习页历史入口，新增2项组件用例。自审核对创建仅在确认后、选择集合固定、busy防连击、失败保留、过期清除与撤销关闭；没有独立人工审查。已有源码/文档改动均保留。

实际命令（Flutter命令工作目录apps/desktop；D为D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F为D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot，实际以绝对路径调用）：

- `dart format`最初通过bat调用未返回；改为直接D format，退出0。受限环境D F analyze报SDK cache/lockfile不可写；后续以所需权限运行，未升级SDK。CIM进程查询访问拒绝，退出1。一次Python文本辅助编辑因默认GBK解码失败退出1，改用显式UTF-8后退出0，原文件未在失败时改写。
- `D F analyze --no-pub; D F test --no-pub test/agent_access_dialog_test.dart test/study_page_test.dart test/learning_record_dialog_test.dart`：首批分析4项info，随后1项info；定向均6 passed（组合命令退出0不表示此前分析无提示）。逐项修正花括号及私有辅助函数命名后再复核。
- `D F test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r6-ui-20261103`：93 passed，测试命令成功。接续Windows构建状态见下。

本批无Python行为改动，未重跑后端全套；实际窗口和人工/阶段验收仍待验。创建授权若响应丢失，客户端无法立即知道其ID；未获知的临时授权依5分钟到期或后端重启失效，不会自动扩大范围或读取。授权UI仅提供当前加载历史，更多记录需先加载；模型/凭据/资源读取/草稿审核仍未实现。未提交/推送/合并/发布。

- 最终 `D F analyze --no-pub`：退出0，No issues found（8.5s）。
- 首次 `D F build windows --release --no-pub`：退出1，WebView插件NuGet依赖步骤MSB3073；另有插件CMake CMP0175开发告警。按既有prepare-windows.ps1约定设置TEMP/TMP=.local/tmp及NUGET_SCRATCH=.local/nuget-scratch后重试。

- 设置上述进程临时目录后，`D F build windows --release --no-pub`重试退出0（53.0s），产物apps/desktop/build/windows/x64/runner/Release/study_workbench.exe。首次失败仍保留。此次仅源码前端构建，不等于冻结后端组合包/安装器更新或真实窗口验收。
- 最终限定文件 `git diff --check`退出0。原始Flutter输出保留在本聊天工具输出，本批未另行保存完整磁盘日志，不将其冒充共享证据。


## Computer-use验收与PR准备（用户明确授权子代理）

用户要求独立子代理用computer-use真实窗口验收，通过才提交PR，否则修改。已启动r6_ui_acceptance，使用computer-use skill与@oai/sky；隔离数据不接触个人库，原始截图放artifacts/r6-ui-acceptance-20261103/。这不替代用户人工/产品阶段验收。

代码审查复现：GrantInput(confirm=1)原先被Pydantic Literal[True]接受，违背字面确认约定；新增before validator以is True校验，回归包含confirm=1拒绝。`.venv/Scripts/python.exe -m pytest backend/tests/test_agent_access.py -q --basetemp=.local/r6-confirm-20261103 --junitxml=artifacts/r6-pr-20261103/confirmation.xml`退出0，2 passed；定向Ruff退出0。一次在backend工作目录误用根相对.venv命令未运行，改从根目录执行。

PR前置核对：远程PR #2仍open/draft、未合并；head=29f23d3558740545a950a51ca04398f9420088fd。建立.local/r6-pr-worktree，分支codex/r6-local-agent-access，基于origin/codex/unified-resource-import；只复制本任务6份代码/测试及报告，并对原基线5份文档追加R6增量，不提交原工作区未完成文档治理/归档/.vscode/无关工具或集成测试修改。后续PR base为codex/unified-resource-import，明确依赖#2，不擅自合并。

- 全后端 `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r6-pr-full-20261103 --junitxml=artifacts/r6-pr-20261103/backend.xml`：pytest退出1，217 passed/1 failed；唯一失败test_reparse_points_rejected在cmd mklink /J建隔离测试junction时Access is denied，尚未进入安全拒绝断言。后续Ruff退出0（组合shell最终0不是pytest通过）。保留JUnit，申请工具权限在独立PR工作树重跑全套，不跳过/删除断言。

- 独立PR工作树全量重跑：绝对路径既有.venv Python执行`-m pytest backend/tests -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/r6-pr-full-elevated-20261103 --junitxml=D:/computer_work/project/StudyWorkbench/artifacts/r6-pr-20261103/backend-elevated.xml`，所需权限运行，218 passed（137.04s），退出0。保留Starlette/AnyIO告警。PR工作树backend/tools Ruff和git diff --check退出0。

子代理初次状态：隔离配置Windows构建成功（51.2s），匹配源码后端；TestClient准备2条自编作答，before.json保留。sky.list_windows初始化成功，但sky.launch_app挂起238.4秒后中止，尚未取得窗口/截图，不能计通过。主代理要求改用Start-Process启动已构建隔离app，再由sky控制真实窗口；不重建、不触碰个人实例。


### 本次验收结论：环境阻塞，未创建PR

子代理真实窗口自动化使用computer-use skill（C:/Users/陈俊豪/.codex/plugins/cache/openai-bundled/computer-use/26.1027.30824/skills/computer-use/SKILL.md）。启动受限进程无窗口后，主代理以所需权限Python Popen从Release目录启动隔离配置，返回PID8148；系统查询MainWindowHandle20973574、标题StudyWorkbench、SessionId1，sky.list_windows亦识别该窗口。

但是sky.get_window_state({include_text:true})挂起152.6秒后由主代理中断；include_text:false/include_screenshot:true纯截图亦挂起44.6秒后中断。15秒工具timeout及20秒Promise.race均未及时终止底层调用。没有返回截图/控件树，没有点击授权流程；仅确认测试app启动，不确认任何业务交互通过。隔离TestClient准备数据为2条测试作答，不是UI验收结果。

原始诊断见artifacts/r6-ui-acceptance-20261103/acceptance.md及before.json。没有可用于晋升evidence的验收截图。未关闭用户已有程序，未操作个人学习数据。没有将自动化结果替代真实窗口结论。PR条件尚未满足，因此独立工作树仅准备，未commit/push/创建PR，未合并/发布。后续需恢复computer-use窗口状态/截图能力后继续该切片验收；失败则修复复验，通过后提交以#2为前置的PR。本次已修复代码审查确认校验缺陷（数字1不再视作true），2项定向与独立PR树218项全后端均通过；其他历史未验项不清除。

### 用户授权SmartScreen后的复验

用户明确允许对已确认本次测试程序点击更多信息/仍要运行，并要求重验。沿用独立子代理，Node重置和sky初始化成功，最初未见StudyWorkbench/SmartScreen。主代理所需权限Python Popen启动同一隔离配置，PID31772；系统查询窗口20318154、Responding=True，sky独立list_windows在2.3s返回同窗口。随后activate_window在20秒工具timeout下仍挂起，75.4s后主代理中断；本轮未进入capture/点击，未观察到SmartScreen，不能判通过。原acceptance.md追加保留失败；无代码新增，不重跑既有自动化，不创建PR。已询问用户其SmartScreen更多信息中的实际应用名，需区分StudyWorkbench与CUA控制组件是否被拦截；这目前仅是待核对方向，不能认定SmartScreen导致挂起。

用户补充SmartScreen更多信息应用名为study_workbench.exe。子代理据此再次fresh list_windows（3秒）仅返回测试窗口20318154，未返回SmartScreen/安全模态；跳过activate，直接纯截图仍在36.9秒后被主代理中断，未取得任何画面或业务点击。不能认定SmartScreen导致CUA挂起；未更改安全设置，验收仍环境阻塞，不创建PR，旧失败继续保留。


### 最终复验：用户手动放行后核心切片通过

用户手动打开本次exe并选择仍要运行后，独立子代理fresh选取句柄658114，截图/激活/输入恢复正常。先从设置页核对隔离数据根.local/r6-ui-acceptance-20261103，读取现有2条自编作答；app.so SHA256=07A66091EC47AEE3CB2187898BF11838265BA011A381096027A180E0E5E80458。未将恢复相关性当作已证实的SmartScreen根因。

实际窗口通过：未选时确认禁用、取消关闭、单选确认后不自动读取、另行读取仅#2、Escape与外部点击不能关闭活动授权、撤销清空摘要并返回选择、多选两条读取、撤销并关闭、重新打开无选择/授权/摘要残留、Tab/Space选择。UI前后均2条且原分数/时间保持。随后只读SQLite核对before.json：2条作答ID/题目/响应/原始状态与分数/时间/版本/幂等键逐值保持，命令退出0，after-check.json仅本机artifacts。

结论：独立代理computer-use核心切片通过，未发现阻断bug，满足用户本切片提交PR条件。不是独立人工批准或完整R6/产品阶段验收。未实测完整5分钟过期、故障注入、100条边界、多屏DPI、安装器/干净机；过期/故障等自动化覆盖与真实交互分开。窗口留在无活动授权的历史页，未关闭用户程序。

原始步骤/6张截图见artifacts/r6-ui-acceptance-20261103/acceptance.md，旧失败不删除。主代理逐张检查并仅晋升no-selection.jpg和single-summary.jpg，来源/hash/筛选理由见[evidence说明](evidence/README.md)，不包含个人数据或令牌。6份功能代码/测试与独立PR工作树逐字节一致。准备提交以PR #2分支为base的独立R6 PR，不合并、不发行。


### PR交付

已创建[PR #3](https://github.com/surface-user/StudyWorkbench/pull/3)，非草稿，base=codex/unified-resource-import（未合并#2），首个远程head=2ce2985b105327daef93a0d825a4b57ec0dac4b5。本地功能提交d690dcfb8a3d14d8a1d2222daf92aab003d84389，15项blob及完整tree 9c3b26cbb9a85d92f486a13ddf895ad4197ef77f逐项相同；提交元信息不同不代表代码差异。追加本节后仅报告/任务状态变化，功能代码不变。

首次组合commit/push在执行前被自动审批拒绝：目的仓库可信性未核实；未绕过拒绝。随后GitHub连接器核验当前用户id205941432与仓库owner相同，visibility=private、admin/push=true、clone_url匹配origin，获准推送。但git push两次退出1，github.com:443连接超时。转用既有GitHub连接器上传同一批审查内容，核对所有blob SHA及tree，创建commit/branch/PR，并已attach_artifact。未提交数据库、原始日志、个人资料或无关文档治理。

首次head的PR CI已查询：[运行41559053107](https://github.com/surface-user/StudyWorkbench/actions/runs/41559053107)，排队中，不能记通过。追加记录后的最终head/CI以PR实时状态为准；报告和任务保留待交付，不宣称合并或产品阶段通过。用户人工、发行/干净机及完整R6继续待验。本次未合并/发布。
