# REL-02d 冻结后端的 Python 许可材料

本地归档覆盖已通过实包文件和模块归属核验的 55 个 PyPI 发行版本。每个包都可查到许可或通知文本。共 134 条引用，其中 132 条与安装记录的 SHA256 相符，另外两条来自固定版本的项目补充资料。相同原文按内容去重，ZIP 内共 121 份不同文本和一份按包索引。可按索引中的 text_path 找到每个文件。

使用同一修复后 Windows 后端，两次独立收集均得到 249595 字节的 ZIP，SHA256 为 `00b225d135bcb4d9ab3990281a45cad42f4477e0e209fd99c97f8268940b1166`。重新打开实际 ZIP 检查完整性、校验全部 134 项引用的大小与 SHA256、对照成员集合，均通过。目录外的源码、个人资料和开发环境未打进许可归档。完整材料留在本机，本 PR 交付生成工具和验证记录。

latex2mathml 仍保留两项来源问题。上游发行归档缺项目许可证正文，已有固定标签的补充原文；其符号数据记录了 LPPL，原始作品和供应方修改条件仍需核实。当前后端确有该包的模块，物理文件清单中未发现该符号表数据文件。不得据此断定所有上游义务已经审核。原生库的许可随包工作另见 [#99](https://github.com/surface-user/StudyWorkbench/pull/99)。

```shell
python tools/frozen_member_licenses.py --source . --payload <冻结后端目录> --origins <已核实的来源报告目录> --output <新的许可ZIP>
python -m pytest -q backend/tests/test_frozen_member_licenses.py backend/tests/test_source_licenses.py backend/tests/test_frozen_python_members.py
ruff check tools/frozen_member_licenses.py backend/tests/test_frozen_member_licenses.py
```

收集器核对实际后端的完整文件指纹，按已证实的成员定位发行包，并比对 METADATA 和 RECORD 的原始摘要。失败保留输入与已有输出。两个 Python 版本各 77 项测试通过，Ruff 通过。合成回归覆盖同文去重、每包的问题记录、替换文件、元数据不符和输出冲突。此批交付材料汇编；发行方的最终义务判定、其他载荷、签署及发布另行跟踪。
