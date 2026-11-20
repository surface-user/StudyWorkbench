# REL-01k 冻结后端的 Python 依赖关系

以已核对的文件级清单为输入，在本机生成含依赖关系的 CycloneDX 1.6 清单。保留全部 970 个文件、59 个库及其原有 SHA256 和版本，新增 23 个包的 68 条依赖边。完整输出保存在本机，大小 242803 字节。本 PR 提供生成工具、合成测试和汇总结果。

先核对实际目录、来源报告和 55 个已映射 PyPI 包的 METADATA 摘要，再按该 Windows CPython 3.13.17 环境解释 Requires-Dist、版本范围和环境条件。仅当目标包确有归属证据、版本相容时写入依赖边。若声明请求目标包的额外功能，按固定点求解所需额外依赖。本包没有已激活的额外功能，520 项条件声明在本环境未激活。图记录上游声明；是否在特定入口实际加载需独立验证。

有四条有效声明缺少包内端点，涉及三个不同的目标包。在冻结模块目录和物理文件索引中未找到这些顶层模块或同名发行元数据。已列入后续富文档入口核查。原生组件和其他发行载荷的依赖另行跟踪。

```shell
python tools/frozen_python_dependencies.py --payload <实际后端目录> --sbom <REL-01j原版清单> --origins <REL-01j来源目录> --output <新清单文件>
python -m pytest -q backend/tests/test_frozen_python_dependencies.py backend/tests/test_patched_file_sbom.py backend/tests/test_frozen_python_members.py
ruff check tools/frozen_python_dependencies.py backend/tests/test_frozen_python_dependencies.py
```

生成退出 0。用固定官方 CycloneDX 1.6 Schema 校验通过，重新计算 970 个文件摘要，并逐字段比较前后组件相同。Python 3.12 和 3.13 各 41 项通过，覆盖依赖环、下游请求额外功能、条件分支、缺端点及版本冲突。Ruff 通过。原始文件级清单可按 [#100 的固定提交](https://github.com/surface-user/StudyWorkbench/blob/6475d4680579e1aca81aa2e1c8be8038e0f9b9b5/dev/records/2026-11-20-patched-backend-sbom/evidence/backend.cdx.json)取得。独立审查和人工测试按本轮安排跳过。
