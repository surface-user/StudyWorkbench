# Windows构建、安装与数据

## 当前已实现

构建基线Flutter/Dart、独立CPython3.13.17/PyInstaller onedir、Inno Setup portable工具、app-local CRT和WebView2离线安装器；不打包开发Anaconda。版本/来源/许可见[依赖](dependencies.md)。

staging文件清单生成与校验共用枚举：只排除根build-inventory.json，嵌套同名文件仍计入；拒绝子目录/文件符号链接、重解析点和非普通文件，不沿它们读写。生成许可副本前先检查现有stage。check_release先要求实际相对路径集合与清单完全相等，再核文件hash及原CPython/.db/CRT/PE检查；绝对路径或../清单项不能借校验读取stage外文件。build-release在生成清单后、编译安装包前执行此检查，非零即停，保留失败stage。该门禁依赖稳定的构建暂存目录，不构成原子文件系统快照或完整发行SBOM、签名/许可/漏洞认证。

固定Windows x64目标另要求根目录PE文件、backend/study_backend.exe及backend内DLL/PYD的Machine为AMD64、可选头为PE32+，在读取导入表前拒绝不符文件；失败仍关闭PE句柄，不修改候选字节。可选转换器目录与backend内独立helper EXE不套用主进程架构门禁，进入已声明运行域的文件再核AMD64/PE32+；闭包外PE保持未分类，不能据路径或不可达就认定不会运行。文件头声明不证明签名、来源身份、CPython ABI或完整加载兼容性，不能替代运行验证。

原生依赖检查覆盖.exe/.dll/.pyd及MZ格式.com/.bin的普通与延迟导入。只在声明的主应用根、后端_internal及各插件自身目录、Office program与其显式Java根、独立Java进程bin/server域解析，不以全包同名DLL或外部PATH兜底。普通私有VC运行库必须位于各进程约定的app-local根，System32不能补私有CRT；NumPy/Pandas的.libs须匹配固定完整冻结初始化代码指纹，才采用其中已核的目录注册行为。注册目录顺序不明或同一后端进程解析到同名不同字节时拒绝。版本/初始化代码变化必须重新取证，规则不是自动支持未来版本的白名单。

Office域还读取固定组件自带的UNO注册入口：先核program/uno.ini、fundamental.ini和7份services注册文件的完整SHA256及注册目录文件集合，再仅解析这些已核字节；URE_INTERNAL_LIB_DIR与LO_LIB_DIR只映射到program，拒绝其他变量、绝对/嵌套/穿越路径和非DLL/PYD原生入口。注册的SharedLibrary及其传递依赖共用原Office搜索根/架构/CRT守卫，报告保留每个入口的注册来源与配置hash。Java/Python脚本注册不计为原生库，用户/扩展动态注册、CLR、其他辅助进程仍不由此证明；版本、启动配置或注册集合变化必须重新核证，不据文件恰在program就认可运行域。

配套JRE的DLL另以固定java/java-runtime-lock.json原字节SHA256核验：要求实际DLL集合、各文件hash/AMD64/PE32+及release身份与原清单相等，只支持bin和bin/server。清单中86个DLL作为保守入口同时加入原Office与Java域；两域的搜索目录和各自program/bin私有CRT规则不变，不以另一域或System32填补缺失。报告单独保留固定Java锁、release和DLL hash映射。其他JRE EXE、托管程序集、安装模板与独立辅助进程仍须另有加载证据。保守静态覆盖不代表每个DLL实际执行，也不限制Java USER_PATHS、自定义JNI、SxS或任意动态加载；这些边界见[任务原报告](../dev/records/2026-11-10-release-integrity/report.md)。

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

源码与冻结helper共用固定bootstrap命令：配置仅从包内share/registry的schema/data/resource层和本任务profile读取，不加载HKLM/HKCU策略或扩展配置层；UNO服务/类型限定原包7份services及3份types注册文件，Java类型仅原包两份jar，不展开用户/共享/捆绑扩展unorc。所有路径由已核组件和任务目录生成file URI，不接HTTP/文档传入的bootstrap参数；环境从SystemRoot/WINDIR重新建立，不继承URE_BOOTSTRAP、INIFILENAME等配置来源。profile显式清空ooSetupConnectionURL；强制策略隔离由省略外来配置层实现，不依赖空值覆盖finalized策略。转换选项升v4，旧缓存与文件保留但须重新生成后使用。该措施不删除原组件、扩展文件或许可，不构成Windows文件/网络沙箱，也不证明TWAIN等所有动态路径不可达；证据及未验边界继续原报告。

组合目录可交给原build-release.ps1的-OfficeRuntime入口，默认主包行为保持。实际加载、转换及限制见[发行任务报告](../dev/records/2026-11-10-release-integrity/report.md)。完整PE进程加载域/延迟导入门禁、发行SBOM、传递许可/源码义务、漏洞和签名仍须分别完成；本步骤不等于Office整包可发行或干净机验证。

## Office Python模板来源证据

使用已有构建Python环境离线运行；输入必须是固定Office-Java组合及已下载的[CPython 3.13.15官方源码归档](https://www.python.org/ftp/python/3.13.15/Python-3.13.15.tar.xz)，命令不会下载、安装或执行归档内容：

```powershell
python tools/office_template_evidence.py --office .local/release-tools/libreoffice-java-26.8.1-21.0.13 --python-source .local/release-tools/cpython31315-source/Python-3.13.15.tar.xz --output artifacts/office-template-01
```

output须为全新目录且父目录已存在，不得位于组件内。固定归档大小/hash、组件原清单hash及完整实际文件集合/hash均须相符；拒绝链接/重解析路径、特殊归档成员、重复/越界/规范化文件名。tar限50000成员、单成员64MiB/总声明展开512MiB；每个wheel限8MiB、4000成员/总展开64MiB、实际单成员4MiB，完整读取内容校验声明长度及CRC；不提取到磁盘。只比较实际pip/setuptools包目录与精确源wheel，LO单补丁使用固定输入/输出hash，单改名使用固定路径及内容hash，不接受模糊补丁或推测安装版本。

report.json保留每个实际成员和源wheel的hash/对应关系、源发行版本、PE架构/ZIP/overlay、producer身份，以及原模板缺少附加archive/shebang或同目录-script.py(w)的条件。launcher C源与上游资产的Git身份仅提供来源关联，不构成可重现编译证明；源发行版本不表示完整安装发行身份。末尾重核源归档、清单、路径集及选中文件稳定，失败保留现场且不生成成功report，不覆盖已有输出。

退出0仅表示有限来源/结构证据采集完成；报告固定`runtime_classification=unclassified`、`runtime_exclusion_verified=false`、`product_release_ready=false`。不执行模板、producer或源码，不根据目录名、缺附加数据或未观察到加载推断实际产品不可达；不删除模板、不改变原生加载域或check_release。实际受控产品入口、Python/托管/x86域及系统来源仍须后续绑定核验，完整发行门禁保持。

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

## 冻结Python成员与本地构建源对应

使用与该冻结包一致的CPython补丁版本及实际锁定构建环境，以前一命令生成的coverage.json为输入；`$buildPython`须指向该环境，工具不会安装/升级依赖或执行候选包代码：

```powershell
& $buildPython tools/frozen_python_members.py --payload dist/study_backend --coverage artifacts/frozen-sbom-01/coverage.json --output artifacts/frozen-members-01
$membersExit = $LASTEXITCODE
```

输入coverage最多16MiB，输出须在payload之外、目录不存在且父目录存在。重新核实体集合/hash、锁、随包METADATA、全部内嵌目录及业务源码；不能只凭一份旧报告或caller head认定输入。对源锁中精确名称/版本的唯一安装分发读取原始METADATA/RECORD，RECORD每份最多4MiB、总100000行，选中构建源最多20000文件/逻辑1GiB；编译源码每份最多8MiB，其他文件最多256MiB。越界/链接/重解析、重复或畸形RECORD、被选中文件hash/长度不符、预算越界均失败。合法控制台脚本的../路径只计为忽略，绝不沿其读取site-packages之外的文件；没有RECORD SHA256的候选列为未验证。

仅为实际存在的PYZ模块或实体文件建立对应。先核本地源文件与RECORD SHA256/长度，再将源码静态编译，与冻结code object的嵌套代码/常量/异常表比较；分别记录等价的优化等级0/1/2，多个等级相等时不推断当时的真实选项。实体文件须路径对应且字节SHA256相等。一个成员若对应多个构建包，保留全部候选并标歧义，不任选归属；namespace无代码不据前缀分包。没有实际唯一对应的环境包不投影为发行成员，不能因某包被匹配就声称它的全部文件都随包。

members.json保存逐实际位置、PURL、源文件/RECORD/METADATA hash、未映射与歧义；python-members.cdx.json为这些唯一对应成员的CycloneDX1.6子集，以occurrence关联实际模块/文件位置。元数据hash不放成整个包的archive hash。工具末尾复核payload/coverage/锁/业务源码和选中的构建证据未变，失败不生成成功报告。

CLI退出1表示失败，退出2表示有限对应完成；product_sbom_complete、upstream_provenance_verified及source_head_authenticated保持false。本地安装文件与RECORD/冻结代码相等不等于官方wheel/源码归档认证、完整包所有权、运行时可达性或完整依赖关系。未映射stdlib、基础ZIP、CArchive脚本/bootloader、原生DLL及其他产品组件继续后续核对；本命令不修改原始scanner输出、打包内容或check_release，不代替许可/漏洞/签名检查。

## 固定Python归档、项目资产与启动来源

对前一节仍未知的内容，可使用固定CPython NuGet和声明的Git blob清单补充来源。source-tree为已另核远端提交/tree后保存的`commit`、`tree`及普通文件`entries`清单；工具不联网认证Git，不把caller字段当签名或远端证明。须使用实际锁定构建环境：

```powershell
& $buildPython tools/frozen_python_origins.py --payload dist/study_backend --coverage artifacts/frozen-sbom-01/coverage.json --python-package .local/release-tools/python.3.13.17.zip --source-tree artifacts/verified-source-tree.json --output artifacts/frozen-origins-01
$originsExit = $LASTEXITCODE
```

只接受prepare-tools.ps1同一CPython3.13.17 NuGet全档SHA256及相同补丁版本解释器。压缩档限64MiB，NuGet最多20000条/声明及实际读取各256MiB、每成员16MiB、编译源码8MiB；拒绝危险原名、重复大小写、链接/特殊或加密成员、DTD/实体及重复/错误id/version。按Windows唯一大小写无关路径查找并记录实际成员名；只读有界字节、静态比较代码或完整文件hash，不落地解包。NuGet自身含其他原生库，匹配其分发字节不等于这些库的独立身份/许可证/签名都已验证。

命令先在新输出的local-members内重新执行前节完整核验，再补CPython的PYZ/基础ZIP代码、二进制、项目迁移/HTML/入口源码、CArchive中的stdlib和PyInstaller初始化/runtime hooks。后者须与精确构建分发的METADATA/RECORD/hash和完整静态代码对应，不按模块前缀猜版本。项目源和payload分别核声明Git blob及代码或字节；Git清单上限16MiB/20000普通文件，source head/tree仍明确是未认证声明。旧阶段选中但未匹配的源输入也继续守原预算并在增强阶段末尾复核。

RECORD自身按标准可有空的self hash；仅当该精确包的原METADATA/RECORD证明一致、self行hash/size均为空，且随包RECORD整字节等于构建原件时，另记`local_record_metadata_bytes`及`record_self_hash_declared=false`。不改第三方RECORD、不填造自证hash，也不将该例外推广到任意无hash源码。移位DLL按RECORD完整字节追溯原路径，多个分发提供相同字节时保留所有来源，不任选所有者。

namespace条目仅记无代码类型、版本null及已验证子模块的构建分发关联；这不是namespace版本认证。origins.json保存所有新增对应和仍未知内容，python-origins.cdx.json增强既有已证子集并用occurrence关联实际位置。NuGet全档hash可作为其分发档hash，其他包的metadata hash不冒充归档。观察到payload/coverage/锁、源Git清单、NuGet、前阶段输出或任何选中构建/项目输入变化时不生成增强最终报告；前阶段局部产物存在不表示整体通过。

退出1为失败、2为有限来源对应完成。product_sbom_complete、upstream_provenance_verified、source_tree_authenticated仍为false；外层PE bootloader、未闭合CRT/native、生成容器身份、完整依赖边、许可/漏洞/签名及其他产品组件仍待核。原scanner输出、旧报告及产品包保持，不据增强子集批准发行。

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
