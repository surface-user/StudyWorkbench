# 富内容与作答协议 v1

本协议是扩展设计基线；M0 的渲染与答题只实现 text/latex 和 single_choice/subjective 的垂直切片。Python 数据校验已覆盖下列全部题型和内容块，不代表 UI/判分已支持全部题型。

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

不允许任意 HTML、脚本、file:// 或网络加载。未知块/协议版本显示不支持并保留原数据，不静默丢弃。M2 需限制深度、大小和附件 MIME，添加跨语言 schema 校验。

机器契约：`backend/study_workbench/question_protocol.py` 为 Python 校验源；`contracts/question-v1.schema.json` 与 `question-bundle-v1.schema.json` 为 JSON Schema 2020-12。运行 `python tools/export_question_schema.py` 导出，`--check` 检查漂移，pytest 已执行这一检查。

结构校验包含内容块判别、字段白名单、长度/表格行列限制、版本号、各题型答案形状、选项及填空 ID 唯一性、答案引用、阅读 response_kind；交换 bundle 还验证共享文章引用、父题引用和来源关系无环。表格不允许嵌套表格，单格最多 20 个内联块、最多 20 列/100 行，题干/解析最多各 200 块。LaTeX 禁止文件/网络与宏定义指令；采用原生数学渲染，不运行完整 TeX 引擎。

JSON Schema 表达结构与字段约束；跨字段答案匹配、引用完整性和来源状态等 Python model_validator 规则不能全部由生成的 Schema 表达，Python 校验仍为写入前权威检查。Dart 端 Schema 运行时校验尚未实现。资源 ID 仅做格式校验，附件存在性/MIME/实际文件权限须 M2 资源服务验证；这不是附件导入或安全认证。

严格写入校验拒绝未知版本/块；未来导入器须另存原始文件与解析原文，拒绝写入不能被解释成删除原始资料。当前 Flutter 未知块提示只适用于展示层，不能绕过写入校验。

选项使用稳定 id 与 content: Block[]，答案引用 id 而非列表位置。填空答案按 blank_id 保存候选/归一化策略；计算/证明/主观题保存参考答案与 rubric，默认 pending_review，不做字符串相等判错。

source：`kind: manual | imported | official | ai_generated`、`title`、`original_resource_id?`、`page?`、`url?`、`license?`、`verification: unverified | human_verified | rejected`、`model?`、`generated_at?`。AI 题必须 ai_generated 且初始 unverified；只有人工验证不能自动推断为官方真题。

机器校验要求 AI 来源带模型与有时区的生成时间，默认 unverified；其他来源不能夹带 AI 字段，official 必须 human_verified。Schema 不证明操作者确有验证权限；M2/M5 的导入/生成业务必须把不可信验证声明降为 unverified，仅由用户确认接口修改状态，不得直接相信模型或文件自报 human_verified。

作答请求：question_id、response（选项 ID 列表/填空映射/富文本与附件）、将来加入 question_revision 与幂等键。服务器读取标准答案，客户端不得提交分数。响应：attempt_id、status graded/pending_review、score nullable。多选精确集合匹配/部分分策略须题目显式定义。历史作答只追加；更正评分另建修订。

示例见 contracts/question-v1.json。M0 的答题接口仅支持两个演示题，不是题库导入接口。
