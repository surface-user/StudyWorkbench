# R5完成批：笔记关联与知识点投影

2026-10-29，在[R5首批](r5-records-2026-10-29.md)基础上完成剩余实现和审查。人工、阶段、普通用户及干净机仍待统一验收。本批隔离数据、自编样例，不读取个人库、不创建子Agent、不替换dist/StudyWorkbench-current、不提交/发布/合并。决策见[ADR0011](adr/0011-learning-record-projections.md)和[R5设计](r5-design.md)。

## 完成行为

事件新增可选note_id/knowledge_points。笔记从同空间列表分页选择、显式关联，关系绑定稳定ID而非名称；详情可打开相关笔记内容和受保护图片。每条作答最多100份不同笔记；丢失或空间不匹配只显示缺失，不清理事件。受控GET .../attempts/{id}/notes/{note_id}同时检查空间/作答归属、事件关系、笔记存在及空间。笔记是当前内容关系，不伪造历史笔记快照或文件节点。

知识点修订仅是记录标签：省略/null不修订，[]明确清除；最多100个独立非空名称，每项500字符。record.knowledge_points保持作答时确认版原值；effective_knowledge_points从完整事件流取最后一条明确修订，没有修订则取确认版，旧无版本不补造。即使请求早期历史页，投影仍基于完整事件流。算法latest-explicit-annotation-v1，可跨重启重算。

reviewed_count按复习事件数重算，相同request_id重试只计一次。自评、复习点击和标签修订不重判答案、增加正确连击或改待批改状态。掌握/到期继续从实际Attempt及最新人工Review按attempt-review-streak-v1重算，不保存不能还原的最后掌握值。题目统计按当前题目分类；记录标签与题目知识点分别显示，不以修订记录偷偷改标准题目。

同一事件重试兼容旧事件中null与省略字段；相同request_id但不同内容409。关联笔记删除后，原成功请求仍返回原事件；不会因重试补写/覆盖旧关系。未知版本、当前MD/来源缺失、快照读取失败分别保留历史并提示，受保护快照及附件继续复用R4校验。

## 验证命令与实际结果

证据：[evidence/r5-final-20261029](evidence/r5-final-20261029)。Python命令从仓库执行。Flutter实际使用固定D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe调用flutter_tools.snapshot，cwd为apps/desktop；Windows先执行tools/prepare-windows.ps1并将.local/bin加入本进程PATH。

| 命令 | 实际结果 |
|---|---|
| .venv/Scripts/python.exe -m pytest backend/tests/test_learning_records.py -q | 0，3通过，8.94秒；records.log。包含同空间/重复/未知字段、DB不可变、分页/全流投影、关联/清除/缺失/重试/重启、旧统计不变 |
| .venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r5-complete312 --junitxml=docs/evidence/r5-final-20261029/backend312.xml | 0，208通过，252.61秒；backend312.log/xml。迁移回滚/备份、旧行/分数、R4快照及已有Office进程保护回归保留 |
| .local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/r5-complete313 --junitxml=docs/evidence/r5-final-20261029/backend313.xml | 0，208通过，161.31秒；backend313.log/xml |
| flutter test --no-pub | 0，83通过/2跳过；flutter-final02.log（最后逻辑增量复测），flutter-final.log为此前同数回归；flutter-records02.log为组件1通过 |
| flutter analyze --no-pub | 最终analyze-final03.log；此前analyze-final.log已无问题，后续错误恢复分支的格式提示亦保留在analyze-final02.log |
| flutter test integration_test/learning_records_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/r5-complete-native01 --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/r5-final-20261029 | 0，1通过，Windows编译68.2秒/交互7秒；windows.log。选择关联笔记、明确修订两项标签、追加关闭、重开阅读、完整原作答精确不变；截图只含自编内容 |
| flutter build windows --release --no-pub | 0，60.4秒；release.log。源码编译不等于组合包/安装器验收 |
| .local/release-venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath .local/r5-frozen/dist --workpath .local/r5-frozen/build .local/r5-frozen/study_backend.spec | 0；freeze.log，复用既有收集配置，独立新目录，不覆盖旧包 |
| .venv/Scripts/python.exe tools/check_question_files.py --test-root .local/r5-source-final01 | 0；source.log；源码真实loopback，R4版本链及R5关联笔记/修订/重启幂等 |
| .local/release-venv/Scripts/python.exe tools/check_question_files.py --exe .local/r5-frozen/dist/study_backend/study_backend.exe --test-root .local/r5-frozen-final01 | 0；frozen.log；PATH仅System32、移除开发PYTHONPATH/PYTHONHOME、cwd隔离，实际关联笔记/标签修订/事件与旧快照跨重启 |
| .local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe .local/r5-frozen/dist/study_backend/study_backend.exe | 0；frozen-lifecycle.log；锁/鉴权/Origin/追加/EOF/崩溃/迁移/原件及媒体保持，不传seed-db |
| .local/release-venv/Scripts/python.exe tools/check_resource_explorer.py --exe .local/r5-frozen/dist/study_backend/study_backend.exe --test-root .local/r5-frozen-resource-final --documents --without-office | 0，frozen-resources.log；当前head0011与旧资源/MD/作答/布局及缺组件回退 |

本批无新产品依赖，原技术栈/固定玻璃库不变。Ruff、Schema --check、Dart格式、git diff --check、本地文档链接和历史迁移/协议哈希见最终审查结果。0011仍是首批同一迁移，完成批不改迁移、不重写旧事件，只扩展受控JSON载荷。

## 失败、审查与边界

首轮flutter.log有82通过/1失败/2跳过：测试期待下拉框提示“关联笔记（可选）”，但null菜单项存在时显示“不关联笔记”。改为稳定控件key并实际选择关联笔记，保留note_id/知识点/同请求重试的全部断言，flutter-records02通过。首轮analyze.log大括号提示修复；均保留日志，不删失败测试、不降低断言。R5首批Windows失败及复核继续见首批记录。本批真实Windows通过不替代人工验收。

审查逐项连接事件输入→同空间笔记→幂等/不可变数据库→全流投影→事件分页→读取快照/当前资源/笔记→控件选择/失败重试，并回测旧学习/资源/迁移调用方。关联笔记只查询同空间，读取再次检查关系；知识点修订不更新原题或旧分数；缺失不自动恢复或删除；无需LLM。

[Windows关联笔记与知识点修订](evidence/r5-final-20261029/learning-record-note.png)已读取图像核对，截图显示笔记正文与追加修订记录。对话框内容滚动，截图并不包含所有顶部信息。

资源/题目导出仍不冒充完整学习数据库备份，事件与关系的独立导出恢复留数据保护专项；无任意删除/事件编辑入口。未运行安装器、普通用户/干净机、完整发行许可/SBOM/签名或人工/阶段验收，未重复R3 LibreOffice实机转换（本批不改转换执行路径）。M0历史缺项、下载队列及完整备份恢复继续保留。下一顺序R6可选Agent辅助，不因R5自动化通过开放越权接口。

最后审查增量：通用请求错误增加兼容HttpException的BackendError状态码；记录页收到明确404/413/422拒绝后保留文本并允许修订，未知网络结果/409仍固定同一请求内容重试。组件测试同时覆盖两条分支，最后全量83通过；后端及冻结内容不变。analyze-final02中的单行if提示补大括号后以analyze-final03为准。最后源码Release复编见release-final.log。

最终复核：双Python全量各208通过，最后Flutter全量83通过/2跳过，analyze-final03退出0且无问题。最后Release复编退出0、48.1秒（release-final.log），与首次60.4秒结果分别保留。冻结资源兼容专项退出0。Ruff、Schema --check、四个最终Dart文件格式核对、git diff --check均退出0；255个本地文档链接和旧迁移/协议哈希核对通过（final-review.json）。新类型错误只细化拒绝恢复，仍兼容HttpException；最终完整组件回归与Release覆盖此增量，Windows笔记/修订成功流程截图来自此增量前同一成功路径。未将静态、组件、原生、冻结、人工或阶段证据混用。
