# M3-03a 后端文本与公式作答

计算、证明、主观和主观阅读题可以把文字与公式按解题顺序提交。提交入口复用已有内容块和数学命令校验，在检查请求是否重复之前验证输入。保留原始 JSON 以便历史回读。书面作答先进入待批改，既有选择和填空规则、已确认题目与评分修订沿用原流程。没有新增依赖或数据库迁移。

## 自动化验证

在 Python 3.12、3.13 各运行一次，均为 52 项通过，退出码 0。两次测试各自使用新的临时库。

```shell
python -m pytest -q backend/tests/test_written_blocks.py backend/tests/test_learning.py backend/tests/test_question_files.py
ruff check backend/study_workbench/app.py backend/study_workbench/learning.py backend/tests/test_written_blocks.py
python tools/export_question_schema.py --check
```

新检查覆盖七类题、阅读题按作答类型分派、缺答案、旧纯文本及新公式块、重复请求和顺序冲突、越界输入、禁止的公式命令和附件引用。一个完整还原用例确认主观阅读题后追加混合作答和评分，备份至新位置并重新打开，核对原作答、评分修订、原确认版和幂等收据。首次静态检查指出导入布局，调整后复查通过。题目 Schema 检查退出码 0。

当前切片覆盖后端接口。旧版桌面编辑器仍提交纯文本，其历史页遇到新格式会显示已有提示。后续分别处理桌面输入展示，以及作答专属附件的明确授权、不可变字节和整库还原。按本轮安排跳过独立审查与人工测试；远端自动检查以 PR 当前提交为准。
