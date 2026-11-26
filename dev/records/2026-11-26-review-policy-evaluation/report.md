# M3-03c1 复习策略离线评价契约

记录了[历史回放契约](../../../docs/learning-workbench-contracts.md#review-policy-evaluation)，按作答提交前可见的记录生成预测，并在报告截止时读取目标作答的实际评分。契约约定比较基线、分母、版本分组以及无法判定的记录。

在隔离数据库中通过普通接口提交三份自编主观题作答。将作答时间设在 1 月上旬，三条满分批改设在 1 月 20 日。1 月 10 日能够使用的批改数为 0。正常学习列表在后来收到三条批改后，按当前资料重建为连续三次满分，即使调用时固定了到期比较时间。合成用例确认了历史评价必须另行限定成绩的可见时间，检查退出 0。

`python -m pytest -q backend/tests/test_learning.py backend/tests/test_learning_records.py` 在 Python 3.12、3.13 各通过 18 项，退出 0。此次交付评价契约。离线回放及其指标输出仍待实现。
