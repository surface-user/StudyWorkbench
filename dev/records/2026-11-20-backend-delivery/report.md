# 2026-11-20 后端独立交付核对

覆盖本次推进的后端 PR 及任务表中状态滞后的规模回归。下列提交均为草稿，不同基础分支须分别阅读。每行对应自己的提交和检查；未执行跨分支整包发布。

| PR | 固定提交 | CI | 核对范围 |
|---|---|---|---|
| [#56](https://github.com/surface-user/StudyWorkbench/pull/56) | `6ffc80c1b` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/43584654303) | 三档合成规模、源码及较早冻结包；桌面性能和真实学习效果未评估。 |
| [#79](https://github.com/surface-user/StudyWorkbench/pull/79) | `692d7ef1d` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44680208170) | 本地 MP4/M4A 探测；从原始 JUnit 核对两版各 1309 个 testcase，suite 计数 1386。 |
| [#80](https://github.com/surface-user/StudyWorkbench/pull/80) | `99b4542eb` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44678350119) | 离线扫描页 OCR；中文、英文和空白页均经源码及冻结 HTTP 核对。 |
| [#81](https://github.com/surface-user/StudyWorkbench/pull/81) | `aba16ba5d` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44678643251) | 只读复验冻结包 969 个文件、46 个业务模块及 58 个清单组件。 |
| [#82](https://github.com/surface-user/StudyWorkbench/pull/82) | `24d137d86` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44679690453) | Office 专项完整组件 19746 个文件，内置 Python 真实运行；此步剩 79 个未知加载关系。 |
| [#83](https://github.com/surface-user/StudyWorkbench/pull/83) | `b7bf96de9` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44679491427) | 显式双栏布局下拆题、共享材料、跨栏续题和选择性确认。 |
| [#84](https://github.com/surface-user/StudyWorkbench/pull/84) | `c6be373a7` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44680779685) | 上限 128 MiB 的托管 PDF 原件，分段提取、取消恢复和显式确认。 |
| [#85](https://github.com/surface-user/StudyWorkbench/pull/85) | `b7052a894` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44681767359) | 核对后端文件、签名者证书、Windows 信任状态和时间戳；当前后端未签名。 |
| [#86](https://github.com/surface-user/StudyWorkbench/pull/86) | `ec214a236` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44682511146) | 定义未登记题目目录与来源、附件、显式确认和收据的关系。 |
| [#87](https://github.com/surface-user/StudyWorkbench/pull/87) | `abf66df7d` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44682889216) | Office 文本编码组件；只读复验 379×2 专项和 16 份受保护输出，此步剩 78 项。 |
| [#88](https://github.com/surface-user/StudyWorkbench/pull/88) | `481d93aac` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44683111794) | 三个实际原生 DLL、两份许可文本与固定上游归档的字节核对。 |
| [#89](https://github.com/surface-user/StudyWorkbench/pull/89) | `610a3e9d3` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44683976323) | 只读匹配完整遗留目录，原件、正文和图片相符才返回候选。 |
| [#90](https://github.com/surface-user/StudyWorkbench/pull/90) | `c5fe7819e` | [通过](https://github.com/surface-user/StudyWorkbench/actions/runs/44684769079) | 用户确认后另存新位置，并发及重启不重复登记，完整备份还原后可重放收据。 |
| [#91](https://github.com/surface-user/StudyWorkbench/pull/91) | `747f6f1e3` | [运行中](https://github.com/surface-user/StudyWorkbench/actions/runs/44686958163) | 固定后端三个原生 DLL 与公开漏洞资料核对。OpenSSL 官方标出 8 条，OSV 返回其中 6 条。 |

以 GitHub 的 PR head 和该提交的 Actions 运行结果逐条核对。额外复核 Office 的清单及原文件哈希、后端来源证据、下载探测的原始测试计数，以及恢复与签名工具提交的全部文件。未重跑性能基准，#56 的实验数据沿用同一提交已完成的主 Agent 核验。

发行仍缺完整 SBOM、传递许可闭合、全部组件漏洞检查、可信发行签名和候选组装。三站下载、双轨合流与其余后端计划继续由各任务跟踪。按用户指令暂缓审查、取消人工测试；未合并或发布。
