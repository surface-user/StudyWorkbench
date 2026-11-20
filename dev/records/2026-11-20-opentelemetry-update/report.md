# REL-03g 修复冻结后端中的 OpenTelemetry API

将现有传递依赖 opentelemetry-api 从 1.45.1 更新至修复 CVE-2026-126360 的 1.45.2。官方通用 wheel 为 60335 字节，SHA256 为 `2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34`，与 PyPI 元数据一致。依赖仍为 typing-extensions，许可为 Apache-2.0，支持 Python 3.10 及以上。两个 Windows Python 环境分别独立安装该 wheel。[项目公告](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-mf5v-w3w3-f6cg) · [PyPI 版本](https://pypi.org/project/opentelemetry-api/1.45.2/)

## 验证与结果

```shell
python -m pytest -q backend/tests/test_written_blocks.py backend/tests/test_learning.py backend/tests/test_imports.py backend/tests/test_source_vulnerabilities.py
./packaging/windows/build-backend.ps1 -Python <发行Python路径>
python dev/records/2026-11-20-opentelemetry-update/verify_wheel.py --exe <冻结后端> --wheel <官方wheel>
python tools/check_api_errors.py --exe <冻结后端> --test-root <新测试目录>
python tools/source_vulnerabilities.py --source . --output <新证据目录>
```

- Python 3.12 和 3.13 各 85 项通过。Windows 发行构建及冻结业务源码对照退出 0，共 48 个业务模块。新可执行文件 SHA256 为 `22434db5516b8dd0e76ef4939fac3614df119cfa9571029aed4f64ef3b32dbc7`。
- 28 个实际内嵌 OpenTelemetry 代码模块与官方 wheel 编译结果逐个相符，包含公告涉及的模块。包内仅有 1.45.2 的该发行元数据目录，METADATA、WHEEL、许可证与入口声明均一致。旧包对照同一 wheel 在涉及的模块被拒，退出 1。两包均保留。核验脚本 Ruff 通过。
- 以新可执行文件实际启动后端，89 项 HTTP 检查通过，包含重启、文件范围读取和确认收据。退出 0。
- 135 个锁定注册表版本的 OSV 复扫含 1.45.2，2026-11-20 06:49:19 UTC 返回 HTTP 200、无匹配，工具退出 3；9 个 Git 或 SDK 项另列。响应 SHA256 为 `a8951bddacf6d6e75295fd045cc53d9acd9e84c7ada55f3f4965f02aec483343`。OSV 数据库覆盖仍未知。

原始发现保留在 [#96](https://github.com/surface-user/StudyWorkbench/pull/96)。其他独立 PR 的旧产物仍对应各自锁文件。完整发行继续跟踪 OpenSSL 修复、其余组件、许可及签名。未合并、未发行，依本轮安排跳过独立审查与人工测试。
