# 可选 Temurin JRE 的模块与随附通知

## 核对结果

从两种已准备的 Office 组件分别读取固定的 Windows x64 Temurin JRE 21.0.13+9。官方 ZIP、Java 锁清单、各自的 CycloneDX 1.6 Java 层和实际目录中的 315 个文件逐项相符。开发机 JDK 的 `jimage list` 从各自的运行时镜像找到 50 个模块描述符。两次核对得到相同的模块、通知和正文映射。[Temurin 官方发布](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.13%2B9)

| 检查 | 结果 |
| --- | --- |
| 镜像模块和通知目录 | 50 个模块各有一个同名通知目录。没有孤立目录。 |
| 三种共同文件名 | 50 个目录中均有 LICENSE、ADDITIONAL_LICENSE_INFO 和 ASSEMBLY_EXCEPTION。三份正文分别载有 GPLv2、涉及特定文件的 Classpath Exception 说明和 OpenJDK Assembly Exception。其他 147 份文件是指向正文的文本引用。 |
| 补充通知 | 7 个模块共附有 29 份，正文标题可识别为 28 个不同标题。一个模块将 CLDR 通知指向另一模块中的同一份正文。 |
| 模块通知合计 | 179 份，其中 31 份直接提供正文，148 份文本引用全部能解析到实际正文。未发现缺失的共同文件、断开的引用、无法归属的文件或无法读取的正文。另有一份独立的 Temurin 根 NOTICE。 |
| 仅在发行元数据中出现的名称 | release 列有 70 项，其中 20 项在此 JRE 镜像中没有模块描述符；无法据此确定这些名称对应已交付组件或遗漏的通知。 |

例如，随包标题将 FreeType 2.14.3 和 Harfbuzz 14.2.0 归在 `java.desktop`，ICU4J 72.1 归在 `java.base`。CLDR v43 的正文位于 `java.base`，`jdk.localedata` 引用这份正文。这些版本出自发布者的通知标题。底层软件的实际版本、每项具体再分发义务、对应源码交付及最终安装器中的材料仍需单独核实。

## 通知正文的源码来源

从官方发布资产核对 JRE 压缩包的专属元数据，压缩包 SHA-256 与实物相同。元数据中的 OpenJDK 源码提交和 Temurin 构建脚本提交都与 JRE 内的 release 对应。逐字节比对后，28 份补充正文与该 OpenJDK 提交下各模块的法律文件一致，三份共同正文与同一提交中的顶层文件一致。Temurin 根 NOTICE 与构建脚本提交中的 `sbin/NOTICE.template` 字节一致。31 份模块正文和 1 份根通知均已定位来源。[OpenJDK 固定提交](https://github.com/adoptium/jdk21u/tree/2ab10ca20c191701c3a9f3153bfc6e93d63714c1) · [Temurin 根通知来源](https://github.com/adoptium/temurin-build/blob/1cf43d7a3e77886bfea7d550a902e151a87d724d/sbin/NOTICE.template)

另以官方发布资产摘要核验了同版 Windows 的供应商 CycloneDX。其 JRE 行中的文件名和源码提交与实物对应，但记载的压缩包摘要与最终发布 ZIP 不同，差异原因未确认。当前交付文件身份使用与最终 ZIP 实测相符的 JRE 专属元数据。[官方发布资产](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.13%2B9)

## 复现和验证

在本机保留每份通知的相对位置、原始哈希、引用链、正文哈希及可识别的发布者标题。工具使用开发者提供的 JDK 镜像读取器，无需运行待核的产品 JRE。逐文件输出放入 Git 忽略的本地目录。

```text
python tools/temurin_module_notices.py --java <prepared-java> --jre-zip <pinned-zip> --prepared-bom <verified-cdx> --bom-sha256 <previously-verified-cdx-digest> --jimage <developer-jdk-jimage> --output <new-local-json>
python -m pytest -q backend/tests/test_temurin_module_notices.py backend/tests/test_prepared_office_sbom.py
ruff check tools/temurin_module_notices.py backend/tests/test_temurin_module_notices.py
```

两次实物核对均退出 0。两份结果的父清单哈希各自不同，其余字段逐项相同。首次运行在包含中文的路径上遇到开发机 JDK 17 默认输出编码不一致，已显式使用 UTF-8 并在原路径重跑通过。合成与相邻回归共 35 项通过，静态检查退出 0。人工测试已依用户要求取消，审查暂缓。本次未生成新的安装器。
