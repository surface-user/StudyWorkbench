# REL-01j 修复后后端文件级 SBOM

[CycloneDX 1.6 清单](evidence/backend.cdx.json)列出这份 Windows 冻结后端的全部 970 个文件。每个文件使用相对于后端目录的名称和 SHA256，即使两个文件内容相同也各有一项。应用版本对应 [#98](https://github.com/surface-user/StudyWorkbench/pull/98) 的 `9c3978cb31bda6279d7b6f60235a1e3832edf37a`。清单大小 239475 字节，SHA256 为 `cdfc3c2720e0b8f3bb0b5b37612ddc57eb165060905ec37c47bc697b9f19960d`。

59 个库包括通过本地包记录和冻结内容比对确认的 55 个 PyPI 发行版本，另有固定 CPython、PyInstaller、OpenSSL 和 libffi。对 libcrypto-3.dll、libssl-3.dll 和 libffi-8.dll 重新核对 [#88 的固定来源记录](https://github.com/surface-user/StudyWorkbench/blob/481d93aacb5f3468c7e54d5989b0f365721b0081/packaging/licenses/cpython-native-3.13.17/provenance.json)中的长度和哈希。清单保留其实际相对位置。OpenTelemetry API 已为 1.45.2，OpenSSL 仍为有已知公告的 3.5.9。

选择这些字段用于逐文件比对及按版本查找公告。完整扫描日志、开发环境和安装路径留在本机。来源检查覆盖 48 个业务模块、额外 311 个内嵌 Python 模块和 154 个基础库归档成员。单靠 Python 来源核查仍有 46 个物理文件未归属，另有独立原生证据；全部文件均已计入清单。Office、桌面端和安装器是其他交付物。组件及传递关系标为 incomplete。[CycloneDX 定义](https://cyclonedx.org/docs/1.6/json/)

## 复验

使用项目固定的 Syft 和发行 Python，先运行以下命令。输出目录须全新。Git 清单从该提交的实际树核对后生成，包含 backend/study_workbench、backend/migrations 和 tools/frozen_entry.py。

```shell
python tools/frozen_sbom.py --payload <冻结目录> --source . --source-head 9c3978cb31bda6279d7b6f60235a1e3832edf37a --exe-sha256 5fa6da04bcabcd1b6cd7fd8639a04ccba29e5f77254eebab08238e3fed960d7d --syft <固定Syft> --output <扫描目录>
python tools/frozen_python_origins.py --payload <冻结目录> --source . --coverage <扫描目录>/coverage.json --python-package <固定CPython归档> --source-tree <Git清单> --output <来源目录>
python dev/records/2026-11-20-patched-backend-sbom/export_sbom.py --payload <冻结目录> --coverage <扫描目录>/coverage.json --origins <来源目录> --native-profile <REL-01i固定provenance.json> --output <新的SBOM文件>
```

前两个工具按设计返回 2，表示产品来源覆盖仍有缺口。初次来源核查遗漏冻结入口，返回 1；对照该提交补入入口后完成。覆盖报告 SHA256 为 `724651ad7980f797c8a3f767b56fd44f24db66cbfedd250b7c2010e4d385aaf0`。来源报告 SHA256 为 `ce62e2d92ba32f429589411d1670eed4e089feaadd3fd8f3157a3791b5b687e8`。

导出退出 0。用固定官方 1.6 Schema 及其两个引用 Schema 独立校验通过，逐一从实际目录重算 970 个 SHA256，与清单完全相同。两个 Python 版本运行 `python -m pytest -q backend/tests/test_patched_file_sbom.py backend/tests/test_frozen_python_origins.py backend/tests/test_frozen_python_members.py`，各 78 项通过。导出器及测试的 Ruff 检查通过。独立审查和人工测试按本轮安排跳过，完整发行及最终包传递许可仍持续跟踪。
