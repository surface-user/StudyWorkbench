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

## 补验 SAL 导入的两份 CRT

固定 sal3.dll 常规导入 MSVCP140_1.dll 和 VCRUNTIME140_1.dll。两份组件分别重跑本报告中的正向诊断，在同一条正式连接存活期间，对持有句柄的 Java 客户端和原生服务分别核对这两份文件。下表中的位置均相对组件根目录；摘要为实际观测到的文件 SHA256。

| 进程 | 加载位置 | SHA256 |
|---|---|---|
| Java 客户端、原生服务 | program/msvcp140_1.dll | bfad5aef4c63a669e3c140655cdfdf395b6c979b400a447bd5dcb65ed8826c3d |
| Java 客户端 | java/bin/vcruntime140_1.dll | 7dd9aa02e271c68ca6d5f18d651d23a15d7259715af43326578f7dde27f37637 |
| 原生服务 | program/vcruntime140_1.dll | 1f2d41c4aa5db0bc33ebf7b66d72943a817d7ce6cbe880502a9403823633093f |

两份组件的八次逐进程、逐文件观察均得到唯一加载路径，对应进程正常退出。Java 目录中没有 MSVCP140_1.dll。组件的 System64 目录中，两份同名库分别与 program 中的副本字节相同。用进程返回的路径和文件身份确定实际加载位置。Windows 64 位系统目录中的两份同名文件均存在，本机的这两份文件与实际加载文件的 SHA256 均不同。

检查器在本机报告中保存全部包内同名候选和 Windows 系统目录候选的摘要，分别报告实际位置和相同字节的副本。未观察到、多个位置、快照不完整、位置超出候选目录或摘要发生变化均保留独立状态。只有两个进程的两份运行库都能判定来源时，本诊断才成功。该判定限于本次正式 Java 客户端与单一服务；普通 Office 入口、依赖图与整包发行门禁继续沿用原规则。

复验命令同上。两份组件的正向运行均退出 0。Python 3.12.7 和 3.13.17 各通过 382 项相关测试，包括同字节不同目录、重复映像、缺项、快照不完整及摘要变化。Ruff、协议导出和 Git 差异检查均通过。

## 本机解释器复核

原正式连接专项保留了两次各 381 项通过的记录；旧日志没有同时保存解释器版本。CRT 补验阶段原先标成双版本的两次 382 项运行，实际使用的是两个 Python 3.13.17 环境。上述原始记录继续保留。下面只计各对应提交上重新核实的本机结果。

| 专项与提交 | Python 3.12.7 | Python 3.13.17 | 单独的 GitHub 检查 |
|---|---|---|---|
| 正式 Java 连接，`21f7965` | 381 项通过，退出 0 | 381 项通过，退出 0 | [PR #121 的 CI](https://github.com/surface-user/StudyWorkbench/actions/runs/45831014107) |
| 两份 CRT 的实际来源，`67dae84` | 382 项通过，退出 0 | 382 项通过，退出 0 | [PR #127 的 CI](https://github.com/surface-user/StudyWorkbench/actions/runs/45837951989) |

两份提交均执行上方列出的四个测试文件，用 `sys.version_info[:3]` 断言指定的精确版本后运行 pytest。本次纠正只涉及自动化回归的本机版本归属；实际 Office/Java 子进程的来源证据在原专项中独立记录。

## 2026-11-28 正式客户端的管道依赖图

对两份已验证的完整组件，将 Java 进程内观察到的 jpipe 和 jpipx 作为独立入口。对应七个包内 DLL 逐一核对固定路径、SHA-256、x64 PE32+ 原生 DLL 类型。这个客户端调用的包内解析只使用这些已观察到的文件。在两份组件中，SAL 的四个私有 CRT 依赖均落在观察到的实际目录。

| 组件 | 原有未归类 PE | 本次剩余 | 新域中的包内依赖 |
|---|---:|---:|---:|
| Office 与 Temurin | 69 / 351 | 67 / 351 | 12 |
| 自包含 Python 布局 | 68 / 354 | 66 / 354 | 12 |

- 对两套实物分别运行 `python tools/check_native_dependencies.py --office <固定组件目录>`，退出 0。与该组件原报告相比，未归类集合仅移出 jpipe 和 jpipx。此前所有进程域的内容逐项一致。新域另列 35 个 API-set 引用及 16 个系统文件引用。
- 分别运行 `python -B -X utf8 tools/check_office_uno_client.py --component <固定组件> --output <新测试目录> --javac <开发用编译器>`。初次运行均未完成管道通信，保留失败报告。在允许使用本机 Windows 管道的独立测试目录复跑，两个正式客户端与服务均正常结束，URLTransformer 调用成功。新的实际加载记录与图中七份文件的路径及摘要逐一匹配。
- `python -m pytest -q backend/tests/test_native_dependencies.py backend/tests/test_office_uno_client.py backend/tests/test_office_java_pipe.py` 在 Python 3.12.7、3.13.17 各通过 351 项。新增用例起初失败，修复后覆盖未知组件、入口摘要变更，以及错误目录中存在同名同字节 CRT 的情况。Ruff 与差异检查退出 0。

此结论仅适用于已实测的正式 Java 管道调用。普通文档转换中的 JVM 启用、其余未归类文件和最终发行整包继续单列。
