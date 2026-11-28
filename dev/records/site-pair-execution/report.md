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

## 2026-11-28 含重排帧的分轨下载与整库恢复

将 [站点双轨执行](https://github.com/surface-user/StudyWorkbench/pull/148) 与 [显示时间索引修复](https://github.com/surface-user/StudyWorkbench/pull/143) 组合。用普通业务 API 显式选择同一预览的视频及音轨并确认下载。站点页面和两份 HTTPS 响应使用自制数据。队列实际启动了一个读取子进程和一个合成子进程。检查工具只在读取子进程里替换网络响应，复用产品的命令协议、额度、文件写入、媒体探测与合成。

以 imageio-ffmpeg 0.6.0 的 Windows FFmpeg 7.1 开发工具生成素材，其程序 SHA-256 为 `2ce797a0f88d7f067180338fb227f7b1928ea727bd9a4d7a1d022f7c52af71a3`。下列命令可在新目录运行，文件不入库。

```shell
ffmpeg -n -f lavfi -i testsrc2=size=320x180:rate=10 -t 2.4 -c:v libx264 -g 8 -keyint_min 8 -sc_threshold 0 -bf 2 -threads:v 6 -x264-params lookahead-threads=1 -pix_fmt yuv420p -movflags +empty_moov+frag_keyframe+default_base_moof+global_sidx -f mp4 video.m4s
ffmpeg -n -f lavfi -i sine=frequency=600:sample_rate=48000 -t 2.4 -c:a aac -threads:a 1 -movflags +empty_moov+frag_keyframe+default_base_moof+global_sidx -f mp4 audio.m4s
python tools/check_site_pair_mux.py --fragment-tracks video.m4s audio.m4s --runtime <固定组件> --test-root <全新输出目录>
```

- 重新生成的两条轨道与原测试输入的 SHA-256 相同。运行检查工具两次，其中一次以 `--mux-exe <打包后端>` 启动冻结的合成子进程。两次均产生 71,599 字节的 H.264/AAC MP4，整库还原后重放同一确认请求均返回原任务。上述命令与打包均退出 0，61 个冻结模块与当前源代码匹配。
- 对两次还原留下的文件，通过 Windows Media Foundation 解码并分别与输入轨比较。视频为 24 帧、2,211,840 字节，音频为 114 个缓冲区、233,472 字节，逐轨摘要一致。
- 沿用原命令参数，在四个新资料库中分别复跑原有小样本和重排帧样本。源码合成和 Windows 打包合成都验证了原有 2,173 字节与新增 71,599 字节输出的固定摘要、音视频编码及还原后的确认收据，四次均退出 0。
- `python -m pytest -q backend/tests/test_media_fragments.py backend/tests/test_site_pair_download.py backend/tests/test_site_pair_selection.py` 在 3.12.7、3.13.17 各通过 62 项，退出 0。此次组合未请求公网站点，也没有向仓库提交媒体或个人链接。
