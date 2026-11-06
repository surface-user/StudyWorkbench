# LW-09 无Agent学习流程集成验证

2026-11-04，接续用户持续推进到额度结束的授权。采用LW-00课程流程，引用[LW-01](../2026-11-03-lw01-notes/report.md)、[LW-02](../2026-11-04-lw02-marks/report.md)、[LW-03](../2026-11-04-lw03-links/report.md)、[LW-04](../2026-11-04-lw04-search/report.md)、[LW-05](../2026-11-04-lw05-backup/report.md)，不复制各任务流水账。无子Agent；用户人工/阶段统一待验。本批仅本地测试，不提交/推送/PR/合并/发行。

## 范围与步骤

1. 新建artifacts/lw09-20261104下的配套前端/冻结后端候选，独立CPython，不替换已有dist或安装包。先做冻结启动/普通API/备份恢复自动烟测，再用computer-use技能操作唯一识别的隔离测试窗口。
2. 仅用自建PDF、MD/TXT、笔记/备注、可用的自编媒体样本，覆盖阅读→笔记/标记→链接往返/搜索→重启→整库恢复。Office缺组件及媒体编码限制分别记录，不能以元数据样本冒充可播放样本。
3. 窗口操作只通过computer-use的node_repl/@oai/sky公开API；不操作个人库，不创建子Agent，不用旧窗口坐标，不因界面自动化通过补写用户或阶段验收。涉及UI删除需另按技能规则处理，本批不执行UI删除。
4. 原始日志/生成文件/截图均在artifacts或.local隔离目录，Git忽略；共享evidence只筛选必要脱敏证据。记录组件、真实进程、窗口、用户与阶段边界。

当前进行中；尚未取得整条流程窗口通过。额度是账户共享窗口，按只读查询结果继续普通开发，不购买/重置额度。


## 冻结/真实进程与前台边界

新冻结后端使用既有独立CPython3.13.17及PyInstaller，产物仅在artifacts/lw09-20261104/frozen/；原dist/安装包未替换。首轮frozen-build.log退出1，spec目录导致相对add-data解析到错误位置；改绝对资源路径后frozen-build-02.log退出0，82.5秒。无新增运行依赖。

新增tools/check_learning_workbench.py对真实loopback进程串联受管添加、自建2页PDF/MD/TXT、自由笔记、页/行标记、显式关系、内部链接/跨空间拒绝、改名移动、集中搜索、草稿/重启和整库备份恢复，独立SQLite iterdump摘要比对，源文件hash保持；脚本拒绝复用既有test-root，不打印凭据。frozen-flow-03.log退出0（不含媒体），frozen-window-seed-04.log退出0（包含媒体导入），实际编码/窗口播放仍未据此记通过。

既有.local/test-tools/imageio_ffmpeg的FFmpeg7.1（GPL/version3配置，见fixture-ffmpeg-version.log）仅生成自编3秒静音VP8/WebM：testsrc2 320×180、15fps，fixture-ffmpeg.log退出0；不复制工具进包、不引入产品依赖，不代表LW-07组件许可已审完。早期headless Edge备用生成尝试失败，保留media-generation.log，未当作播放证据，最终采用上述FFmpeg样本。

隔离前端编译常量STUDY_DATA_DIR指向仓库.local/lw09-window/data，不读取个人默认位置；恢复后的相邻隔离配置可持久选择，新增用例覆盖整窗重启选择规则。analyze-frontend-03退出0，flutter-full-03为137通过，windows-isolated-03退出0（47.4秒）；这是隔离测试构建，不是默认profile或安装验收。配套window-bundle/hash另存window-bundle-hashes.json，没有覆盖已有发行包。

computer-use按SKILL读取guidance/API/confirmations并初始化@oai/sky。首次启动应用授权超时；再次尝试在有效窗口选择之前被物理Escape停止，随后用户明确正在使用电脑。已停止全部前台/Computer Use操作，不再重试；窗口状态/输入/播放均无通过证据，见window-status.json。后续只做后台开发和自动化，实际窗口择时继续；任务保持进行中，用户人工/阶段不通过。

## 2026-11-05 恢复窗口尝试

用户明确“你可以正常使用了”，撤销上轮占用电脑期间的前台暂停。重新读取当前AGENTS及必读规范、computer-use技能/guidance/API/confirmations；初始化@oai/sky、list_apps未返回StudyWorkbench窗口。使用原window-bundle前逐项核对window-bundle-hashes.json的三个SHA256，均一致；测试库仍限定.local/lw09-window/data，未使用个人库。

第一次sky.launch_app（原隔离包完整exe路径）返回`computer-use request timed out: launch_app`；重新sky.list_windows后匹配窗口0，再试同一路径仍返回相同超时。未选择到有效窗口、未点击/键入，不将helper超时写成产品启动失败或窗口通过。原始调用结果见本聊天工具记录，结构化摘要artifacts/lw09-20261105/window-status.json；保留11-04旧停止记录，不覆盖。停止进一步UI重试，后台继续LW-06回归/构建与XLSX实现。实际阅读/播放、窗口导航/恢复及用户/阶段验收均待完成；不需要用户重复授权，但需Computer Use启动通道恢复或用户自行打开隔离测试包后再识别窗口。

随后对新增JSON/XLSX更新同一tools/check_learning_workbench.py，真实冻结API补缓存值/缺缓存/多表稀疏地址/禁止编辑、重启与恢复后相同内容，媒体仅导入。首轮fixture换行失败及修正、冻结/全套/配套新隔离包的实际命令均继续记录在[LW-06报告](../2026-11-04-lw06-formats/report.md)，不另建一份报告或复制命令表。frozen-flow-02退出0，源文件及SQLite行摘要保持一致，user_acceptance/phase_acceptance/media_playback_window_verified明确false。新window-bundle仍固定原隔离库、未启动；旧11-04配套包与失败均保留。


## 2026-11-05 LW-07配套隔离包窗口尝试

LW-07新冻结进程及前端均构建后，创建独立artifacts/lw07-20261105/window-bundle并记录window-bundle-hashes.json，数据仅.local/lw07-window/data。用户已有“可以正常使用”授权仍有效。sky.list_apps未找到应用；sky.launch_app完整隔离exe路径仍返回computer-use request timed out: launch_app；刷新list_windows匹配0。未点击/键入/截图，实际窗口/播放均无验证，结构化摘要artifacts/lw07-20261105/window-status.json。未改系统设置、未用shell启动绕过Computer Use，也不再重复盲试。LW-07公网源测试的DNS阻断及LW-08无模型候选冻结闭环分别记录各自报告，不能替代本任务实际窗口门禁。


## 2026-11-06 Office修补后的配套窗口复核

沿用用户“可以正常使用”授权，完整重读Computer Use技能/guidance/API/confirmations。新建artifacts/lw06-native-20261106/window-bundle，复用LW-08已构建且逐文件SHA验证的未改动前端，排除两份旧backend目录，仅配入4cd157a对应新冻结后端；1044文件/158602347字节，hash清单另存window-bundle-hashes.json。编译与配置位置确认仍.local/lw08-window-delivery/data，不读取个人默认库。可选Office组件未随此窗口包复制，不能借此声称窗口Office转换已验。

sky.list_apps成功但未返回StudyWorkbench；仅尝试一次新包完整exe路径launch_app，再次返回computer-use request timed out: launch_app；刷新list_windows成功、匹配窗口0。没有选定窗口、没有输入/截图，不把helper超时判为产品启动失败，不改系统设置、不经shell绕过，停止后续重试。摘要artifacts/lw06-native-20261106/window-status.json，旧失败继续保留。实际阅读/播放/授权审核交互、用户/阶段验收仍待完成；同版本真实后台进程闭环和Office页图结果另见LW-06报告，不能替代本任务窗口门禁。
