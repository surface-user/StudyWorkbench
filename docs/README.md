# 当前有效文档

本目录回答当前需求、架构、契约和操作方法。开发过程见[dev](../dev/README.md)，原始运行产物写artifacts，不在本目录追加逐日流水账。

查当前任务先读task，改行为时再读对应规范。初始讨论与评估归dev的原任务目录，历史归档按需查；不再维护平行的doc目录。路线/契约不重复维护任务进度、测试计数和自审过程。

| 文档 | 职责 |
|---|---|
| [requirements](requirements.md) | 产品目标、范围和验收要求 |
| [学习工作台路线](learning-workbench-roadmap.md) | 已采纳范围、LW任务依赖及交付目标；任务进度统一查task |
| [普通学习流程契约](learning-workbench-contracts.md) | 普通学习行为与规划契约；当前已实现字段查API/数据模型，自审与实施过程查原任务报告 |
| [task](task.md) | 当前安排、状态、历史遗留和退出条件 |
| [architecture](architecture.md) | 当前模块和数据流；规划与待验证分列 |
| [data-model](data-model.md) | 当前表、身份、权威与迁移保护 |
| [api-spec](api-spec.md) | 已实现路由与契约；规划接口不得当成可调用接口 |
| [question-content-spec](question-content-spec.md) | QuestionDocument/Bundle v1及作答协议 |
| [question-markdown-spec](question-markdown-spec.md) | 旧提取MD v1兼容格式 |
| [question-file-spec](question-file-spec.md) | QuestionFile v1与不可变确认版本 |
| [tabs-and-webview](tabs-and-webview.md) | 标签、页面生命周期和网页隔离 |
| [editor-tabs-spec](editor-tabs-spec.md) | 用户标签栏规范原文；目标要求不表示逐项已验收 |
| [agent-design](agent-design.md) | 本地授权/候选审核与Agent规划 |
| [security-privacy](security-privacy.md) | 当前安全控制、边界和待验证项 |
| [dependencies](dependencies.md) | 当前依赖、许可、维护证据及候选 |
| [testing](testing.md) | 测试命令与人工验收方法 |
| [packaging-windows](packaging-windows.md) | 构建、可选组件、安装与数据规则 |
| [ADR](adr/) | 架构决策及替代关系，变更相关架构时读取 |

状态定义：**当前已实现**指实际代码具备；**规划中**指确定方向但代码尚未实现；**待验证**指已实现但证据尚不足。已实现与待验证可以同时成立，不能把自动化通过当成人工/阶段验收。具体状态以task及其指向的报告为准，历史记录不覆盖本目录现行约束。
