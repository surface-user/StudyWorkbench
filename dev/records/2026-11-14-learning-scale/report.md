# M3-03d：学习统计与分页规模回归

## 范围和预注册（性能采集前）

2026-11-14，基于主Agent已接受的INT-04/草稿PR #49精确head68eaabd43de808ff0b258ebc4e854a4b355194bd、tree740ffd2116ee97782c3cd04d21a77dea5ead4aa5，逐487个Git blob复制到独立.local/goal-20261112/learning-scale。原根、其他分支和既有冻结包不改。已读AGENTS及requirements/architecture/question-content-spec/task、现行API/数据模型/ADR0011、learning/learning_records及既有用例。主Agent确认以下预注册后方可采集性能，不根据第一次结果调高门槛。

最小6文件：独立诊断工具、正确性测试、task、dev索引、本报告及一份精选摘要。复用既有启动握手、API、模型和自生成夹具；不加依赖、不改产品/迁移/复习算法。仅当实测暴露失败才另定最小共享查询修复，旧失败保留。M3-03a/b/c、百万规模、冷缓存、并发多用户、学习效果和长期掌握校准均不由本切片销项。

环境先于采样登记：Intel Core i7-14650HX，24逻辑处理器，物理RAM16,944,848,896字节，Windows11 build26200。本地源解释器使用既有独立CPython3.13.17；专项兼容另核3.12.7。操作系统/解释器/工具hash随实际报告再记录。工作站同时开发，主Agent当前重负载回归期间只实现、造数据和跑小型正确性检查；正式性能采样等待其告知串行空闲窗口，报告注明实际条件，不伪装专用性能机。

每档主空间1,000/10,000/100,000条作答，隔离空间另有10%作答，交错全局ID；各100份自编题分四组，每组25份：连续满分且人工0→1复评、原满分但人工1→0复评、未批改主观、未复评零分。回答/反馈各1KiB，历史日期固定且足够久，不依采样分钟边界；预设组和生成时显式ID序列作为oracle，不复制study_rows的查询/连击代码。直接批量造库只限本命令新建且有标记的隔离目录，受现有schema/FK/触发器约束，不从现有个人库复制。

单条作答10,000事件，另空间1,000噪声事件；含annotation/reviewed、两个现存笔记及一份先创建并建立事件关系、再在隔离夹具构造期移除的历史笔记。历史缺失关系不冒充API允许关联不存在笔记；另验跨空间关联拒绝。最后明确knowledge_points=[]放在最新100项之外，此后null/省略不能改投影；完整事件流每页都应给出同一标签/复习数/笔记关系和算法版本。历史版本未知保持未知，不补造确认快照。

正确性验收：完整作答/事件分页严格降序、before游标边界、无漏重、隔离空间不混入；所有事件页的全流projection一致；统计符合四组的人工预期（mastered25/wrong50/pending25，100自编题及2演示题），事件/自评不改成绩。拒绝无鉴权/外Origin及跨空间读取/关系。独立受控追加阶段验证新作答不挤入已取得的旧页游标。只读阶段前后全库逻辑摘要及合成原件hash相同；追加阶段单列预期新增，不将主动写入称为全程只读。

性能验收只在明确本地benchmark运行，source和既有#49冻结版各三档串行；冻结包须先44业务模块核源及记录exe/完整payload hash，明确其为#49旧构建、非本次新build。每种API先3次预热，再30次完整HTTP响应/JSON读取计时，p95采用nearest-rank ceil(0.95*n)，保留全部原始样本。历史页在头/中/尾分配；另记录完整遍历耗时和页延迟。门槛：history p95≤500ms；statistics及study各p95≤5,000ms；10,000事件record p95≤2,000ms；单请求10秒、单档20分钟硬预算。门槛失败不得删样本、增加预热或改阈值使其通过。

Windows进程内存：操作系统PeakWorkingSet≤768MiB；就绪基线后观察到的PrivateUsage增长≤256MiB。每50ms及请求后采样，记录基线/峰值/退出；操作系统工作集峰值包含启动，私有内存短瞬态可能落在两次采样之间，不宣称得到了真实私有峰值。只测后端进程，不把测试驱动或整机内存混入该指标；不代表安装器/干净机/硬件矩阵通过。

CI仅跑小型夹具的API/分页完整性、oracle与可信边界检查，不设置依赖共享runner速度的性能断言。实际本地规模结果与当前head CI分别记录。人工测试取消，代码审查按用户指令暂缓；待独立草稿PR/当前head CI及主Agent有限核验后才登记DONE，不合并/发行。

## 实施与首轮失败保留

工具支持只选择已预注册三档之一的--attempts，默认仍完整三档；用于在各Agent的静默小窗口间交替，不可挑绿档省略失败。首次源1k于09:29:21–09:29:54 UTC运行，接口/分页/逻辑hash通过，但原.local/m303d-source1000-01/report.json的内存仅4MiB，事后确认采到了Windows venv python.exe启动stub，不能作为有效内存结果。原始文件/数据/日志保持不改，虽其当时status=passed，整档判无效，修正观察器后必须新目录重采全部六档；原阈值不变。

修正只在诊断工具内：按[GetExtendedTcpTable](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable)取得握手端口的精确127.0.0.1监听PID；按[PROCESSENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w)核其位于本命令启动进程的最多8层父子链，再以[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)核同一实际exe身份。持该服务PID的同一handle取得基线/峰值/私有值，采样和每次计时请求后重验端口owner及[GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess)仍活动；PID变化、退出、错exe或观察失败即拒绝。TCP表≤8MiB/20000行/3次调整、进程元数据≤20000项，不共享其他进程/连接；不把后代内存求和当单后端，不给产品/握手增加PID字段。50ms观察及身份检查本身有开销，短瞬态私有峰未知仍保留。

小型首轮q01出现19个fixture错误：1KiB填空参考答案超过现行每个候选500字符限制。改为四个256字节的合法空格，仍保持回答值总1KiB，不放宽协议或减少样本负载；主观回答/人工说明仍1KiB。之后原19项和相关18项已通过；观察器补入真实服务进程、错误exe和owner变化反例后继续复验。历史缺失笔记明确先生成合法Note/事件关系，再仅在隔离夹具造库事务中移除Note，保留Resource原件与全部事件，未伪装API允许关联不存在笔记。

## 100k环境失败定位与采集前临时目录策略修正

修正PID后的源1k/冻结1k、源10k/冻结10k四档原本均通过；源100k完整1000历史页与100事件页后，statistics实际HTTP500，串行立即停止，冻结100k当时未运行。原.local/m303d-source100000-01及日志保持，未把前四档计为全任务通过。对同一失败库以mode=ro直接study_rows、完整statistics路由函数及jsonable_encoder均正常返回102题/100000作答，故未先改共享查询。

artifacts/m303d/replay_100k.py把自生成失败库备份到新的diagnostic01，仅用artifact wrapper在原安全错误日志位置输出堆栈，未修改产品：statistics→study_rows/session.execute→sqlite3.OperationalError: unable to open database file。原库前后逻辑hash一致。temp_probe.py对照显示相同SQLite3.50.4/同一只读库：受限进程的TEMP存在、临时文件写入成功且查询返回102；普通本机权限进程继承了另一TEMP，该目录虽存在但临时文件PermissionError(errno13)，查询同样unable to open database file。只记录临时目录hash/可写结果，不共享用户绝对目录；不是数据/算法故障或客户端10秒超时。原HTTP响应在安全日志仅关联ID，诊断副本才有堆栈，未记录会话令牌/Authorization/请求头或正文。

主Agent批准在新采样前仅修诊断环境：source/frozen子进程TEMP/TMP指向各自新隔离case/runtime-tmp，启动前写入/关闭自动删除一份自有TemporaryFile确认可写；同一磁盘SQLite默认temp_store保持，不把排序移内存、不改共享查询/数据/门槛。report记录temp_policy，此后全部六档新目录重采，前四小档作为旧环境结果保留，不沿用到新汇总。既有#49 exe业务未变，不仅因工具环境变化重建冻结包。

Windows监听PID查询在受限进程返回AccessDenied5，普通本机权限正常返回需要缓冲区122；首次q05/p06各3项观察器失败保留。q07/p07在已授权本机只读查询权限下各39通过（新21+原18），其后临时目录策略再改后仍须用新q08/p08复核。未把权限拒绝当作跳过，也不回退到启动stub。

## 最终自动化与六档实测

IQ/IP分别为../starlette-fix/.local/starlette-{q,p}-isolated/Scripts/python.exe，版本3.13.17/3.12.7，既有pytest9.0.3；不升级共享环境。最终工具SHA256 0b1094436e5fd5689ea721b11ecf62e142f3f383b38f2cee475ad61b3d6c6599，全部六档报告均一致。

- IQ/IP -X utf8 -m pytest backend/tests/test_learning_scale.py backend/tests/test_learning.py backend/tests/test_learning_records.py -q --basetemp=.local/m303d-q09或p09 --junitxml=artifacts/m303d/q09.xml或p09.xml：各退出0，39通过，失败/错误/跳过均0。新21项使用400作答/200事件小夹具，核合法历史、全页oracle、完整投影、追加后旧游标/旧数据、跨空间/权限、错误exe/owner变更/真实监听PID、输出及重造保护、p95定义/坏值；不设置CI主机速度断言。q08/p08各3项失败因require-existing no_links在mkdir前检查新临时目录，改成核根→mkdir→核目标，原链接拒绝不变，旧失败保留。其余q02至q07/p03至p07中间结果也留原artifacts，不混为最终计数。
- Q（根.local/release-venv/Scripts/python.exe）-m ruff check backend tools与Q tools/export_question_schema.py --check均退出0。预检曾把实际check_frozen_sources.py误写成不存在的文件名及Windows rg字面glob导致查找失败；改用实际入口后通过，未改环境/业务。IQ tools/check_frozen_sources.py --exe ../batch-four/dist/study_backend/study_backend.exe退出0，44业务模块含嵌套code/常量与本副本逐项一致。
- 正式采样由IQ -X utf8 tools/check_learning_scale.py --attempts N --test-root .local/m303d-<模式><N>-<轮次>执行；冻结版另加--exe ../batch-four/dist/study_backend/study_backend.exe。N依次1,000/10,000/100,000，source/frozen交替串行。新有效目录分别source1000-03、frozen1000-02、source10000-02、frozen10000-02、source100000-02、frozen100000-01（均带m303d-前缀）；六次实际退出0，串行包装进程最终退出0。
- 本机协调窗口2026-11-14 10:07:05–10:11:30 UTC（各目录创建至report写入，包含核源/造库/启动/退出，非纯采样时段）。开始前root与sbom/downloads明确已结束本机重负载；全程仅远端CI/文本并行，结束明确释放。没有监控或控制其他Windows/用户后台活动，不冒充专用性能机。raw保留全部30样本、完整遍历每页延迟、进程链/镜像hash/内存及前后逻辑摘要。

| 模式/主作答数 | history p95 ms | statistics p95 ms | study p95 ms | 1万事件record p95 ms | PeakWS MiB | 观察私有增长 MiB |
|---|---:|---:|---:|---:|---:|---:|
| source / 1,000 | 35.31 | 38.67 | 40.25 | 105.04 | 100.54 | 5.46 |
| frozen / 1,000 | 36.84 | 39.26 | 38.70 | 94.58 | 106.92 | 6.23 |
| source / 10,000 | 37.74 | 107.49 | 107.20 | 103.51 | 100.08 | 5.18 |
| frozen / 10,000 | 36.31 | 100.28 | 108.75 | 117.43 | 107.93 | 7.32 |
| source / 100,000 | 31.93 | 541.83 | 533.23 | 79.22 | 105.11 | 10.61 |
| frozen / 100,000 | 34.34 | 636.83 | 487.56 | 79.66 | 112.76 | 12.03 |

全部满足预先500/5000/5000/2000ms及768/256MiB门槛，没有删掉尾部样本或改变阈值。源服务均为venv启动stub的真实Python子进程，镜像SHA256 7c2fc2b303a4ee3cc14cc17b47bc6e8bca98c78792edd123b846a560da44b203；冻结服务为原#49同一exe进程，SHA256 68f0a3cb710bb7bafb273c14ccfe44cd7b27b097ee228b11201976be0fc299c3。每次基线/峰值取同一真实服务handle，并重验监听owner和活动状态；不求后代总和。冻结完整payload内容身份9f6a0ff3beca35a75f59b5f21aa1e1a64b6e907f480cfe1a59e85a51d0b56d0d，三次前后均一致，构建来源为已接受#49既有包，明确非本次build，source_head_authenticated/product_performance_certified仍false。

每档完整主历史10/100/1000页、完整事件100页，无漏重且foreign ID不混入；100自编题及2演示题的study两页合计、四组知识点/人工复评/待批改统计均与预设oracle相符。每个事件页（含空尾页）保持完整流清空标签、5000复习及2可用/1历史缺失笔记关系；注记未改变成绩。跨空间/无令牌/外Origin与外空间笔记关联拒绝。只读阶段全库逻辑摘要及两份合成原件hash相同；随后显式追加一条作答，旧before页不挤动，排除该新增一行后的全库摘要精确等于原值，未把主动追加叫全程只读。

IQ artifacts/m303d/select_evidence.py退出0，[精选摘要](evidence/summary.json)27,389字节/SHA256 ac5a71c2689220bb3d088da8c1f1a8ef000cbbb26af4e67dd4283fe2228a8d48。只筛身份、机器/窗口、每档统计/完整性、p95/内存、JUnit/hash及旧失败说明；完整原始样本、页延迟、服务PID链、stderr、诊断堆栈和自生成库留忽略的artifacts/.local，不提交测试库或整目录原始日志。既有失败数据保持；通过夹具暂存供本轮主Agent核验，之后按dev现行留存规则回收本任务自生成目录，不清理他人或个人数据。

有限实现/相关自动化/文档已完成，M3-03d保持REVIEW等待独立草稿PR/当前head CI及主Agent核验。新CI只验证小型正确性及原Windows/冻结链，其新exe未在本次旧#49性能数字中冒充受测包。M3-03c算法校准、百万规模/冷缓存/并发/学习效果与完整发行继续单列；审查暂缓、人工取消，未合并或发布。

IQ artifacts/m303d/check_docs.py退出0：6文件、485未变base blob、491总文件、UTF-8/LF/逐文件git diff --check及102本地引用通过；全部产品/迁移/依赖锁与#49字节相同。实际创建并附加[独立草稿PR #56](https://github.com/surface-user/StudyWorkbench/pull/56)，分支codex/learning-scale，base为#49精确68eaabd，首提交db16395f6f7fba5661d1ada85cd4e2c0fac30b1c/treea806c0c2c3d4100f5fa4c893b56afd7a78b1910a。补入本交付链接后保持6文件；最终head/当前CI与主Agent核验结论在PR实时描述维护，不为记自身最终SHA反复改head。未改原根/其他分支/既有exe，未合并或发行。
