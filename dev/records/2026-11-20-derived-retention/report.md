# M2-05j 派生文件留存设计

根据现有恢复、Office 预览、下载容量报告和旧题恢复收据，补充[留存与处置契约](../../../docs/learning-workbench-contracts.md#derived-retention)。对有引用、可恢复、来源不明和无完整核验的对象分别说明留存理由。未来处置须先明确用户所选集合、核对版本与引用、记录逐项结果；重启或撤回时保留冲突字节。此次仅交付设计。

本地在 Python 3.12、3.13 上分别运行以下已有检查。两次均为 73 项通过、2 项失败、4 项未选，退出 1。名称未含链接的两项综合夹具也需创建 NTFS 硬链接，均在建立夹具时收到 Windows 的拒绝访问。用普通权限运行的原始结果保留于忽略的 artifacts 目录，测试代码及断言未修改。

```shell
python -m pytest -q backend/tests/test_recovery_storage.py backend/tests/test_office_storage.py backend/tests/test_download_storage.py -k "not junction and not hardlink and not reparse"
```

申请完整本地回归及一次重试时，自动审批均超时，两个请求均未实际执行。提交 CI 应按原版本运行完整测试并单列结果；这一设计切片保持待交付直至核实。未操作个人库、未清理文件，未执行人工测试或独立审查。
