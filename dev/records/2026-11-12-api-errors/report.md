# API-01a 兼容错误响应

2026-11-12，父任务API-01首切片。基于#29最终9027508bdbc78316b546c8000cc06267c51f3149，独立目录.local/goal-20261112/api-errors；按Git树逐blob验证复制444文件，根工作区、txt-search与其他Agent目录不改。主Agent已核#29最终CI43066543568三job/44步成功及本地双Python58/Flutter200，授权LW-04a登记DONE；本项领取IN_PROGRESS。

## 设计和范围

现有入口为FastAPI默认HTTPException/校验、Origin JSON、RequestLimits实际帧413，以及TrustedHost纯文本400。Dart Backend.request只读字符串detail并截240字符；两个业务调用方仅依赖statusCode，上传/附件各有固定HttpException提示。没有逐字节依赖校验detail的调用方。

新增API错误响应工厂/处理器及固定状态级code/message，顶层detail保留字符串/列表形状；不逐条替换业务异常或幂等行为。error.request_id为服务端每次API HTTP请求独立生成32位小写hex，不采纳传入头/正文，也不等同业务重放编号；响应头X-Request-ID一致。HTTPException原安全业务detail字符串保留，新error.message固定，不拼路径、URL或异常文本。422列表仅返回安全来源/数字下标/field占位和固定信息，去input/ctx/任意字段值；最多100项摘要，不承诺还原全部校验细节。

Host适配沿现有只准127.0.0.1及中间件顺序，API Origin/实际帧预算统一；非API媒体/Range/成功体不换包装。未预期异常在未开始响应时生成固定500并仅记录关联ID，已开始的流异常不另发JSON；不吞取消。Dart BackendError保留构造和statusCode，新增可选code/requestId；优先保留原字符串detail的用户提示，422使用固定error.message，旧JSON/非JSON兼容回退，不暴露原响应/traceback。

修改边界为api_errors.py、app.py、request_limits.py、backend.dart，相关后端/桌面测试、冻结HTTP探针和CI接入、API/学习契约/架构、task/dev索引及本报告；无新依赖/迁移/自动重试/业务错误码全集。父API-01继续开放，原模型/授权/学习记录行为不扩展。

## 验证安排和过程

Q=根.local/release-venv/Scripts/python.exe（3.13.17），P=根.venv/Scripts/python.exe（3.12），D/F沿锁定Flutter SDK。所有原始日志/JUnit/构造资料置本目录artifacts/api01a及.local，不进Git。先专项红绿验证、双Python相关回归、桌面全量/静态，再实际冻结HTTP与最终head CI；代码审查依ADR0014暂缓，人工依ADR0013取消，未授权合并/发布/清理。

初次复制清单脚本未指定编码，在Windows默认GBK读取UTF-8清单时退出1，未复制任何源码；随后显式encoding=utf-8/-X utf8重跑退出0，444文件全部Git blob一致。前一轮随后的文档读取因复制未执行失败，未计作已读；成功复制后重新读取。

### 实施和已执行检查

先加11项参数化契约用例（初版10项，后补已开始流异常），覆盖不可信来路编号、Host/Origin、422值/未知键/上下文、非法JSON/查询/百项摘要、无Content-Length实际帧预算、429并发门禁、空间/幂等、异常头、未预期500和非API兼容。业务实现集中在api_errors/app/request_limits，不全局改写业务异常。Dart共用解析覆盖JSON请求、原件导入、媒体上传、附件读取，旧错误提示及原文件保留/刷新核实文字继续；新增3项测试，另回归两个原状态码调用方。

- `Q -m pytest backend/tests/test_api_errors.py -q --basetemp=.local/api01a-red01 --junitxml=artifacts/api01a/backend-red01.xml`：退出1，10项先红，证实现有响应缺error/未预期异常透出；不删除失败。
- 接入后`Q -m pytest backend/tests/test_api_errors.py backend/tests/test_api.py -q --basetemp=.local/api01a-green01 --junitxml=artifacts/api01a/backend-green01.xml`：退出1，14通过/1失败。夹具误把未定义GET /api/workspaces当列表；改用现行GET /api/workbench核只有一个空间，未改业务代码或弱化无写入断言。
- 补已开始流故障用例后，同专项改basetemp=.local/api01a-green02及backend-green02.xml：pytest退出0，16通过，5.96秒；同命令后续Ruff退出1，仅新测试import排序。对该文件`Q -m ruff check --fix backend/tests/test_api_errors.py`退出0；随后`Q -m ruff check backend tools`退出0。
- 新目录复制锁定依赖的package_config/package_graph；默认权限建立.venv junction被拒且未创建链接，获扩展权限后只建立本目录链接到既有Q环境成功，不修改依赖/SDK。D format两个修改Dart退出0。
- `D F --no-version-check test --no-pub test/backend_error_test.dart test/agent_access_dialog_test.dart test/learning_record_dialog_test.dart`：退出0，8通过，11秒，flutter-target01.txt。
- `D F --no-version-check analyze --no-pub`：退出0，No issues found，131.5秒，analyze01.txt。`D format --output=none --set-exit-if-changed apps/desktop/lib apps/desktop/test apps/desktop/integration_test`：退出0，88文件无变化。
- `Q tools/check_api_errors.py --test-root .local/api01a-http01`：退出0，真实源码HTTP34检查、18独立错误ID，跨重启收据/原文件/非API媒体206/416保持。探针只输出计数/布尔，不输出会话令牌或原响应。
- `$env:PYINSTALLER_CONFIG_DIR=<本目录>/.local/pyinstaller-cache; ./packaging/windows/build-backend.ps1 -Python <Q>`：退出0，111.5秒PyInstaller构建及44模块逐字节码核源通过，freeze01.txt；首次独立构建，不覆盖其他任务包。
- `Q tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/api01a-frozen01`：退出0，同34检查/18错误ID及重启/收据/Range通过，frozen-http01.txt。子进程PATH仅System32、清除PYTHONPATH/PYTHONHOME、cwd为独立构造目录；非真实窗口/安装验收。该探针已加入CI冻结阶段。

### 全量失败及兼容调整

`Q -m pytest backend/tests -q --basetemp=.local/api01a-full31301 --junitxml=artifacts/api01a/backend-full31301.xml`退出1：710通过、16失败、77子测试通过，481.07秒。12项日志明确为构造夹具mklink/hardlink的WinError5/拒绝访问；另4项是保存finalize、资料移除原子回滚、题目持久化assets_only/markdown_written原测试期待TestClient直接抛原异常，与新的安全500响应契约不兼容，不能归为环境失败。

后4项仅把错误边界断言改为500/internal_error/固定detail且注入文本不回显；原旧字节/恢复收据/回滚/孤立候选不登记/重启保护断言全保留。保存/移除两项源码改动发生于首轮运行完成前，该轮pytest已载入原函数；旧报告可能显示新行文本但实际失败仍为DID NOT RAISE，不将其计作新版断言失败。用扩展权限与全新api01a-full31302夹具重跑所有后端，结果后补。

新Starlette版本独立修复由REL-03c处理，本分支依赖锁未改变。现有Host适配维持原位置/只准127.0.0.1/端口剥离规则，Origin仍最外层，取ASGI scope.path避免构造包含Host的URL；这不构成对公开公告的修复结论。合并不同切片时须在新固定Starlette下重新验证API边界。

- `D F --no-version-check test --no-pub --concurrency=1 --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/api-errors --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/api-errors/.local/flutter-full01`：退出0，完整203通过、无skip，1分45秒，flutter-full01.txt；PYTHONPATH为本切片backend。仅串行测试文件，不改变断言/超时或跳过真实后端用例。

### 本地结果和交付边界

- `Q -m pytest backend/tests -q --basetemp=.local/api01a-full31302 --junitxml=artifacts/api01a/backend-full31302.xml`：退出0，726通过、77子测试通过，361.26秒，无skip；backend-full31302.txt/xml。具备隔离夹具链接权限后12项原环境失败恢复，4项新500契约及旧数据保护完整通过，原失败仍保留。
- `P -m pytest backend/tests/test_api_errors.py backend/tests/test_api.py backend/tests/test_document_files.py backend/tests/test_resource_removal.py backend/tests/test_markdown_questions.py backend/tests/test_workspaces.py backend/tests/test_agent_access.py backend/tests/test_analysis_review.py backend/tests/test_media_library.py backend/tests/test_learning_records.py backend/tests/test_media_downloads.py -q --basetemp=.local/api01a-target31201 --junitxml=artifacts/api01a/backend-target31201.xml`：退出0，76通过，69.86秒；backend-target31201.txt/xml。Python3.12本机为相关回归，其全量由当前head CI另核，不与Q全量混称双版本全量。
- 17份交付文件逐项`git -c core.safecrlf=false diff --no-index --check <基线文件或空文件> <当前文件>`无诊断；单项退出1表示确有差异，聚合校验退出0。12份既有文件修改均在清单内，其余5份新增；6份Markdown共137处本地链接目标存在，校验退出0。测试资料、日志、清单和包不进Git。

API-01a实现、本地相关自动化、实际冻结HTTP和文档完成，任务转REVIEW，独立草稿PR/最终head CI待交付核实；主Agent核验后才可登记DONE。API-01父项仍进行中，详细业务错误码、跨版本演进和REL-03c新Starlette组合回归不在本切片冒称完成。审查暂缓、人工取消，未合并/发行/清理数据。
