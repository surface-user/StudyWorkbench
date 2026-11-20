# OFF-02p：固定 Java UNO 管道开发诊断

在开发环境中提供可复跑的有限诊断：使用项目自有 Java 类、固定 Office jar 和既有 Temurin JRE，验证 `PipeConnection` 能加载 JNI 包装库并到达“管道不存在”的原生 OPEN 分支。该结果尚不能证明成功管道通信或普通 Office 宿主执行。

基于已核 #104 精确 `b6b29e87766b1659a6cf1a302b9c37954c5b195b`。仅新增检查器、Java 源、可信边界测试和本报告四个文件；基线 508 个文件保持。完整任务表、完整依赖清单、上游源码、系统工具路径及原始输出留本机；不重写历史任务表或整份打包指南。Office 原有背景与阻断见[原发行报告](../2026-11-10-release-integrity/report.md)。

## 使用与边界

从仓库根目录运行，先自行提供可信的既有 JDK 编译器；工具不会下载、安装或修改系统配置：

```powershell
python tools/check_office_java_pipe.py --component <固定Office-Java组件目录> --output <尚不存在的本地结果目录> --javac <既有javac.exe>
```

只接受现有 Office-Java 与 Office-Python 自包含组合的两个固定组件锁。输出必须与组件分离、父目录已存在且路径不经重解析点；已存在的结果目录拒绝覆盖。编译器只用 `--release 11` 编译仓库内精确 hash 的自有诊断源；该编译器属于开发工具，不分发进应用，也不是产品执行入口。

固定 JRE 子进程只运行生成的自有类；以 parent=null 的 URLClassLoader 加载固定 `libreoffice.jar`，核实际 `NativeLibraryLoader` 返回的 jpipe 文件身份。诊断使用新生成的 UUID 管道名，预期不存在，不指定已有服务；只调用连接的 OPEN 分支，不创建监听器。只有 `IOException` 包裹精确 `RuntimeException("cannot create native pipe")` 才接受。意外连接成功判失败；read/write/flush/close 数据通信路径未在本项验证。

沿用受控 Windows Job：隐藏进程、20秒、1GiB、最多4进程，独立空工作目录和临时/用户目录，最小环境；结果上限64KiB。Java 完整写入 staging 后原子改名，避免半写结果；观察器核自有 Java PID/image/Job 及七个实际模块路径/hash，进程退出后再核完整组件、控制器、Java 源/类及编译器字节保持。失败保留；没有执行任意用户脚本、Office服务或产品业务接口。

## 来源、图与实测分别记录

固定 LO commit `bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1` 的 [PipeConnection](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/ridljar/com/sun/star/lib/connections/pipe/PipeConnection.java) 初始化调用 NativeLibraryLoader；[Windows wrapper](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/jurt/source/pipe/wrapper/wrapper.c) 将自身绝对 DLL 路径 jpipe 改为 jpipx，使用 `LOAD_WITH_ALTERED_SEARCH_PATH`。实际两库均 AMD64 原生可执行 DLL，普通导入为已知 SAL/VCRT 或系统 API，无延迟导入；这只是导入图证据。

固定 jar SHA256 `abb1956fdfc79ddd001642951cf76c1b573d48eb4cf869c9e67dcd6b26fde1d0`；jpipe `c55a66a75dfc23c401fe5f4dc9878dc8f9f11174a531e73a75032706a30471ad`，jpipx `b2484a3d66be395f730c32d0fd7bcd4b2bb80143f8d77217ab412c6975db5379`。本机保留10份相关固定源的 Git blob/SHA 与两个实际 class member hash；源码关联不冒充可重现编译。

修正后自包含组合的工具实测 `runtime04` 退出0：完整19746文件前后保持，预期 JNI 失败分支及七个实际模块均通过，零采样错误。jpipe/jpipx/SAL 实际来自 program；JVM/Java/VCRT/MSVCP 来自 java/bin 或其 server 子目录。这里的 Java CRT 字节不同于 Office program CRT，绝不据此替换 Office 静态域或认证普通宿主。

原 Office-Java 组合以同一工具在新目录 `runtime05-original` 也退出0：完整19743文件前后保持、同一精确JNI分支与七模块归属通过、零采样错误。两份结果、编译日志、类和摘要的只读复核入口留本机；不会在只读复核中重新运行 JVM 或编译器。

固定自有 Java 源 SHA256 `3845c5d1ebe2e164c5eaaab3a446857409fb83fd94d16afc7eb1a88abb66edb0`；本机使用 javac17.0.11、release11，生成类 SHA256 `19c3d48b42d90bd47b3f1a60214ac8184c41a7fad615cf0220886b9407bc1fdc`。工具记录实际编译器/控制器身份于本地输出，不在 Git 保存系统路径。既有 #82 冻结程序的45业务模块与当前源保持，未声称本项新本地应用构建。

## 自动化与交付

Q3.13.17/P3.12.7 分别运行：

```text
python -B -X utf8 -m pytest backend/tests/test_office_java_pipe.py backend/tests/test_office_java_bundle.py backend/tests/test_java_runtime_preparation.py -q --basetemp=<新隔离临时目录> --junitxml=<本机原始结果>
python -m ruff check backend tools
python -B -X utf8 tools/export_question_schema.py --check
python -B -X utf8 tools/check_frozen_sources.py --exe <既有匹配冻结程序>
```

两环境相关测试各90通过、1既有warning，Ruff/Schema/45模块冻结核源均退出0。新增21例检查原件/旧证据不可覆盖、固定自有源改动、class/结果预算、返回对象/精确布尔/PID/普通宿主过度声明，以及同字节 CRT 处于错误域仍拒绝；CI只用这些小型夹具，不依赖本机Office/JDK原件。

旧失败全留本机：首个原型真实 JNI 诊断成功；工具最初相对组件路径未归一化而失败，修正为绝对路径且保留原有重解析拒绝；随后读到 Java 尚未写完的空结果，改 staging 原子提交后在新目录通过。专项初次超长参数默认名称触及 Windows 环境变量长度限制，改短标签后保留原断言，未删失败或调低测试。准备脚本一次文本替换断言与一次 Ruff lambda 检查失败也保留；最终只发布实际通过的源版本。

当前实现/本机自动化已完成，独立草稿 PR/current-head CI交付中；人工依用户指令取消，审查按用户安排延后，均不记为通过。无合并或发行。

本项不改 native/check_release、运行时搜索域、组件、依赖锁或产品接口；原71个未分类项全部保持。普通 Office 的实际 Java classloader/管道使用与 NativeLibraryLoader 的 fallback 尚未证明，任意动态加载/USER_DIRS/SxS/系统来源、成功IPC、完整Java桥及完整Office发行均不因此完成。
