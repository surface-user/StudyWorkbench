# LW-03 内部超链接

2026-11-04，用户授权沿路线继续开发直到额度结束。遵循AGENTS、现行需求/架构/富内容协议/task及LW-00契约；沿用ponytail最小完整实现，无子Agent、新依赖或技术栈变化。本批仅本地，不要求提交/新PR，不推送/合并/发行；人工与阶段统一待验。

## 设计与拆分

1. 严格解析v1 URI，保留default及旧合法ID，单次解码后拒绝路径、控制字符、百分号残留、空段与多余参数；所有请求只发固定受鉴权resolve API，跨空间统一404，不自动切换空间。
2. nodes/marks/legacy notes复用现有业务数据，不迁移表。节点首页与书签位置分开；标记/来源墓碑及内容变化显示原因，不复活、不按同名/hash猜目标。响应不返回磁盘路径、令牌或媒体capability。
3. 原生UI复制资源/书签/旧笔记链接；MD编辑显式插入经过校验的链接，MD预览点击才解析。不放宽旧富内容块协议；外部HTTPS只在隔离WebView中打开，危险scheme拒绝。
4. 每空间运行时往返最多50条，仅存URI及受限视图位置，不存正文/令牌；返回也重新resolve，失败不吞掉历史、不清草稿。关闭/重启不承诺恢复该临时栈。
5. 后端非法URI/隔离/墓碑/版本/重启及Flutter复制/插入/点击/往返/失败测试，静态、全套回归、Windows构建、自审，更新所属规范和任务状态。完整原始产物保留artifacts/lw03-20261104/。

设计时尚未验证；以下追加本批实施和验证，不将自动化通过写成人工/阶段验收。


## 实施、自审与边界

基于既有未提交工作树继续，HEAD仍为29f23d3558740545a950a51ca04398f9420088fd，结果属于本地修改。无schema迁移，沿用0014。新增internal_links.py、原生InternalLinkHost/Scope及输入框；资源、书签、旧笔记可复制稳定链接，MD工作副本插入经过校验且转义标签的链接，预览只在用户点击时跟随。外部HTTPS复用隔离WebView，不增加业务桥或令牌暴露。源文件与旧题目/富内容块协议不改。

自审修正精确mark URI往返，避免前进退化资源首页；返回视图只保存hash/页/缩放/滚动/行/选择及预览标识，不存正文、草稿或能力。文档二次核对字节，Office额外核对原派生版；脏目标拒绝覆盖，失败不弹出历史。临时回调/视图不进入layout JSON，节点普通打开清理旧待应用视图。输入失败留原值，未知/移除/失效不按同名猜目标。未创建子Agent，属于开发自审，非独立批准。

## 命令与结果

工作目录为仓库根，Flutter命令在apps/desktop。P=.venv/Scripts/python.exe；D=D:/computer_work/Tools_work/flutter/bin/cache/dart-sdk/bin/dart.exe；F=D:/computer_work/Tools_work/flutter/bin/cache/flutter_tools.snapshot。Flutter入口D F --suppress-analytics，未升级SDK/依赖。设置FLUTTER_SUPPRESS_ANALYTICS/DART_SUPPRESS_ANALYTICS=true；TEMP/TMP指仓库.local/tmp，NUGET_SCRATCH指.local/nuget-scratch。SDK缓存及Windows junction回归用获准扩展权限，隔离测试库，不操作个人库。

| 实际命令 | 退出码及结果 | artifacts/lw03-20261104/产物 |
|---|---|---|
| P -m ruff check backend tools | 0，通过 | ruff-03.log、backend-exit-03.json |
| P -m pytest backend/tests -q --basetemp=.local/lw03-full-03 --junitxml=artifacts/lw03-20261104/backend-full-03.xml | 0，269通过，158.15秒 | backend-full-03.log/xml |
| D F --suppress-analytics test --no-pub test/internal_links_test.dart --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw03-flutter-04 | 0，9通过 | flutter-links-04.log |
| D F --suppress-analytics test --no-pub --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/lw03-flutter-final-05 | 0，121通过 | flutter-full-05.log |
| D F --suppress-analytics build windows --release --no-pub | 0，45.6秒 | windows-release-05.log |
| D fix --apply --code=curly_braces_in_flow_control_structures lib/document_page.dart；同命令针对test/internal_links_test.dart；D format lib/document_page.dart test/internal_links_test.dart | 各0，仅补花括号/格式，业务行为未变 | fix-document-06.log、fix-test-06.log、format-06.log |
| D F --suppress-analytics analyze --no-pub | 0，No issues found | analyze-06.log |

后端新增30项覆盖不可信URI/单次解码/旧ID、版本变化、改名/移除/重启、跨空间/归档、未知目标、请求预算/字段及令牌/Origin校验。Flutter9项覆盖解析、50条上限、规范剪贴板内容、失败输入、精确书签往返/失败记录保留、脏目标、显式点击、版本匹配的原文视图恢复和插入后普通草稿。静态分析末次只补花括号，未重复无行为变化的整套测试/构建。

中间失败保留：links-01为29通过/1失败，重命名测试漏传现行接口要求的parent_id，补正确请求后links-02为30通过；flutter-links-03为5通过/2失败，一处URI解码抛ArgumentError已规范成FormatException，另一处测试将RawTooltip误读为IconButton，改按真实IconButton查找，保留断言。analyze-01/02/05有花括号info；fix-03/04因多路径不被dart fix支持未执行，改为单文件调用后分析通过。不删失败日志或放宽断言。Python保留Starlette/anyio弃用警告，构建保留CMake CMP0175开发警告。

## 人工、交付与后续

本地实现、自动化及自审完成，任务保持待验收。未执行真实窗口/剪贴板/中文IME/DPI、实际WebView导航/解码、用户人工/阶段、安装/干净机；源码/组件通过不替代。没有更新冻结后端或安装发行组合；未提交/推送/PR/合并/发布，远程head/CI未知，旧义务保留。往返栈只在当前空间窗口运行时有效，重启不恢复；原标签按既有布局保存。旧富内容笔记没有内联链接块，仅可复制自身稳定链接。

下一项LW-04集中查找；仍无完整整库恢复，LW-05/09门槛不取消。每任务唯一报告与task状态继续维护，不把流水账散放规范。


文档收尾：`P artifacts/lw03-20261104/check_docs.py`退出0，45份Markdown、220处本地链接/7处标题锚点通过，114份受保护历史文件SHA256不变；`git diff --check`、`git check-ignore artifacts/lw03-20261104/docs-checks.json`各0。结果在同目录docs-checks.json，完整日志保持Git忽略，未晋升整包证据。
