# LW-04 学习记录集中查找

2026-11-04，接续用户“推进下一轮，直到额度结束”的授权。按现行契约推进，无子Agent/新依赖；仅本地交付，不要求本批提交/PR，不推送/合并/发行，人工/阶段统一待验。LW-03命令与结果继续留其原报告。

## 设计与拆分

1. GET W/learning-search仅当前活动空间，字面子串匹配（Unicode casefold），不执行正则/HTML/Markdown。范围明确为活动MD/MARKDOWN当前工作副本或原件、旧富内容笔记、未移除书签标题/备注；TXT全文、OCR及其他格式不混入。
2. 每次完整扫描预算范围后按kind/id稳定排序，再分页，不能先分页再过滤。q=1–200非空字符，offset≥0、limit=1–100默认50；只返回纯文本摘要、类型/稳定ID、URI和读取版本，不返回路径或能力。
3. 复用文档受管读取及2槽并发门禁。MD≤1000份、单份≤1MiB；总读取文字≤16MiB；旧笔记/标记另设合计10000条上限，避免未限定数据库扫描。任何预算截断/坏文件均返回truncated、原因及扫描计数，不把部分无匹配冒充全库无结果。
4. 原生集中入口、分页/刷新/错误反馈、结果跳转复用内部链接。文件笔记跳转前重验当前正文hash；旧笔记重验revision；书签保留失效备注可查看，真正跳转仍走实时位置验证。翻页间库变动可能改变结果，显示可刷新，不承诺跨请求快照。
5. 预算/坏文件/中文与大小写/隔离/分页/版本变化及UI测试，完整回归、静态、Windows构建、自审和所属文档更新。schema沿用0014，不新增正文索引或镜像。

设计时尚未验证。完整日志放artifacts/lw04-20261104/；同任务失败和重试追加此报告。


## 实施与自审

新增learning_search.py与原生学习查找弹窗；复用固定受鉴权路由、空间门禁、文档处理并发槽、受管路径、内部URI和旧笔记修订。无新表/索引/正文镜像，schema仍0014。MD按原件格式判断，不按可改的显示名误判；当前工作副本优先；旧富内容只抽文字/公式/表格/附件说明，未知结构明确部分未扫描。返回纯文本摘要，不渲染HTML。

先扫描预算范围后排序分页，分页失败保留原结果/查询；UI显示结果对应搜索词、范围及扫描计数，翻页合并按kind/id去重。文件hash及旧笔记revision变化要求刷新，书签结果先展示保留备注，实际来源跳转仍重验。来源移除不隐藏备注；普通资源被移除不从搜索重新打开。不含个人路径/令牌/播放器capability，不扩大Agent grant。

自审补强坏文件读取计费：使用现有受管路径与工作副本规则做有界读取，非UTF-8/损坏/超大字节也消耗16MiB预算，最多额外1字节判溢出；旧笔记按序列化JSON字节预检和计费，避免少量提取文字掩盖大体积JSON读取。无打开标签时仍保留集中入口。上述为开发自审，非独立人工批准。

## 专项与失败

工作目录仓库根，P=.venv/Scripts/python.exe；Flutter在apps/desktop，D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe，F=D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot；入口D F --suppress-analytics。沿用项目.local/tmp与.local/nuget-scratch及关闭分析上报的进程环境，SDK缓存和junction全套回归使用获准扩展权限；不操作个人库/上游缓存代码，不升级依赖。

- `P -m ruff check backend tools`退出0，ruff-03.log。
- `P -m pytest backend/tests/test_learning_search.py -q --basetemp=.local/lw04-search-03 --junitxml=artifacts/lw04-20261104/search-03.xml`退出0，12通过，5.67秒；覆盖当前正文/原件保持、富内容、中文/casefold/字面%_、失效来源、移除、完整扫描后分页、隔离/重启、q/分页约束、MD/DB/字节预算、坏字节计费及未知块。
- `D F --suppress-analytics test --no-pub test/learning_search_test.dart --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw04-flutter-01`退出0，6通过，flutter-search-01.log；覆盖纯文本/截断、分页去重、失败保留、文件/旧笔记版本重验和失效书签备注查看。
- search-01保留10通过/1失败：隔离fixture为同字节创建多个Resource，撞现行(workspace,sha256)唯一约束；改为不同字节自建样本，不降低断言，search-02为11通过，新增坏字节/未知块后search-03为12通过。
- analyze-02有6处花括号info；初次dart fix在格式化前未发现需要修复的折行，格式化后分别对lib/learning_search_dialog.dart、lib/learning_marks_dialog.dart、test/learning_search_test.dart运行`D fix --apply --code=curly_braces_in_flow_control_structures <单文件>`并format，均退出0；`D F --suppress-analytics analyze --no-pub`末次退出0，No issues found（analyze-03.log）。仅格式变化，没有重复无必要的业务回归。

全套和构建结果见下方追加。完整产物位于artifacts/lw04-20261104/，未删除旧失败、未整包进入evidence。


## 全套、构建与交付

- `P -m pytest backend/tests -q --basetemp=.local/lw04-backend-full-04 --junitxml=artifacts/lw04-20261104/backend-full-04.xml`退出0，281通过，153.63秒；backend-full-04.log/xml。Starlette/anyio弃用警告保留。
- `D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw04-flutter-full-02`退出0，127通过；flutter-full-02.log。
- `D F --suppress-analytics build windows --release --no-pub`退出0，44.2秒；windows-release-02.log，原CMake CMP0175开发警告保留。flutter-exit-02.json如实保留当时analysis=1，随后analyze-03为0，不改写旧失败为成功。

实现、自动化及本批自审完成；真实窗口/IME/DPI/真实个人库规模、用户人工/阶段、安装/干净机未执行，保持待验收。自动测试用构造样本，不构成大库性能验收。没有更新冻结后端/安装发行组合；未提交/推送/PR/合并/发布，远程head/CI未知。下一项LW-05，现有export仍非整库恢复包。

收尾命令：`P artifacts/lw04-20261104/check_docs.py`退出0，46份Markdown、223处本地链接/7处标题锚点通过，114份受保护历史文件SHA256保持；`P tools/export_question_schema.py --check`退出0；`git -c core.safecrlf=false diff --check -- docs dev apps/desktop/lib backend`退出0。完整运行产物仍在被忽略的artifacts目录，未整包晋升evidence。
