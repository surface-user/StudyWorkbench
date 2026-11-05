# LW-08 授权与外部候选审核（无模型）

2026-11-05，用户明确选择“先完善授权和审核，暂不接模型”。本轮不接Ollama/远端、不查询/下载模型、不配置凭据；此前Ollama官方协议调研不构成接入授权。本功能是LW-08/R6剩余能力的同一任务，独立扩展报告引用[原R6切片](../2026-11-03-r6-agent-access/report.md)，不重复统计或清除原PR/窗口/失败义务。仅本地开发/自动化/自审，不要求本批提交或新PR，未授权推送/合并/发行。原始产物artifacts/lw08-20261105/。

## 需求与分步设计

1. 旧授权默认仍仅作答摘要，1–100个显式同空间ID、1–900秒、内存且重启失效。新增严格布尔include_content=false，只有用户另勾选才读取所选作答正文及当时确认版题目/参考答案；不读取最新人工评分/学习事件/笔记/二进制附件，不扩大到同题其他作答。旧无版本作答明确未知，不用当前题目冒充当时版本。
2. 受控分析上下文返回稳定引用/版本及hash；确认版复用既有version_read校验MD/编译metadata，附件只列ID/MIME/大小/hash元数据且明确未读取。整体UTF-8 JSON≤1MiB、单作答正文≤64KiB；超过则完整拒绝并要求减少选择，不静默截断或自动打开引用。复用版本读取，读前/读后重验授权期限/空间；撤销与读取串行，不把一次读取视作永久权限。
3. 普通UI展示只读上下文，用户手工粘贴候选分析文本并提交“待审核草稿”。不产生模型回复或假AI来源；来源固定外部候选/未验证，自填来源说明也不升级验证等级。草稿记录上下文hash及授权引用，不保存grant_id、会话token、正文上下文镜像或任何模型凭据。
4. 新增0016 analysis_review_drafts用于持久候选/修订/状态/失败与采用收据；继承workspace隔离、预算、幂等。草稿最多16000字符/64KiB，title≤200、来源说明≤200；默认pending，拒绝只标rejected不删除。更新/拒绝/采用均须expected_revision与payload hash，避免审核A后保存B。
5. 采用由普通UI单独确认，复用自由MD创建及DocumentFiles乐观保存/收据，不修改题目、标准答案、评分或原作答。确定性创建请求绑定draft ID；候选正文用足够长的代码围栏作为字面文本，附来源与ID/hash引用。先保存adopting收据，再创建/保存独立笔记，最后登记adopted结果；中断不自动覆盖或重放，失败保留草稿/已建笔记，重试仅接受同参数且核对初始/预期已写hash；遇到用户编辑/未对账保存则冲突，等待处理。
6. 采用不需要再次读取源或依赖尚未过期的grant：引用/候选已在授权有效时提交，后续是用户审核自己的持久草稿。授权撤销不能撤回已明确保存的候选；UI说明这一点。模型没有采用工具或业务Bearer；当前根本不接模型，审核在普通程序之外置于明确确认步骤。
7. 0016须纳入完整库备份/恢复（含pending/failed/adopted、MD和关系/收据），保留旧版本/失败；默认摘要兼容、严格确认、跨空间/过期/撤销、预算、未知历史、草稿冲突、失败/重启/幂等与原答案/作答保持分别测试。实际窗口/用户/阶段仍待验。

以上为实施设计，不把未接入接口或模型能力写成当前已实现。先实现读取授权，再实现持久草稿/独立采用及UI；更新各自现行契约，不把本报告整段复制到docs。


## 实现与自审

已实施AgentAccess扩展及read-analysis-context；旧read-attempts始终只返回摘要。确认版复用version_read核验MD/元数据，但不调用附件字节读取；历史未知不回退当前缓存。上下文按固定排序/规范JSON计算hash，单条/整体超限413；二进制未读，不含后续人工评分。所有新路由仍由app的Bearer/Host/Origin统一鉴权。

0016新增analysis_review_drafts与append-only analysis_review_revisions；AnalysisReviews普通业务保存外部候选，不含模型/网络代码。创建幂等不依赖旧grant继续有效，但新创建必须重新读取同hash授权上下文；同请求内容改变409。编辑/拒绝/采用绑定revision/hash，拒绝保留；已有采用收据后只接受原参数重试。DocumentFiles.save_text从原PUT路由原样抽出复用，不引入另一套文件保存协议。采用先记adopting、确定性创建MD、检查初始/预期hash并乐观保存，最后adopted；失败/重启追加审核快照，保留候选/部分笔记，不覆盖用户编辑。所有外部候选、来源自填及引用文本置于足够长围栏，不执行Markdown图片/指令；采用仍标未验证。

桌面学习页新增“分析候选 / 独立审核”，原授权弹窗增加默认未选的正文选项及本地上下文/手工候选入口。可显式展开只读上下文，不发送外部；持久列表分页、待审编辑、拒绝、修订查看、独立采用确认。采用失败重试锁原请求，已建笔记资源ID可在树查找。编辑器在退出/整库备份/迁移前登记刷新；并发刷新合并同次保存，失败保留文字并取消退出；关闭默认保存，也可另行明确放弃窗口未存编辑。创建响应未知时固定原请求重试，不默默换幂等键；明确放弃说明服务器可能已保存，须到列表核对。授权过期不会自动续期或扩大范围。

自审补丁：重启adopting转failed也追加修订；幂等返回先校验现存候选hash；备份除表/字节摘要外检查候选hash、作答/确认版同空间引用、采用笔记关系及连续审核修订/快照hash；修订使用游标流式检查，不按不可信revision分配大列表。上述是原任务修补，不新增契约平行文件或依赖。

## 自动化记录

以下P=.venv/Scripts/python.exe（开发Anaconda3.12.7），Q=.local/release-venv/Scripts/python.exe（发行CPython3.13.17），D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F=同SDK的bin/cache/flutter_tools.snapshot。Python工作目录仓库根；Flutter工作目录apps/desktop。PYTHONIOENCODING=utf-8；Flutter TEMP/TMP固定仓库.local/tmp、NUGET_SCRATCH=.local/nuget-scratch；测试及构建只用项目隔离库。原始日志/JUnit在artifacts/lw08-20261105/，不进Git。

- P -m pytest backend/tests/test_analysis_context.py backend/tests/test_agent_access.py -q --basetemp=.local/lw08-context-20261105-01 --junitxml=artifacts/lw08-20261105/context-01.xml：退出0，7通过，7.21秒；默认兼容/严格bool、历史确认版、未知版本、预算、跨空间/撤销/读取中到期、损坏MD及原记录保持。
- P -m pytest backend/tests/test_analysis_context.py backend/tests/test_analysis_review.py backend/tests/test_document_files.py -q --basetemp=.local/lw08-review-20261105-01 --junitxml=artifacts/lw08-20261105/review-01.xml：退出1，18通过1失败，34.41秒。测试误将POST最小作答响应与GET详情比较；保留失败，改为操作前/后同GET详情完全相等，并另验创建ID存在，未降低不改作答断言。
- 上条改独立root/xml为02：退出0，19通过，33.84秒。覆盖无模型网络断言、原答案/作答保持、采用单独严格确认、幂等、修订冲突/拒绝、跨空间/Origin、失败后用户编辑不覆盖、保存后崩溃/重启去重、全库pending/adopted/修订恢复及grant不恢复。
- P -m pytest backend/tests/test_analysis_review.py -q --basetemp=.local/lw08-review-20261105-03 --junitxml=artifacts/lw08-20261105/review-03.xml：退出0，9通过，9.25秒；追加候选hash/引用/笔记关系损坏备份拒绝、源库字节不变。
- P -m pytest backend/tests/test_analysis_review.py backend/tests/test_analysis_context.py -q --basetemp=.local/lw08-review-20261105-04 --junitxml=artifacts/lw08-20261105/review-04.xml：退出0，15通过，12.16秒；再加历史修订身份损坏拒绝。该次后将修订遍历改为流式，最终完整回归另记。
- P -m pytest backend/tests -q --basetemp=.local/lw08-backend-20261105-01 --junitxml=artifacts/lw08-20261105/backend-01.xml：退出0，460通过，279.14秒；这是首版审核6用例的快照，后续审计/备份负面补丁不能冒充已在本次覆盖。
- 同全量命令root/xml改02：退出1，462通过1失败，297.81秒。test_office_previews.py::test_owned_process_is_killed_on_cancel_and_owner_exit[False]读取PID标记时文件已存在但尚为空，int('')失败；不是Job未杀进程的结论。夹具改为临时文件写完整PID后os.replace原子发布，不删用例、不改杀进程断言/期限。
- P -m pytest backend/tests/test_office_previews.py -q --basetemp=.local/lw08-office-20261105-01 --junitxml=artifacts/lw08-20261105/office-01.xml：退出0，13通过，24.78秒。完整开发/发行环境回归继续后列，原失败保留。
- D F --suppress-analytics test --no-pub test/analysis_review_dialog_test.dart test/agent_access_dialog_test.dart：flutter-review-01退出1，3通过2失败。旧授权精确map需新增include_content=false断言；新审核测试误用ensureVisible寻找尚未构建的懒列表项。修正为精确断言新默认值及真实scrollUntilVisible，未弱化确认/内容断言。flutter-review-02退出0，5通过；添加审核历史等UI后flutter-review-03退出0，5通过。
- Flutter全量命令D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw08-flutter：flutter-full-01退出1，147通过1失败，44秒；审核小窗口新增操作后标题输入不在实际视区，先滚到输入再录入。改fresh root为lw08-flutter2，flutter-full-02退出1，147通过1失败，49秒；拒绝成功后状态位于已滚出顶部，保持原状态断言、补滚回顶部。root=lw08-flutter3的flutter-full-03退出0，148通过，47秒。覆盖并发刷新一次提交、文字/原请求保持、明确采用/拒绝及600×450无溢出，不等同真实窗口。
- D F --suppress-analytics analyze --no-pub：analyze-01退出0（31.9秒）、analyze-02退出0（11.4秒）。D format及单文件curly修复只整理对应新增Dart。
- D F --suppress-analytics build windows --release --no-pub --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw08-window/data：windows-01退出0，61.0秒；隔离构建，不是默认profile/安装验收；现有CMake CMP0175开发警告保留。
- Q -m PyInstaller --noconfirm --clean --distpath artifacts/lw08-20261105/frozen/dist --workpath artifacts/lw08-20261105/frozen/build artifacts/lw08-20261105/frozen/spec/study_backend.spec：frozen-01退出0，109.2秒；spec沿用既有固定依赖与metadata/collect策略，无新增运行依赖。
- P tools/check_learning_workbench.py --exe artifacts/lw08-20261105/frozen/dist/study_backend/study_backend.exe --test-root .local/lw08-window --media-fixture artifacts/lw09-20261104/fixture.webm：frozen-flow-01退出0。除原学习闭环，新增默认摘要授权、外部候选、独立MD采用、未验证/字面内容、重启原收据幂等及整库恢复同候选/笔记断言；SQLite语义hash060e70686ae78468097220405742cc74de92547e93bbd5d76c1c7b7169866448，原件字节保持。固定下载子进程拒绝HTTP也通过，无实际公网下载或播放。最后审计流式校验修补发生在此包之后，最终包另记，不混用版本。
- P -m ruff check backend tools：退出0；P tools/export_question_schema.py --check：退出0，后续终检另记。

## 状态与下一步

本地实现/自动化/自审继续推进，不接任何模型、模型枚举/下载、远端凭据或传输。当前实际窗口仍受Computer Use启动超时阻断，未再次盲目尝试；用户/阶段验收、installer/干净机、PR/当前head CI未执行或未知，未提交/推送/合并/发行。LW-08保持进行中/待验，既有R6 PR #3义务单独保留。下一步完成最终版本双Python全量、冻结与文档一致性，再等待真实窗口条件恢复后按授权审核逐项验收。


## 后续边界复核与最终版本

继续同任务自审，没有接模型。补上精确总预算（最终context_sha256字段也计入1MiB）、附件只给元数据/禁止附件读取断言、实际adopting中断后的启动审计、成功采用前保留adopting修订。未知采用结果锁定窗口编辑、重试原参数，重开失败收据显示原文件名；未知创建明确确认后可放弃窗口，不删除可能已存候选。授权上下文404与摘要404统一回到重新确认。

采用后的笔记提供“打开已建笔记”，通过普通节点接口重验ready/移除状态，逐层关闭审核/授权对话框再交给原资源导航；不要求用户用资源ID找文件。失败审核允许明确拒绝，保留已建笔记/原采用参数/结果/错误和历史，拒绝后禁止重试采用，避免不可恢复失败只能永久悬挂。普通UI同样需在列表重新核对失败状态后处理，不把未知响应当作已完成。

新增历史边界用例先错误调用不存在的GET question/file：context-02退出1，7通过1失败，7.37秒；改为读取测试库已有QuestionFileRecord定位节点，未新增产品API。context-03与context-release-01分别退出1，7通过1失败（9.15/8.37秒），原因为夹具缺少普通用户显式建立working-copy，PUT正确拒绝409；补复用既有working夹具，不放宽保存门禁。随后P -m pytest backend/tests/test_analysis_context.py backend/tests/test_analysis_review.py -q --basetemp=.local/lw08-review-20261105-08 --junitxml=artifacts/lw08-20261105/review-08.xml退出0，19通过，16.71秒：新确认版、后续人工评分和备注均不改变原授权上下文/hash。

中间回归保留：backend-03（root .local/lw08-backend-20261105-03）464通过299.99秒；release-01（.local/lw08-release-20261105-01）464通过273.22秒。backend-04为467通过299.43秒，release-02为467通过273.48秒；均退出0，发生在最后“失败可拒绝”修补之前。review-05为11通过12.62秒，review-06为18通过14.84秒，review-07为18通过15.90秒，退出均0，分别见同名JUnit。Flutter-review-04至07均退出0，最终定向10项覆盖独立正文勾选/过期、未知响应、明确放弃、失败收据和已建笔记打开；Flutter-full-04退出0，152通过48秒，full-05退出0，153通过44秒。analyze-03退出0（11.7秒），analyze-04退出1（9.4秒），仅新增测试FakeBackend一处if缺大括号；单文件dart fix后终检通过，不忽略规则。windows-02/03分别退出0，61.4/54.0秒，仍各自固定隔离目录。frozen-02退出0（107.5秒），frozen-flow-02退出0，行摘要df92a04503279a0fb356ba57e0fa85caa59acd49194f8ef40b384cdb411b127a；保留该包，不将其当作最后失败拒绝补丁版本。

### 最后验证命令与结果

以下命令均实际运行；Junit/log与命令中的同一批次对应。Python完整测试仍保留Starlette/anyio弃用警告，Windows保留CMake开发警告，没有删除断言或跳过失败项。

| 命令（工作目录与缩写同上） | 退出码 | 结果/产物 |
|---|---|---|
| P -m pytest backend/tests -q --basetemp=.local/lw08-backend-20261105-05 --junitxml=artifacts/lw08-20261105/backend-05.xml | 0 | 468通过，318.47秒；backend-05.log/XML |
| Q -m pytest backend/tests -q --basetemp=.local/lw08-release-20261105-03 --junitxml=artifacts/lw08-20261105/release-03.xml | 0 | 468通过，297.14秒；release-03.log/XML |
| D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw08-flutter6 | 0 | 153通过，50秒；flutter-full-06.log |
| D F --suppress-analytics analyze --no-pub | 0 | 无问题，13.0秒；analyze-05.log |
| D F --suppress-analytics build windows --release --no-pub --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw08-window-delivery/data | 0 | 62.1秒；windows-04.log；不读取个人默认库 |
| Q -m PyInstaller --noconfirm --clean --distpath artifacts/lw08-20261105/frozen-review-final/dist --workpath artifacts/lw08-20261105/frozen-review-final/build artifacts/lw08-20261105/frozen/spec/study_backend.spec | 0 | 114.1秒；frozen-03.log；保留前两包 |
| P tools/check_learning_workbench.py --exe artifacts/lw08-20261105/frozen-review-final/dist/study_backend/study_backend.exe --test-root .local/lw08-window-delivery --media-fixture artifacts/lw09-20261104/fixture.webm | 0 | frozen-flow-03.log；既有学习/JSON/XLSX/媒体导入/重启/整库恢复、独立采用及失败后拒绝保留收据全部断言通过 |

冻结最终闭环额外使用自编不存在父目录使采用返回404，断言failed及原参数收据保留，再由普通reject操作关闭候选，旧采用重试409；恢复后同候选/收据完全一致。此负面样本不改用户目录、不增加故障注入产品接口。最终SQLite语义hash076c9d14fa7334d6f7770026efc8c0bf292335481f7862ec3d99f10a76df46c4，材料源字节保持；实际公网下载、播放窗口、用户与阶段flag明确false。

最后备份用例包含pending/adopted/failed/rejected四种持久状态、采用笔记及append-only历史，源/目标SQLite行相等且grant不恢复。实现无新增第三方依赖。完整调用退出码已从后台进程收取，未留正在运行的本批验证任务。

最终隔离window-bundle含1161文件、198647252字节，逐文件SHA256在artifacts/lw08-20261105/window-bundle-hashes.json，绑定HEAD 29f23d3558740545a950a51ca04398f9420088fd及明确未提交脏树、隔离数据目录；source-sha256.json含109个运行源码/迁移/本地验证工具hash。仅打包未启动窗口，actual_window_verified=false，不是安装器/发行包。完整artifacts/与.local/保持Git忽略，不复制到evidence或清理旧失败。

自审完成范围：前端授权/模态退出/资源打开与后端范围/预算/幂等/审核状态、文件保存收据及备份引用联动。未做独立人审，不把自动化当用户批准。当前本地实现和上述自动化通过，人工窗口/用户/阶段仍待验；Computer Use启动通道仍阻断，未盲目重试或改系统设置。模型/凭据/通用资料工具后排，后续新增模型须再确认；原R6 PR #3/当前head CI义务未清除，未检查远端CI、未提交/推送/新建PR/合并/发行。

文档终检还清理README和Agent文档旧“下载/恢复未实现、始终只读摘要”描述，按当前代码区分授权/审核与规划模型，不为同步计数重写无关规范。路线仅补用户11-05缩小首批目标，进度计数留task/本报告。终检文档/源格式及保护证据结果另附下面。


终检：P -m ruff check backend tools、P tools/export_question_schema.py --check、git -c core.safecrlf=false diff --check均退出0。P artifacts/lw08-20261105/check_docs.py退出0：51份当前/任务Markdown、246本地链接、7标题锚点、15原任务报告，114份受保护旧文件hash全部不变，未出现doc平行目录。R6 task仅更新与本任务相关的实现指向和PR历史/当前未知边界，原自动化/自审/人工列逐字保持；7aa8251和原PR依赖/链接继续保留，不冒充当前head。

逐项重算window-bundle全部1161文件与source-sha256的109文件均匹配；verification-summary.json核实末轮双Python各468项、失败/错误/跳过均0。git check-ignore确认测试库及原始JUnit受忽略；HEAD仍29f23d3558740545a950a51ca04398f9420088fd，整个继承脏树保留，未提交/推送。当前源码没有在此后修改；最终格式引擎复核继续写LW-06原报告，不在此重复记录。下一步为授权/审核真实窗口与独立人工验收、原PR当前head/CI交付核验；模型暂缓不自动恢复。

最终真实格式复核补充：LW-06当前0016冻结DOCX未生成PDF，组件目录出现MDMP转储，随后Calc被清单门禁拒绝；失败与根因待定位见[LW-06原报告](../2026-11-04-lw06-formats/report.md)。本报告的授权/审核和冻结业务闭环通过仅限已列范围，不能表述为所有组件集成通过。未修改源代码或豁免该失败。
