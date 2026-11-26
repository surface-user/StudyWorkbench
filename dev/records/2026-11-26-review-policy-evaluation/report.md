# M3-03c1 复习策略离线评价契约

记录了[历史回放契约](../../../docs/learning-workbench-contracts.md#review-policy-evaluation)，按作答提交前可见的记录生成预测，并在报告截止时读取目标作答的实际评分。契约约定比较基线、分母、版本分组以及无法判定的记录。

在隔离数据库中通过普通接口提交三份自编主观题作答。将作答时间设在 1 月上旬，三条满分批改设在 1 月 20 日。1 月 10 日能够使用的批改数为 0。正常学习列表在后来收到三条批改后，按当前资料重建为连续三次满分，即使调用时固定了到期比较时间。合成用例确认了历史评价必须另行限定成绩的可见时间，检查退出 0。

`python -m pytest -q backend/tests/test_learning.py backend/tests/test_learning_records.py` 在 Python 3.12、3.13 各通过 18 项，退出 0。此次交付评价契约。离线回放及其指标输出仍待实现。

## M3-03c2 本机只读回放

运行 `python tools/evaluate_review_policy.py --database <本机数据库> --workspace <学习空间> --cutoff <含时区的截止时间>`，可比较连续三次满分和上一次满分两种预测。工具在同一只读事务中按提交前可见的成绩生成预测，按截止时可见的批改确定目标成绩。输出包含共同分母、排除原因、版本分组与预测计数。输出仅有汇总数据。

`python -m pytest -q backend/tests/test_learning.py backend/tests/test_learning_records.py backend/tests/test_review_policy_replay.py` 在 Python 3.12.7、3.13.17 各通过 24 项，退出 0。覆盖普通业务接口写入的数据库、旧版未分学习空间的数据、跨空间隔离、迟到和同时发生的批改、后续改分、缺失时间以及无法评分的记录。对同一测试库运行两次命令，汇总输出一致，库文件摘要保持一致。Ruff 检查退出 0。使用合成记录验证计算规则，实际学习效果仍待评价。
