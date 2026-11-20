# REL-03f 冻结后端 PyPI 软件包漏洞核对

核查对象是 REL-01h 保存的冻结后端。查询前后分别重新计算 969 个文件的内容摘要，整体指纹为 `77b7e5ade7568c557b6a4b16d408641101dcd764163f702ffdeaa9beee22407e`。将已有归属证据的 55 个包与当时的 CycloneDX 清单按名称和版本逐一匹配。PyInstaller 启动程序、CPython、原生 DLL 和归属未知的字节另行跟踪。

两次向 OSV 查询均收到 HTTP 200。第二次服务器时间为 2026-11-20 06:46:32 UTC，查询摘要为 `3454562fc34c94de5e72909179bf45cd2cfd8e2ac4edb9debedcd49bac00292d`，响应摘要为 `a32634d8a53989352a8063a3c3d4ed9c46e5f0d6ef9874afbfd18790bd5928ab`。OpenTelemetry API 1.45.1 返回 GHSA-mf5v-w3w3-f6cg，对应 CVE-2026-126360。另 54 个包在该次查询未返回公告。上游将问题定为中等严重度，修复版为 1.45.2。本次核查没有测定产品实际暴露程度。[上游安全公告](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-mf5v-w3w3-f6cg)

```shell
python tools/check_frozen_pypi_advisories.py --payload <REL-01h冻结目录> --output <新证据目录>
python -m pytest -q backend/tests/test_frozen_pypi_advisories.py backend/tests/test_source_vulnerabilities.py backend/tests/test_backend_native_advisories.py
ruff check tools/check_frozen_pypi_advisories.py backend/tests/test_frozen_pypi_advisories.py
```

扫描报告退出码 2 表示发现匹配。首轮 PowerShell 宿主返回 1，保留原始报告；第二次显式转发进程退出码，得到 2。两个 Python 版本的专项各 51 项通过，Ruff 通过。测试覆盖漏项、重复项、替换清单、包文件变化、分页和网络失败。工具对不匹配的包拒绝沿用历史归属，查询证据写到包外新目录。

REL-03g 另行更新锁定版本、核实重建包内代码并复扫。完整发行还依赖原生公告修复及其他发行组件核查。按本轮安排跳过独立审查和人工测试。
