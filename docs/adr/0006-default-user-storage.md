# ADR 0006：默认用户数据位置和无选择框启动

状态：已按2026-10-25用户明确要求实施；自动化与人工验收分别记录。

用户要求首次进入不必指定数据库位置。此前配置目录失败降级只解除第一处阻断；用户随后在D盘创建`.study.lock`仍被拒绝，说明配置不可写和数据不可写是两个边界。原文件锁不存在，不能按残留锁删除处理。

Windows原生通道使用SHGetKnownFolderPath，默认数据位置为用户LocalAppData/StudyWorkbench/data；若本进程完整性低于Medium，则使用为低完整性写入设计的LocalAppDataLow/StudyWorkbench/data。不提升进程权限，不修改ACL，不用安装目录或临时目录放数据库。该profile内已有m0/study.db时继续使用；空m0目录不触发旧库选择。

启动配置统一放在Known Folder LocalAppDataLow/StudyWorkbench/settings.json，普通/低完整性模式共享同一配置定位规则，避免仅因完整性变化忘记已选数据位置。没有新配置时兼容读取此前LOCALAPPDATA/StudyWorkbench/settings.json；已有明确数据位置仍优先，无法访问时显示失败，不自动改用新空库。Windows打包应用的文件虚拟化仍由系统管理，不承诺跨不同打包身份合并profile。

首次自动用已保存位置或默认位置启动；手动选择移至设置和启动恢复。错误页新增明确的“使用默认数据位置”，只有用户点击后才切换，原目录保留；配置不可写提示和数据锁继续生效。迁移仍按ADR0004校验/保留旧数据/配置提交，不能借默认启动跳过。

技术栈和运行依赖未改变，新增调用仅使用Windows SDK的Shell/Advapi32 API。实际低完整性Windows默认目录、无测试数据目录覆盖、冻结后端的启动结果见default-startup-2026-10-25.md；普通Medium进程、安装器/干净机和人工验收另留待验。
