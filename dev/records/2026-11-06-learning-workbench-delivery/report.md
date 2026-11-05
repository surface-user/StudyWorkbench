# 通用学习工作台阶段PR交付

2026-11-06用户明确授权“这一版先提交pr，提交完之后继续推进task.md任务”。本批允许提交、推送新分支并创建PR，覆盖此前本地积累的LW-00至09及文档治理；不等同人工/阶段验收，不授权合并、发布、删除数据或接模型。旧真实窗口后才PR的顺序针对本次送审由用户新指令覆盖，原窗口待验义务仍保留。

## 基线与范围

远端实际核验：PR #2 open/draft、head 29f23d3558740545a950a51ca04398f9420088fd，base main；PR #3 open/非draft、未合并，head 7aa8251561c548df9d34163f326980bde20200cd，base codex/unified-resource-import。本批独立分支codex/learning-workbench-20261106以#3 head为parent、以已验本地完整源码快照为tree，避免重复R6并保留#2/#3依赖，不改写两个旧分支。

送审内容：自由MD笔记、位置书签/备注、内部链接、集中查找、离线整库备份恢复、受限UTF-8文本/XLSX查看、直接HTTPS媒体队列、无模型本地授权及外部候选人工审核；0013–0016迁移、桌面入口和测试；docs现行规范与dev历史/证据分离。普通业务离线、原件/旧学习数据保留。依用户偏好不接模型/凭据。

.vscode本机设置保留在工作区而不提交；artifacts/.local、个人库、模型、导入原件和下载视频不入库。旧归档/共享证据迁移在提交树中作为保留内容检查，不丢历史失败。

## 已有验证及送审边界

开发/发行Python各468通过，Flutter153通过、静态/Windows Release/冻结学习及人工候选闭环通过，详见[LW-08原报告](../2026-11-05-lw08-authorization-review/report.md)。这是11-05末轮同源码结果，本次未重跑全部测试；实际重算109运行源码/工具SHA256均不变，记录artifacts/pr-workbench-20261106/source-verification.json。

必须保留阻塞：最终Office DOCX未生成PDF并产生MDMP转储，Calc因组件多出未登记文件被完整性门禁拒绝，PPTX末轮未执行，见[LW-06原报告](../2026-11-04-lw06-formats/report.md)；下载公网源受当前DNS负面门禁阻断，见[LW-07报告](../2026-11-05-lw07-downloads/report.md)；Computer Use启动超时、实际窗口/用户/阶段/安装与干净机待验，见[LW-09报告](../2026-11-04-lw09-integration/report.md)。PR采用draft，不请求合并。

## 送审步骤与后续

先验证保护文件/链接、源码hash、暂存范围与敏感文件，再以当前完整源码树生成以#3为parent的单一阶段提交，推送新分支并由GitHub连接器建PR。实际命令/退出码、commit/tree/PR和当前head CI结果在本报告追加。提交完成后优先继续LW-06组件崩溃定位：保留原转储，在新隔离组件目录对照源/冻结进程，不降低校验、不修改个人库；其他任务仍依task与现行契约推进。

送审前实测：git fetch origin codex/r6-local-agent-access退出0；.vscode仅本机路径配置，未暂存。git -c core.safecrlf=false add -A -- .gitattributes AGENTS.md README.md apps backend contracts docs dev tools及暂存diff --check退出0。暂存树412文件/4743126字节、相对#3为235项变化；模式扫描未发现真实密钥样式或长Bearer，禁止路径/数据库/媒体/可执行包断言均通过。运行保护文档检查第一次因LW-01改成用户已授权PR送审状态而失败；仅按用户新授权转换该交付措辞，保留其余原单元格全文相等检查，未豁免失败/验收信息。Ruff/schema检查退出0，运行源码仍109项一致。


实际创建：git write-tree得到ffdd0a1c4924b6a54afcef88c1bb26c77b63c9fb；git commit-tree该tree -p 7aa8251561c548df9d34163f326980bde20200cd -F artifacts/pr-workbench-20261106/commit-message.txt得到c7dc5dddd58ed73dbacd306d0c9e7f59b5c11891；git update-ref以不存在旧ref的零SHA保护创建codex/learning-workbench-20261106，git switch及git push -u origin同名分支均退出0。只剩.vscode未跟踪，无丢失/覆盖继承改动。通过GitHub连接器创建[PR #4](https://github.com/surface-user/StudyWorkbench/pull/4)，draft/open，以#3为base，235变更文件、1阶段提交，未合并/发行。

首head c7dc5dd的PR CI [run 42061516523](https://github.com/surface-user/StudyWorkbench/actions/runs/42061516523)实查进行中：双Python已过Ruff且在pytest，桌面已过格式且在analyze；不是最终通过。提交后的工作继续LW-06，定位到LibreOffice从冻结包继承VCRUNTIME，设计/修补/验证继续[LW-06原报告](../2026-11-04-lw06-formats/report.md)。新增修补验证后跟进同PR，不自动合并。


## 首轮CI失败与路径修补

run42061516523最终双后端job均success（含pytest和R1–R5 HTTP黑盒），desktop失败于Flutter测试：152通过1失败，后续Windows/冻结步骤未执行。日志保留artifacts/pr-workbench-20261106/desktop-ci-first.log。唯一失败backend_process_test.dart首项“isolated restored settings remain selected on a fresh application start”，第13行期望true实际false：仅testData转正斜杠，repository未规范化；CI Resolve-Path给反斜杠，本地前批给正斜杠，导致错误前缀比较。不是后端业务失败，CI缺口确由本地未原样复现参数造成。

用户询问原因后继续按已授权task/PR交付工作使用gh-fix-ci排查流程，通过GitHub连接器取实际job日志。修补只规范化同一个断言两边的路径，不删除“必须在仓库.local中”的保护，不改CI参数或跳过测试。按CI同样的$taskRoot=(Resolve-Path ../..).Path，D F --suppress-analytics test --no-pub --dart-define="STUDY_ROOT=$taskRoot" --dart-define="STUDY_DATA_DIR=$taskRoot/.local/ci-path-before-20261106" test/backend_process_test.dart --plain-name 'isolated restored settings remain selected on a fresh application start'先退出1复现（ci-path-before.log）；改after新profile后退出0（ci-path-after.log）。全量同参数改ci-path-full-20261106退出0，153通过45秒（flutter-full-path.log）；analyze退出0无问题，77.7秒（analyze-path.log，组件复制并行带来机器负载，不降低断言/超时）。当时的静态核对误判未发现硬编码漂移；实际输出截断漏看了check_resource_explorer.py第172行，下一轮CI证实这一遗漏，不能把静态核对当作执行完CI命令链。只提交该测试及交付状态；Office修补仍在工作区验证，不混入此CI修补提交。推送后的当前head CI仍需实际等待。


## 第二轮CI：冻结探针旧schema常量

路径修补提交f0a34e3714e618ed95cf3b4f9ab6f8623c3c97ed已推送。PR run42064343519双后端成功；desktop通过153测试、Windows Release、原生COM和冻结打包，随后Frozen unified resource import and document regression失败：tools/check_resource_explorer.py第172行仍严格断言0012，而当前应用正确升级0016；同脚本末尾汇报字段也写死0012。原日志desktop-ci-second.log保留。这里是探针未随迁移维护，不是把旧库未升级当作通过；先前静态核对遗漏由本报告明确纠正。

保留原整数/关系/hash断言，以Alembic ScriptDirectory读取源码唯一current head，SQLite仍须严格相等，报告revision随实际已核head，不使用>=或放宽列表。复用先前已验、与PR后端代码一致的frozen-review-final包，避免混入尚在验证的Office修改。

P tools/check_resource_explorer.py --exe artifacts/lw08-20261105/frozen-review-final/dist/study_backend/study_backend.exe --test-root .local/pr4-resource-before-20261106 --documents退出1复现原schema断言（resource-before.log）；修补后改独立root .local/pr4-resource-after-20261106，退出0（resource-after.log），验证5节点/原件去重/文档/墓碑/布局/历史/重启/SQLite完整性和FK，schema0016。

完整执行该失败步骤及其后CI命令：新建项目.local/pr4-lifecycle-real-20261106和指向它的pr4-lifecycle-alias-20261106 junction，将TEMP/TMP设alias；P tools/check_backend_lifecycle.py --exe同一冻结包退出0（lifecycle-after.log），独占锁、鉴权/Origin、中文主观与客观题、EOF、重启/崩溃恢复和迁移父EOF取消通过。P tools/check_document_workers.py --exe同一包退出0（document-workers-after.log），DOCX/PDF真实离线worker、文字/图片/公式/页及编号/跨页拆分通过。驱动实际收取resource_exit=0/lifecycle_exit=0/workers_exit=0，不仅查看日志。Ruff与暂存diff检查另做后才推送；不改工作流、不跳测试、不更新尚未验证的Office运行代码。新的PR head须再实查全CI，保留两轮红灯及本地先红后绿。

当前已送审head 54ad12b51b0d5bc2c8d2e4d71e42926ab4e86135的PR run42068871152三个job全部success，GitHub实查确认；两轮失败保留。PR描述已据此更新，不改commit/不合并。Office新试验尚未提交，不能混称该head已包含或解决组件问题。


## PR后继续：Office隔离启动与深目录修补

按用户原授权继续LW-06，已在原任务报告记录两项原因及最小修补：冻结组件DLL继承由独立受控helper清理自身，外部组件深profile路径使用samefile确认的短名。修补后双Python各476通过，新冻结包真实DOCX/PPTX各2页、Calc、四页页图、完整CI冻结三项探针、R1–R5 HTTP及授权审核/整库恢复闭环通过，实际命令和退出码收取边界见[LW-06原报告](../2026-11-04-lw06-formats/report.md)。没有将54ad12b的绿灯套用到新代码；本次推送后的当前head CI仍需GitHub实际核对。旧Office失败、原组件转储、两次红CI和窗口/人工/安装待验保持，不合并/发行、不接模型。
