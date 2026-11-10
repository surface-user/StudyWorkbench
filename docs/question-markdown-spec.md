# 旧提取Markdown v1兼容规范

当前仍兼容该格式；它没有文件内稳定题目ID，不等于[QuestionFile v1](question-file-spec.md)。旧MD不在打开时静默升级，不改源Word/PDF，转为可判分题需显式编辑副本及另行确认。

该格式单元为 MarkdownQuestion，与需要题型/标准答案的 QuestionDocument 分开索引。原件资源共享，每个题目有独立ID、标题、Markdown资源、来源资源、来源页/区域或Word内容顺序。转为可判分练习题需要单独的人为确认，不自动推断题型或标准答案。

磁盘组织为数据目录下`workspaces/<workspace>/questions/<id>/question.md`及同目录`assets/<resource-id>.png`。MD使用UTF-8，图片相对引用`assets/...png`，公式使用数学标记，Word表格保留Markdown。末尾JSON元数据记录原文件名/SHA256/资源ID、来源页、裁切区域、解析器版本、unverified及not_inferred。索引由SQLite管理；文件内容和哈希仍受资源API校验，不将本机路径/令牌交给网页。

PDF：仅对可提取文字的显式题号做保守候选识别，保存单栏全宽原貌裁图及提取文字，跨页延续到下一题号；裁图保存公式/插图，提取文字不代表公式识别。区域坐标为从左上角起的归一化`[left,top,right,bottom]`。Word：按内容顺序切分显式题号/可恢复自动编号，保留公式、图片和表格；不声称有实际分页裁图。

先预览候选、核对并选择，再明确确认；预览不写正式MD题目索引。确认带候选内容摘要、选中下标及confirm=true，写入事务串行，重复同组选题返回既有记录；另一组选题不覆盖已入库批次。正式确认后旧解析任务不可覆盖。原件和整篇资料预览仍保留；整篇另存笔记与逐题MD是两个明确入口。

无题号/扫描无文字时不编造候选。当前不支持OCR、多栏稳定阅读顺序、复杂/嵌套题号自动区分及阅读共享材料自动归组；题号前的卷头/共享材料保留在原件/整篇预览，不自动复制到每题。确认前可改标题、合并相邻候选、分割Word内容、水平重裁PDF并手动归组共享材料，改动以expected_revision校验；已存MD不由旧预览回写。PDF手工子裁图仅保留精确图像，不复制无法定位的原提取文字。当前检索仅标题，分批加载；原文全文检索和该旧格式自身不直接判分，显式转换见下方R4兼容入口。

原件8MiB、PDF20页、解析25秒、200个候选、图片总量64MiB预算延续。源文本可能含HTML/链接，界面以纯文本或受控块展示，不执行其脚本。每个MD附的图片副本在题目目录，导出另附`questions/<id>/question.md`和相对assets目录，离开原数据目录仍可打开；它不等于整库恢复包。

正常写入检查所有选题的源资源后落盘。进程崩溃/磁盘失败可能留下未登记的派生MD/图片目录；它们不是原件，不自动删除。离线完整性巡检已按资源索引识别`workspaces/<workspace>/questions/<id>`的未登记目录（含空目录及仅写入图片的中断），只提示`unreferenced_derived_candidate`；不会补登记、重写或删除文件。已登记题目的MD沿用资源大小/hash校验；巡检另读取旧题目blocks及shared_materials中的image引用，核对同空间MD资源与固定题目路径，再按同空间原附件Resource的大小/hash核验assets副本。原附件或MD绑定无效分别报告invalid_legacy_attachment_reference/invalid_legacy_question_reference，损坏JSON返回不完整；仍不证明全部业务元数据语义。图片副本缺失/变化只报告，不从原图自动补回；候选的恢复语义尚未定义。持久化成功以API响应/索引/哈希为准，不能只看有目录就断言入库。

## R4兼容入口

本文件描述的旧提取Markdown v1保留原行和原字节。新[QuestionFile v1](question-file-spec.md)单独编号；旧题详情的“创建可编辑题目文件”先显示预览，显式创建稳定ID映射，再另行发布确认版。旧MD不猜测答案，转换为明确待批改的主观草稿；页码/区域/解析器/来源原件hash及未知非正文元数据随legacy_provenance保留。已有同ID旧JSON冲突拒绝，不自动合并。详见[R4记录](../dev/archive/reports/r4-validation-2026-10-26.md)。
