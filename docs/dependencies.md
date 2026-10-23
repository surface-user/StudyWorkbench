# 依赖审查与风险登记（2026-10-23）

版本以 pubspec.lock / backend/requirements.lock.txt 为准。下表是 M0 技术选型审查，不是完整发行 SBOM 或法律意见。维护时间会变化，发行前重查。许可证来源链接是上游一手资料；锁定包 LICENSE 是实际分发审查依据。

| 依赖 | 许可证/来源 | 维护与 Windows 兼容 / 决策 |
|---|---|---|
| Flutter 3.47.1 / Dart 3.13.1 | [BSD-3-Clause](https://github.com/flutter/flutter/blob/master/LICENSE) / BSD | 本机 stable；官方 Windows 工具链，VS2022 + SDK 26100 检查通过；不是最低配置认证 |
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

