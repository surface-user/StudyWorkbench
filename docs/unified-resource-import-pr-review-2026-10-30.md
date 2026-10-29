# 统一资源导入：PR审查与CI（2026-10-30）

用户要求补齐提交、PR审查及远程CI。已从远程最新main `fcf57e1`建立`codex/unified-resource-import`，保留旧分支；旧分支虽有不同提交哈希，其文件树与已合并main一致，不重复携带历史变更。只提交本批实现、依赖的0012删除迁移、必要测试/文档和两张隔离样本截图；`.vscode`及旧证据目录留在本地。

PR：[surface-user/StudyWorkbench#2](https://github.com/surface-user/StudyWorkbench/pull/2)。初始提交`8d32843`，已实际推送并触发push/pull_request两组GitHub Actions，包含Python3.12、3.13.17与Windows2022桌面。增加Release原生COM自检和冻结统一资源/文档专项。未合并。

## PR差异审查

针对远程PR的实际diff与相连调用，按单个本地桌面用户的负载审查。代理自审，不冒充独立人工批准。正式[COMMENT审查](https://github.com/surface-user/StudyWorkbench/pull/2#pullrequestreview-5702602654)及两条行内评论绑定初始提交。

1. **P2，停止预检仍创建复制任务。** 延迟确认时的识别响应，在等待中点停止，旧代码仍POST新任务，再取消；快速worker可能已登记资源。新增测试明确断言零提交，修复前实际提交`D:/note.md`。修复为识别返回后、创建任务前检查stop/mounted。
2. **P2，连续拖放静默丢掉后一批。** 首批识别等待期间的第二批回调命中busy直接返回，没有清单项或错误。新测试复现`second.md`缺失。修复为依序暂存，在第一批完成后去重第二批；其他忙操作则明确提示稍后重新添加。

追踪范围还包括：原件哈希及同空间读取、分析复用ImportJob、删除墓碑/迁移回滚/历史、目录预算、失败轮询保留job_id、媒体共享数据、模态生命周期、Tab及草稿保留。未发现本轮范围内其他可复现的阻断项；实际Explorer鼠标拖放、多屏DPI、安装器/干净机仍待人工验收。

## 命令及证据

- `git fetch origin`、基线树比较、`git switch -c codex/unified-resource-import origin/main`、精确路径`git add`、`git commit`、`git push -u origin codex/unified-resource-import`均退出0。旧分支及未选文件保留，无强推/reset。
- `flutter test --no-pub test/add_resources_dialog_test.dart`：修复前退出1，3通过/2失败（`.local/pr2-review-red-02.log`）；修复后退出0，5通过（`.local/pr2-review-green.log`）。首个测试脚本因等待自己尚未释放的闸门而挂起，已修正发送调度并终止本轮测试进程树；未删断言。
- Dart format、Ruff、静态检查及远程CI的最终结果在后续提交/PR中更新；不把旧提交的绿灯当当前head结果。

此前本地交付及未通过人工项见[实现记录](unified-resource-import-2026-10-30.md)。此前独立测试包对应初轮实现；本次PR修复的两个竞态不因此宣称已包含在旧包内。
