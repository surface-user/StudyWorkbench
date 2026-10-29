# M1 首批实现与验证（2026-10-24）

用户明确授权暂时忽略 M0 问题、提前开发 M1，见 [ADR 0003](adr/0003-early-m1-workbench.md)。本批完成 M1-01/02 的工作台垂直切片，不宣称整个 M1 完成，不把 M0 遗留故障改成通过。

当前检出：`D:/computer_work/project/StudyWorkbench`；本地分支：`codex/m1-workspaces-tabs`。原有未提交 M0 修复、文档、证据与 `.vscode` 均保留。开发前将工作副本补丁和涉及源码复制到忽略的 `.local/m0-before-m1-20261024`；未提交、推送、合并、发布或创建子 Agent。

## 可用内容

- 真实侧栏工作空间创建、重命名、切换、确认移除与恢复；至少保留一个活动空间。移除采用归档，保留题目、作答、布局和 profile。
- 每空间独立演示题、判分及追加作答。数据库复合主键/外键与服务端作用域检查；旧 API 固定 default，不受查询参数或当前 UI 选择影响。
- 标签栏从三个固定按钮改为动态页面：可新增多个题目/网页/播放器，关闭、重新打开；关闭历史最多10项，打开页最多16项。已访问页面切换时保留实例，关闭后销毁；未访问恢复页按需创建。
- 主观草稿、网页最后成功加载地址、活动工作空间/标签、关闭历史经受保护 API 保存在 SQLite，重启恢复。串行自动保存避免旧请求覆盖新草稿；切换空间与正常退出等待保存，失败保留待保存状态并提示。
- 迁移0002前使用 SQLite backup API 与 integrity_check，旧记录归属 default、ID/响应/成绩原样保留；显式事务包裹 DDL，故障注入证明失败回滚与备份保留。不静默改写标准答案或重建个人数据库。

![真实 Windows 工作空间和动态标签截图](evidence/m1-20261024/m1-workbench.png)

新普通预览入口：`apps/desktop/build/windows/x64/runner/Debug/study_workbench.exe`。需保留同目录 DLL/data、仓库和已有 `.venv`；本轮编译指定源码后端与 `.local/m1-preview-20261024` 隔离数据，首次运行只创建默认空间，其他空间由用户创建。旧 Release 没有更新为 M1，其故障仍搁置。

## 实际检查

所有证据在 [本轮证据目录](evidence/m1-20261024/)。命令在仓库根目录运行；Flutter 命令工作目录为 `apps/desktop`，使用已有 SDK/依赖与受审查的扩展权限，不安装新依赖、不改 SDK/系统设置。Python TEMP/TMP 和 Windows NuGet scratch 仅设置到项目内当前进程目录。

| 实际命令 | 退出码 / 结果 | 范围 |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests -q --junitxml=artifacts/m1-20261024/backend-complete.xml` | **0；47 passed** | [日志](evidence/m1-20261024/backend-complete.log)、[XML](evidence/m1-20261024/backend-complete.xml)。含 M0 原40项，以及空间隔离、归档/恢复/确认、名称/权限、布局完整性/版本/URL、完整数量的长中文草稿、旧库备份/升级及 post-DDL 故障回滚；有既存 Starlette/AnyIO 弃用警告 |
| `.venv/Scripts/python.exe -m ruff check backend tools` | **0** | [日志](evidence/m1-20261024/ruff.log)；只修正了新增导入排序，未降低规则 |
| `flutter test --no-pub` | **0；16 tests passed** | [日志](evidence/m1-20261024/components-final.log)。原12项、标签ID/关闭重开/草稿/数量/循环2项、活动空间移除加载期间有效页面与并发保存新草稿2项 |
| `flutter analyze --no-pub` | **0；No issues found** | [最终日志](evidence/m1-20261024/analyze-final.log)；10.5秒。首轮/中间轮风格错误原日志保留 |
| `dart format --output=none --set-exit-if-changed lib test integration_test` | **0；0 changed** | 最终格式检查；不是运行验收 |
| 下述 `flutter test integration_test/m1_test.dart -d windows ...` | **0；1 passed** | [最终日志](evidence/m1-20261024/native-final.log)；30.1秒构建，约19秒运行；真实 Flutter/Python/SQLite 重启，不是内存后端 |
| 同参数体系运行 `integration_test/m0_test.dart` | **0；1 passed** | [日志](evidence/m1-20261024/m0-regression.log)；30.7秒构建，约17秒运行。保留题目/网页/视频/字幕/跳转断言，新增关闭播放器后重开并再次解码 |
| `.venv/Scripts/python.exe tools/smoke_backend.py` | **0** | [日志](evidence/m1-20261024/process-smoke.log)；源码后端真实随机端口、鉴权 SQLite health、父进程 EOF 退出 |
| 下述 `flutter build windows --debug ...` | **0** | [构建日志](evidence/m1-20261024/debug-build.log)；29.0秒；普通入口预览，不是安装包/冻结后端/Release |
| `git diff --check` | **0** | Git 有 LF/CRLF 提示，无空白错误 |

Windows M1 集成的具体行为：默认空间提交正确答案；通过界面创建第二空间后提交，确认为仅1条作答；第一页输入中文草稿，新建第二题目页输入不同草稿，关闭后回到第一页，重开恢复第二页草稿；两空间来回切换；通过菜单重命名；重建整个 StudyApp 并重新启动真实 Python 后端，确认空间名、活动标签和中文草稿恢复；先取消移除，再确认归档，恢复空间后再次提交，累计2条作答证明旧记录保留。截图在重启后、归档前捕获。该自动交互不等于用户人工接受体验。

M0 回归在新工作台中通过菜单实际新增网页和播放器标签，读取真实 WebView DOM；真实样本是自有6秒无音轨 VP9 WebM。字幕为测试生成的 WebVTT Blob，断言 track 解码和中文 cue；跳转2秒容差±0.25秒；原生播放器关闭/重开后重新检查 metadata，销毁检查无 Flutter 异常。不证明完整编码、音轨、字幕文件对话框或跨启动播放进度；此前文件对话框实测仍单独保留在 M0 跟进报告。

复现（两个原生集成和普通构建串行运行，使用独立数据目录，重跑用新目录保留旧失败现场）：

```powershell
. ../../tools/prepare-windows.ps1
$env:PATH = 'D:\computer_work\project\StudyWorkbench\.local\bin;' + $env:PATH
flutter test integration_test/m1_test.dart -d windows --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m1-native-20261024-3 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm `
  --dart-define=STUDY_EVIDENCE_DIR=D:/computer_work/project/StudyWorkbench/artifacts/m1-20261024

# M0 回归用 .local/m1-m0-regression-20261024-1，测试文件改为 integration_test/m0_test.dart。
flutter build windows --debug --no-pub `
  --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench `
  --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m1-preview-20261024 `
  --dart-define=STUDY_MEDIA=D:/computer_work/project/StudyWorkbench/.local/sample.webm
```

## 失败保留与审查

- [首次 M1 原生失败](evidence/m1-20261024/native-first.log)，退出1：移除当前空间时先删页面缓存，切换还未完成造成 IndexedStack 索引为-1。现改为在一次成功的服务器状态刷新中同时更新活动空间与清理归档页面缓存；失败刷新不先丢弃现有缓存。新增延迟加载回归保留此断言。
- 首轮另有恢复弹窗与侧栏同名文字的测试定位歧义。现用 SimpleDialog 后代与 workspace ID 行键定位，不改变作答/持久化断言；随后整轮重跑通过。
- [组件中间失败](evidence/m1-20261024/components.log)、[诊断](evidence/m1-20261024/shell-diagnostic.log)，退出1：新增替身后端返回了未展开的 Future，诊断明确为 Future 无 `[]`。修正替身的 await，保留原有效页面断言；并发草稿测试也保留。最终16项整轮通过。
- [首次分析](evidence/m1-20261024/analyze-first.log)与[中间分析](evidence/m1-20261024/analyze.log)退出1，均为缺失大括号的风格规则，补齐后最终通过，没有关闭 lint。
- 所有 Windows 构建保留既有 WebView 插件 CMP0175 开发警告；未改上游依赖源码。

本轮自审核对了题目/作答所有调用者、旧 API default 兼容入口、复合外键、备份/回滚、归档引用、布局输入边界、保存请求时序、页面键、WebView profile 与关闭后重开，以及旧集成脚本；未使用独立审查 Agent。布局请求单独放宽至2 MiB以容纳16个打开页+10个关闭历史的有界中文草稿，其余请求仍64 KiB，模型数量/字段白名单继续约束。题目页只从当前空间请求标准答案与提交，客户端不传分数。

## 未完成项与阶段边界

| 状态维度 | 本批结论 |
|---|---|
| 实现 | M1-01/02 首批工作台流程已接入；归档不等于永久删除；拖动排序未实现 |
| 自动化 | 47后端、16组件、2项真实Windows集成、静态/源码进程/Debug构建通过 |
| 人工 | 用户尚未验收；高DPI/多窗口/真实IME和原生WebView焦点下快捷键未完成；未使用受阻的浏览器 Computer Use 验收来代替这些项目 |
| 阶段 | **M1 未通过**；M0仍保留原未解决与未验收状态 |

M1-03 首次数据根选择、设置与跨卷安全迁移/故障回滚尚未开发；本批 schema 升级备份不等于已实现数据目录迁移。M1-04 多实例/崩溃、独立 CPython、Runtime 安装检测、setup/干净机/升级卸载验收尚未开发或完成。后续按这两项继续推进，不以本轮 Debug 预览代替正式分发。M0 Release mkdir/默认profile 500、签名与浏览器工具限制继续搁置。
