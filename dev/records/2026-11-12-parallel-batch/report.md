# 首批并行任务组合回归

日期：2026-11-12。INT-01状态REVIEW：只组合已分别交付的#24–#27，并核验共存后的回归。审查依ADR0014暂缓，人工/Computer Use不执行；未合并任何PR或main，未发行。#28–#30等后续任务在各自分支推进，未计入本候选实现。

## 输入与验收

共同基线#23/2645366ca4f37cced53f41119ccebd732239a123。每份输入先与远端最终head的Git blob核对，再按共同基线组合无重叠改动；共享task行分别合并，原报告追加均保留，冲突直接失败，不覆盖别的任务。

| 小任务 | 精确head | 主Agent核实的最终CI |
|---|---|---|
| DL-01a #24 | 91db70413303c76d9fb5d78bb3c40f16089b1ca0 | [43059706025](https://github.com/surface-user/StudyWorkbench/actions/runs/43059706025)，成功 |
| REL-01a #25 | 1b52eb30785de734e7d5149d3198c5ee80bb78cf | [43060243273](https://github.com/surface-user/StudyWorkbench/actions/runs/43060243273)，成功 |
| PAR-01 #26 | 1d103f3c21cb8c95f5ea62841be11a4b7b2d16f9 | [43061041645](https://github.com/surface-user/StudyWorkbench/actions/runs/43061041645)，成功 |
| LW-07a #27 | 6af03602e5d70b40de58420b8b323c173612aaac | [43060817695](https://github.com/surface-user/StudyWorkbench/actions/runs/43060817695)，成功 |

各小任务证据经主Agent核验后，在task保留DONE条目；DONE只指各自有限开发交付范围。源码SBOM不是最终发行SBOM；解析不包含OCR/任意多栏；公网证据不包含正向Range/重定向；分页不是并发事务快照。完整父任务、历史失败及审查/发行义务继续保留。

## 本批实际命令与结果

工作目录D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-one。Q为D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（3.13.17）。原始日志、JUnit和输入manifest在忽略的artifacts目录，不上传个人数据或下载媒体。

- 根artifacts/goal-20261112/combine_batch.py：退出0，核对远端blob后组合21份改动；没有网络分支合并、未改功能逻辑。
- Q -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch01/backend.xml：原生进程退出0，760通过、77子测试通过，479.39秒；Starlette弃用警告1条。对应backend.txt/xml保留。原生权限用于已有Windows路径/链接测试，不操作个人库。
- apps/desktop内使用固定Flutter 3.47.1的dart.exe flutter_tools.snapshot --no-version-check pub get --offline：退出-1073741816，SDK cache/lockfile写权限不足；日志artifacts/batch01/pub-get.txt保留。此失败不计为Flutter通过。本批UI代码与#27最终已验版本相同，组合当前head仍需完整Flutter/Windows/冻结CI。
- 本次文档/差异核对另记录提交检查输出；最终提交SHA、当前head CI结果与退出结论在本PR描述持续更新，避免为记录自身SHA循环提交。

## 交付与下一步

组合PR基于#27最终head，保留各项原独立PR及完整历史；仅新建候选分支，不将原PR标为已合并。等待本候选最终head CI通过后，INT-01由主Agent验收；尚未通过前保持REVIEW。下一批Office+Java、TXT全文和复杂Office矩阵分别核验，再组合，不能把各分支各自通过冒充完整产品通过。
