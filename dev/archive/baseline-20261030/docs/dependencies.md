# 依赖审查与风险登记（2026-10-23）

## 2026-10-26 R3可选离线分页转换器

选用LibreOffice26.8.1 Windows x64官方MSI作为独立进程运行时候选；[官方稳定目录](https://download.documentfoundation.org/libreoffice/stable/)及[固定包校验](https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64.msi.sha256)已读取。官方SHA256为c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312，下载完整包374870016字节，Windows签名Valid、发布者The Document Foundation；首次传输意外EOF，保留部分文件并续传后才通过完整hash，未执行未校验字节。准备方式为项目内MSI管理镜像解包，不作系统安装/关联；程序/许可/二进制逐文件清单用tools/lock_office_runtime.py生成，不含MSI副本。

维护证据为官方2026-10稳定目录与[26.8命令行说明](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)。许可按[官方说明](https://www.libreoffice.org/licenses/)以MPL2.0为主，包含不同许可的组合组件；保留此版本license.txt、LICENSE.html、NOTICE等完整许可文件，不将整个包简单标成单一许可。是可选独立进程，不更换Flutter/Python技术栈；发行还须按实际清单审查组合组件和来源义务，不能把本轮记录当法律认证。

执行采用每任务独立profile，宏/Windows OLE Automation/Python脚本关闭，Word加载链接设Never。输入层拒绝OLE对象、宏/外部关系/动态字段，嵌入图表XLSX仅支持无公式的静态值；无内部chart/OMML时同时禁用ActiveContent，有受限内部图表/公式时只启用其渲染。实测总禁用会让图表变占位且公式消失，已用真实页图/公式文字断言修复，并将选项升v3。配置依据为同版本官方[Common.xcs](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/officecfg/registry/schema/org/openoffice/Office/Common.xcs)和[Writer.xcs](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/officecfg/registry/schema/org/openoffice/Office/Writer.xcs)。这些控制和进程资源限制不等于完整OS文件/网络沙箱。

实际离线清单19417文件/1577045386字节（约1.47GiB，不含MSI和清单）；MSI374870016字节。Windows独立进程、无开发PATH冻结、随包组件默认查找/缺组件、中文/OMML公式/表格/图表/多页、坏输入/取消/重试/缓存/源hash已取得专项证据。真实引擎短超时/取消及Job所属进程结束、Job所有者异常退出时结束子进程另有实证，不以模拟超时替代。新转换前完整读取清单校验会增加延迟，缓存命中无需重转。干净机、任意第三方文件保真、全传递许可/签名及安装升级卸载仍未验证；详见[本批记录](r3-office-validation-2026-10-26.md)。

2026-10-25资源中心审查：未新增/升级产品依赖。开发与发行venv均无python-pptx；常用安装位置/PATH未发现LibreOffice，尚未选定其版本/分发。已装Office 16.0.20430.20182的自编DOCX/PPTX桌面导出PDF探针通过，不能替代无Office/冻结包/干净机。Word/PPT候选、官方来源和许可/体积门槛见[审查报告](resource-first-architecture-review.md)，实施留R3。

2026-10-25默认目录修复未新增包：原生Known Folder/TokenIntegrityLevel复用Windows SDK，runner链接Windows自带advapi32.lib（此前已有shell32/ole32/uuid）；没有复制或随包带入新的第三方DLL。实际低完整性源/冻结后端默认启动另记，普通Medium进程分支尚未人工验证。

2026-10-25 M2/M4本批未新增运行依赖：裁切复用既有Pillow，媒体流式保存/哈希复用Python，播放复用WebView2/HTML5。开发测试用既有imageio_ffmpeg工具生成自编VP9无音轨WebM，FFmpeg未锁为产品依赖、未随开发包分发。只验证该样本可播放；MP4/WebM/M4A后缀和容器检查不保证全部编码兼容，yt-dlp/FFmpeg下载/转码尚未接入。新增library_player.html已加入PyInstaller数据文件并冻结回归。

## 2026-10-24 M2/M3续开发

已在隔离环境用自编真实DOCX/PDF比较MarkItDown 0.1.9和Docling slim 2.142.1的离线后端，结果与输出见`evidence/m2-followup-20261024/parser-comparison.json`。PDF比较只使用Docling底层文字后端，不代表测试过模型布局/OCR；PDF样本无中文，`chinese_retained=false`不是中文识别失败证据。

运行依赖已固定在`backend/requirements.lock.txt`：

| 依赖 | 许可/维护一手来源 | Windows证据与未验证项 |
|---|---|---|
| docling-slim 2.142.1 / docling-core 2.104.0 | MIT；[官方仓库](https://github.com/docling-project/docling)、已安装wheel版本和LICENSE | 直接使用Word后端，不启用模型、OCR、LibreOffice或插件；Python3.12/3.13源进程和3.13冻结子进程实测；复杂版式未完整验证 |
| python-docx 1.2.0 / pylatexenc 2.10 | MIT / MIT；[python-docx](https://github.com/python-openxml/python-docx)、[pylatexenc](https://github.com/phfaist/pylatexenc) | Word结构及OMML转换；pylatexenc版本较旧，wheel构建成功；复杂公式仍需更广样本 |
| pypdfium2 5.14.0 | BSD-3-Clause / Apache-2.0及原生依赖许可；[官方项目](https://github.com/pypdfium2-team/pypdfium2)、实际wheel内18份许可文件 | Windows x64 PDFium DLL，源/冻结逐页文字和图像回归；不等于任意PDF安全认证，生产限制8MiB/20页/25秒 |
| Pillow 13.0.0 | MIT-CMU；[官方项目](https://github.com/python-pillow/Pillow)及wheel LICENSE | 图片读取/PNG生成；尺寸/总量预算和子进程隔离，完整恶意样本矩阵待验 |
| doclang 0.8.0、lxml 6.1.3、pandas 3.1.0、numpy 2.5.4等传递依赖 | Apache-2.0、BSD-3-Clause及组合许可，实际元数据/许可位置见`parser-dependencies.json` | 增加离线发行体积，最终SBOM/漏洞/二进制与安装包审查仍待完成 |

MarkItDown仅在忽略的`.local/parser-benchmark`作为候选比较，未接入产品。yt-dlp 2026.10.21只做M4预备查询/开发环境安装，未写入产品锁文件、未分发FFmpeg，不表示M4实现。首次ensurepip失败及后续安装日志保留，没有删除临时目录警告指向的文件。

发行许可收集器现在遍历LICENSES/BUILD_LICENSES目录，避免遗漏PDFium的abseil/icu/freetype等许可文本；wheel快照不能替代最终二进制发行审核。

2026-10-24 M2 首批未增加第三方依赖：JSON、HTML文字提取、SHA256和图片头部检查使用CPython标准库；文件选择复用既有Win32 COM通道。后端验证使用Python 3.12.7/独立3.13.17。Docling/MarkItDown/Word/PDF候选尚未选型，不宣称完成真实样本对比或其发行许可审查。

2026-10-24 M1 构建补充（下文 M0 的“未安装/仍为 Anaconda”为历史）：

| 项目 | 实际配置与来源 | 验证及边界 |
|---|---|---|
| CPython 3.13.17 x64 | PSF NuGet python 3.13.17，PSF license；[官方发行](https://www.python.org/downloads/release/python-31317/)2026-10-21；SHA256固定于 prepare-tools.ps1，PSF签名 Valid | 独立 .local/release-venv；58测试、冻结受限 PATH 作答/重启通过；干净机待验 |
| Inno Setup 7.1.0 x64 | [官方发行](https://jrsoftware.org/isdl.php)2026-08-12；实际 license.txt 允许任意用途并要求保留通知；固定 SHA256，Pyrsys B.V. Valid | 项目内官方 portable模式；setup编译通过；产品安装/卸载未通过 |
| WebView2 Standalone x64 | 微软官方 linkid=2124701，固定 SHA256，Microsoft Corporation Valid；FileVersion 1.3.299.15是安装更新器版本，非内核版本 | setup包含离线安装器，按[官方 registry pv 规则](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)检测缺失；无 Runtime干净机待验。可变 URL更新必须复核哈希/签名/许可证 |
| VC++ CRT 14.44.35211.0 | VS2022 REDIST/MSVC/14.44.35112/x64/Microsoft.VC143.CRT；实际DLL版本/签名已核对；[官方本地分发说明](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170) | Release本地 DLL，PE检查通过；更新需重构建，干净机待验 |
| 既有 native NuGet | WebView2 SDK LICENSE/NOTICE、WIL LICENSE、nlohmann.json 头文件3.11.2及[同版本 MIT](https://raw.githubusercontent.com/nlohmann/json/v3.11.2/LICENSE.MIT) | staging/licenses/native，Dart/Flutter/Python也收集；334文件哈希清单不是完整漏洞认证或法律审核 |

本次未新增 Pub 或 Python 业务依赖；目录选择使用 Windows 自带 COM IFileOpenDialog。未分发开发用 FFmpeg 或 Anaconda。

版本以 pubspec.lock / backend/requirements.lock.txt 为准。下表是 M0 技术选型审查，不是完整发行 SBOM 或法律意见。维护时间会变化，发行前重查。许可证来源链接是上游一手资料；锁定包 LICENSE 是实际分发审查依据。

| 依赖 | 许可证/来源 | 维护与 Windows 兼容 / 决策 |
|---|---|---|
| Flutter 3.47.1 / Dart 3.13.1 | [BSD-3-Clause](https://github.com/flutter/flutter/blob/master/LICENSE) / BSD | 本机 stable；官方 Windows 工具链，VS2022 + SDK 26100 检查通过；不是最低配置认证 |
| flutter_localizations（Flutter SDK，锁文件 0.0.0）/ intl 0.20.3 | Flutter BSD-3-Clause / Dart BSD-3-Clause；已核对本机 SDK pubspec 与 intl LICENSE | 2026-10-24 为中文编辑菜单接入 SDK 自带本地化；使用现有 SDK 的约束，`flutter pub get --offline` 解析成功，锁文件已更新；intl 来自 SDK 约束，维护来源为 dart-lang/i18n。Windows Debug、中文菜单实测及组件测试通过；完整语言/IME/无障碍矩阵未验，发行 NOTICE 仍需包含该许可 |
| lightweight_liquid_glass 0.1.0 | [MIT，固定 SHA](https://github.com/surface-user/Flutter_liquid_glass/blob/a0bc51acf22db1b867294f810157cfeba7e951fb/LICENSE) | 新自有库、无运行时第三方依赖；23 项原有测试通过；性能须实机 |
| flutter_inappwebview 6.1.5 / windows 0.6.0 | [Apache-2.0](https://pub.dev/packages/flutter_inappwebview/license) | pub.dev 稳定版发布约两年前，另有 beta；Windows 插件已解析到 0.6.0，NuGet WebView2 1.0.2792.45/WIL/nlohmann；维护节奏与 Flutter 新 SDK 存在风险；M0 试验采用 |
| webview_windows 0.4.0 | [BSD-3-Clause](https://pub.dev/packages/webview_windows/license) | 同样较久未发 stable；Windows.Graphics.Capture 合成、Win10 1809+ / Windows 11 SDK；保留候选，未采用 |
| flutter_math_fork 0.7.4 | [Apache-2.0](https://pub.dev/packages/flutter_math_fork/license) | 纯 Flutter，README 的 Windows 平台标签不等于验证；本项目组件测试实际解析积分；长公式/字体矩阵待测 |
| url_launcher 6.3.2 | [BSD-3-Clause](https://pub.dev/packages/url_launcher/license) | Flutter 官方插件体系；Windows 实现 3.1.6；系统浏览器回退需实际交互 |
| FastAPI 0.161.1 / Uvicorn 0.54.0 | [MIT](https://github.com/fastapi/fastapi/blob/master/LICENSE) / [BSD-3-Clause](https://github.com/encode/uvicorn/blob/main/LICENSE.md) | pip Windows 安装与真实进程请求通过；使用标准 asyncio，不依赖 Windows 不支持的 uvloop |
| SQLAlchemy 2.1.6 / Alembic 1.20.1 | [MIT](https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE) / [MIT](https://github.com/sqlalchemy/alembic/blob/main/LICENSE) | Windows wheel 已安装；SQLite 迁移、重启作答持久化通过；生产备份/WAL迁移待测 |
| SQLite | [public domain](https://sqlite.org/copyright.html) | Python 标准库自带，实际版本写测试报告；本地单机，不放网络共享盘，不允许多主写入 |
| yt-dlp（候选，未集成） | [Unlicense 主体及打包例外](https://github.com/yt-dlp/yt-dlp#license) | 活跃项目，Windows 可用；部分发行二进制包含 GPLv3+ 依赖，不能只看源码 Unlicense；M4 锁定具体分发方式，网站更新/JS runtime/版权授权另验 |
| FFmpeg（候选，未随产品分发） | [LGPL 2.1+，按配置可转 GPL/nonfree](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md) | 原生 Windows 有第三方构建；M4 选定供应者、版本、哈希、buildconf、许可证/源码义务再发行；M0 开发样本工具放忽略目录，不进安装包 |
| Seal（仅参考） | [GPLv3](https://github.com/JunkFood02/Seal) | Android 项目，不能作为 Windows 运行库；仅参考队列/格式/状态交互，未复制代码或资源 |
| Docling（候选） | [MIT 代码](https://github.com/docling-project/docling/blob/main/LICENSE) | 文档列 PDF/DOCX/HTML 等，OCR/模型各有依赖与许可；模型下载、Windows wheel、离线体积、公式识别准确率待样本实测，不纳入 M0 |
| MarkItDown（候选） | [MIT](https://github.com/microsoft/markitdown/blob/main/LICENSE) | 文档列 PDF/Office/HTML；DOCX 与旧 .doc 不能混为一谈；可选依赖/系统工具和公式/图片提取保真度待实测；不保证题目自动拆分 |
| PyInstaller 6.22.3 | [GPL 带 bootloader 分发例外](https://pyinstaller.org/en/stable/license.html) | 本机打包与冻结 exe 启动通过；当前 venv 基于 Anaconda，生成物仍含该解释器 DLL，正式发行前改用 python.org CPython 构建并复查所有许可证 |
| Inno Setup | [自有宽松许可](https://jrsoftware.org/files/is/license.txt) | 许可文本允许商业使用并有通知保留条件；官网请求商业用户购买；未安装，setup.iss 尚未编译，不宣称 setup.exe 已产出 |
| pytest / Ruff / Flutter Test / integration_test | MIT / MIT / Flutter BSD | 开发工具，不作为产品业务依赖；CI 与本地实际运行分开报告 |

安全方面：稳定版本锁定不代表无漏洞。当前未执行专门漏洞数据库审计；发行前生成传递依赖 SBOM、许可证 NOTICE、Python/Flutter/native runtime 漏洞清单和二进制哈希。

远程实证补充：windows-latest 的 VS18 / MSVC14.51 编译 flutter_inappwebview_windows 0.6.0 时触发 STL1011（experimental/coroutine 已弃用）。CI desktop 固定 windows-2022/VS2022 与本地基线一致；VS18 不在当前已验证工具链范围，升级前必须替换或升级插件协程实现。详见 evidence/ci-first-run-failure.md。

关键集成风险：WebView 原生合成/焦点/DPI；第三方网站登录；媒体容器与编码矩阵；后台进程退出与多实例；SQLite WAL 一致性备份；Python DLL 打包体积；NuGet 供应链与离线构建；安装器签名与 WebView Runtime 分发。对应验证和门禁在 testing.md、task.md。
# R3新增Markdown查看依赖（2026-10-26）

选用flutter_markdown_plus 1.0.12（精确固定），BSD-3-Clause；[包与维护说明](https://pub.dev/packages/flutter_markdown_plus/versions/1.0.12)、[变更记录](https://pub.dev/packages/flutter_markdown_plus/changelog)说明其接续已停止维护的原flutter_markdown，平台列表含Windows。另直接固定其解析器markdown 7.3.1（BSD-3-Clause，[版本页](https://pub.dev/packages/markdown/versions/7.3.1)），用于已有flutter_math_fork公式扩展。现有依赖已包含meta/path，最终传递版本以pubspec.lock为准。新增纯Dart/Flutter渲染，无原生转换器或网络运行要求。

集成必须覆盖默认图片加载器：图片只能经受保护的同空间相对资源接口读取，不允许网络/file/assets/data URI默认加载；链接仅显示不执行，HTML不执行。维护/Windows列表为上游声明，产品静态/组件/Windows构建和真实阅读另行验证；完整CommonMark兼容、超大文档性能、发行传递许可证/SBOM与干净机仍未验证。不能凭依赖支持列表宣称应用PPT/Word分页完成。

## R4依赖增量

无新增产品依赖。Markdown/公式/PNG、快照存储、确认服务、Schema沿用已有Dart/Python/SQLite依赖及公开API；样例生成复用现有Pillow，自编内容不含下载资料。未更新主要技术栈或固定玻璃库提交。R4冻结目录为隔离测试产物，不包含可选Office运行时；完整发行传递依赖/二进制许可、SBOM、漏洞、签名、安装/干净机验收仍待发行专项。见[R4记录](r4-validation-2026-10-26.md)。
