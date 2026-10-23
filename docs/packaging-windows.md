# Windows 安装与数据

M0 脚手架：Flutter release 目录 + PyInstaller onedir 后端 + Inno Setup setup.exe。不打包开发用 Anaconda；由独立 venv 构建。PyInstaller 必须在 Windows 构建 Windows 程序，SQLAlchemy/SQLite/迁移文件收集与干净机运行是独立验收。

安装可选择目录，默认每用户 LocalAppData/Programs/StudyWorkbench；数据默认 LocalAppData/StudyWorkbench/data。M0 原型使用独立 m0 子目录。安装器不设置 UninstallDelete 到个人数据。卸载默认保留，彻底删除功能必须显式确认并校验目标目录。

首次启动数据位置选择和设置内迁移是 M1 任务。迁移流程：停止写入/下载→检查空间与路径（禁止程序目录/根目录/嵌套自身）→SQLite backup API 一致性备份（包含 WAL）→临时目标复制→哈希/数量与 integrity_check→原子切换配置→重启验证→完成日志。失败切回旧配置，绝不自动删除旧目录，跨卷复制不能伪装为原子 move。

WebView2 Evergreen Runtime 安装检测/离线分发、VC++ runtime、代码签名、自动升级回滚、非管理员/中文/空格路径、睡眠恢复、卸载保留数据待 M1 干净 Windows VM 验证。

许可证：PyInstaller GPL 带 bootloader 例外，可发行自有应用但依赖义务仍在；Inno Setup 自有许可且当前商业使用条款需复核；FFmpeg 需按实际构建开关审查 LGPL/GPL/nonfree 与源码提供义务；未确定二进制前不得发行。
