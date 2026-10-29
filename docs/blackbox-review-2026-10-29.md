# R1–R5 黑盒复核总记录（2026-10-29）

状态：in_progress。用户授权每阶段一个新子代理，按R1→R5串行复核；发现产品缺陷须先留失败用例和任务，再修复复测。既有实现/自动化记录不等于人工或阶段验收。规范路径为docs/task.md（仓库无doc/task.md）。

当前实现：R1–R5已实现，R6未实施。此前确有自动化及Windows集成证据，本轮独立重验，不将历史证据当本轮执行。

## 根代理回归

以下均从仓库根执行，Flutter命令cwd为apps/desktop。日志在[evidence/blackbox-20261029](evidence/blackbox-20261029)。

- `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/blackbox-20261029-full --junitxml=.local/blackbox-20261029-full.xml`：退出1，207通过/1失败，157.52秒。唯一失败test_reparse_points_rejected在cmd mklink /J准备fixture时Access is denied，尚未到产品断言；不删除失败证据。
- 获沙箱外执行许可后原测试 `.venv/Scripts/python.exe -m pytest backend/tests/test_explorer.py::test_reparse_points_rejected -q --basetemp=.local/blackbox-20261029-junction-retry`：退出0，1通过，2.36秒。未改测试/断言，未更改机器权限。
- `D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot test --no-pub`：首轮SDK cache lock拒绝，获执行许可后同命令退出0，83通过/2跳过。首轮和复测日志均保留。
- `.venv/Scripts/python.exe tools/export_question_schema.py --check`：退出0，Schema一致。
- `git diff --check`：退出0，只有换行提示。
- 全局Ruff首轮发现新增R1脚本I001；由R1代理修复导入排序，定向Ruff退出0，产品逻辑不变；后续仍需最终全局复查。

## PR与交付条件

当前分支codex/m1-workspaces-tabs。GitHub连接器查询`repo:surface-user/StudyWorkbench is:pr is:open`返回空列表，当前无开放PR。大量R1–R5改动未提交，不将本地工作树当已推送PR。gh不在PATH；git ls-remote经凭据助手出现MSYS命名对象Access denied并失败，因此未触发CI、审查或合并。无自动审批拒绝；不得伪造另一审查者批准，也不能把无PR描述为已合并。

目前未运行本轮安装/干净机/人工验收；分阶段报告必须区分HTTP黑盒、组件及真实Windows窗口证据。未访问个人库、未替换dist开发包。

最终新增脚本落地后的全局 .venv/Scripts/python.exe -m ruff check backend tools 退出0，All checks passed（R2原生验证进行中时）。
该时点R1完成、R2运行中；最终分阶段结果见下表。

## 分阶段复核结果

每阶段均为新子代理，按顺序完成后才启动下一阶段。HTTP脚本只启动真实后端、调用公开接口和使用自编来源；Windows既有测试含内部状态断言，单列为混合集成。

| 阶段 | 独立真实HTTP | Windows混合集成 | 范围内结论与报告 |
|---|---|---|---|
| R1 | 两轮71/67次响应断言，退出0；轮询次数可变 | 本轮未执行R1窗口 | 无产品缺陷；[R1报告](r1-blackbox-2026-10-29.md) |
| R2 | 24次响应断言，退出0 | 1通过，退出0 | 无产品缺陷；[R2报告](r2-blackbox-2026-10-29.md) |
| R3 | 最终58次响应断言，退出0；轮询次数可变 | 1通过，退出0 | 无产品缺陷；[R3报告](r3-blackbox-2026-10-29.md) |
| R4 | 44次响应断言，退出0；既有重启专项也通过 | 1通过，退出0 | 无产品缺陷；[R4报告](r4-blackbox-2026-10-29.md) |
| R5 | 最终50次响应断言，含重启，退出0 | 1通过，退出0 | 无产品缺陷；[R5报告](r5-blackbox-2026-10-29.md) |

保留新增tools/check_r1_blackbox.py至check_r5_blackbox.py作为后续回归。各报告记录具体命令、输出、测试准备错误及限制；目前无需产品修复。R1窗口、完整Office转换矩阵、冻结/安装/干净机、人工与阶段验收不在已通过结论内。

## 后续PR安排建议

用户追问如何补交大量本地代码及未来PR规则。本批建议一个R1–R5集成PR，说明跨阶段依赖并在PR内组织模块/提交和验证证据，避免硬拆不可构建的中间状态。未来按可独立验证任务建立分支、实现/回归/文档后提交并创建PR，同一分支修复，CI和规定审查通过后合并。当前仅建议，未修改交付规则、提交、推送或创建PR。


## 最终结论

R1至R5各由独立新子代理按序执行，上述限定范围均未发现产品缺陷，故无产品代码修复。本轮新增五份真实HTTP回归脚本及分阶段记录；失败日志均保留（环境权限、测试准备/输入预期与执行中断），未删失败用例或放宽产品校验。R2–R5各一项Windows混合集成通过。全部五份脚本落地后全局Ruff、Schema漂移和git diff --check均退出0。根代理已查看R2与R3运行截图；截图时点限制见R2报告。

当前PR/CI流程、R1窗口复核、安装/干净机及人工/阶段验收尚未完成，总任务保持in_progress，不将限定黑盒覆盖称为全产品通过。不提交/推送/创建或合并PR；用户正在讨论本批集成PR方案，尚未确认新PR整理执行。用户明确暂不修改Codex全局规范，本轮未写全局文件。
