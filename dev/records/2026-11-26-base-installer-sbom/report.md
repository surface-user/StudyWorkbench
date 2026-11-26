# REL-01l 普通 Windows 安装器成品清单

## 范围和复现

核验 [基础打包 PR #110](https://github.com/surface-user/StudyWorkbench/pull/110) 生成的普通 Windows 测试安装器。当前 Inno 配置用一个未加密的 LZMA2 数据流封装文件。工具按实际编译日志恢复输入顺序，检查暂存清单、逐文件长度、SHA256、原字节或 Inno 对可执行文件使用的变换，并在输出前复核输入。成品摘要写入 CycloneDX 1.6 的根组件。此检查证明输入文件字节出现在该数据流中，安装器元数据和安装行为另行验证。

```shell
python tools/base_installer_sbom.py --stage <打包暂存> --setup <安装器> --runtime <离线运行时安装器> --compiler-log <同次编译日志> --output <本机新清单> --backend-sbom <同载荷后端清单> --desktop-report <桌面来源核验> --webview-manifest <对应版本的WinGet清单>
```

后三个参数可选。后端来源材料必须与该次暂存全部后端文件匹配。桌面复制件只复用已核上游来源并与当前字节一致的记录。工具把来源材料的摘要写入报告，并保留部分覆盖标记。

## 成品与依赖

工具核对 1292 个暂存文件（含暂存索引）及离线运行时安装器，退出 0。55 个冻结 Python 包与随包许可归档匹配。970 个后端物理文件与后端清单一致，68 条有效依赖关系已关联，另有 4 条有效声明缺少已映射的目标。桌面输入的 41 项中，27 项复制件匹配 7 个来源组件，生成的 AOT 与本机代码来源仍需单独证明。

WebView2 离线安装器摘要匹配微软 WinGet 的 x64 条目。另在本机只读解包，用 7-Zip 25.01 的 BCJ2 解码实现还原更新程序。内层清单的版本、长度和 SHA256 与实际内嵌安装器匹配，运行时为 156.0.4314.42。对更新程序的 105 个文件、浏览器归档的 492 个文件与 4 个中间封装逐一计算摘要。该次深层解包作为本机附加取证，通用命令核验到外层离线安装器及对应版本。[微软 WinGet 版本记录](https://github.com/microsoft/winget-pkgs/blob/master/manifests/m/Microsoft/EdgeWebView2Runtime/156.0.4314.42/Microsoft.EdgeWebView2Runtime.installer.yaml) · [7-Zip BCJ2 来源](https://github.com/ip7z/7zip/blob/25.01/C/Bcj2.c)

两份本机清单分别含 1360 和 1961 个组件，均通过 CycloneDX 1.6 官方 JSON Schema。补充清单含 1894 个文件、66 个库和 1 个运行时应用，安装器另列为根组件。完整清单、逐文件来源和原始编译日志保留本机。

## 自动化与发行边界

Python 3.12.7、3.13.17 各通过 128 项相关测试，其中 23 项覆盖新工具。Ruff 和题目 Schema 检查退出 0。初次用 Windows 换行检出作为来源输入时，固定 Git 字节校验中止。将来源覆盖核验与导出都切换到同一提交的原始 Git 字节后通过，既有断言保留。桌面来源工具和原生漏洞工具均按部分覆盖约定退出 2。

2026-11-26 对实物映射的 55 个 PyPI 包向 OSV 查询，该次返回 0 项。实物中的 OpenSSL 3.5.9 在上游版本公告命中 12 项 Low，修复版本均为 3.5.10。OSV 按提交和标签分别返回 9 项，libffi 3.4.4 两次查询均返回 0 项。组件版本命中尚需核定本产品配置与可达性。WebView2 内部许可证和漏洞覆盖、安装器元数据、其余本机及生成组件、Office 整包、产品签名与正式发行另行跟踪。[OpenSSL 3.5 公告](https://openssl-library.org/news/vulnerabilities-3.5/) · [WebView2 运行时发布记录](https://learn.microsoft.com/en-us/microsoft-edge/webview2/release-notes/runtime)
