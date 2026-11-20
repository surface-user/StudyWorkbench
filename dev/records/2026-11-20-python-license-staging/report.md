# REL-02f Python 许可归档随包暂存

此前的普通发行入口没有自动纳入已绑定后端的 Python 许可 ZIP。现在收集器对标准后端组件要求归档和预核 SHA256，先核实际后端的全部文件指纹、归档成员和每条文本引用，再独占复制到固定许可位置；重复执行保留相同文件及修改时间。检查器独立重验，发行脚本另传预核 SHA256，避免仅修改外层清单就绕过检查。没有该后端组件的旧通用 stage 保持适用。

以 [#107](https://github.com/surface-user/StudyWorkbench/pull/107) 的精确源码为基线，叠加 [#105](https://github.com/surface-user/StudyWorkbench/pull/105) 必要原生许可保护和 [#102](https://github.com/surface-user/StudyWorkbench/pull/102) 的汇集器与原测试。业务源码、迁移脚本和锁保持基线。最初在 #105 副本核 #107 实包时，document_files 源码不同而退出 1；该失败保留。改用 #107 后，48 个冻结业务模块和迁移源脚本检查退出 0，未把不同源码误报通过。

## 两条可用入口

默认命令保持原有后端构建。新后端完成后，复用既有静态成员匹配，对锁、RECORD、实际 PYZ 和实体文件建立唯一对应，再汇集本次实物的许可。环境包不会直接变成内嵌成员；歧义和未映射计数保留，未经认证的源码提交为 null。随后验证新 ZIP 并暂存。

```powershell
./packaging/windows/build-release.ps1
```

已有后端及与其绑定的 ZIP 可以直接使用，避免脚本再次编译使绑定失效。此路线先检查当前源码与归档，原后端不能放在会被 Flutter 构建或搬移的输出目录中。

```powershell
./packaging/windows/build-release.ps1 -BackendDirectory '<已构建后端>' -PythonLicenseBundle '<许可ZIP>' -PythonLicenseSha256 '<预核小写SHA256>'
```

可选 Python 参数指定同一固定发行解释器，默认仍为原发行环境。原调用方只有发行脚本；CI 独立构建后端，调用方式保持。普通使用说明中的默认一条命令仍适用；上述可选路线无需修改历史任务表。

ZIP 只读解析，不解压或执行内容。压缩输入限 16 MiB、4096 项，声明和实际展开各限 32 MiB；索引限 8 MiB、单文本 4 MiB、1024 个版本和 8192 条引用。成员仅允许 index.json 和内容地址文本，拒绝重复名称/键、链接、危险路径、异常长度、未引用文本、错误摘要及错包。原文和问题记录不被改成完整义务通过。

## 实物与自动化

复用 #107 既有 970 文件后端，exe SHA256 为 `0618da6cfa7141c0e6ab6b3051e4b600caafec302370238577bcb5d97bd5b49a`。没有重建后端或重新生成真实的 55 包许可 ZIP。既有 ZIP 为 249594 字节，SHA256 为 `9701029318376c64583a72a4541fb5336521ac04e0eac2acb979f7b53e716e16`，55 个版本、134 条引用、121 份原文及一个包的问题均通过实际核对。

普通收集器自动复制该 ZIP，暂存 1169 文件和 161 个 PE 的原严格检查退出 0。两次收集内容一致，ZIP 及两份原生许可的修改时间不变；原件保持。清单 SHA256 为 `ec37129413d9b8fcd88fd0ae54ee92010b8a570eb6260cbdef193ec57b69c3ef`。缺输入、旧包 ZIP、损坏归档、外部 SHA 错误、删除暂存 ZIP 后重写外层清单、本机安装路径六个反例均拒绝，保留各自文件及清单。桌面元数据是自编空夹具；未暂存桌面或 Office，不将此组件检查当成完整发行。

另只读运行默认分支实际采用的成员匹配：55 个版本的 METADATA/RECORD 摘要逐项等于现有 ZIP，3344 个来源文件和 14072 行 RECORD 复核，2358 个 PYZ/861 个实体匹配；320 个模块和 109 个实体仍未映射。此探针没有生成归档。默认分支的实际 PowerShell 控制流和自动汇集接口另由自编夹具验证，没有声称重新执行完整编译、签名或真实的 55 包归档生成。

```shell
Q/P -m pytest backend/tests/test_release_inventory.py backend/tests/test_native_dependencies.py backend/tests/test_frozen_sbom.py backend/tests/test_frozen_member_licenses.py backend/tests/test_source_licenses.py backend/tests/test_frozen_python_members.py backend/tests/test_staged_python_licenses.py backend/tests/test_frozen_migrations.py -q
Q tools/frozen_member_licenses.py --payload <后端> --verify-bundle <许可ZIP> --sha256 <预核SHA256>
Q tools/release_inventory.py --stage <新暂存> --python-license-bundle <许可ZIP> --python-license-sha256 <预核SHA256>
Q tools/check_release.py <新暂存> --python-license-sha256 <预核SHA256>
release-python -m ruff check backend tools
Q tools/export_question_schema.py --check
```

本机 Python 3.13.17/3.12.7 各 352 项通过，分别 23.28/23.84 秒，退出 0；Ruff、Schema 退出 0。先前临时父目录未建立导致 46 项准备错误，以及 PowerShell 夹具缺显式模块导入导致两项失败，已修正环境后保持断言通过；合并辅助脚本的缺失输入中止及首轮 Ruff 格式失败也保留。原始日志、XML、完整清单、归档、实物和本机路径只留本机；远端仅必要代码、测试、公开固定输入和本摘要。

当前实现及相关自动化完成，独立 PR 和当前提交 CI 仍须核实，未满足前保持待交付。代码审查暂缓，人工测试取消，不合并、签署或发行。原未签名状态、OpenSSL 版本命中、未知 CRT/内嵌条件、latex2mathml 来源条件和最终分发义务继续跟踪；本文不认证完整 SBOM 或完整产品许可。
