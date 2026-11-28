# B 站双轨确认下载与合成

同一预览显式选择 H.264 视频轨与 AAC 音频轨后，`confirm-pair` 再次核对作品、开放下载许可、轨道声明与资源身份。元数据重取、跳转与两轨共享请求、字节及时间限额。临时地址只交给取流进程。合成进程读取本次收到并核验过的本地文件，以固定组件生成一个 MP4。第二轨失败会保留已验收的首轨。重新获取媒体须新预览和确认，已提交的确认可在恢复个人库后重放。

## 自动化验证

Windows 上的 Python 3.12.7 和 3.13.17 各通过 555 项媒体、站点、备份和完整性用例，退出码均为 0。包括尺寸未知时按实际流量扣减共用额度、首轨跳转耗尽请求数、第二轨拒绝、预览过期、来源或许可变化、输出未发布、幂等重放与恢复。扩大回归首次为 552 通过、1 失败，历史备份负例仍把本次合法的 0023 当未知版本。依赖分支已修正该用例并保留拒绝未知版本的断言。两环境仍报告 Starlette 弃用提醒。

```powershell
$cases = (Get-ChildItem backend/tests -Filter 'test_*.py' -File |
    Where-Object { $_.Name -match '^test_(media_|site_|bilibili|backup_|library_integrity)' }).FullName
python -m pytest -q @cases --basetemp $testDirectory --junitxml $junit --tb=short
ruff check backend tools
git diff --check
```

固定自制分片输入为 1598 字节视频和 1052 字节音频。测试替换站点元数据和 HTTPS 响应体，实际执行取流逻辑、来源及文件校验、数据库事务与原生 FFmpeg 合成。源码和替换为冻结版原生工作进程的两次运行都输出 2173 字节的 H.264/AAC MP4，SHA-256 为 `d62f2c8b02e7eec8603bb2c2d2ae13928127ef23ea917d99c3f4ca4f20801731`。整库备份恢复后，同一确认返回原任务，成品哈希一致，数据库中未发现测试签名串。另向冻结版取流进程传入已用尽的请求额度，进程在写入轨道或请求媒体前拒绝。构建核对了 61 个冻结应用模块。以下命令均退出 0。

```powershell
./packaging/windows/build-backend.ps1 -Python $releasePython
python tools/check_frozen_sources.py --exe dist/study_backend/study_backend.exe
python tools/check_site_pair_mux.py --runtime $runtime --fragment-tracks $video $audio --test-root $newSourceDirectory
python tools/check_site_pair_mux.py --runtime $runtime --fragment-tracks $video $audio --test-root $newPackagedDirectory --mux-exe dist/study_backend/study_backend.exe
```

自制媒体、数据库、原始证据和完整清单留在项目忽略目录。公网 B 站样本仍需在允许普通访问的环境获得成功下载证据。抖音、爱奇艺与其他格式的能力单独跟踪。
