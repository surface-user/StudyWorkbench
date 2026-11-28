# REL-03j　Office 内置 setuptools 的公告适用范围

2026-11-28，以 [Office 26.8.3.1 更新 #153](https://github.com/surface-user/StudyWorkbench/pull/153) 的 Windows x64 原始组件、两种 Java 组合和同一提交的源码及冻结后端核对。**Windows 版本命中仍待处置**。学习资料导入、日常转换、Java 客户端和用户安装脚本中均未发现使用 Office 内置 setuptools 安装 wheel 的入口。

## 组件与上游公告

原始组件内的 CPython 为 3.13.18，pip 为 26.2.2，setuptools 为 79.0.1。逐文件比对结果见[组件更新报告](../office-windows-runtime-update/report.md)。本次在对应版本的 `setuptools/wheel.py` 确认旧式安装方法仍存在，`setuptools/installer.py` 和 `setuptools/command/easy_install.py` 都保留了对它的引用。该包随 Office 交付。[CPython 官方发行页](https://www.python.org/downloads/release/python-31318/)

按 `PyPI/setuptools@79.0.1` 查询 PyPI 版本接口和 OSV，两库各返回相同的三条记录。下表按别名归并。[PyPI 版本接口](https://pypi.org/pypi/setuptools/79.0.1/json) · [OSV 查询说明](https://google.github.io/osv.dev/api/)

| 上游问题 | 固定版本与运行条件 | 此次 Windows 交付的判定 |
|---|---|---|
| GHSA-xmj3-9gf7-h52w | 旧式 wheel 安装；上游受影响范围为 38.2.2 至小于 84.1.0，84.1.0 修复。 | 版本、平台、相关代码均符合。下述产品入口没有发现调用，所有 Office 扩展或外部调用的可达性未知。保留供应商修复或发行处置待办。[上游 Windows 公告](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w) |
| GHSA-h35f-9h28-mq5c、PYSEC-2026-3447（同一 CVE-2026-59890） | 在 macOS APFS/HFS+ 上生成源码发行包。上游公告标记受影响版本至 82.0.1，修复版本一栏为空；OSV 的修复边界为 83.0.0。 | 79.0.1 命中版本范围，本次 Windows x64 运行环境和转换、打包流程不满足上述 macOS 构建条件。[上游 macOS 公告](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c) · [OSV 记录](https://osv.dev/vulnerability/PYSEC-2026-3447) |

## 正常产品和安装路径

| 入口 | 实际行为与证据 |
|---|---|
| 桌面及后端 | 对 #153 的 `create_app` 生成路由清单，共 94 个路径、116 个 HTTP 方法与路径组合。核对路由处理、桌面后端启动参数和 Windows 启动器，没有发现接受 Python 依赖安装请求的入口。生成清单时 GET/HEAD 的两个重复操作标识警告保留。 |
| 导入普通 wheel | 将官方 pip 26.2.2 wheel 通过普通资料入口导入，在两套独立临时库中分别启动源码后端和 #153 冻结后端。两次导入均完成，各保存一个完整原件；文档信息均返回 200、类型 `unsupported`，选取该资料进行 Office 分页转换均返回 422。 |
| Word、PowerPoint、Excel | `office_previews.py` 限制分页源为 DOCX/PPTX。`office_runtime.py` 启动固定的 `soffice.com`，参数指定 Writer 或 Impress 导出 PDF；冻结模式由固定后端启动同一命令。`document_files.py` 使用工作簿值查看器处理 XLSX。#153 的实际普通接口对源码和冻结版各验证 Word/PPT 各 3 页、工作簿 2 表 15 格。 |
| 项目内 Java | `compose_office_runtime.py` 与 `stage_office_runtime.py` 按锁复制文件。核对两份实际 Java 客户端记录，标准和自包含布局均启动组件内 `java.exe` 与 `uno.exe`，经命名管道完成 URL 转换服务调用并正常退出。 |
| Windows 安装和构建 | `prepare-office-runtime.ps1` 验证签名、以 MSI 管理模式解包并生成锁。`setup.iss` 递归复制发布目录，只在需要时另运行 WebView2 安装器。`prepare-tools.ps1` 与 CI 确有 `pip install -r backend/requirements.lock.txt`，执行者为用于构建后端的独立 Python 环境。 |

**复核资料导入**。使用 SHA-256 为 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`、1,819,850 字节的官方 wheel。以新数据目录启动源码或冻结后端，调用默认空间的 `POST resource-add-jobs`，轮询任务至完成，然后对返回的节点请求 `GET document` 与 `POST previews`，后者带原件摘要。两次与保存原件的字节比对和返回值断言均退出 0。[官方 wheel](https://pypi.org/project/pip/26.2.2/#files)

上游直接启动的历史试验镜像留有 9 处缓存目录、39 个 Python 缓存文件，包括 `uno` 和 `pythonloader`；其中没有位于 pip 或 setuptools 目录的文件。缓存仅为该次运行的部分痕迹。完整 Python 调用轨迹、第三方扩展、独立调用随包工具及最终安装组合仍未覆盖。本次保留供应商文件，未复现漏洞。
