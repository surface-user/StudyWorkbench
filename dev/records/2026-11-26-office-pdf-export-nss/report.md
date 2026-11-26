# OFF-02q 普通 Office 导出 PDF 时加载的 NSS 与 SQLite 库

基于 [OFF-02p](https://github.com/surface-user/StudyWorkbench/pull/108)。用应用实际的 Writer、Impress 转换命令及两份自制三页文档，确认 Office 从自己的 program 目录加载 softokn3.dll、freebl3.dll、sqlite3.dll。依赖检查将前两者作为普通导出流程中已观察到的加载入口。SQLite 通过 softokn3 的常规导入纳入同一 Office 域。

| 固定组件 | 实际文件 | PE 文件 | 加入前未分类 | 加入后未分类 | 普通转换 |
|---|---:|---:|---:|---:|---|
| Office-Java | 19,743 | 351 | 72 | 69 | DOCX、PPTX 各 3 页 |
| Office-Java 与自包含 Python | 19,746 | 354 | 71 | 68 | DOCX、PPTX 各 3 页 |

每次转换都在独立配置目录和受限 Windows Job 中执行，对照既有复杂样本检查分页、文本和版面。观察器核对进程确属该 Job，核对 soffice.bin 及每个目标模块的实际路径和 SHA256。四次转换均取得三个目标模块的正向记录，源文档与组件在核查后字节保持。采样还有短暂的 Win32 5、299 错误，未取得的快照只作为缺失样本处理。

对两份固定组件清单，检查三个文件在 Office program 中的身份、AMD64 PE32+ 原生可执行 DLL 头及 SQLite 的普通导入。仅在两份已观察清单上使用这项证据。对照上版完整依赖图，其他域、旧边和私有 CRT 搜索范围保持，两个组件的 Office 域均为 156 个入口、216 个节点、1,935 条边。签名、全部 NSS 功能、其他加载方式、Java 成功通信及剩余原生文件仍待分别核实。

## 自动验证

在 Python 3.12.7 和 3.13.17 上运行以下专项，均为 374 项通过，退出 0。

```text
python -B -X utf8 -m pytest backend/tests/test_native_dependencies.py backend/tests/test_office_java_pipe.py backend/tests/test_office_java_bundle.py -q
ruff check backend tools
python -B -X utf8 tools/export_question_schema.py --check
python -B -X utf8 tools/check_native_dependencies.py --office <对应固定组件目录>
```

Ruff、协议校验、两个组件的完整依赖图和四次转换的有界观察均退出 0。本机逐项复比两个旧图与新图，核实正好减少上述三个未知项。首次 pytest 的临时目录父目录缺失，日志和失败记录留存，改用已存在的父目录后重跑了原断言。一次 Ruff 模块入口找不到可执行文件，改用既有发行环境的 Ruff 后通过。

本项仅更新发行检查器、测试和本报告。原件、清单、进程记录与原始图只留本机。人工测试已取消，独立审查暂缓。草稿 PR 的当前 CI 和最终状态见相应 GitHub 检查。
