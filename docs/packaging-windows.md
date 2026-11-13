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

## 规划中

自动升级/完整回滚产品流程、下载/转码组件、正式签名发行按专项实施。FFmpeg须先锁定实际构建开关与LGPL/GPL/nonfree及来源义务；本地生成样本不等于可随产品分发。

## 待验证

实际setup安装/升级/卸载、无Python/无WebView2干净机、普通用户/中文空格路径、睡眠和硬件矩阵、完整传递依赖许可/SBOM/漏洞/代码签名仍待验。编译出setup、本机清单检查、专项冻结通过不代替它们。发布和合并必须取得对应授权。

本机历史测试包路径与hash仅在[任务报告](../dev/README.md)记录，不在本指南维护多个“最新”入口；本轮未生成或替换测试包。
