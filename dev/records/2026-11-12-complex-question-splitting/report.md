# PAR-01：复杂题号与显式共享材料候选

## 范围、设计与状态

基线为调度草稿PR #23的2645366ca4f37cced53f41119ccebd732239a123，继承#22全部代码及历史记录。仅修改此任务的隔离副本；根工作区和其他并行任务不变。IN_PROGRESS领取后实施，相关自动化通过后进入REVIEW，由主Agent核验交付证据及当前head CI才可DONE；代码审查依ADR0014暂缓，人工/Computer Use取消，未授权合并/发行。

原Word按文本块、PDF按页内坐标分别拆题，只识别阿拉伯数字题号，材料只能手动选块归组。此任务将题号/分组状态复用到两个入口：增加第N题的规范中文一至九十九及【N】，保留原数字点/顿号形式。括号小问、章节“一、”、小数不新建候选；重号保留不同候选并警告，不按题号覆盖。任意数字列表和题干含义无法仅凭语法识别，仍须用户核对。

共享材料仅识别契约列明的中英文显式范围标题。先收集标题后至首题的材料，验证后续题号与范围完整有序、不缺失不重复且不超200道，再关联候选；不满足则警告并保留整篇预览。未增加模型、OCR或新依赖。跨页PDF材料和题目各保留独立裁图/页码/区域；Word只声称内容顺序。材料ID按同次解析出现顺序生成。预览、修订摘要、显式确认、幂等重试、源hash校验均沿既有流程；不猜答案，不改原文件或已确认题目。

影响范围：question_splitting.py共用规则；documents.py的Word/PDF调用和合并内容预算校验；imports.py将新解析任务版本改为builtin-4-grouped-md；markdown_questions.py补充MD导出中的材料页码/区域元数据。既有手动归组/合并/裁图调用无需更改接口，仍由回归验证。测试新增自编DOCX/PDF及纯文本样本；契约更新question-markdown-spec.md；任务表只改PAR-01两行。数据库、桌面UI、配置及导出路由无变化。

## 样本与验收证据

- 正常/反例：第十一题、【12】、括号小问、小数、中文无效序号、重复题号、两组重置编号、不同换行符；题号范围缺失/重复/乱序/反向/零起点/超限/无题拒绝自动关联。
- 自编真实Word由既有自编样本添加显式材料标题，保留公式/表格/图片；真实PDF包含跨两页材料以及第二页两道题。验证候选无提前索引、共享材料相同、原图/区域边界、显式改标题后旧摘要409、确认重试幂等、入库后编辑409、导出相对图片/源hash/材料区域、重启后确认重试和原件字节不变。
- 沿用原Word自动编号、跨页PDF题目、手动归组/合并/拆分/裁图、坏包/超时、工作空间隔离和原件保留测试。材料+题目合并后继续受原Content 200块预算限制；题数/材料组数各有200上限。8MiB原件、20页PDF、25秒解析、64MiB图片总预算保持。

## 实际命令与结果

工作目录：项目下.local/goal-20261112/parsing。Q为根.local/release-venv/Scripts/python.exe（Python3.13.17），P为根.venv/Scripts/python.exe（Python3.12）。原始日志/JUnit只写本副本artifacts/par01，不入Git，不包含用户资料。

1. Q -X utf8 -m pytest backend/tests/test_complex_question_splitting.py backend/tests/test_markdown_questions.py backend/tests/test_documents.py backend/tests/test_draft_editing.py -q --junitxml=artifacts/par01/target-first.xml：退出1，16通过/14准备错误。默认Windows临时目录创建失败，尚未运行依赖tmp_path的用例；target-first.txt/xml保留。
2. 同命令改--basetemp=.local/par01-target02：退出1，16通过/14准备错误；新隔离副本尚无.local父目录，准备目录失败，target02日志保留。随后显式创建副本内.local父目录，没有改测试断言或替换平台mkdir。
3. 同命令改--basetemp=.local/par01-target03、target03.xml：退出0，30项通过，59.95秒，既有Starlette弃用警告保留。
4. Q -m ruff check相关四实现文件及新测试：首次退出1，仅新测试函数内导入排序；排序修正后Q -m ruff check backend tools退出0，All checks passed，ruff.txt保留。
5. P -X utf8 -m pytest同四文件 -q --basetemp=.local/par01-target312 --junitxml=artifacts/par01/target312.xml：退出0，30项通过，95.31秒，Python3.12.7，既有弃用警告保留。
6. git -c core.autocrlf=false diff --no-index --check ../base/backend/study_workbench/question_splitting.py backend/study_workbench/question_splitting.py：退出1，无错误输出（no-index文件不同）；不记为退出0，空白检查另按最终明确文件执行。

7. Q -X utf8 -m pytest -q --basetemp=.local/par01-full313 --junitxml=artifacts/par01/full313.xml：退出1，711通过、12失败、77子测试通过，586.55秒。12项均为既有Windows junction/hardlink或元数据只读测试，失败trace包含链接创建拒绝/受限进程文件访问差异；所有解析新增及原用例通过。完整full313.txt/xml保留。
8. 为定位上述运行环境差异，按原断言在获准的任务隔离目录原生执行备份1项（native01，退出0，2.43秒）、恢复/下载3项（native02，退出0，3.29秒）、Explorer/巡检/Office3项（native03，退出0，4.12秒）。全量结束后统一执行Q -X utf8 -m pytest --lf -q --basetemp=.local/par01-native-failed --junitxml=artifacts/par01/native-failed.xml：退出0，全量所列12项全部通过，6.76秒；native-failed.txt/xml记录实际用例与结果。没有改生产代码、夹具、目录链接行为或断言来绕过失败，不将原全量退出1改记退出0。
9. artifacts/par01/bundle.py对明确8份提交文件执行UTF-8/LF/末尾换行/无尾空格断言并计算规范Git blob hash，退出0；只提交代码、测试及必要契约/任务/报告，运行日志/样本临时库不入PR。

交付为[独立草稿PR #26](https://github.com/surface-user/StudyWorkbench/pull/26)，分支codex/complex-question-candidates，base为#23的2645366，实现提交ee0000e680b882c4d22a45cac7ac2874de4d52af，8份文件。补充本段与任务实际链接后核最终head CI，最终head/运行链接和主Agent交付核验结论在PR描述维护，不因写入自身SHA循环提交。状态仍REVIEW，不据父head或专项通过登记DONE。

未执行项目代码审查或人工测试，不把上述自动化当全格式/多栏/OCR/任意编号支持。完整M2-04以及整体发行仍未完成，未合并/发布。
