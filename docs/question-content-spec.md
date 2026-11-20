# 富内容与作答协议 v1

当前QuestionDocument/Bundle严格协议；新QuestionFile空答案编译模型独立编号，不能放宽旧JSON。实际实现见question_protocol.py、question_files_format.py及contracts Schema；生成器tools/export_question_schema.py --check检查漂移。

题目：`schema_version: 1`、`id`、`revision`、`subject`、`kind`、`stem: Block[]`、`options`、`answer`、`explanation: Block[]`、`knowledge_points: string[]`、`source`、`passage_id?`、`parent_question_id?`。

kind 枚举：single_choice、multiple_choice、fill_blank、calculation、proof、subjective、reading_question。阅读题使用 passage_id 共享文章，并显式声明其作答类型；禁止靠展示文本推断评分规则。

Block 是判别联合：

| type | 字段 |
|---|---|
| text | text（纯文本） |
| latex | tex（无网络或文件命令），display bool |
| image | attachment_id, alt, caption? |
| chart | attachment_id, alt, data_attachment_id?（M2 先用静态图，保留原数据） |
| table | headers: Block[][], rows: Block[][][] |
| attachment | attachment_id, label |

不允许任意 HTML、脚本、file:// 或网络加载。未知块/协议版本显示不支持并保留原数据，不静默丢弃。深度、大小和附件MIME经服务校验；Dart离线Schema参与展示/提交前检查。

机器契约：`backend/study_workbench/question_protocol.py` 为 Python 校验源；`contracts/question-v1.schema.json` 与 `question-bundle-v1.schema.json` 为 JSON Schema 2020-12。运行 `python tools/export_question_schema.py` 导出，`--check` 检查漂移，pytest 已执行这一检查。

结构校验包含内容块判别、字段白名单、长度/表格行列限制、版本号、各题型答案形状、选项及填空 ID 唯一性、答案引用、阅读 response_kind；交换 bundle 还验证共享文章引用、父题引用和来源关系无环。表格不允许嵌套表格，单格最多 20 个内联块、最多 20 列/100 行，题干/解析最多各 200 块。LaTeX 禁止文件/网络与宏定义指令；采用原生数学渲染，不运行完整 TeX 引擎。

JSON Schema 表达结构与字段约束；跨字段答案匹配、引用完整性和来源状态等 Python model_validator 规则不能全部由生成的 Schema 表达，Python 校验仍为写入前权威检查。Dart已接入离线Schema及跨字段检查；Python仍为写入权威。资源 ID 仅做格式校验，附件存在性/MIME/实际文件权限由资源服务验证；这不是附件导入或安全认证。

严格写入校验拒绝未知版本/块；导入器须另存原始文件与解析原文，拒绝写入不能被解释成删除原始资料。当前 Flutter 未知块提示只适用于展示层，不能绕过写入校验。

选项使用稳定 id 与 content: Block[]，答案引用 id 而非列表位置。填空答案按 blank_id 保存候选/归一化策略；计算/证明/主观题保存参考答案与 rubric，默认 pending_review，不做字符串相等判错。

source：`kind: manual | imported | official | ai_generated`、`title`、`original_resource_id?`、`page?`、`url?`、`license?`、`verification: unverified | human_verified | rejected`、`model?`、`generated_at?`。AI 题必须 ai_generated 且初始 unverified；只有人工验证不能自动推断为官方真题。

机器校验要求 AI 来源带模型与有时区的生成时间，默认 unverified；其他来源不能夹带 AI 字段，official 必须 human_verified。Schema 不证明操作者确有验证权限；导入/未来生成业务必须把不可信验证声明降为 unverified，仅由用户确认接口修改状态，不得直接相信模型或文件自报 human_verified。

作答请求使用 question_id、response，可携带 question_revision、question_version_id 和 request_id。选项以稳定 ID 提交，填空以 blank_id 映射提交。多选按精确集合匹配，填空按每空 exact/trim 归一化后按正确空数比例计分，阅读题按 response_kind 选择规则。

计算、证明、主观题和主观阅读题沿用 `{"text":"解题过程"}`，后端也接受 `{"blocks":[{"type":"text","text":"所以"},{"type":"latex","tex":"x=2","display":true}]}`。两种形式单独使用。blocks 按序保存 1 至 200 个文本或公式块，每块须有非空白内容。各块合计最多 20000 个 Unicode 码点，公式另受既有单块 8000 字符及命令限制。display 可省略，传入时须为布尔值。文件、图片、附件 ID 和外部 URL 引用均没有作答附件读取或导入语义。

服务器追加保存提交时的原始结构和题目版本，返回 id、status、可空 score。书面作答始终先进入 pending_review，评分修订单独追加。历史接口原样返回作答块；现有桌面端可继续提交纯文本，块编辑、展示和作答附件归属另行交付。题目附件仍归题目确认版。

示例见 contracts/question-v1.json。旧default演示接口保留；真实题目导入和学习入口见[API](api-spec.md)。

## R4并行协议边界

旧QuestionDocument v1/QuestionBundle v1继续严格要求原有答案，不放宽旧JSON导入。新[QuestionFile v1](question-file-spec.md)复用七类题型与全部块，仅其编译模型FileQuestion允许answer=null及独立blank_ids；跨语言Schema为question-file-content-v1.schema.json。旧提取Markdown v1不因此变为可判分题，须显式转换与确认；来源验证声明不能自行升级。缺答案一律待批改，旧有答案评分规则不变。确认快照包含材料、标题与附件，不用当前文件重算旧分数。自动化与限制见[R4记录](../dev/archive/reports/r4-validation-2026-10-26.md)。
