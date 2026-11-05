# Editor Tab Bar UI 交付记录（2026-10-25）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

需求：task.md / Tab UI Specification v1.0；设计与任务拆分见 [editor-tabs-design.md](editor-tabs-design.md)。本批保留已有未提交开发，不发布、不合并、不操作个人数据库，无新增依赖。人工与阶段验收仍待统一执行；M0 历史默认启动失败与其他阶段遗留项不据此清除。

## 实现与审查

- EditorTabBar：38px 连续标签，112–220px 宽度、单行省略/完整标题提示、统一图标；活动面与内容区相连，非活动/悬停/键盘焦点独立。关闭命中区24px，状态点独立占位。打开160ms、关闭140ms、切换120ms，遵循系统减少动画。
- 短标签组后紧跟工具；溢出时横向滚动，滚轮可横移，活动页/标题变化/窗口宽度变化后定位。禁用覆盖标签的系统滚动条；固定新建、恢复、列表菜单。保留拖动排序。
- 右键关闭、其他、右侧、全部与网页地址复制。批量关闭走同一草稿确认；不显示尚未实现的固定标签。Ctrl+T 默认学习页；Ctrl+W、Ctrl+Shift+T、Ctrl+Tab/Shift+Tab、Ctrl+1–8/9统一处理，空白双击新建默认页。侧栏学习/导入/媒体按类型去重，显式新建仍允许独立页面。
- 关闭活动页选左邻、无左邻选右邻，非活动关闭不改变当前页，末页关闭给出空工作区。题目草稿与最后成功保存值比较，保存/放弃/取消，保存失败保留页面，恢复关闭页只保留确认过的草稿。
- 各业务页报告加载/错误，网页成功加载后更新标题；页面加载与布局自动保存不阻塞标签。后端断开显示状态并继续保留可操作标签及内存页面。
- PageHost：以页ID为Stack直接子项的Key，Offstage保留实例、ExcludeFocus阻止后台焦点、TickerMode暂停后台Flutter动画。原生媒体保持继续播放策略，关闭释放WebView环境；未访问恢复页惰性创建，关闭页立即销毁，仅标签外观动画短暂留存。

核心文件：`editor_tab_bar.dart`、`workspace_layout.dart`、`workspace_shell.dart`、`page_host.dart`、`page_activity.dart`；`question_page.dart`、`study_page.dart`、`import_page.dart`、`media_page.dart`、`web_page.dart`增加状态回调，`main.dart`传入后端连接状态。新增标签/宿主测试与Windows集成；M1旧集成兼容新增保存确认。

审查覆盖页面工厂、导航、串行保存及调用方、后端layout协议、原生资源释放、快捷键输入与减少动画。JSON持久化结构不变，运行时网页标题/加载/错误不写数据库。关闭释放只针对对应页面，不释放其他标签环境。沿用每空间16页/关闭历史10页，移除空间和退出时释放其页面。

## 验证命令与证据

工作目录为仓库根；Flutter命令在`apps/desktop`执行。由于受限环境无法写项目外SDK lockfile，验证经工具权限提升运行，未修改SDK/插件缓存源码。实际Flutter调用使用已有快照：

```powershell
& 'D:\computer_work\Tools_work\flutter\bin\cache\dart-sdk\bin\dart.exe' 'D:\computer_work\Tools_work\flutter\bin\cache\flutter_tools.snapshot' <参数>
```

日志根：`docs/evidence/editor-tabs-20261025`。

| 实际命令/参数 | 退出码与结果 |
|---|---|
| `analyze --no-pub`；最终直接 `dart analyze lib test integration_test` | 首轮1（5条格式提示，analyze-02.log）；最终0，无问题，analyze-final-06.log |
| `test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/editor-tabs-pipe-final-05` | 0，61项全量通过，含2项真实后端管道；flutter-tests-final-12.log |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_workspaces.py -q --basetemp=.local/editor-tabs-workspaces-01 --junitxml=docs/evidence/editor-tabs-20261025/workspaces.xml` | 0，9项通过；backend-layout-01.log。仅运行受影响的layout/空间协议回归，未重复后端全量 |
| `test integration_test/editor_tabs_test.dart -d windows --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/editor-tabs-native-final-05 --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/m4-generated.webm --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/docs/evidence/editor-tabs-20261025` | 0，真实Windows流程1项通过，windows-native-final-05.log；含后台继续播放与关闭兄弟页/后端断开后的同实例断言 |
| `build windows --release --no-pub` | 0，windows-release-final-02.log，生成普通入口而非集成测试入口 |
| `.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage dist/StudyWorkbench-current` | 0，inventory-final-02.log |
| `.local/release-venv/Scripts/python.exe tools/check_release.py dist/StudyWorkbench-current` | 0，release-check-final-02.log，1284文件哈希/CPython/无数据库/PE导入通过 |
| `dart format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test`；`git -c core.safecrlf=false diff --check` | 最终0，format-final-03.log、diff-check-final-02.log |

Windows命令前执行`. ../../tools/prepare-windows.ps1`并将项目`.local/bin`加入本进程PATH；TEMP/TMP/NUGET_SCRATCH使用项目内路径。构建有既有插件CMake CMP0175开发警告，未修改其缓存。

## 失败与修复证据

保留全部失败断言和日志，没有删失败测试或降低断言。

- flutter-tests-01.log：高DPI侧栏溢出与非一致颜色圆角边框断言；改为可滚动侧栏、统一边框与独立焦点/活动线。
- flutter-targeted-02/03、scroll-diagnostic-04：打开标签展开前定位导致未完全可见；增加展开完成后的定位，测试按帧推进覆盖完整动画。
- flutter-targeted-03：内容ColoredBox遮挡ListTile ink的Flutter断言；改Material表面。
- windows-native-01/02：关闭中间学习页使后方原生网页被销毁。查当前Flutter SDK发现IndexedStack为各页插入无Key包装，内部Key不足以跨列表位置保留；改为PageHost并增加关闭/重排State身份回归。03已通过原实例及DOM标记断言。
- flutter-tests-final-06：新增宿主测试缺少Material祖先；修正测试环境，page-host-07通过。
- flutter-tests-final-08：系统减少动画的0ms结束回调在build期间移除标签；改帧后移除。09还暴露双击测试留下40ms手势计时器，测试等待其正常结束；reduced-motion-10与final-11均通过。
- format-final.log首轮1：新增测试待格式化；已格式化，最终检查另记。

## 实际窗口与状态结果

截图是Windows运行时渲染捕获，非设计稿；[五种标签与作答页](../../../artifacts/legacy-evidence/editor-tabs-20261025/editor-five-question.png)、[活动播放器与悬停标签](../../../artifacts/legacy-evidence/editor-tabs-20261025/editor-five-hover-player.png)、[加载态](../../../artifacts/legacy-evidence/editor-tabs-20261025/editor-five-loading.png)、[关闭中间标签的过程](../../../artifacts/legacy-evidence/editor-tabs-20261025/editor-middle-closing.png)、[后端停止后的页面错误](../../../artifacts/legacy-evidence/editor-tabs-20261025/editor-offline-error.png)。

自动化已验证五类页面、连续快捷切换、题目/导入/学习实例与输入、网页同一控制器和DOM标记、暂停视频在2秒/1.5倍速保留、中间关闭左邻选择与资源销毁、重开、后端停止后的标签交互。组件另验证末页空状态、长标题/工具位置、横向溢出与360/640/1200宽度、模拟100/200/300%DPI、保存失败/取消/放弃/保存、减少动画和双击。结果值见`native-results.json`。

## 限制与下一步

人工/阶段验收待统一执行；真实显示器多DPI、性能量化、原生WebView获得操作系统键盘焦点后的快捷键矩阵、外站登录/DRM/休眠和干净机/安装升级未在本批验收。Windows集成使用源码后端隔离数据，不能替代默认目录/冻结后端普通Explorer启动认证。

题目演示页草稿可持久化，导入/学习/网页完整实例仅在页仍打开时保留；重开网页恢复URL而非原DOM。笔记及真实练习仍为既有模态窗口，没有新增独立资源ID标签或固定标签。关闭导入页不删除已保留原件/服务器预览，发起中的媒体入库由既有后台完成/失败记录负责；关闭播放器释放本页解码环境。后端恢复重建页面仅保留现有序列化状态，不承诺恢复完整网页进程。M2/M3/M4及M5-AI未完成项继续沿原清单推进。

## 最终补记与开发包

收尾审查补齐从磁盘恢复的关闭历史草稿基线：重开后在自动保存前立即关闭，已保存草稿不再误报“未保存”；新增回归，最终61项Flutter全量通过（final-12）。新增测试的两处花括号风格提示已修正，最终`dart analyze lib test integration_test`为0（analyze-final-06.log）。

最终Windows流程补测后台继续播放，视频在后台由1秒继续推进且保持播放，返回后再暂停；同一WebView控制器及文档标记在关闭/重开兄弟页、真实后端停止后仍保留。截图与native-results.json均为真实窗口，人工验收不据此通过。

固定开发入口：`dist/StudyWorkbench-current/study_workbench.exe`（完整目录154.04MiB），同目录backend/data/DLL/licenses必须保留。旧包完整保留在`dist/StudyWorkbench-before-editor-tabs-20261025`。本次仅更新Flutter产物，冻结后端沿用既有版本；其exe哈希与备份相同（B5057FFF10117935A5607467DA01E4DA575DF5BCEFC44C07E9CBE2821A7B46E6）。没有重做setup或宣称全新安装环境通过。

包更新实际步骤：`Copy-Item -LiteralPath dist/StudyWorkbench-current -Destination dist/StudyWorkbench-before-editor-tabs-20261025 -Recurse`先创建新备份；将`apps/desktop/build/windows/x64/runner/Release`内除backend之外的产物复制覆盖current；运行`.local/release-venv/Scripts/python.exe tools/release_inventory.py --stage dist/StudyWorkbench-current`及`tools/check_release.py dist/StudyWorkbench-current`，并对exe、AOT app.so、Flutter DLL和WebView插件DLL与构建输出做SHA256一致性断言。备份不覆盖，未删除目录/个人数据。
