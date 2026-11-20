# 后端原生组件漏洞核对

2026-11-20 UTC 对已锁定的 Windows 后端进行了两项独立核对。OpenSSL 官方 3.5 分支列有 69 条公告，8 条版本范围包含 3.5.9，上游均定为 Low。按固定 Git 标签、提交分别查询 OSV，各返回其中 6 条。另两条是 CVE-2026-107493 和 CVE-2026-107496。libffi 3.4.4 的两种 OSV 查询均返回空集合，数据库覆盖仍未知。[OpenSSL 3.5 公告](https://openssl-library.org/news/vulnerabilities-3.5/) · [OSV 查询](https://google.github.io/osv.dev/post-v1-query/)

| 组件 | 关联的冻结包文件 | 本批结论 |
|---|---|---|
| OpenSSL 3.5.9 | libcrypto-3.dll、libssl-3.dll | 8 条上游公告均列出从 3.5.0 到 3.5.10（不含）的受影响范围。按版本登记阻断，产品调用可达性另核。 |
| libffi 3.4.4 | libffi-8.dll | 未返回公告；不推断 Windows DLL 已完成安全认证。 |

11 月 10 日和 17 日的上游公告给出了修复状态，11 月 17 日公告预计包含修复的正式版本于 12 月 1 日发布。后续须取得兼容的发行二进制、重新绑定实际 SHA256 和来源、复验冻结启动及 SSL/哈希和业务链，再运行同一核对。11 月 20 日查询 NuGet 官方索引，当前 3.13 系列最高稳定包仍为 3.13.17。当前三个 DLL 的字节绑定来自[来源 PR #88](https://github.com/surface-user/StudyWorkbench/pull/88)。没有证据表明产品已触发某条公告。[11 月 10 日公告](https://openssl-library.org/news/secadv/20261110.txt) · [11 月 17 日公告](https://openssl-library.org/news/secadv/20261117.txt)

本次查询选择、三份二进制摘要、两来源匹配、查询时间和原始响应摘要见[精选证据](evidence/observation.json)。真实 OSV 响应和厂商页面分别取得：首次 OSV 直连超时，后续取得 HTTP 200；同次串行联网复扫在取得 OSV 后又遇厂商连接错误并退出 1。用分别取得的原始数据在 #74 和 #90 的冻结包上离线重算，两者均退出 2，表示存在匹配。原始响应留在忽略的 artifacts 中。额外对照 OpenSSL 3.5.8 时按提交返回 19 条、按标签返回 14 条，说明两种选择不能互相替代。两条公告源也不能互相替代。

自动化执行 `python -m pytest -q backend/tests/test_backend_native_advisories.py backend/tests/test_source_vulnerabilities.py`，Python 3.12 和 3.13 各 46 项通过、退出 0。覆盖版本区间、输入变动、响应顺序与缺项、快照查询不匹配和失败保留。Ruff 和题目 Schema 检查退出 0。运行方式见[打包指南](../../../docs/packaging-windows.md)。本检查仅涵盖两个上游项目、三个已识别的后端 DLL，不构成完整 SBOM、完整漏洞检查或发行验收。
