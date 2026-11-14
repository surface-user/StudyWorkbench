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

## 固定bootloader与CRT本地来源链

在前节基础上，另提供实际构建的COLLECT-00.toc、[固定PyInstaller wheel](https://pypi.org/pypi/pyinstaller/6.22.3/json)和调用者明确指定的CRT来源根。来源根必须由实际COLLECT路径确定，不能猜System32；命令不安装wheel、不运行外来代码或修改冻结包：

```powershell
& $buildPython tools/frozen_native_origins.py --payload dist/study_backend --coverage artifacts/frozen-sbom-01/coverage.json --python-package .local/release-tools/python.3.13.17.zip --source-tree artifacts/verified-source-tree.json --collect-toc build/study_backend/COLLECT-00.toc --pyinstaller-wheel artifacts/pyinstaller-6.22.3-py3-none-win_amd64.whl --crt-source-root $verifiedCrtSourceRoot --output artifacts/frozen-native-origins-01
$nativeOriginsExit = $LASTEXITCODE
```

TOC限1MiB、100000 AST节点、深度8和20000项，只接受字符串tuple/list字面量及既有四种条目类型；不执行表达式，拒绝危险目标名、重复大小写、非绝对或含上行的源路径，目标集合须等于全部实际payload。只对范围内api-ms-win-*及ucrtbase.dll读取显式来源根以内的普通文件并核完整字节，保留TOC原hash/条目索引/源路径与源和payload hash。根路径只声明本地来源，不证明包身份；记录component identity/version/官方archive为null、来源认证/许可/再分发资格false，仍列入未映射集合，不给未知CRT新建已认证CDX包。TOC本身不是签名构建证明。

wheel要求[依赖登记](dependencies.md)中的完整固定hash和精确长度，文件读取上限8MiB；ZIP先沿用危险原名/大小写重复/链接/特殊/加密拒绝，最多10000成员、声明和实际读取各32MiB，单成员声明16MiB、所选源码/PE读取8MiB。安装和wheel原RECORD分别限4MiB/每份100000行，逐文件核原SHA256和长度，不能把安装新增脚本后的RECORD误当原wheel RECORD。实际安装METADATA与wheel原件整字节相同，名称规范化后唯一、版本精确；run.exe及静态winutils.py/building/api.py另须同时满足两套RECORD及wheel成员相同。源码只记录字节，不执行其构建函数。

PE核AMD64/PE32+、最多16个非重叠有界节和16个DEBUG条目；执行节集合、入口及对应代码字节必须相同。每个节同时保留源/目标实际raw/virtual位置、长度、属性及hash，新增资源、其他数据差异、头和overlay分别记录。仅当成对DEBUG结构除TimeDateStamp外完全相同、完整4字节域在相同.rdata相对位置，且各时间值分别等于对应COFF时间时，才检查.rdata是否只存在这些确切字段差异；记录原新值/hex及每个改变字节的实际偏移。该字段检查不忽略任意.rdata变化，也不认证整个header、资源、overlay或可重现构建。

新阶段先建立上述输入证据，再在新输出的python-origins内完整重跑前节，不读取旧成功JSON代替验证。最终复核所有新输入（最多128文件/逻辑128MiB）、payload、锁、coverage、声明Git清单及Python归档；发生变化时不生成最终native-origins.json/native-origins.cdx.json，局部旧阶段产物不表示整体通过。CDX仅为原已证子集增加PyInstaller官方wheel hash/分发链接及实际字节相等节的occurrences，不把部分节相等写成整个exe身份。退出1为失败、2为有限来源完成，完整产品/全上游来源/整个bootloader/可重现/许可/漏洞/签名认证均不成立；原未知集合及check_release门禁保持。

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
