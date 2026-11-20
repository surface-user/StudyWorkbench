# REL-02e 后端许可暂存组合

基于 [#102](https://github.com/surface-user/StudyWorkbench/pull/102) 的 `265a12b3283348b18f0d91c86390ba87cf42b587`，合入 [#99](https://github.com/surface-user/StudyWorkbench/pull/99) 已验证的三 DLL 许可复制和独立复核。保留 #98 对安装来源元数据的检查，以及 #102 的 Python 许可收集器。新增共同启用两项保护的回归；固定 profile、两份原文和字节属性从 #99 原样采用，不重做原生来源判断。当前为待交付，需本项独立草稿 PR、当前提交 CI 和主 Agent 核验。代码审查暂缓，人工测试取消，未合并或发行。

## 实物范围

使用 #98 的实际 970 文件后端，exe SHA256 为 `5fa6da04bcabcd1b6cd7fd8639a04ccba29e5f77254eebab08238e3fed960d7d`。逐文件对照现有文件级 SBOM，并核新包自身指纹；不要求它与 #88 的旧整包指纹相同。三个原生 DLL 与固定 profile 逐字节一致。

在本任务独立目录复制完整后端，直接采用 #102 已生成的 249595 字节许可 ZIP，未重新收集或压缩。核 ZIP 完整性、55 个版本、134 条文本引用的实际大小和 SHA256、121 份去重原文及完整成员集合，并确认索引绑定同一后端。ZIP SHA256 保持 `00b225d135bcb4d9ab3990281a45cad42f4477e0e209fd99c97f8268940b1166`。

实际调用组合后的收集器，生成包含 1169 个文件的暂存清单，其中有两份原生许可原文及既有 Python 许可 ZIP。两次调用的清单和文件内容完全相同，两份原生许可的修改时间不变。清单 SHA256 为 `9f6d3f9eaab0f1670402d542e4d6e4a2de25d7118f6c6b95c59e9cc867e8eed3`。原后端、原 SBOM、ZIP 和三份固定来源资产的摘要前后保持。另在本任务副本构造缺少 DLL、改变 DLL 和本机安装路径三个反例，均拒绝且保留已有字节和清单。

普通 stage 检查退出 0：1169 个文件摘要、CPython、无数据库和 161 个实际 PE 的静态加载域均通过。此为后端组件暂存；没有桌面二进制，Flutter 元数据仅为自编空夹具。清单中的 74 个构建环境发行包不等于包内实际成员，真实 Python 成员依据仍为许可索引的 55 个版本。没有重新构建后端或运行其应用入口。

原件与副本的 Windows 签名状态均为 NotSigned，exe 摘要相同。另调用 #85 原验签入口，使用实际 exe 摘要和未采用的全零证书摘要，退出 1，明确因 NotSigned 拒绝；未签署文件、选择证书或降低验签要求。

## 自动化

工作目录为本任务独立源码副本；Q 为现有干净构建环境 Python 3.13.17，P 为已有修复依赖环境 Python 3.12.7，环境只读使用。临时目录只属于本项。

```shell
Q/P -X utf8 -m pytest backend/tests/test_release_inventory.py backend/tests/test_native_dependencies.py backend/tests/test_frozen_sbom.py backend/tests/test_frozen_member_licenses.py backend/tests/test_source_licenses.py backend/tests/test_frozen_python_members.py -q --basetemp=artifacts/rel02e/tq01-or-tp01 --junitxml=artifacts/rel02e/q01-or-p01.xml
Q -X utf8 artifacts/rel02e/probe_real.py
Q -X utf8 artifacts/rel02e/probe_real.py --read-only
Q -X utf8 tools/check_release.py .local/rel02e-real01/complete
release-python -X utf8 -m ruff check backend tools
Q -X utf8 tools/export_question_schema.py --check
```

两版各 297 项通过，Q 18.29 秒、P 16.94 秒，均退出 0。真实暂存探针、普通 stage 门禁、Ruff 和 Schema 漂移检查退出 0。首次辅助合并在缺少固定资产时停止，随后补入既有公开原件；第一次测试命令因日志父目录不存在未启动，Ruff 两次环境定位失败，修正后完整执行，原输出保留，不作为测试通过。原始日志、XML、只读复核入口、实物副本和完整清单仅存忽略目录，不随本报告上传。

许可文本和字节对应不代表最终分发义务审核完成。latex2mathml 的来源/修改条件、原生库附带条件、44 个历史 CRT 的上游身份/许可、OpenSSL 3.5.9 的八条上游版本命中、真实签署及完整产品发行继续保留。此次未重新扫描漏洞、未生成安装器，也不认证整套桌面/Office、全部 SBOM 或 AOT 来源。
