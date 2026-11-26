# B 站站点预览与单文件确认

## 后端集成基线

从草稿 PR #118 移入普通视频预览、固定工作进程、许可和测试，用于带 0021 数据结构的后端。工作区仅在用户提供链接并确认有权获取后创建临时预览。现有身份核对、网络限制、到期和取消行为继续生效。此基线提供预览；单文件下载确认另行交付。

运行 `python -m pytest -q backend/tests/test_bilibili_preview.py backend/tests/test_media_site_previews.py backend/tests/test_bilibili_probe.py backend/tests/test_media_downloads.py`，124 项通过，退出码 0。有两条现有测试框架弃用提示。此组使用受控输入，没有验证真实站点传输。
