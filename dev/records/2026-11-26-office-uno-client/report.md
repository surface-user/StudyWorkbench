# OFF-02r 自带 Java 与原生 UNO 服务的成功调用

基于 [OFF-02q](https://github.com/surface-user/StudyWorkbench/pull/115)。使用随包 JRE、libreoffice.jar 和原生 uno.exe，验证 Java 客户端跨本机命名管道调用 URLTransformer。两个固定组件均完成了完整连接、远程调用及正常退出。

| 组件 | 全部文件核验 | Java 进程内验证 | 原生进程内验证 |
|---|---:|---|---|
| Office-Java | 19,743 | java.exe 与 7 个模块 | uno.exe 与 6 个模块 |
| Office-Java 与自包含 Python | 19,746 | java.exe 与 7 个模块 | uno.exe 与 6 个模块 |

Java 通过 UnoUrlResolver 取得远程代理，核对服务实现名，并要求原生 parseStrict 返回合成 HTTPS 地址的协议、域、目录、随机文件名、查询及片段，再通过原生 assemble 核对应用专用 URI。本次输入仅作为字符串解析。两个进程在同一个受限 Windows Job 中运行，观察器持有创建时返回的进程句柄，在连接存活期间核对真实映像、模块目录和 SHA256。

Java 进程中确认 jpipe、jpipx、SAL、自带 JVM、Java 运行库及两份 Java 目录内的 CRT。原生进程中确认 SAL、cppu、URLTransformer 所属的 mergedlo、iolo、binaryurp 及 Office 目录内的 VCRT。两个进程均以 0 退出，运行前后核验组件、Java 源和类、编译器及检查器身份。

诊断使用两个一次性标识、仅开放一个服务并设置 singleaccept。原生启动器按实例名返回该服务。诊断进程使用独立临时配置、固定组件目录和项目的进程资源限制，普通 DOCX/PPTX 转换入口保持原命令。实现依据见 [UNO SDK](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/odk/docs/tools.html) 和[固定版本的原生启动器](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/cpputools/source/unoexe/unoexe.cxx)。

## 复验

```text
python -B -X utf8 tools/check_office_uno_client.py --component <固定组件> --output <全新本地目录> --javac <既有可信JDK的javac.exe>
python -B -X utf8 tools/check_office_java_pipe.py --component <固定组件> --output <另一个全新本地目录> --javac <既有可信JDK的javac.exe>
python -B -X utf8 -m pytest backend/tests/test_office_uno_client.py backend/tests/test_office_java_pipe.py backend/tests/test_native_dependencies.py backend/tests/test_office_java_bundle.py -q
ruff check backend tools
python -B -X utf8 tools/export_question_schema.py --check
```

在两个组件上分别运行正向工具，在原组件上回归既有缺失管道诊断，均退出 0。两个 Python 版本（3.12.7、3.13.17）各通过 381 项相关测试。Ruff 和协议导出检查均退出 0。完整清单、私有标识、系统路径及运行日志留在本机。

早期受限运行得到 NoConnectException。获得本机端点后，独立 UNO 启动器缺少 LO_LIB_DIR 导致服务无法装载。现在仅在该诊断进程内将其绑定到锁定的 program 目录。试验还观察到该固定组件对已解析的 HTTPS 地址重新组装时重复域名；该路径仍未通过。失败样本均已保留。

此证据覆盖 SDK 的 Java 客户端与原生服务，普通文档转换中启用 JVM、JDBC、其余原生依赖及整包发行仍待分别核实。当前批次的独立审查暂缓，人工测试已取消。
