# Windows构建、安装与数据

## 当前已实现

构建基线Flutter/Dart、独立CPython3.13.17/PyInstaller onedir、Inno Setup portable工具、app-local CRT和WebView2离线安装器；不打包开发Anaconda。版本/来源/许可见[依赖](dependencies.md)。

staging文件清单生成与校验共用枚举：只排除根build-inventory.json，嵌套同名文件仍计入；拒绝子目录/文件符号链接、重解析点和非普通文件，不沿它们读写。生成许可副本前先检查现有stage。check_release先要求实际相对路径集合与清单完全相等，再核文件hash及原CPython/.db/CRT/PE检查；绝对路径或../清单项不能借校验读取stage外文件。build-release在生成清单后、编译安装包前执行此检查，非零即停，保留失败stage。该门禁依赖稳定的构建暂存目录，不构成原子文件系统快照或完整发行SBOM、签名/许可/漏洞认证。

固定Windows x64目标另要求根目录PE文件、backend/study_backend.exe及backend内DLL/PYD的Machine为AMD64、可选头为PE32+，在读取导入表前拒绝不符文件；失败仍关闭PE句柄，不修改候选字节。可选转换器目录与backend内独立helper EXE不套用主进程架构门禁，仍受原文件hash及PE导入检查。文件头声明不证明签名、来源身份、CPython ABI或完整加载兼容性，不能替代运行验证。

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

准备Java组件不改变build-release的默认产品包，也不自动配置Office或补CRT。OFF-02后续仍须确定Office查找JVM与CRT加载根，完成冻结转换/取消重启及无开发依赖验证。完整SBOM、传递许可/源码义务、漏洞和签名另行完成；不可据本步骤称Office整包已可发行。

## 源码锁文件SBOM

在仓库根使用已有构建Python环境运行：

```powershell
.local/release-venv/Scripts/python.exe tools/source_sbom.py --syft .local/release-tools/syft-1.57.1/syft.exe --output artifacts/source-sbom-01
```

先从[固定官方zip](https://github.com/anchore/syft/releases/download/v1.57.1/syft_1.57.1_windows_amd64.zip)取得Windows x64工具，校验[依赖登记](dependencies.md)中的zip SHA256后解压到新目录并保留LICENSE；命令每次另核exe SHA256，错误版本/内容拒绝执行。output必须是不存在的新目录且父目录已存在；失败保留日志与现场，没有通过对照时不会生成comparison.json，不覆盖已有输出。

只读取backend/requirements.lock.txt和apps/desktop/pubspec.lock，拒绝链接/重解析路径、大于1MiB的锁文件、非精确Python版本、重复/不支持的来源。隔离扫描输入保留Python精确锁与pub.dev hosted/完整Git提交的Dart包，SDK项因缺少实际SDK版本明确列为excluded_sdk_components；Syft不能把sdk约束下界当实际版本。原锁hash及投影扫描输入hash分别写comparison.json；Git源或包压缩内容未下载/核验，hosted包hash只作为原锁身份的一部分保留。

固定两个cataloger、显式配置、清除继承的SYFT配置环境变量、关闭更新与enrich/远端许可查询；生成CycloneDX 1.6 source.cdx.json，逐项核对包PURL/名称/版本/Git提交或host、来源文件及文件SHA256，额外/缺失/重复/不一致均失败。成功后复核原锁未变化，报告源范围、全部未知边界及SBOM hash。包集合与输入hash可重复核对；工具生成的时间戳/UUID会变化，不承诺文件字节完全相同。

这是包含开发/构建/跨平台依赖的源码锁文件清单，未分类为最终运行时成员；没有冻结/原生、Flutter/Dart SDK实际版本、NuGet/CRT/WebView2/Office/Java及安装器payload覆盖，也没有完整依赖边、许可证原文/义务或漏洞结论。Syft推断的CPE不等于确认漏洞匹配。本命令不替代原check_release门禁；完整REL-01仍需对照实际发行包，REL-02/03单独处理许可与漏洞。

## 冻结后端SBOM与覆盖对照

对一个已核构建来源的后端onedir目录运行以下独立命令；`$verifiedSourceHead`和`$verifiedExeSha256`分别由该次构建的精确源码提交和exe字节提供。使用与冻结字节码一致的固定CPython 3.13.17，不执行候选包内代码：

```powershell
.local/release-venv/Scripts/python.exe tools/frozen_sbom.py --payload dist/study_backend --source-head $verifiedSourceHead --exe-sha256 $verifiedExeSha256 --syft .local/release-tools/syft-1.57.1/syft.exe --output artifacts/frozen-sbom-01
$coverageExit = $LASTEXITCODE
```

输出须为payload外的新目录，父目录须存在。复用固定Syft exe hash、锁解析及staging文件/链接拒绝；本清单也包含已存在的根build-inventory.json。限20000实体文件、每文件256MiB、总3GiB；原件不复制、修改或执行。扫描仅启用Python installed/PE/binary cataloger及全部文件SHA256，关闭更新/enrich/远端许可查询并清除继承SYFT配置变量。保留原始backend.cdx.json（CycloneDX 1.6）、backend.syft.json及日志；coverage.json逐项核对实体路径集合/hash、实际随包METADATA身份与源码锁，以及两种扫描输出中的候选身份/位置。缺失、额外、重复、错版本或内容变化失败，不输出成功对照。

静态读取CArchive/PYZ和base_library.zip目录，检查容器范围、数量、重复/重叠和名称；不落地提取或运行代码。PYZ记录的是压缩字节hash，不冒称全部解压代码身份；namespace条目无内容。ZIP限单成员8MiB/总256MiB，记录实际读出的字节hash，成员仍不据名称认定包来源。全部study_workbench模块须与当前源码按嵌套代码/常量/异常表相等，另存源码SHA256/Git blob。结束复核payload、锁及业务源码不变；不声称原子文件系统快照。

source head和预期exe hash是调用者声明，工具不认证远端Git或构建来源；实际交付仍须把记录的源码blob核对到指定head/tree及构建证据。METADATA只证明随包声明，不能代表全部冻结Python成员或官方归档认证；PE资源版本/PURL/CPE保留为未核候选，PYD、内嵌模块及源锁中未观察到METADATA的包分别列缺口，不能把“缺元数据”写成“未打包”。文件覆盖数量不是完整包身份覆盖。latex2mathml的项目MIT声明不能覆盖其上游内嵌数据的LPPL及修改来源待核事项；此工具不添加当前未用的HTML/MathML导出资源。

退出1表示检查失败；退出2表示有限扫描/对照完成但完整产品SBOM仍不完整，固定product_sbom_complete=false，不返回发行通过码。CLI核对范围/身份，交付另用固定官方1.6 Schema验证实际输出。未知版本/来源/模块映射、完整依赖边、传递许可/漏洞/签名、前端/其他组件与安装器payload继续分别处理；不替代check_release，也不改变现有打包或产品流程。

## 源码锁文件漏洞查询

在确认两份锁文件仅包含可公开查询的依赖名后，以既有构建Python执行：

```powershell
.local/release-venv/Scripts/python.exe tools/source_vulnerabilities.py --output artifacts/source-vulns-01
$queryExit = $LASTEXITCODE
```

output必须是不存在的新目录且父目录已存在。复用源码SBOM相同锁解析/身份/链接拒绝，结束重核锁未变；只向固定https://api.osv.dev/v1/发送公开名称/版本/生态及服务返回的分页token/公告ID，不发送源码、锁文件内容、hash、Git URL/commit、个人数据或凭据。禁用代理继承与重定向；单次30秒/8MiB、最多1000包/8轮分页/1000公告预算。企业代理环境不可直连时明确失败，不改用其他查询站点。

report.json记录查询器1.0及两份工具源码hash、锁hash、Python版本、UTC查询时间、HTTP Date、逐项匹配/原始影响范围和修复事件、别名、来源、撤回/映射缺失/变更状态；编号request/response文件保存原始字节，evidence记录对应SHA256，超预算仅保留已读前缀并报错。API批次时间可精确到微秒而详情含纳秒，比较明确使用微秒精度并保留两种原值。完整数据库版本/时间/hash无法由在线API取得，必须保留snapshot/freshness未知；HTTP Date新鲜不证明数据库新鲜。超过24小时或超前5分钟的响应Date拒绝，缺Date明确未知；重新查询使用新目录，旧记录不视为持续有效。

退出1表示查询、结构、映射批次或源一致性失败；已有原始现场/失败报告保留。退出2表示返回公告（含需进一步判定的撤回/变更/映射未知），退出3表示当前查询完成但没有返回公告；两者均不是发行通过码，工具不返回安全认证的0。空结果只能称“无公告返回”，不能称“安全包”。Git和SDK排除项、开发/构建/跨平台成员、最终产品未覆盖始终保留；不依据空结果自动批准发行、不自动升级或改变既有check_release门禁。网络查询仅显式运行；CI用离线自编响应验证信任边界，不依赖在线数据库稳定性。

## 规划中

自动升级/完整回滚产品流程、下载/转码组件、正式签名发行按专项实施。FFmpeg须先锁定实际构建开关与LGPL/GPL/nonfree及来源义务；本地生成样本不等于可随产品分发。

## 待验证

实际setup安装/升级/卸载、无Python/无WebView2干净机、普通用户/中文空格路径、睡眠和硬件矩阵、完整传递依赖许可/SBOM/漏洞/代码签名仍待验。编译出setup、本机清单检查、专项冻结通过不代替它们。发布和合并必须取得对应授权。

本机历史测试包路径与hash仅在[任务报告](../dev/README.md)记录，不在本指南维护多个“最新”入口；本轮未生成或替换测试包。
