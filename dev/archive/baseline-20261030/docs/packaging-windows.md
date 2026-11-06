# Windows 安装与数据

2026-10-26：Word/PPT分页为可选LibreOffice26.8.1组件。官方MSI固定hash/签名后，用 packaging/windows/prepare-office-runtime.ps1 -Package <已下载固定MSI> -Destination <项目内新目录> 作管理镜像解包并生成runtime-lock，不注册安装或关联。build-release.ps1默认不带该组件；显式 -OfficeRuntime <已核目录> 才通过 tools/stage_office_runtime.py 复制清单文件/许可并复核到新stage/converters/libreoffice。已存在组件目录拒绝覆盖。离线运行时19417文件/1577045386字节（约1.47GiB，不含MSI和清单）；默认主包不增加该体积。冻结后端相对安装根定位；仅启动环境可用STUDY_OFFICE_RUNTIME指定可信本地绝对路径，HTTP不接受路径或命令。独立冻结/受限PATH/自编样本测试见[R3记录](r3-office-validation-2026-10-26.md)，不替代干净机、组合许可和安装/卸载验收；未替换StudyWorkbench-current或发布安装器。

2026-10-24 更新：本地 M1 配套 Release/setup 已编译，独立 CPython 3.13.17、app-local CRT、WebView2 离线安装器和许可/文件清单已接入。首次目录选择与设置迁移已实现。下方“M0 脚手架/待 M1”保留为设计来源，最新实际命令、通过项与未完成安装/卸载/干净机验收以 [持续开发报告](m1-completion-2026-10-24.md) 为准。

构建：先 `packaging/windows/prepare-tools.ps1` 验证固定下载与签名、建立 `.local/release-venv`，再 `packaging/windows/build-release.ps1`。Inno 使用官方 portable 模式部署到项目内；Evergreen 下载地址可变化，哈希不一致必须停止复核。构建脚本从 pubspec.yaml 读取产品版本，只写全新 staging，旧 Release 后端移到项目忽略目录保存。发布仍需要独立授权。

M0 脚手架：Flutter release 目录 + PyInstaller onedir 后端 + Inno Setup setup.exe。不打包开发用 Anaconda；由独立 venv 构建。PyInstaller 必须在 Windows 构建 Windows 程序，SQLAlchemy/SQLite/迁移文件收集与干净机运行是独立验收。

安装可选择目录，默认每用户 LocalAppData/Programs/StudyWorkbench；数据默认 LocalAppData/StudyWorkbench/data。M0 原型使用独立 m0 子目录。安装器不设置 UninstallDelete 到个人数据。卸载默认保留，彻底删除功能必须显式确认并校验目标目录。

首次启动数据位置选择和设置内迁移是 M1 任务。迁移流程：停止写入/下载→检查空间与路径（禁止程序目录/根目录/嵌套自身）→SQLite backup API 一致性备份（包含 WAL）→临时目标复制→哈希/数量与 integrity_check→原子切换配置→重启验证→完成日志。失败切回旧配置，绝不自动删除旧目录，跨卷复制不能伪装为原子 move。

WebView2 Evergreen Runtime 安装检测/离线分发、VC++ runtime、代码签名、自动升级回滚、非管理员/中文/空格路径、睡眠恢复、卸载保留数据待 M1 干净 Windows VM 验证。

许可证：PyInstaller GPL 带 bootloader 例外，可发行自有应用但依赖义务仍在；Inno Setup 自有许可且当前商业使用条款需复核；FFmpeg 需按实际构建开关审查 LGPL/GPL/nonfree 与源码提供义务；未确定二进制前不得发行。
