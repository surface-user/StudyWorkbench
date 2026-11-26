# 可选 Office 与 Java 的分层组件清单

工具复用现有固定组件锁、Java ZIP 校验和原生加载域分析器。清单根节点标记为本机准备的可选组件，文件引用沿用基础安装器清单的挂载路径。提供普通安装器、其已验证的清单和预核摘要时，工具检查两者的对应关系及 Office 挂载目录是否出现。[基础安装器清单](https://github.com/surface-user/StudyWorkbench/pull/119)

## 实物

| 可选准备目录 | 逐文件核对 | 清单组件数（根节点另计） | 已解析的组件内 PE 依赖边 | 加载域仍未知的 PE |
|---|---:|---:|---:|---:|
| LibreOffice 与 Temurin JRE | 19743 | 19784 | 1020 | 69 / 351 |
| 同一组合加自包含 Python 启动布局 | 19746 | 19787 | 1067 | 68 / 354 |

用 Windows Installer 数据库的只读接口读取固定 LibreOffice 26.8.1 MSI，核对 CAB 的 19427 个成员。它们映射到 19417 个实际目标路径，其中 10 个路径各有两个字节不同的 CRT 候选。逐个核对 CAB 成员长度和 SHA256 后，以目标路径和实际文件摘要确定采用的成员。Temurin 21.0.13+9 的 315 个文件与固定官方 ZIP 成员逐一匹配。8 个应用目录 CRT 副本和自包含布局增加的 3 个 Python 入口所需副本，通过各自来源路径和摘要关联。三份项目生成的组件索引另列。

两份清单各记录 38 种 CRT 文件名、版本和架构的组合，并根据 PE 中的发布者及版本字段识别了 CPython 3.13.15。两布局分别有 46 和 47 个 CRT 文件位置，包括组件自身携带的 Windows 通用运行库。这里确认的是它们随 Office 或 Java 下载包提供的字节。MSI 中的原始 DLL 供应链、独立签名和许可义务另待核实。依赖边保留静态检查器解析到包内库或私有 CRT 的目标，未知项仍逐个标注。

与普通测试安装器及其固定清单复比，基础安装器的已验证挂载路径中没有这两套可选组件。两份准备目录的清单均通过 CycloneDX 1.6 官方 JSON Schema。完整文件、来源和加载关系清单仅保存在本机。Office 加载门禁、含 Office 的最终安装器实物、签名与发行条件仍待完成。

## 验证

```shell
python tools/prepared_office_sbom.py --directory <准备目录> --msi <固定Office原包> --jre-zip <固定JRE原包> --output <本机新清单> --base-bom <已验证普通安装器清单> --base-bom-sha256 <预核摘要> --base-setup <普通安装器>
python -m pytest -q backend/tests/test_prepared_office_sbom.py backend/tests/test_office_java_bundle.py backend/tests/test_native_dependencies.py
python -m ruff check backend tools
python tools/export_question_schema.py --check
```

本机 Python 3.12.7 和 3.13.17 各通过 369 项，Ruff 与题目协议检查退出 0。Office 核验临时展开固定 CAB，需要约 2 GiB 可用空间。首次试用系统 tar 顺序读 CAB 时遭遇 LZX 解码错误，随后改用 Windows 自带的 expand 解包，核对所有成员后清理工具自己的临时目录。整个流程没有启动 MSI 安装或 Office 转换进程。
