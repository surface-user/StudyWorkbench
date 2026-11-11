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

## INT-02 第二批组合

首批INT-01的#31最终b8d534a96e6ced1ddd425c36d25ebad1251b5efd已由主Agent核验[CI43069606085](https://github.com/surface-user/StudyWorkbench/actions/runs/43069606085)三组全成功；前文REVIEW是当时提交快照，现首批有限任务已DONE。人工/审查/合并/发行边界保持。

第二批以该精确tree的450份Git blob为基线，在新.local/goal-20261112/batch-two源码副本组合以下已交付改动。没有复制前批测试库、缓存或产物；未合并原PR/main。INT-02本地组合回归完成，当前REVIEW，独立PR/最终head CI待核，不把各PR绿灯当组合版本绿灯。

| 独立任务PR | 精确head | 主Agent核验的最终CI |
|---|---|---|
| OFF-02a #28 | 2187fec21fee25472124aa97a2b1ea524d85e357 | [43065303373](https://github.com/surface-user/StudyWorkbench/actions/runs/43065303373)，成功 |
| LW-04a #29 | 9027508bdbc78316b546c8000cc06267c51f3149 | [43066543568](https://github.com/surface-user/StudyWorkbench/actions/runs/43066543568)，成功 |
| FMT-01 #30 | c352424aae9e6d6e6752f754c51297ecc1ce5f8b | [43067590610](https://github.com/surface-user/StudyWorkbench/actions/runs/43067590610)，成功 |
| REL-03a #32 | 89f0d775d847981b97a70c1a88281e140756c8f2 | [43071363779](https://github.com/surface-user/StudyWorkbench/actions/runs/43071363779)，成功 |
| OFF-02b #33 | e0a3fcf66f18752df4c67b19151b21ef94f2f0f4 | [43072881498](https://github.com/surface-user/StudyWorkbench/actions/runs/43072881498)，成功 |

各输入先核最终Git blob，再根据各自PR基线组合差异。源代码没有重叠冲突；task由主Agent统一登记有限DONE及未完成父项，补齐下方重复摘要的旧状态，保留历史失败，不让上表DONE与下表未实施并存。已满足的源许可检查范围另列REL-02a READY；完整发行范围仍待REL-01，不据源包标签宣称许可义务完成。

实际组合脚本位于根artifacts/goal-20261112：prepare_batch_two.py核450基线后应用#28/#29；在#30依赖说明插入处，五行上下文跨到了既有SBOM说明，保守拒绝退出1，保留现场，没有覆盖。检查差异确认仅开发样本工具独立段落后，用唯一相邻段落定位并完成其余#30改动，退出0。extend_batch_two.py将#32/#33独立追加报告与源码组合，退出0。没有放宽功能测试或改写任一特性实现。两份manifest记录精确输入head/文件hash，原始组合现场留在忽略的artifacts。

已执行Q -m ruff check backend tools退出0，Q为根.local/release-venv/Scripts/python.exe（3.13.17）。组合后端全量与桌面自动化结果继续追加，使用全新测试目录，不修改共享Python环境。完整SBOM、传递许可/源码义务、漏洞修复、PE域门禁、签名及发行仍未完成；API-01a/#34、OFF-02c及pytest/Starlette修复尚未纳本候选。

本批实际后端命令：PYTHONPATH=backend; Q -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch02/backend.xml，原生测试权限退出0，882通过、77子测试通过，387.63秒。2条警告分别为原Starlette弃用和Java重复ZIP路径负例，保留backend.txt/xml。没有跳过真实链接用例或放宽保护。

桌面准备：固定Flutter3.47.1的Dart/flutter_tools.snapshot --no-version-check pub get --offline，依赖解析完成后因本机缺Developer Mode的插件symlink要求退出1（pub-get.txt）。不修改系统设置；requirements/pubspec锁逐字不变，得到的package_config用于--no-pub组件测试，不能把该pub准备失败写成Windows构建成功。桌面完整测试另运行并记录退出码。

桌面实际命令：本副本新建.venv目录链接只读复用Q，不改变共享环境；PYTHONPATH指本副本backend。D F --no-version-check test --no-pub --concurrency=1 --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-two --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-two/.local/flutter-full01，退出0，完整200通过/无跳过，1分42秒，artifacts/batch02/flutter-full01.txt。该结果是组件与真实隔离后端回归，不是窗口/人工验收。

提交前检查：D format --output=none --set-exit-if-changed lib test integration_test退出0（87文件无变化）；D F --no-version-check analyze --no-pub退出0。32份实际变更的UTF-8/LF、逐文件git diff --no-index --check与Markdown本地链接聚合检查退出0；两份依赖锁与#31逐字保持。当前组合实现/本地自动化完成，保持REVIEW直到独立草稿PR最终head CI核验，提交/CI结果在PR描述维护。
