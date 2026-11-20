# Windows 后端数据库升级脚本打包

以 [#103](https://github.com/surface-user/StudyWorkbench/pull/103) 的 Windows 后端为基线。该候选含 1006 个文件，迁移目录多出的 36 个 Python 3.12、3.13 缓存文件逐一与构建目录的缓存摘要相符。新的打包参数只收集 Alembic 入口和版本目录的 Python 源脚本，构建结束时校验迁移文件集合及原始字节。

## 实物验证

保留旧包，运行新的 `python tools/check_frozen_sources.py --exe <旧后端>` 退出 1。在带缓存的源码目录执行 `./packaging/windows/build-backend.ps1 -Python <发行解释器>` 退出 0。新包有 970 个文件，其中包括完整的 18 份迁移源脚本；48 个冻结业务模块与源文件相符。新 exe 的 SHA256 为 `0618da6cfa7141c0e6ab6b3051e4b600caafec302370238577bcb5d97bd5b49a`。

执行 `python tools/check_backend_lifecycle.py --exe <新后端>` 退出 0。新建库、记录写入、退出、重启、崩溃恢复和两次移动数据目录前后，安装目录的全部 970 个文件名称、大小和 SHA256 相同。另用 Alembic 构建 0016 夹具，写入可识别的数据，通过实际后端启动两次。数据库已升至 0017，保留一份完整的 0016 备份，两者数据及 SQLite 完整性检查通过，退出 0。

`python -m pytest backend/tests/test_frozen_migrations.py backend/tests/test_frozen_sbom.py backend/tests/test_release_inventory.py backend/tests/test_backup_store.py -q` 在 Python 3.12、3.13 各通过 135 项，退出 0。首次普通运行两版各有 3 项因测试环境无法创建 NTFS 目录链接而失败，允许在临时测试目录创建链接后以相同断言通过。Ruff 检查退出 0。Windows 签名状态为 NotSigned。代码审查暂缓，人工测试已取消；发行仍需完成签名及其余发行任务。
