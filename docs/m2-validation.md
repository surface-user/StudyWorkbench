# M2 首批导入开发与验证（2026-10-24）

用户要求继续开发，暂不验收，task.md完成后统一验收；授权和设计见ADR 0005。本报告区分实现、自动化与人工/阶段验收，不把构建或组件通过写为产品验收。

## 本批实现

- 侧栏“导入资料”和可保存/恢复的import标签；原生单文件选择，Flutter仅传输用户所选字节，解析和持久化由Python负责。
- 原件保留在数据根下workspaces/{workspace}/originals/{resource}.bin，文件名只作元数据。SHA256、字节数、MIME、解析版本、错误和任务预览入库；同空间同原件返回已有任务，不同空间独立。
- JSON题目/完整bundle、UTF-8文本、Markdown、HTML及PNG/JPEG。文本/Markdown作为纯文本笔记；HTML只提取文字，不执行脚本、不取远端资源、不推断标准答案。JSON支持共享阅读材料与来源链校验。
- 显式预览确认事务才写正式题目/文章/笔记；冲突整批拒绝，不覆盖标准答案或作答，确认幂等。非AI来源统一imported/unverified；AI保留生成信息但降为unverified，不信任文件自报official/human_verified。
- 表格使用原生组件，PNG/JPEG经私有API取字节；来源、AI和验证状态可读；参考答案和解析折叠。大批bundle逐条分页预览，历史和资料库支持继续加载。
- Alembic 0003新增resources/import_jobs/passages/notes；升级前备份目标动态取head，保留旧作答。旧0001及0002升级、故障回滚、重启不重复备份均有回归。

可用自编样例为[import-bundle-v1.json](../contracts/import-bundle-v1.json)，包含数学公式/表格和共享阅读材料；均非真题、未验证。导入后目前在资料库预览；完整学习作答入口及七类题评分属M3。

## 接口与边界

所有接口沿用Bearer鉴权、Origin拒绝和空间隔离；归档空间不可操作，没有服务器文件路径参数或网络抓取。

| 方法 | /api/workspaces/{workspace} 后的路径 | 行为 |
|---|---|---|
| POST | /imports?filename=... | application/octet-stream原字节；返回任务、preview和duplicate |
| GET | /imports | limit默认50、最大100，offset分页；不含整份预览 |
| GET | /imports/{job} | 任务与预览 |
| POST | /imports/{job}/confirm | 显式确认；重复调用不重复写入 |
| GET | /resources/{resource} | 鉴权取原字节，校验归属、路径、大小和SHA256 |
| GET | /questions | 题目摘要；limit默认50、最大100、offset分页 |
| GET | /questions/{question} | 题目及参考答案，用于学习预览，不是保密考试API |
| GET | /passages/{passage} | 共享阅读材料 |
| GET | /notes | 已确认笔记；limit默认50、最大100、offset分页 |

上传HTTP 200不表示解析/入库成功，必须检查status=preview/failed/confirmed。格式或协议失败仍保留原件与错误，失败任务确认返回409；404表示未知/跨空间/归档，413超限，422空文件或非法文件名，原件损坏/ID冲突409。

ASGI中间件逐帧累计实际字节，导入8 MiB、布局2 MiB、其他64 KiB；省略Content-Length也执行，超限不写原件。笔记最多20万字符，协议保留原有块/表格限制。附件仅接受同空间PNG/JPEG、纯文本和JSON，未知格式原件不可成为正式题目引用。图片头部声明尺寸最大8192×8192且不超过1600万像素；实际解码失败有替代文本，头部检查不等于完整图片格式认证。资源返回attachment、nosniff、no-store和sandbox，不传令牌到URL/网页，不以任意本地路径读取。

不增加第三方依赖，复用Python标准库与既有技术栈。Word/PDF解析器与Docling/MarkItDown尚未选型，不宣称已做真实样本比较。

## 实际命令与证据

在仓库根目录执行Python命令。为避开沙箱临时目录编码问题，进程内设置PYTHONUTF8=1、TEMP/TMP为仓库.local/tmp。每次pytest使用新的--basetemp，不清除历史失败。Flutter命令在apps/desktop执行，进程内TEMP/TMP同上；Windows编译PATH增加.local/bin并设置NUGET_SCRATCH=.local/nuget-scratch。

| 实际命令 | 退出码/结果 | 证据 |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest backend/tests -q`（首次） | 1；35通过、46环境/测试设置错误 | 临时目录编码失败；大参数测试名超过Windows环境变量32767字符，见下文 |
| `.venv/Scripts/python.exe -m pytest backend/tests/test_imports.py -x -q --basetemp=.local/m2-import-tests-01` | 1；4通过、2设置/清理错误 | evidence/m2-20261024/import-tests-01.log |
| `.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m2-final312-06 --tb=short --junitxml=docs/evidence/m2-20261024/backend-06.xml` | 0；84通过，Python3.12.7 | backend-06.log/xml |
| `.local/release-venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=.local/m2-final313-05 --tb=short --junitxml=docs/evidence/m2-20261024/backend-05.xml` | 0；83通过，Python3.13.17；其后增加的自编样例测试见上行 | backend-05.log/xml |
| `.venv/Scripts/python.exe -m ruff check backend tools` | 0 | ruff-final.log；开发时修正过1项导入排序 |
| `dart format --output=none --set-exit-if-changed lib test integration_test`（使用SDK内dart.exe） | 0；23文件、0更改 | format-final.log |
| `flutter analyze --no-pub` | 0；No issues found | analyze-final.log；此前代码风格提示保留analyze-02.log |
| `flutter test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/m2-pipe-tests` | 0；25通过，含真实后端管道 | flutter-tests-04.log |
| `flutter build windows --release --no-pub` | 0；最终增量构建74.9秒 | windows-build-01/02.log；插件CMP0175警告保留 |
| `packaging/windows/build-backend.ps1` | 0；独立CPython3.13.17冻结 | frozen-build-02.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py` | 0 | source-lifecycle-01.log |
| `.local/release-venv/Scripts/python.exe tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe` | 0；全部断言通过 | frozen-lifecycle-02.log；受限PATH、无开发Python，原件/笔记、EOF、崩溃及两次迁移 |

证据位于[本批目录](evidence/m2-20261024)。首次终端未重定向的环境错误保留上述命令/退出码和原因；保存的失败日志对环境变量整体脱敏，并压缩200001字符测试值的重复展示，保留异常和失败结果。没有删除失败测试或降低断言；参数仅增加短ID以兼容Windows。pytest仍有Starlette/AnyIO弃用警告，不将警告隐藏。

组件首次2项失败是确认对话框打开后仍处于加载动画，pumpAndSettle超时；已把等待确认和HTTP请求状态分开，失败日志flutter-tests-01.log保留，定向5项和最终25项通过。自查另修正图片资源切换时重取字节、未知附件MIME限制，并补实际ASGI多帧边界测试、并发去重/确认和0002升级备份测试。未使用子Agent。

## 限制与下一步

原件写入与SQLite提交不是跨介质原子事务：中途进程崩溃可能留下未被任务引用的原件；不会自动删除，后续实现恢复巡检。当前去重依据原件SHA256，不做语义重复合并；失败后修正文件，以新原件重新导入，同字节不自动重解析。

继续M2-03附件导出/管理，M2-04真实Word/PDF样本与解析器比较、手动题/笔记编辑、链接/视频导入衔接；M2-05完整Dart Schema、旧任务恢复、大文件和全格式回归。M3–M5尚未完成，不标为实现或验收成功。

本批没有启动产品窗口、没有执行用户人工验收、安装/卸载或干净机验证；原生文件选择与实际图片交互仍待统一验收。检出目录为D:/computer_work/project/StudyWorkbench，分支codex/m1-workspaces-tabs。未提交、推送、发布或合并，保留全部原有改动。dist下既有M1预览/安装包未更新为M2；Windows编译与冻结后端是本地验证产物，不冒充完整可分发安装包。git diff --check退出0，见diff-check.log。
