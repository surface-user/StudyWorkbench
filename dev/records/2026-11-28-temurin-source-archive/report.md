# 可选 Office 组件的 Java 对应源码

固定的 Windows x64 Temurin JRE 为 21.0.13+9。已核对官方 OpenJDK 源码归档的 115,231,532 字节，SHA-256 为 `b5232c9980d8a0f0459676c084c41c6e2c771ed9e785890b03c6a438406ad1ca`。JRE 专属元数据与源码专属元数据指向同一 OpenJDK 和 Temurin 构建脚本提交，均与实际 JRE 内的发布记录相符。源码归档元数据的生成系统标为 Linux，归档中包含 Windows HotSpot 和 Java 原生实现。[官方发行文件及摘要](https://github.com/adoptium/temurin21-binaries/releases/expanded_assets/jdk-21.0.13%2B9)

源码归档有 70 个具有通用或 Windows 模块描述符的模块。之前已在运行时映像确认的 50 个模块，各自都找到了对应描述符，31 份直接模块通知在归档中均有同名且逐字节相同的正文。JRE 根通知与固定构建脚本归档的通知模板相同。另用 Git 核对了该脚本归档的全部 153 个文件，每份的 Git blob 和可执行标志均与固定提交一致。[OpenJDK 提交](https://github.com/adoptium/jdk21u/commit/2ab10ca20c191701c3a9f3153bfc6e93d63714c1) · [构建脚本归档](https://codeload.github.com/adoptium/temurin-build/zip/1cf43d7a3e77886bfea7d550a902e151a87d724d)

## 离线复验

从官方发行页取得 JRE ZIP、源码 tar.gz 和各自的同名 `.json`，并单独取得上面的构建脚本 ZIP。使用项目现有的开发 Python 环境运行以下命令。工具只读归档，核对前后均校验五个输入的摘要。

```text
python tools/temurin_sources.py --jre <JRE-ZIP> --jre-metadata <JRE-JSON> --sources <源码-tar.gz> --sources-metadata <源码-JSON> --build-sources <构建脚本-ZIP>
python -m pytest -q backend/tests/test_temurin_sources.py backend/tests/test_temurin_module_notices.py backend/tests/test_prepared_office_sbom.py
ruff check tools/temurin_sources.py backend/tests/test_temurin_sources.py
```

Python 3.12.7、3.13.17 的实物校验均退出 0，生成的汇总字节一致。两版各通过 41 项测试，静态检查退出 0。首次下载中断的归档摘要不符，补全后重新校验通过。首次检查遗漏 Windows 专用模块目录，补入该目录规则后重新核对了全部 50 个模块。

完整归档与逐文件证据仅存在本机。当前工作验证开发端持有对应源码，最终安装器中的源码交付、告知方式和其余再分发义务仍待核实。本项按用户要求暂缓独立审查与人工测试。
