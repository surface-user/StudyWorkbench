# StudyWorkbench

Windows本地优先学习工作台，按工作空间、文件/链接资源和学习记录组织内容。普通导入、阅读、编辑、练习与复习不依赖LLM。

当前源码已具备资源树/统一暂存添加、受管复制、搜索与树删除、资源身份标签、受限文件查看器、Markdown工作副本、QuestionFile确认版与追加学习记录。DOCX/PPTX静态分页需可选离线组件。源码另含自由笔记、位置标记、内部链接/查找、受限XLSX查看、直接HTTPS媒体下载队列与完整库备份恢复，以及无模型的本地授权/人工候选审核。模型与凭据尚未接入；实际Explorer拖放、安装/干净机与人工/阶段验收仍待验。详细状态见[任务](docs/task.md)，不以源码能力宣称现有安装包包含全部改动。

## 开发运行

基线为Flutter3.47.1/Dart3.13.1、Python3.12/3.13.17、VS2022 C++桌面工作负载/Windows SDK和WebView2 Runtime。固定依赖见[依赖登记](docs/dependencies.md)。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
cd apps/desktop
flutter pub get
flutter run -d windows --dart-define=STUDY_ROOT=<仓库绝对路径> --dart-define=STUDY_DATA_DIR=<新的隔离开发目录>
```

STUDY_ROOT用于源码后端，STUDY_DATA_DIR隔离开发/测试数据；不得指向正式学习目录跑技术测试。插件链接/临时目录问题可用tools/prepare-windows.ps1按项目内方式准备，之后--no-pub运行；不改SDK或上游缓存。

应用默认采用已保存数据位置或Windows用户默认位置，原目录不可访问时显示错误，不静默切空库。设置提供校验迁移；安装与学习数据分离，卸载默认保留。打包运行需要完整前后端目录及DLL/data/licenses，不能只复制exe；现有测试包版本和hash按对应报告核对，本轮文档整理不生成新包。

## 文档入口

- [当前有效文档](docs/README.md)：需求、架构、数据、API、协议、安全和Agent规划。
- [任务与退出条件](docs/task.md)：实现/自动化/审查/人工/交付分别记录。
- [测试指南](docs/testing.md)与[Windows打包](docs/packaging-windows.md)。
- [开发报告及证据规则](dev/README.md)：过程记录写dev，完整原始产物写artifacts，精选共享证据才放evidence。

归档默认不参与日常开发；遇历史兼容/失败溯源才查询，架构变更查询相关ADR。流程约束见[AGENTS.md](AGENTS.md)。
