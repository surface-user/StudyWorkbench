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
