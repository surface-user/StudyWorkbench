# DL-03c3a 本地来源与执行收据：PR交付摘要

本项为后续双轨合流建立持久记录及备份保护。状态：实现及相关自动化完成，草稿PR/当前head CI待核；审查按用户要求暂缓，人工测试取消。尚无本地双轨创建、执行或桌面入口，不以模型、模拟元数据或备份成功冒称原生合流成功。C3b继续实际合流与恢复入口。

## 范围

- 复用media_download_jobs。0018接0017，新增source_kind、可空source_url、严格本地来源快照/单列派生摘要及run_generation。旧直链14列、URL/query、进度/结果/错误、状态、文件与历史原样保留，旧generation=0，不补造旧执行历史。
- source v1只准local_pair、固定mp4-copy-pair-v1和既有组件摘要、按video/audio顺序的两条media_id/hash/size/MIME/role/stream_index。未知键/版本、bool数值、重复JSON键/NaN/过深/超16KiB拒绝；两轨尺寸合计512MiB。派生摘要不进入自身preimage，不接受传输URL、headers、cookies或任意命令。
- media_download_attempts按(job_id,generation)及同空间复合FK绑定Job，显式attempt/阶段/状态；严格8KiB收据保存最多两条固定冻结路径/复制与probe状态及可空输出凭据。最终输出有独立prepared/committed路径、实际size/hash和视频音频元数据，不能使用输入progress冒充。
- 完整备份/恢复校验原媒体身份、已复制轨道、当前执行和最终输出/节点；prepared移动间隙只保留与核验，不自动发布。离线巡检复用相同严格模型及原共享行/字节/时间预算。容量只读执行标量归属，不读取来源/收据正文、URL、hash或媒体内容，分类不授权清理。
- 重启将当前running Job及running执行标interrupted，不自动派发。列表以固定文字表示本地来源、can_resume=false；尚未接入的本地retry明确409。原直链执行、输入预检、同步探测及播放保留。

## 基线与上传范围

集成父历史为已接受探测692d7ef1d04bfb38b991e4fdba939c498a434a83和PDF1125e03b4c258a72370e7e45144bd4683f38f2d1；代码集成父commit 527d564cfa89c54f9d80227620d6982877090042，tree c56e2aad22a37b6bf369a00cc61a104327c9855e。main/app/check_api_errors合并两方行为，其余PDF代码复用现有远端blob；单头0017后才使用0018。最终代码与已验证的完整本地副本一致。

原完整任务表、发行/架构/API历史文档上传被自动审批拒绝，本次按明确授权缩为业务代码、测试、必要迁移和本摘要，继续原GitHub连接器。没有上传原始日志、数据库、媒体、二进制、SBOM或完整旧任务表。完整本地task/原报告及失败现场保留，不能将未外发的历史文档声称为此PR交付。无新依赖、系统工具安装、组件重建、上游缓存修改、合并或发行。

## 自动化证据

独立副本media-local-queue；IQ为既有starlette-q-isolated的CPython3.13.17，IP为starlette-p-isolated的3.12.7。既有Starlette1.3.1/pytest9.0.3及两锁不变。以下均退出0：

- 集成基线156项先通过；新增来源/收据与旧schema/媒体/备份/PDF/授权/EOF等22文件，IQ q04/IP p01各499通过、0skip。命令为各固定解释器 -m pytest <相关22文件> -q --basetemp=<独立运行目录> --junitxml=artifacts/dl03c3/a-q04.xml（IP为a-p01.xml），带-W error::pytest.PytestUnhandledThreadExceptionWarning。
- 后续只补真实新表FK/状态/phase/代次/长度/hash约束case，未改生产代码；两版 -m pytest backend/tests/test_media_sources.py -q，各61通过/0skip。499与61重叠，不相加，也不冒称完整500本地已跑。
- 真0017→0018逐列摘要验证六种旧下载状态/私有query/所有旧值，检查原FK/表达式索引和完整性；注入create_table失败后，旧行/DDL/版本完整回滚，源文件和升级前备份保留。
- packaging/windows/build-backend.ps1 -Python <IQ>成功，50应用模块与当前源码/嵌套code/常量相同，check_frozen_sources最终再核成功。
- 源码与新冻结程序各14个真实CLI检查，覆盖copied、prepared已移动、committed三状态巡检/容量/完整备份/新空目录恢复，所有行摘要/非DB字节一致；破坏输出凭据后巡检/备份非零且不发布/不改源。fixture仅自编语义字节和模拟元数据，不是编码媒体或实际mux结果。
- 源码/冻结tools/check_api_errors.py各85检查/43错误ID，保留PDF确认、授权、旧收据/Range/重启及缺可选组件边界。
- Ruff、Question Schema --check通过。1425 collected仅表示收集，不冒称全量本地通过；最终CI另核。

失败保留：初次新专项57通过/2失败因自有旧表fixture占位符15对14，修fixture后59通过；扩大Q03为490通过/9失败及定位12通过/1失败，均在受限环境创建自有Windows链接时WinError5，原断言未到达。原审批环境重跑后各499原断言全部通过，未删除或放宽失败。初始表达式索引反射警告经精确resolve_fks参数解决，真实FK仍核；仅原FastAPI/anyio弃用提示。原日志/JUnit与本机验证脚本保留在忽略目录，未作为上传附件。

## 后续

C3b接现有用户下载/入库入口，实现真实所选两轨copy/probe/固定mux、共享预算、取消/父EOF、重启保留旧attempt后显式重开、发布收据覆盖文件移动与SQL间隙及幂等入库，并独立PR/当前CI。站点提取/确认/下载、WebM/分片/HLS与发行门禁继续独立，不借本项关闭。
