# Windows构建、安装与数据

## 当前已实现

构建基线Flutter/Dart、独立CPython3.13.17/PyInstaller onedir、Inno Setup portable工具、app-local CRT和WebView2离线安装器；不打包开发Anaconda。版本/来源/许可见[依赖](dependencies.md)。

staging文件清单生成与校验共用枚举：只排除根build-inventory.json，嵌套同名文件仍计入；拒绝子目录/文件符号链接、重解析点和非普通文件，不沿它们读写。生成许可副本前先检查现有stage。check_release先要求实际相对路径集合与清单完全相等，再核文件hash及原CPython/.db/CRT/PE检查；绝对路径或../清单项不能借校验读取stage外文件。build-release在生成清单后、编译安装包前执行此检查，非零即停，保留失败stage。该门禁依赖稳定的构建暂存目录，不构成原子文件系统快照或完整发行SBOM、签名/许可/漏洞认证。

固定Windows x64目标另要求根目录PE文件、backend/study_backend.exe及backend内DLL/PYD的Machine为AMD64、可选头为PE32+，在读取导入表前拒绝不符文件；失败仍关闭PE句柄，不修改候选字节。可选转换器目录与backend内独立helper EXE不套用主进程架构门禁，仍受原文件hash及PE导入检查。文件头声明不证明签名、来源身份、CPython ABI或完整加载兼容性，不能替代运行验证。

仓库根先执行packaging/windows/prepare-tools.ps1验证固定下载SHA256/签名并建立.local/release-venv，再执行packaging/windows/build-release.ps1。后端使用--clean避免增量缓存保留旧业务代码，并由tools/check_frozen_sources.py在固定CPython3.13.17下核对包内全部业务模块与源码（含嵌套代码/常量/异常表），失败即构建失败。构建从pubspec.yaml读取版本，写全新staging，收集Python/Dart/Flutter/native许可证、文件hash与PE依赖。Windows构建串行；只能交付配套前端data/app.so与冻结backend，不能只拿exe或旧runner后端。

可选LibreOffice26.8.1组件以prepare-office-runtime.ps1 -Package <固定MSI> -Destination <新目录>管理镜像解包，不注册系统安装或关联。build-release.ps1默认不带组件；显式-OfficeRuntime <已核目录>才经tools/stage_office_runtime.py复制清单/许可并校验。拒绝覆盖现有组件目录。历史清单19417文件/约1.47GiB（不含MSI/清单），体积属于当时固定版本；默认主包不增加此组件。

后端相对安装根定位组件，仅启动环境可用STUDY_OFFICE_RUNTIME指定可信绝对路径，HTTP不接受转换器路径/命令。完整核验运行时会增加耗时，90秒限制只约束引擎执行。

安装与数据目录分离。每用户安装默认LocalAppData/Programs/StudyWorkbench，安装器允许选择目录。数据由Known Folder定位：普通进程LocalAppData/StudyWorkbench/data，低完整性进程LocalAppDataLow；已有明确配置/同profile旧m0库优先。配置定位LocalLow并兼容旧LocalAppData设置，具体见[ADR0006](adr/0006-default-user-storage.md)。首次自动用默认/已保存位置，选择入口位于设置/失败恢复；不因权限失败静默切空库。

数据迁移：保存页面/释放WebView→停写和后端→本地路径/空间/非嵌套/空目标校验→SQLite backup和文件复制→hash/数量/逻辑内容/integrity/外键检查→原子配置切换→重启确认。失败保留旧数据/配置和目标现场，不伪装跨卷原子move，不执行破坏性downgrade。卸载无个人数据删除规则，默认保留学习资料。

## 规划中

自动升级/完整回滚产品流程、下载/转码组件、正式签名发行按专项实施。FFmpeg须先锁定实际构建开关与LGPL/GPL/nonfree及来源义务；本地生成样本不等于可随产品分发。

## 待验证

实际setup安装/升级/卸载、无Python/无WebView2干净机、普通用户/中文空格路径、睡眠和硬件矩阵、完整传递依赖许可/SBOM/漏洞/代码签名仍待验。编译出setup、本机清单检查、专项冻结通过不代替它们。发布和合并必须取得对应授权。

本机历史测试包路径与hash仅在[任务报告](../dev/README.md)记录，不在本指南维护多个“最新”入口；本轮未生成或替换测试包。
