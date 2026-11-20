# REL-05a 后端安装来源元数据

在 [#97](https://github.com/surface-user/StudyWorkbench/pull/97) 的本机测试构建中，逐文件清点发现 pip 的 direct_url.json 记录了安装 wheel 的本地位置。该构建仅作验证，保留原始文件作反例。本报告只记录元数据类型，省略本机位置。该元数据并非 OpenTelemetry 功能或公告所致。

冻结后端检查和最终 Windows 暂存检查共用同一规则。对后端 Python 发行元数据中本机文件 URL、裸路径、损坏及超出 64 KiB 的来源记录拒绝打包，报错省略来源内容。普通 HTTPS 来源记录仍可保留。其他独立组件按其发行规则核验。

用同一份已核摘要的官方 wheel 在独立环境中按包名离线安装，再从项目源码重建。真实旧开发包被新门禁拒绝，退出 1。新包中 direct_url.json 数量为 0，48 个业务模块通过源码比对，28 个 OpenTelemetry 内嵌模块及 4 份元数据仍与官方 1.45.2 wheel 相符。新后端 SHA256 为 `5fa6da04bcabcd1b6cd7fd8639a04ccba29e5f77254eebab08238e3fed960d7d`。

```shell
python -m pip install --no-index --no-deps --find-links <已核wheel目录> opentelemetry-api==1.45.2
./packaging/windows/build-backend.ps1 -Python <新环境Python路径>
python tools/check_frozen_sources.py --exe <后端exe>
python dev/records/2026-11-20-opentelemetry-update/verify_wheel.py --exe <新后端exe> --wheel <官方wheel>
python -m pytest -q backend/tests/test_release_inventory.py backend/tests/test_frozen_sbom.py
```

Python 3.12 和 3.13 的最终相关回归各 115 项通过，退出 0。首轮长测试名称使一个夹具路径超过上限，另两项在创建目录链接时失败；保留首轮输出，缩短测试名称后在可创建临时链接的环境完整重跑，断言保持。Ruff 通过。此次仅验证后端安装来源记录，未对任意其他文件宣称无个人信息。独立审查和人工测试按本轮安排跳过，未合并或发行。
