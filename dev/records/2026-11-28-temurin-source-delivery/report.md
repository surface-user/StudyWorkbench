# 可选 Office 安装材料中的 Java 源码

构建入口新增可选参数 `-TemurinSources`，接收已核定的 OpenJDK 源码及 Temurin 构建脚本两份归档。与带固定 JRE 的 `-OfficeRuntime` 一起使用，校验通过后才将两份原件及 `manifest.json` 加入 `sources/temurin/`。清单含版本、两项上游提交、下载地址和 SHA-256。暂存目录与既有源码材料均受覆盖保护。[构建与核对方法](../../../docs/packaging-windows.md#为可选-office-包配套-java-源码)

## 实物核对

- 使用 `python tools/stage_office_runtime.py --runtime <Office与JRE> --stage <新暂存目录> --temurin-sources <OpenJDK源码> <构建脚本>` 完成真实组件复制和整份运行时校验，退出 0。可选 Office 目录含 19,743 个文件。另有 3 个源码交付文件共 115,968,075 字节。对该应用根目录执行 `python tools/temurin_source_delivery.py --installed <暂存目录>` 退出 0。
- 从上述暂存中选取固定 JRE 和源码目录，以 Inno Setup 7 编译隔离测试包。实物大小 154,914,967 字节，SHA-256 为 `01e9416173c90a8f4dfb53790f2f2d3cc59ba6c2fa9490dfa1792758fe84b04d`。复用[基础安装器字节核对方法](https://github.com/surface-user/StudyWorkbench/pull/119)，按编译输入顺序比对成品压缩流的全部 319 个文件，共 267,832,083 字节，退出 0。再从成品流直接恢复两份源码归档及清单，与固定摘要及清单字节再次匹配。
- 同一仅写文件的测试包经过实际静默安装。初次通过启动器运行超过 4 分钟没有安装子进程或日志，核对进程身份后结束了本次启动器。直接启动的首次尝试返回 1，安装目录未创建。随后为子进程指定专用 `TEMP` 和 `TMP`，使用 `/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<新的测试应用目录> /LOG=<本机日志>`，退出 0。实际安装了 319 个文件、267,832,083 字节，位置、文件集合和逐文件摘要均与暂存输入完全一致。两个 Python 版本分别运行 `--installed` 复验，均退出 0。

## 自动化

`python -m pytest -q backend/tests/test_temurin_source_delivery.py backend/tests/test_temurin_sources.py backend/tests/test_temurin_module_notices.py backend/tests/test_office_previews.py` 在 Python 3.12.7 和 3.13.17 各通过 45 项。初轮两项既有 Windows 子进程退出检查在受限环境失败，在专用目录重新运行原测试后通过。调整失败时的目录创建顺序后，两版各复跑 6 项源码交付回归并再次暂存真实归档，均退出 0。Ruff、打包脚本语法和 `git diff --check` 退出 0。未选择 Office 或只提供单个源码归档时，打包入口会在构建前拒绝该配置。

本次编译的是用于验证收录的 JRE 与源码测试包。普通安装器保持默认配置，含完整 Office 的最终应用安装器仍须通过既有原生依赖、许可及签名等发行条件。完整归档和测试包仅保存在本机，按用户要求暂缓独立审查及人工测试。
