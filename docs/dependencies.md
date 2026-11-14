# 当前依赖与风险登记

版本以apps/desktop/pubspec.lock、backend/requirements.lock.txt、打包脚本固定清单为准。下列维护/Windows证据按各条注明的来源与验证范围解读，不把历史稳定版描述当成今日最新版本；本批指定依赖的联网核对与升级记录见相应条目及任务报告。新增依赖必须记录版本、许可证、维护证据、Windows支持和未验证项。

## 已采用的运行与构建依赖

| 依赖/版本 | 许可及来源 | Windows证据与边界 |
|---|---|---|
| docling-slim 2.142.1 / docling-core 2.104.0 | MIT；[官方仓库](https://github.com/docling-project/docling)、已安装wheel版本和LICENSE | 直接使用Word后端，不启用模型、OCR、LibreOffice或插件；Python3.12/3.13源进程和3.13冻结子进程实测；复杂版式未完整验证 |
| python-docx 1.2.0 / pylatexenc 2.10 | MIT / MIT；[python-docx](https://github.com/python-openxml/python-docx)、[pylatexenc](https://github.com/phfaist/pylatexenc) | Word结构及OMML转换；pylatexenc版本较旧，wheel构建成功；复杂公式仍需更广样本 |
| pypdfium2 5.14.0 | BSD-3-Clause / Apache-2.0及原生依赖许可；[官方项目](https://github.com/pypdfium2-team/pypdfium2)、实际wheel内18份许可文件 | Windows x64 PDFium DLL，源/冻结逐页文字和图像回归；不等于任意PDF安全认证，提取限制8MiB/20页/25秒，阅读另为128MiB/2000页 |
| Pillow 13.0.0 | MIT-CMU；[官方项目](https://github.com/python-pillow/Pillow)及wheel LICENSE | 图片读取/PNG生成；尺寸/总量预算和子进程隔离，完整恶意样本矩阵待验 |
| doclang 0.8.0、lxml 6.1.3、pandas 3.1.0、numpy 2.5.4等传递依赖 | Apache-2.0、BSD-3-Clause及组合许可，实际元数据/许可位置见`parser-dependencies.json` | 增加离线发行体积，最终SBOM/漏洞/二进制与安装包审查仍待完成 |
| CPython 3.13.17 x64 | PSF NuGet python 3.13.17，PSF license；[官方发行](https://www.python.org/downloads/release/python-31317/)2026-10-21；SHA256固定于 prepare-tools.ps1，PSF签名 Valid | 独立 .local/release-venv；58测试、冻结受限 PATH 作答/重启通过；干净机待验 |
| Inno Setup 7.1.0 x64 | [官方发行](https://jrsoftware.org/isdl.php)2026-08-12；实际 license.txt 允许任意用途并要求保留通知；固定 SHA256，Pyrsys B.V. Valid | 项目内官方 portable模式；setup编译通过；产品安装/卸载未通过 |
| WebView2 Standalone x64 | 微软官方 linkid=2124701，固定 SHA256，Microsoft Corporation Valid；FileVersion 1.3.299.15是安装更新器版本，非内核版本 | setup包含离线安装器，按[官方 registry pv 规则](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)检测缺失；无 Runtime干净机待验。可变 URL更新必须复核哈希/签名/许可证 |
| VC++ CRT 14.44.35211.0 | VS2022 REDIST/MSVC/14.44.35112/x64/Microsoft.VC143.CRT；实际DLL版本/签名已核对；[官方本地分发说明](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170) | Release本地 DLL，PE检查通过；更新需重构建，干净机待验 |
| 既有 native NuGet | WebView2 SDK LICENSE/NOTICE、WIL LICENSE、nlohmann.json 头文件3.11.2及[同版本 MIT](https://raw.githubusercontent.com/nlohmann/json/v3.11.2/LICENSE.MIT) | staging/licenses/native，Dart/Flutter/Python也收集；334文件哈希清单不是完整漏洞认证或法律审核 |
| Flutter 3.47.1 / Dart 3.13.1 | [BSD-3-Clause](https://github.com/flutter/flutter/blob/master/LICENSE) / BSD | 本机 stable；官方 Windows 工具链，VS2022 + SDK 26100 检查通过；不是最低配置认证 |
| flutter_localizations（Flutter SDK，锁文件 0.0.0）/ intl 0.20.3 | Flutter BSD-3-Clause / Dart BSD-3-Clause；已核对本机 SDK pubspec 与 intl LICENSE | 2026-10-24 为中文编辑菜单接入 SDK 自带本地化；使用现有 SDK 的约束，`flutter pub get --offline` 解析成功，锁文件已更新；intl 来自 SDK 约束，维护来源为 dart-lang/i18n。Windows Debug、中文菜单实测及组件测试通过；完整语言/IME/无障碍矩阵未验，发行 NOTICE 仍需包含该许可 |
| lightweight_liquid_glass 0.1.0 | [MIT，固定 SHA](https://github.com/surface-user/Flutter_liquid_glass/blob/a0bc51acf22db1b867294f810157cfeba7e951fb/LICENSE) | 新自有库、无运行时第三方依赖；历史23项原有测试通过；性能须实机 |
| flutter_inappwebview 6.1.5 / windows 0.6.0 | [Apache-2.0](https://pub.dev/packages/flutter_inappwebview/license) | pub.dev 稳定版发布约两年前，另有 beta；Windows 插件已解析到 0.6.0，NuGet WebView2 1.0.2792.45/WIL/nlohmann；维护节奏与 Flutter 新 SDK 存在风险；M0 试验采用 |
| flutter_math_fork 0.7.4 | [Apache-2.0](https://pub.dev/packages/flutter_math_fork/license) | 纯 Flutter，README 的 Windows 平台标签不等于验证；本项目组件测试实际解析积分；长公式/字体矩阵待测 |
| url_launcher 6.3.2 | [BSD-3-Clause](https://pub.dev/packages/url_launcher/license) | Flutter 官方插件体系；Windows 实现 3.1.6；系统浏览器回退需实际交互 |
| FastAPI 0.161.1 / Uvicorn 0.54.0 | [MIT](https://github.com/fastapi/fastapi/blob/master/LICENSE) / [BSD-3-Clause](https://github.com/encode/uvicorn/blob/main/LICENSE.md) | pip Windows 安装与真实进程请求通过；使用标准 asyncio，不依赖 Windows 不支持的 uvloop |
| Starlette 1.3.1 | [BSD-3-Clause，同版本原文](https://github.com/Kludex/starlette/blob/1.3.1/LICENSE.md)；[官方发行](https://github.com/Kludex/starlette/releases/tag/1.3.1)2026-06-12 | PyPI要求Python>=3.10、OS Independent，现有FastAPI0.161.1要求Starlette>=0.46.0；固定覆盖已发现五CVE的最低共同修复版本，Windows/冻结验证及查询边界见原发行报告 |
| SQLAlchemy 2.1.6 / Alembic 1.20.1 | [MIT](https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE) / [MIT](https://github.com/sqlalchemy/alembic/blob/main/LICENSE) | Windows wheel 已安装；SQLite 迁移、重启作答持久化通过；SQLite backup/WAL迁移已有隔离回归，真实升级/干净机待验 |
| SQLite | [public domain](https://sqlite.org/copyright.html) | Python 标准库自带，实际版本写测试报告；本地单机，不放网络共享盘，不允许多主写入 |
| pytest 9.0.3 / Ruff / Flutter Test / integration_test | [pytest MIT](https://github.com/pytest-dev/pytest/blob/9.0.3/LICENSE) / MIT / Flutter BSD | 开发工具，不作为产品业务依赖；pytest固定修复CVE-2025-71176的最小版本，Windows独立环境与CI证据分别记录 |
| PyInstaller 6.22.3 | [同版本GPL及bootloader分发例外](https://pyinstaller.org/en/v6.22.3/license.html)；[官方PyPI元数据](https://pypi.org/pypi/pyinstaller/6.22.3/json) | 已使用独立CPython冻结；固定Windows x64 wheel及有限PE来源说明见下，安装/干净机/最终依赖义务仍待验 |

玻璃库仅公开入口API、ref固定a0bc51acf22db1b867294f810157cfeba7e951fb，保留MIT通知，不改上游/缓存。Windows SDK原生Known Folder、OLE、Shell/Advapi32用于选择/拖放和默认目录，无新增第三方包。

PyInstaller既有构建依赖的官方`pyinstaller-6.22.3-py3-none-win_amd64.whl`固定1454907字节、SHA256 500bd58c7bf7e584a8435adccbd763a0b918d5c12b08d74ff50fd79b2915458b，2026-09-12发布；本批已核官方PyPI元数据及实际完整下载。Windows支持与GPL-2.0-or-later/bootloader例外按同版本文档和归档内原文解读，不新增运行依赖或重新安装环境。来源工具另核wheel内METADATA/RECORD、实际安装RECORD及run.exe/两份构建源码；精确PE代码节/部分数据节相等，不表示整个生成exe原样或可重现构建，不把资源、时间戳或overlay差异抹掉。官方档hash不代替签名或整个发行许可审查。

冻结后端COLLECT记录中的api-ms-win-*及ucrtbase.dll须按真实源路径逐文件核，不能默认来自System32。当前记录指向本机构建环境附带的第三方runtime目录时，只能保留caller本地字节链，component identity/version、官方档案、许可及再分发资格均未知；不得据同目录、PE版本资源或有效签名为其补造包身份或发行通过。详细边界见[来源工具](packaging-windows.md#固定bootloader与crt本地来源链)。

Starlette官方wheel为73632字节，SHA256 c7372aae11c3c3f26a42df7bd626cec2f47d03483d261d369516a615a53714c6，包内BSD-3-Clause原文已保留；[同版本PyPI元数据](https://pypi.org/pypi/starlette/1.3.1/json)与实际下载字节核对。仅升级该传递依赖，FastAPI、AnyIO及httpx保持原锁；实际TestClient兼容现有httpx0.28.1但上游已给弃用提醒，不为消除警告新增httpx2。业务未使用StaticFiles、HTTPEndpoint或表单解析入口；未使用不等于全产品可达性已证实，已知公告、修复复扫与Host/path/Origin入口回归分别记录。

### 可选离线Office组件

冻结后端通过独立内部helper清除继承的PyInstaller DLL目录后启动组件，避免其加载打包Python的CRT；不在并发主后端切换DLL搜索状态。外部转换的输入/输出/profile与临时目录使用经samefile核对的Windows短名，原始路径和数据保持不变。无短名卷及极端目录尚未验证；此兼容措施不放宽运行时逐文件清单、输入门禁或Job限制。



选用LibreOffice26.8.1 Windows x64官方MSI作为已接入的可选独立进程运行时；[官方稳定目录](https://download.documentfoundation.org/libreoffice/stable/)及[固定包校验](https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64.msi.sha256)已读取。官方SHA256为c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312，下载完整包374870016字节，Windows签名Valid、发布者The Document Foundation；准备方式为项目内MSI管理镜像解包，不作系统安装/关联；程序/许可/二进制逐文件清单用tools/lock_office_runtime.py生成，不含MSI副本。

维护证据为官方2026-10稳定目录与[26.8命令行说明](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)。许可按[官方说明](https://www.libreoffice.org/licenses/)以MPL2.0为主，包含不同许可的组合组件；保留此版本license.txt、LICENSE.html、NOTICE等完整许可文件，不将整个包简单标成单一许可。是可选独立进程，不更换Flutter/Python技术栈；发行还须按实际清单审查组合组件和来源义务，不能把本轮记录当法律认证。

执行采用每任务独立profile，宏/Windows OLE Automation/Python脚本关闭，Word加载链接设Never。输入层拒绝OLE对象、宏/外部关系/动态字段，嵌入图表XLSX仅支持无公式的静态值；无内部chart/OMML时同时禁用ActiveContent，有受限内部图表/公式时只启用其渲染。实测总禁用会让图表变占位且公式消失，已用真实页图/公式文字断言修复，并将选项升v3。配置依据为同版本官方[Common.xcs](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/officecfg/registry/schema/org/openoffice/Office/Common.xcs)和[Writer.xcs](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/officecfg/registry/schema/org/openoffice/Office/Writer.xcs)。这些控制和进程资源限制不等于完整OS文件/网络沙箱。

实际离线清单19417文件/1577045386字节（约1.47GiB，不含MSI和清单）；MSI374870016字节。Windows独立进程、无开发PATH冻结、随包组件默认查找/缺组件、中文/OMML公式/表格/图表/多页、坏输入/取消/重试/缓存/源hash已取得专项证据。真实引擎短超时/取消及Job所属进程结束、Job所有者异常退出时结束子进程另有实证，不以模拟超时替代。新转换前完整读取清单校验会增加延迟，缓存命中无需重转。干净机、任意第三方文件保真、全传递许可/签名及安装升级卸载仍未验证；详见[Office历史实证](../dev/archive/reports/r3-office-validation-2026-10-26.md)。


### 可选Java组件准备（Office整包前置）

用户2026-11-12委托技术判断后，固定选择[Eclipse Temurin 21.0.13+9 Windows x64 HotSpot JRE](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.13%2B9)，官方发布时间2026-10-22；官方zip 49106397字节，SHA256 2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628。只在项目新目录解包，不注册系统Java、不改PATH/文件关联；新增的是可选外部组件，未改主要技术栈。

完整保留NOTICE和179份legal文件，包内声明GPL-2.0及Classpath Exception，并包含Assembly Exception和各第三方原始许可，不能把全部组件当作单一许可。对应官方[源码资产](https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk-sources_21.0.13_9.tar.gz)已定位，发布元数据SHA256 b5232c9980d8a0f0459676c084c41c6e2c771ed9e785890b03c6a438406ad1ca；本切片未下载核验或提供发行源码包，完整分发义务仍由REL-02承接，不以保留通知代替许可闭合。zip来源/hash已核，未验证其GPG签名，不冒充产品签名。

实际准备315文件/151829828字节，逐文件与官方zip字节核对一致；入口java.exe、jawt.dll及server/jvm.dll为AMD64/PE32+，release字段为Windows/x86_64/JRE/Temurin 21.0.13+9，java -version通过。该证据不证明Office找到JVM、Java/CRT加载闭合或干净机运行；Office运行布局与冻结复验在OFF-02后续实施。无自动更新；升级须重新核官方来源/固定hash/许可、重建清单并重跑架构/加载/冻结和漏洞检查，不能就地替换文件。

### Markdown渲染



选用flutter_markdown_plus 1.0.12（精确固定），BSD-3-Clause；[包与维护说明](https://pub.dev/packages/flutter_markdown_plus/versions/1.0.12)、[变更记录](https://pub.dev/packages/flutter_markdown_plus/changelog)说明其接续已停止维护的原flutter_markdown，平台列表含Windows。另直接固定其解析器markdown 7.3.1（BSD-3-Clause，[版本页](https://pub.dev/packages/markdown/versions/7.3.1)），用于已有flutter_math_fork公式扩展。现有依赖已包含meta/path，最终传递版本以pubspec.lock为准。新增纯Dart/Flutter渲染，无原生转换器或网络运行要求。

集成必须覆盖默认图片加载器：图片只能经受保护的同空间相对资源接口读取，不允许网络/file/assets/data URI默认加载；链接仅显示不执行，HTML不执行。维护/Windows列表为上游声明，产品静态/组件/Windows构建和真实阅读另行验证；完整CommonMark兼容、超大文档性能、发行传递许可证/SBOM与干净机仍未验证。不能凭依赖支持列表宣称应用PPT/Word分页完成。


## 开发工具和未采用候选

源码锁文件SBOM构建工具固定为[Anchore Syft 1.57.1 Windows amd64](https://github.com/anchore/syft/releases/tag/v1.57.1)，Apache-2.0，保留官方压缩包内LICENSE。官方发布于2026-11-09，Windows构建及本项目真实离线扫描已核；只用于开发/构建，不随应用分发、不增加Python运行依赖。官方zip SHA256为3a01fe865076bb548352195b77e88fa4649277861ea458efe165c3a810b6dcc7，30255314字节；解包syft.exe SHA256为42deb23bff7852997bf0316a540d3dcb364953273152749205e47881dd270c53，由生成命令每次核对。官方HTTPS发布资产digest/checksums核验不等于签名认证；Authenticode为NotSigned，Sigstore未验证。

[支持生态](https://oss.anchore.com/docs/capabilities/all-packages/)声明可解析Python requirements与Dart pubspec.lock；本项目只启用对应两个cataloger，禁用更新检查/联网补全，不扫描开发环境。SDK版本占位不能推断成实际Flutter/Dart SDK；投影输入显式排除SDK并在对照报告保留未知项，Git依赖核对完整resolved-ref。锁文件SBOM不证明运行时成员、许可证义务、漏洞状态或最终二进制闭合，详见[生成说明](packaging-windows.md#源码锁文件sbom)。

pytest/Ruff/Flutter Test/integration_test是开发工具。样本生成可使用本机python-pptx、开发FFmpeg，但它们不是产品运行依赖；MarkItDown0.1.9与Docling的样本比较是历史选型记录，不把MarkItDown列为当前产品依赖。

pytest固定9.0.3；[官方2026-04-07发行说明](https://github.com/pytest-dev/pytest/releases/tag/9.0.3)明确修复CVE-2025-71176，[PyPI该版本元数据](https://pypi.org/pypi/pytest/9.0.3/json)要求Python>=3.10、声明Windows支持且wheel未撤回。官方pytest-9.0.3-py3-none-any.whl为375249字节，SHA256 2c5efc453d45394fdd706ade797c0a81091eccd1d6e4bccfcd476e2b8e0ab5d9；包内MIT许可保留。现有3.12/3.13的其他锁依赖已满足其要求，无额外传递升级。已知公告触发条件为UNIX默认测试临时目录，本项目Windows回归不等于复现该漏洞或证明全部平台安全；原发现与修复复查在原发行报告保留。现有Starlette/FastAPI锁不随此开发工具补丁升级。

webview_windows0.4.0仅保留候选；已采用的是flutter_inappwebview。yt-dlp2026.10.21仅做过开发预备，下载队列未实现；FFmpeg未选定产品二进制/构建配置，不能只按主体许可证发行。Seal只参考交互，不复制GPLv3代码/资源。

## 待验证与升级门禁

源码依赖漏洞查询使用项目内tools/source_vulnerabilities.py 1.0及[OSV v1官方API](https://google.github.io/osv.dev/api/)，复用既有锁文件解析，仅发送公开PyPI/pub.dev包名、生态和精确版本，后续只取返回公告ID。网络使用Python标准库，没有新运行依赖、第三方扫描器安装或源码上传；查询器及解析器文件SHA256、Python版本随报告固定。OSV当前维护[数据来源](https://google.github.io/osv.dev/data/)包括GitHub/PyPI公告，PyPI与Pub为其支持的生态；公告数据来源许可与应用依赖许可是不同事项，原始返回保留在忽略的artifacts，不随产品分发。

OSV在线查询不提供固定数据库快照或全库新鲜度证明，报告明确database_snapshot=null/database_freshness=unknown_live_api。每次查询保存UTC起止、HTTP Date、原始请求/响应SHA256和公告modified/published；这只固定本次观察，不能重建完整数据库。无返回记录仍保留包映射/收录覆盖未知，Git/SDK和最终二进制明确未覆盖；发现、撤回、映射缺失及查询后公告变化不静默抹去。用法和退出码见[构建指南](packaging-windows.md#源码锁文件漏洞查询)，具体发现与修复任务只在task/原报告维护。

锁版本不代表无漏洞；有限源范围查询不构成完整漏洞审计、法律认证或全部上游版本复核。发行前必须核实际传递依赖、二进制配置、NOTICE/SBOM/签名和干净机；保留PDFium BUILD_LICENSES等组合许可，构建环境包清单不是完整发行SBOM。

flutter_inappwebview_windows0.6.0与VS18旧协程头存在历史STL1011失败，CI固定windows-2022/VS2022；升级工具链前重验。WebView原生焦点/DPI/合成、Office复杂字体版式、媒体编码/音轨、NuGet供应链/离线构建及安装升级仍有未验项。历史来源见[依赖快照](../dev/archive/baseline-20261030/docs/dependencies.md)，仅需溯源时读取。
