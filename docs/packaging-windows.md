# Windows构建、安装与数据

## 当前已实现

构建基线Flutter/Dart、独立CPython3.13.17/PyInstaller onedir、Inno Setup portable工具、app-local CRT和WebView2离线安装器；不打包开发Anaconda。版本/来源/许可见[依赖](dependencies.md)。

staging文件清单生成与校验共用枚举：只排除根build-inventory.json，嵌套同名文件仍计入；拒绝子目录/文件符号链接、重解析点和非普通文件，不沿它们读写。生成许可副本前先检查现有stage。check_release先要求实际相对路径集合与清单完全相等，再核文件hash及原CPython/.db/CRT/PE检查；绝对路径或../清单项不能借校验读取stage外文件。build-release在生成清单后、编译安装包前执行此检查，非零即停，保留失败stage。该门禁依赖稳定的构建暂存目录，不构成原子文件系统快照或完整发行SBOM、签名/许可/漏洞认证。

固定Windows x64目标另要求根目录PE文件、backend/study_backend.exe及backend内DLL/PYD的Machine为AMD64、可选头为PE32+，在读取导入表前拒绝不符文件；失败仍关闭PE句柄，不修改候选字节。可选转换器目录与backend内独立helper EXE不套用主进程架构门禁，进入已声明运行域的文件再核AMD64/PE32+；闭包外PE保持未分类，不能据路径或不可达就认定不会运行。文件头声明不证明签名、来源身份、CPython ABI或完整加载兼容性，不能替代运行验证。

原生依赖检查覆盖.exe/.dll/.pyd及MZ格式.com/.bin的普通与延迟导入。只在声明的主应用根、后端_internal及各插件自身目录、Office program与其显式Java根、独立Java进程bin/server域解析，不以全包同名DLL或外部PATH兜底。普通私有VC运行库必须位于各进程约定的app-local根，System32不能补私有CRT；NumPy/Pandas的.libs须匹配固定完整冻结初始化代码指纹，才采用其中已核的目录注册行为。注册目录顺序不明或同一后端进程解析到同名不同字节时拒绝。版本/初始化代码变化必须重新取证，规则不是自动支持未来版本的白名单。

Office域还读取固定组件自带的UNO注册入口：先核program/uno.ini、fundamental.ini和7份services注册文件的完整SHA256及注册目录文件集合，再仅解析这些已核字节；URE_INTERNAL_LIB_DIR与LO_LIB_DIR只映射到program，拒绝其他变量、绝对/嵌套/穿越路径和非DLL/PYD原生入口。注册的SharedLibrary及其传递依赖共用原Office搜索根/架构/CRT守卫，报告保留每个入口的注册来源与配置hash。Java/Python脚本注册不计为原生库，用户/扩展动态注册、CLR、其他辅助进程仍不由此证明；版本、启动配置或注册集合变化必须重新核证，不据文件恰在program就认可运行域。

check_release遇到任一闭包外未分类PE即拒绝发行并输出partial及路径/架构，不提供绕过开关；必须后续建立可审计的运行域或非运行分类。只读tools/check_native_dependencies.py --office <组合组件目录>或--backend <冻结后端目录>可输出有限域图及未知范围，其中--office先核组件完整清单/hash，不调用OfficeRuntime。诊断退出0仅说明已声明域解析完成，pe_coverage=partial仍不满足发行门禁。API set另列Windows契约，本机System32仅为OS文件存在证据；最低Windows版本、已加载模块/SxS/动态加载/导出转发、干净机与完整Office加载范围仍需独立证据。

许可复制的Python/Dart/native包目录名限定为普通ASCII包组件，候选许可路径必须相对并解析后保持在该包目录内；拒绝驱动器/根路径、冒号及Windows尾点/尾空格歧义。Python RECORD含..项仍按原规则跳过。复制前检查目标，错误使收集失败并保留已完成的合法副本，不回滚/删除stage；此前已有链接/重解析点检查继续执行。此边界面向稳定staging和本地构建输入，不构成恶意构建依赖沙箱、完整许可覆盖或SBOM/漏洞审计。

仓库根先执行packaging/windows/prepare-tools.ps1验证固定下载SHA256/签名并建立.local/release-venv，再执行packaging/windows/build-release.ps1。后端使用--clean避免增量缓存保留旧业务代码，并由tools/check_frozen_sources.py在固定CPython3.13.17下核对包内全部业务模块与源码（含嵌套代码/常量/异常表），失败即构建失败。构建从pubspec.yaml读取版本，写全新staging，收集Python/Dart/Flutter/native许可证、文件hash与PE依赖。Windows构建串行；只能交付配套前端data/app.so与冻结backend，不能只拿exe或旧runner后端。

可选LibreOffice26.8.1组件以prepare-office-runtime.ps1 -Package <固定MSI> -Destination <新目录>管理镜像解包，不注册系统安装或关联。build-release.ps1默认不带组件；显式-OfficeRuntime <已核目录>才经tools/stage_office_runtime.py复制清单/许可并校验。拒绝覆盖现有组件目录。历史清单19417文件/约1.47GiB（不含MSI/清单），体积属于当时固定版本；默认主包不增加此组件。

后端相对安装根定位组件，仅启动环境可用STUDY_OFFICE_RUNTIME指定可信绝对路径，HTTP不接受转换器路径/命令。完整核验运行时会增加耗时，90秒限制只约束引擎执行。

安装与数据目录分离。每用户安装默认LocalAppData/Programs/StudyWorkbench，安装器允许选择目录。数据由Known Folder定位：普通进程LocalAppData/StudyWorkbench/data，低完整性进程LocalAppDataLow；已有明确配置/同profile旧m0库优先。配置定位LocalLow并兼容旧LocalAppData设置，具体见[ADR0006](adr/0006-default-user-storage.md)。首次自动用默认/已保存位置，选择入口位于设置/失败恢复；不因权限失败静默切空库。

数据迁移：保存页面/释放WebView→停写和后端→本地路径/空间/非嵌套/空目标校验→SQLite backup和文件复制→hash/数量/逻辑内容/integrity/外键检查→原子配置切换→重启确认。失败保留旧数据/配置和目标现场，不伪装跨卷原子move，不执行破坏性downgrade。卸载无个人数据删除规则，默认保留学习资料。

## 固定Java组件准备

已提供独立构建命令，输入为[固定Temurin官方zip](https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip)，依赖/许可和更新限制见[依赖登记](dependencies.md)。仓库根执行，目标父目录须存在：

```powershell
.local/release-venv/Scripts/python.exe tools/prepare_java_runtime.py --package .local/release-tools/temurin-jre21.0.13-9/OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip --destination .local/java-runtime-21.0.13-9
```

命令先核固定49106397字节/SHA256，再完整检查ZIP路径/大小写冲突/Windows保留名/原名规范化/特殊文件和数量/膨胀预算。只把固定顶层目录内部内容解到新目录，保留全部文件及NOTICE/legal；拒绝已有目标和链接/重解析路径，不安装、不运行Java、不修改环境。结束重核原zip与目标文件集合/hash、release版本/架构/JRE身份及java.exe/jawt.dll/server/jvm.dll的AMD64/PE32+，再独占写java-runtime-lock.json。失败保留现场且不覆盖旧目录，成功清单字段为version/package_sha256/source_url/bytes/files；后续组件使用前必须再核实际文件集合与hash，不能只相信清单存在。

准备Java组件不改变build-release的默认产品包；需要配套Java时，另用下述命令组合，不就地修改任一原组件。

## Office与Java组合运行时

```powershell
.local/release-venv/Scripts/python.exe tools/compose_office_runtime.py --office .local/release-tools/libreoffice-26.8.1 --java .local/java-runtime-21.0.13-9 --destination .local/office-java-runtime
```

两个输入必须分别通过固定原清单/hash与完整文件核验；目标父目录须存在，目标必须全新且不位于输入内，拒绝链接/重解析目录。命令保留原Office所有文件与原清单office-runtime-lock.json，在java/保留全部JRE及java-runtime-lock.json，只另将Office原System64中的8份VC运行库逐字复制到program/，不覆盖原文件。新runtime-lock.json声明配套Java及完整组合集合；加载时要求两份原清单hash和文件集合精确相等，转换前继续逐文件核验。失败保留现场，不能因清单已写入就视为成功；必须以命令退出0及完整复核为准。

Office子进程才接收包内JAVA_HOME、UNO_JAVA_JFW_JREHOME文件URI和headless参数，PATH只包含Office程序、包内Java bin/server与系统目录；不继承JAVA_TOOL_OPTIONS或其他外来Java启动参数，不改主后端DLL目录或系统配置。用同版本LibreOffice的[Java框架直接模式](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/include/jvmfwk/framework.hxx)显式选JRE，输入限制、宏/脚本保护与进程预算保持。原不含Java组件仍支持，不自动发现开发机Java。

组合目录可交给原build-release.ps1的-OfficeRuntime入口，默认主包行为保持。实际加载、转换及限制见[发行任务报告](../dev/records/2026-11-10-release-integrity/report.md)。完整PE进程加载域/延迟导入门禁、发行SBOM、传递许可/源码义务、漏洞和签名仍须分别完成；本步骤不等于Office整包可发行或干净机验证。

## 源码锁文件SBOM

在仓库根使用已有构建Python环境运行：

```powershell
.local/release-venv/Scripts/python.exe tools/source_sbom.py --syft .local/release-tools/syft-1.57.1/syft.exe --output artifacts/source-sbom-01
```

先从[固定官方zip](https://github.com/anchore/syft/releases/download/v1.57.1/syft_1.57.1_windows_amd64.zip)取得Windows x64工具，校验[依赖登记](dependencies.md)中的zip SHA256后解压到新目录并保留LICENSE；命令每次另核exe SHA256，错误版本/内容拒绝执行。output必须是不存在的新目录且父目录已存在；失败保留日志与现场，没有通过对照时不会生成comparison.json，不覆盖已有输出。

只读取backend/requirements.lock.txt和apps/desktop/pubspec.lock，拒绝链接/重解析路径、大于1MiB的锁文件、非精确Python版本、重复/不支持的来源。隔离扫描输入保留Python精确锁与pub.dev hosted/完整Git提交的Dart包，SDK项因缺少实际SDK版本明确列为excluded_sdk_components；Syft不能把sdk约束下界当实际版本。原锁hash及投影扫描输入hash分别写comparison.json；Git源或包压缩内容未下载/核验，hosted包hash只作为原锁身份的一部分保留。

固定两个cataloger、显式配置、清除继承的SYFT配置环境变量、关闭更新与enrich/远端许可查询；生成CycloneDX 1.6 source.cdx.json，逐项核对包PURL/名称/版本/Git提交或host、来源文件及文件SHA256，额外/缺失/重复/不一致均失败。成功后复核原锁未变化，报告源范围、全部未知边界及SBOM hash。包集合与输入hash可重复核对；工具生成的时间戳/UUID会变化，不承诺文件字节完全相同。

这是包含开发/构建/跨平台依赖的源码锁文件清单，未分类为最终运行时成员；没有冻结/原生、Flutter/Dart SDK实际版本、NuGet/CRT/WebView2/Office/Java及安装器payload覆盖，也没有完整依赖边、许可证原文/义务或漏洞结论。Syft推断的CPE不等于确认漏洞匹配。本命令不替代原check_release门禁；完整REL-01仍需对照实际发行包，REL-02/03单独处理许可与漏洞。

## 源码锁文件漏洞查询

在确认两份锁文件仅包含可公开查询的依赖名后，以既有构建Python执行：

```powershell
.local/release-venv/Scripts/python.exe tools/source_vulnerabilities.py --output artifacts/source-vulns-01
$queryExit = $LASTEXITCODE
```

output必须是不存在的新目录且父目录已存在。复用源码SBOM相同锁解析/身份/链接拒绝，结束重核锁未变；只向固定https://api.osv.dev/v1/发送公开名称/版本/生态及服务返回的分页token/公告ID，不发送源码、锁文件内容、hash、Git URL/commit、个人数据或凭据。禁用代理继承与重定向；单次30秒/8MiB、最多1000包/8轮分页/1000公告预算。企业代理环境不可直连时明确失败，不改用其他查询站点。

report.json记录查询器1.0及两份工具源码hash、锁hash、Python版本、UTC查询时间、HTTP Date、逐项匹配/原始影响范围和修复事件、别名、来源、撤回/映射缺失/变更状态；编号request/response文件保存原始字节，evidence记录对应SHA256，超预算仅保留已读前缀并报错。API批次时间可精确到微秒而详情含纳秒，比较明确使用微秒精度并保留两种原值。完整数据库版本/时间/hash无法由在线API取得，必须保留snapshot/freshness未知；HTTP Date新鲜不证明数据库新鲜。超过24小时或超前5分钟的响应Date拒绝，缺Date明确未知；重新查询使用新目录，旧记录不视为持续有效。

退出1表示查询、结构、映射批次或源一致性失败；已有原始现场/失败报告保留。退出2表示返回公告（含需进一步判定的撤回/变更/映射未知），退出3表示当前查询完成但没有返回公告；两者均不是发行通过码，工具不返回安全认证的0。空结果只能称“无公告返回”，不能称“安全包”。Git和SDK排除项、开发/构建/跨平台成员、最终产品未覆盖始终保留；不依据空结果自动批准发行、不自动升级或改变既有check_release门禁。网络查询仅显式运行；CI用离线自编响应验证信任边界，不依赖在线数据库稳定性。

## 锁定源码依赖的本地许可证据

`tools/source_licenses.py`复用源码SBOM的精确锁身份，只读当前Python环境及明确指定的Dart package_config。使用与待检查锁一致的独立环境执行；不会安装依赖、联网查询、读取个人学习库或修改现有发行stage：

```powershell
python tools/source_licenses.py --package-config apps/desktop/.dart_tool/package_config.json --output artifacts/source-licenses-01
```

输出必须是不存在的新目录且父目录已存在。Python匹配唯一的精确名称/版本，读取顶层dist-info的METADATA及原始RECORD，保留License-File声明和具名许可/通知文件（含嵌套LICENSES/BUILD_LICENSES）；RECORD中声称的SHA256或长度不符即失败，未提供SHA256单列缺证。直接读取RECORD，不能用会过滤不存在文件的importlib.files()掩盖缺失或越界项。Dart先核缓存pubspec名称/版本，再收集根目录具名许可文件及许可目录内原文；保留锁定hosted archive hash或Git resolved-ref作为声明来源，不声称缓存已与官方归档/Git内容认证。

输入锁各限1MiB，其他证据文件各限4MiB；Dart每包许可发现限10000条。拒绝链接/重解析、源文件越界及已有输出；按内容SHA256保存原字节，报告记录每包版本、来源、原相对路径、长度/hash和缺证项，不输出本机绝对目录。末尾复核锁/config未变；错误保留现场且不生成成功report。执行依赖稳定的本地构建目录，不构成原子快照或恶意构建依赖沙箱。

退出0仅表示选定本地证据无已发现缺口，退出2表示报告已生成但有缺文/版本/RECORD缺证，退出1表示输入/完整性错误。report始终明确`product_licenses_complete=false`、`archive_provenance_verified=false`、`distribution_obligations_reviewed=false`；8类SDK锁占位另列未知。命名发现可能漏掉源文件内嵌或其他名称的通知，缺证不得以元数据标签代替原文。最终产品成员、完整官方来源、组合许可/源码提供义务、NOTICE及Office/Java/native/安装器仍由REL-01/02后续核验。

精确版本`latex2mathml3.81.1`另有[固定来源补充](../packaging/licenses/latex2mathml-3.81.1/provenance.json)：官方wheel/sdist都漏带项目LICENSE，经固定tag的九个package文件逐字节核对后，收集器将本地九文件与已记录SHA256比较，再复制固定MIT和LPPL原文。任一package文件、许可文本、版本或来源配置不符即失败；采集中再次核配置及package文件未变。补充记录标记`repository_supplement`，不伪装为installed RECORD文件，也不成为其他版本或其他包的兜底。

项目代码MIT与`unimathsymbols.txt`的LPPL-1.3-or-later分开映射，保留数据作者、原头部日期及vendor修改后未更新通知的事实。补齐原文仍保留上游归档缺文、LPPL原Work/修改条件待核；此组件有issue，CLI仍退出2，完整产品/归档来源/分发义务仍false。该补充不向产品payload添加数据或修改原依赖，不证明HTML/MathML导出已受支持；最终发行复制/成员范围和义务另核。

## 规划中

自动升级/完整回滚产品流程、下载/转码组件、正式签名发行按专项实施。FFmpeg须先锁定实际构建开关与LGPL/GPL/nonfree及来源义务；本地生成样本不等于可随产品分发。

## 待验证

实际setup安装/升级/卸载、无Python/无WebView2干净机、普通用户/中文空格路径、睡眠和硬件矩阵、完整传递依赖许可/SBOM/漏洞/代码签名仍待验。编译出setup、本机清单检查、专项冻结通过不代替它们。发布和合并必须取得对应授权。

本机历史测试包路径与hash仅在[任务报告](../dev/README.md)记录，不在本指南维护多个“最新”入口；本轮未生成或替换测试包。
