# 知识点题数、掌握数与错题数

题目协议允许一个知识点在同一题内出现多次。原统计按标签出现次数累加，导致一题贡献多个题数、掌握数或错题数。现在按「科目、知识点、题目」计数，题目原文、标签顺序和作答历史保留。

## 自动验证

`python -m pytest backend/tests/test_learning.py backend/tests/test_learning_records.py backend/tests/test_question_protocol.py backend/tests/test_question_files.py -q` 在两个受支持的 Python 版本各通过 82 项，退出 0。新增用例通过普通导入和作答接口检查重复标签、同名跨科目标签及独立知识点。修复前同一用例退出 1，记录保留。Ruff 通过。

用旧 Windows 后端导入两道各带两次相同标签的题，一道答错，另一道连续答对三次，统计返回题数 4、掌握数 2、错题数 2。用 `packaging/windows/build-backend.ps1` 重建后端，48 个业务模块核源通过。对同一测试数据库启动新后端并再重启一次，两次均通过 HTTP 得到题数 2、掌握数 1、错题数 1，四次作答与题目原有标签均完整。该修复只涉及统计读取。知识点自定义分类、关系编辑和复习评价仍由后续任务处理。
