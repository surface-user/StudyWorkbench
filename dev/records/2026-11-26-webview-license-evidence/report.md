# WebView2 实物的第三方许可页

本项承接 [普通安装器清单 PR #119](https://github.com/surface-user/StudyWorkbench/pull/119)。工具读取预先核实摘要的本机嵌套 SBOM，核对基础安装器、离线 WebView2 安装器、资源包和所选独立声明的字节。资源包到浏览器归档、内层安装器和离线安装器的关联取自上述固定清单。嵌套清单由上一步解包生成，本工具复用这些已有证据。

## 复现

```shell
python tools/webview_license_evidence.py --bom <本机嵌套清单> --bom-sha256 <预核摘要> --setup <普通安装器> --runtime <离线安装器> --pack <解出的resources.pak> --resource-id 51531 --notice <清单内的声明文件名> <本机声明文件> --output <新的本机索引>
```

可重复传入 `--notice` 核对选定声明，输出同时列出缺席项。资源编号针对这次核实的运行时版本。工具核对资源表边界和解压大小，以构建环境已有的 PowerShell 7（.NET 7 或更高版本）读取 Brotli 流，以项目锁定的 lxml 解析许可页。索引按原顺序保留同名条目、空白正文和每段正文的独立摘要。索引和原始材料仅保留在本机。

## 实物结果

WebView2 156.0.4314.42 的 Credits 页共 6634860 字节，从中读取 629 条第三方声明，涉及 615 个不同的显示名称。626 条含正文，3 条正文为空。另核对更新程序 NOTICE、Mu 与 Sigma 两份声明及 Widevine 的声明，四份字节均匹配固定清单。其中包括 GPLv3 原文、商业许可提示和权利人使用限制。上述证据说明随包提供的材料，各组件适用版本、源代码提供方式、商业授权与实际分发权仍须分别核定。

## 验证

```shell
python -m pytest -q backend/tests/test_webview_license_evidence.py backend/tests/test_base_installer_sbom.py
python -m ruff check backend tools
python tools/export_question_schema.py --check
```

Python 3.12.7 和 3.13.17 各通过 46 项测试，包括 23 项新增的合成样本。覆盖同名声明、空白正文、篡改、破损资源流、解压上限、封装关系和错误的成品摘要。Ruff 与题目协议检查退出 0。实际命令提取及四份声明核验退出 0，全程只读取安装文件。原始发现阶段曾按另一种资源表字段宽度读取，偏移量与成品不符。核对本次实物的表首、末端和长度后确定 32 位字段布局，测试已覆盖边界错误。
