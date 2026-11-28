# 可选 Office 转换组件更新

旧 Windows x64 组件为 26.8.1.1。[版本核对 #151](https://github.com/surface-user/StudyWorkbench/pull/151) 记录了 19 条列出同一维护线修复点 26.8.2 的公告。本次准备 26.8.3.1，将可选转换器和项目内 Java 组合切换到新版本。已有学习库和原件沿用原格式。

## 安装包及原始文件

- 官方 MSI 为 376,311,808 字节，SHA-256 为 `0e6918c273eabbdbbd800ee0dacbbf130a14c13c2e4cec861b06dd59e015bf94`。Windows Authenticode 检查为 Valid，发布者为 The Document Foundation。[官方校验元数据](https://download.documentfoundation.org/libreoffice/stable/26.8.3/win/x86_64/LibreOffice_26.8.3_Win_x86-64.msi.metalink)
- 使用 `msiexec /a` 管理镜像解包，退出 0。镜像内 soffice.bin 的产品版本为 26.8.3.1，version.ini 的 buildid 为 `861effc5289d539f15c4c18d1ba8579ffd78728b`。该 buildid 与官方 Git 标签 libreoffice-26.8.3.1 指向的提交一致。原有六项安全配置和三项 Writer 更新配置在固定源码的 Common.xcs 和 Writer.xcs 对应组中均存在。内置 CPython 升至 3.13.18。
- `python tools/lock_office_runtime.py --root <管理镜像> --package <官方MSI>` 退出 0。原始内容共 19,423 个文件、1,584,132,037 字节。用 #134 的 `verify_msi` 从 MSI 文件表、目录表和嵌入 Cabinet 独立核对 19,433 个成员，对应全部 19,423 个路径，退出 0。
- 上游直接转换自制 DOCX 和 PPTX 均输出 3 页 PDF，分节、表格、双栏、图表、页眉页脚和公式标记符合原有断言。上游直接启动曾在试验镜像写入 Python 缓存，导致后续完整性检查拒绝。保留失败现场，再从独立核对过的 19,423 个原始文件构建干净输入并逐个校验。
- 对比旧、新两套实物，LICENSE.html 的 583,943 字节、license.txt 的 512,187 字节及 NOTICE 的 1,859 字节分别完全相同。
- 26.8.3.1 已达到官方公告明确列出的全部 29 个同线修复点。对照 CPython 3.13.18 官方源码所附 wheel，镜像的 pip 26.2.2 有 415 个文件逐字节匹配。setuptools 79.0.1 的 252 个实物文件全部与旧 Office 相同，其中 250 个与上游原名原字节一致，其余两个沿用已有文本补丁和改名。pip 内置 certifi 已升至 2026.10.19，超过 emSign 公告的 2026.10.18 修复点。[LibreOffice 安全公告](https://www.libreoffice.org/security/) · [CPython 发行来源](https://www.python.org/downloads/release/python-31318/) · [certifi 公告](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
- setuptools 的三条数据库记录对应两个问题。macOS 源码构建公告带平台条件，Windows 旧式 wheel 安装公告的版本范围包含 79.0.1，修复版本为 84.1.0。已确认模块存在，转换业务是否执行相关路径仍待验证。[macOS 公告](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c) · [Windows 公告](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w)
- 使用 `tools/compose_office_runtime.py` 分别准备标准与自包含的 Office/JRE 组合。两次来源和目标完整核验均退出 0，分别锁定 19,748 和 19,751 个文件（另附组合总清单）。原始 JRE 为 21.0.13+9。

## 自动检查

- `python -m pytest -q backend/tests/test_office_java_bundle.py backend/tests/test_office_previews.py` 在 Python 3.12.7 和 3.13.17 各通过 47 项，包括旧 MSI 声明的组件启动和组合时均拒绝。同一产品入口对真实 26.8.1 运行时拒绝、对修复版的固定清单接受。
- `packaging/windows/build-backend.ps1` 退出 0。检查器逐项对照了 45 个冻结模块及其嵌套代码。详细清单、媒体与运行目录保存在本机。
- 用 `tools/check_office_previews.py --runtime <已核组件> --docx <复杂分节样本> --pptx <复杂图表样本> --complex-xlsx <复杂工作簿样本> --test-root <全新目录>` 验证普通产品接口。第二次用 `--exe` 指定本次 Windows 后端。两次退出 0，Word 各 3 页、108,085 字节，PowerPoint 各 3 页、77,988 字节；Excel 值查看器各返回 2 张表、15 个单元格。两版经接口返回的 6 对页面 PNG 摘要逐一相同，已核取消再试、原件、重启复用、超预算拒绝与数据库完整性。
- 标准及自包含组件分别执行 `tools/check_office_uno_client.py`，两次均退出 0。包内 Java 客户端经命名管道完成原生 URLTransformer 调用，两端均正常关闭。两套实物各核实 Java 侧 7 个、Office 侧 6 个指定模块，完整性检查在执行前后均通过。
- 此版本需重新核对发行包内的原生依赖、通告适用性、传递许可和安装器内容。默认基础安装器与签名状态另行跟踪。
