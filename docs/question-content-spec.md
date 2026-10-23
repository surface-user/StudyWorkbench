# 富内容与作答协议 v1

本协议是扩展设计基线；M0 只实现 text/latex 和 single_choice/subjective 的垂直切片。其他类型不得宣称已支持。

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

选项使用稳定 id 与 content: Block[]，答案引用 id 而非列表位置。填空答案按 blank_id 保存候选/归一化策略；计算/证明/主观题保存参考答案与 rubric，默认 pending_review，不做字符串相等判错。

source：`kind: manual | imported | official | ai_generated`、`title`、`original_resource_id?`、`page?`、`url?`、`license?`、`verification: unverified | human_verified | rejected`、`model?`、`generated_at?`。AI 题必须 ai_generated 且初始 unverified；只有人工验证不能自动推断为官方真题。

作答请求：question_id、response（选项 ID 列表/填空映射/富文本与附件）、将来加入 question_revision 与幂等键。服务器读取标准答案，客户端不得提交分数。响应：attempt_id、status graded/pending_review、score nullable。多选精确集合匹配/部分分策略须题目显式定义。历史作答只追加；更正评分另建修订。

示例见 contracts/question-v1.json。M0 的答题接口仅支持两个演示题，不是题库导入接口。
