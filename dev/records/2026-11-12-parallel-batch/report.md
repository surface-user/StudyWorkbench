# 首批并行任务组合回归

日期：2026-11-12。INT-01状态REVIEW：只组合已分别交付的#24–#27，并核验共存后的回归。审查依ADR0014暂缓，人工/Computer Use不执行；未合并任何PR或main，未发行。#28–#30等后续任务在各自分支推进，未计入本候选实现。

## 输入与验收

共同基线#23/2645366ca4f37cced53f41119ccebd732239a123。每份输入先与远端最终head的Git blob核对，再按共同基线组合无重叠改动；共享task行分别合并，原报告追加均保留，冲突直接失败，不覆盖别的任务。

| 小任务 | 精确head | 主Agent核实的最终CI |
|---|---|---|
| DL-01a #24 | 91db70413303c76d9fb5d78bb3c40f16089b1ca0 | [43059706025](https://github.com/surface-user/StudyWorkbench/actions/runs/43059706025)，成功 |
| REL-01a #25 | 1b52eb30785de734e7d5149d3198c5ee80bb78cf | [43060243273](https://github.com/surface-user/StudyWorkbench/actions/runs/43060243273)，成功 |
| PAR-01 #26 | 1d103f3c21cb8c95f5ea62841be11a4b7b2d16f9 | [43061041645](https://github.com/surface-user/StudyWorkbench/actions/runs/43061041645)，成功 |
| LW-07a #27 | 6af03602e5d70b40de58420b8b323c173612aaac | [43060817695](https://github.com/surface-user/StudyWorkbench/actions/runs/43060817695)，成功 |

各小任务证据经主Agent核验后，在task保留DONE条目；DONE只指各自有限开发交付范围。源码SBOM不是最终发行SBOM；解析不包含OCR/任意多栏；公网证据不包含正向Range/重定向；分页不是并发事务快照。完整父任务、历史失败及审查/发行义务继续保留。

## 本批实际命令与结果

工作目录D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-one。Q为D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（3.13.17）。原始日志、JUnit和输入manifest在忽略的artifacts目录，不上传个人数据或下载媒体。

- 根artifacts/goal-20261112/combine_batch.py：退出0，核对远端blob后组合21份改动；没有网络分支合并、未改功能逻辑。
- Q -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch01/backend.xml：原生进程退出0，760通过、77子测试通过，479.39秒；Starlette弃用警告1条。对应backend.txt/xml保留。原生权限用于已有Windows路径/链接测试，不操作个人库。
- apps/desktop内使用固定Flutter 3.47.1的dart.exe flutter_tools.snapshot --no-version-check pub get --offline：退出-1073741816，SDK cache/lockfile写权限不足；日志artifacts/batch01/pub-get.txt保留。此失败不计为Flutter通过。本批UI代码与#27最终已验版本相同，组合当前head仍需完整Flutter/Windows/冻结CI。
- 本次文档/差异核对另记录提交检查输出；最终提交SHA、当前head CI结果与退出结论在本PR描述持续更新，避免为记录自身SHA循环提交。

## 交付与下一步

组合PR基于#27最终head，保留各项原独立PR及完整历史；仅新建候选分支，不将原PR标为已合并。等待本候选最终head CI通过后，INT-01由主Agent验收；尚未通过前保持REVIEW。下一批Office+Java、TXT全文和复杂Office矩阵分别核验，再组合，不能把各分支各自通过冒充完整产品通过。

## INT-02 第二批组合

首批INT-01的#31最终b8d534a96e6ced1ddd425c36d25ebad1251b5efd已由主Agent核验[CI43069606085](https://github.com/surface-user/StudyWorkbench/actions/runs/43069606085)三组全成功；前文REVIEW是当时提交快照，现首批有限任务已DONE。人工/审查/合并/发行边界保持。

第二批以该精确tree的450份Git blob为基线，在新.local/goal-20261112/batch-two源码副本组合以下已交付改动。没有复制前批测试库、缓存或产物；未合并原PR/main。INT-02本地组合回归完成，当前REVIEW，独立PR/最终head CI待核，不把各PR绿灯当组合版本绿灯。

| 独立任务PR | 精确head | 主Agent核验的最终CI |
|---|---|---|
| OFF-02a #28 | 2187fec21fee25472124aa97a2b1ea524d85e357 | [43065303373](https://github.com/surface-user/StudyWorkbench/actions/runs/43065303373)，成功 |
| LW-04a #29 | 9027508bdbc78316b546c8000cc06267c51f3149 | [43066543568](https://github.com/surface-user/StudyWorkbench/actions/runs/43066543568)，成功 |
| FMT-01 #30 | c352424aae9e6d6e6752f754c51297ecc1ce5f8b | [43067590610](https://github.com/surface-user/StudyWorkbench/actions/runs/43067590610)，成功 |
| REL-03a #32 | 89f0d775d847981b97a70c1a88281e140756c8f2 | [43071363779](https://github.com/surface-user/StudyWorkbench/actions/runs/43071363779)，成功 |
| OFF-02b #33 | e0a3fcf66f18752df4c67b19151b21ef94f2f0f4 | [43072881498](https://github.com/surface-user/StudyWorkbench/actions/runs/43072881498)，成功 |

各输入先核最终Git blob，再根据各自PR基线组合差异。源代码没有重叠冲突；task由主Agent统一登记有限DONE及未完成父项，补齐下方重复摘要的旧状态，保留历史失败，不让上表DONE与下表未实施并存。已满足的源许可检查范围另列REL-02a READY；完整发行范围仍待REL-01，不据源包标签宣称许可义务完成。

实际组合脚本位于根artifacts/goal-20261112：prepare_batch_two.py核450基线后应用#28/#29；在#30依赖说明插入处，五行上下文跨到了既有SBOM说明，保守拒绝退出1，保留现场，没有覆盖。检查差异确认仅开发样本工具独立段落后，用唯一相邻段落定位并完成其余#30改动，退出0。extend_batch_two.py将#32/#33独立追加报告与源码组合，退出0。没有放宽功能测试或改写任一特性实现。两份manifest记录精确输入head/文件hash，原始组合现场留在忽略的artifacts。

已执行Q -m ruff check backend tools退出0，Q为根.local/release-venv/Scripts/python.exe（3.13.17）。组合后端全量与桌面自动化结果继续追加，使用全新测试目录，不修改共享Python环境。完整SBOM、传递许可/源码义务、漏洞修复、PE域门禁、签名及发行仍未完成；API-01a/#34、OFF-02c及pytest/Starlette修复尚未纳本候选。

本批实际后端命令：PYTHONPATH=backend; Q -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch02/backend.xml，原生测试权限退出0，882通过、77子测试通过，387.63秒。2条警告分别为原Starlette弃用和Java重复ZIP路径负例，保留backend.txt/xml。没有跳过真实链接用例或放宽保护。

桌面准备：固定Flutter3.47.1的Dart/flutter_tools.snapshot --no-version-check pub get --offline，依赖解析完成后因本机缺Developer Mode的插件symlink要求退出1（pub-get.txt）。不修改系统设置；requirements/pubspec锁逐字不变，得到的package_config用于--no-pub组件测试，不能把该pub准备失败写成Windows构建成功。桌面完整测试另运行并记录退出码。

桌面实际命令：本副本新建.venv目录链接只读复用Q，不改变共享环境；PYTHONPATH指本副本backend。D F --no-version-check test --no-pub --concurrency=1 --dart-define=STUDY_ROOT=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-two --dart-define=STUDY_DATA_DIR=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/batch-two/.local/flutter-full01，退出0，完整200通过/无跳过，1分42秒，artifacts/batch02/flutter-full01.txt。该结果是组件与真实隔离后端回归，不是窗口/人工验收。

提交前检查：D format --output=none --set-exit-if-changed lib test integration_test退出0（87文件无变化）；D F --no-version-check analyze --no-pub退出0。32份实际变更的UTF-8/LF、逐文件git diff --no-index --check与Markdown本地链接聚合检查退出0；两份依赖锁与#31逐字保持。当前组合实现/本地自动化完成，保持REVIEW直到独立草稿PR最终head CI核验，提交/CI结果在PR描述维护。

## 2026-11-13：INT-03 第三批组合

主Agent已核INT-02/#37最终54d26ec04a046fe2852d078db6e9752e2a4a2603，CI43093356970第二次三组44步成功；首次desktop与Python3.12均在upload-artifact创建产物时五次返回HTML/JSON错误，测试/构建步骤成功。只重跑失败检查后恢复，未跳过产物上传、未改源码/断言；首次失败仍保留。INT-02有限开发交付DONE，正式发行仍未完成。

在新.local/goal-20261112/batch-three核对并复制#37精确462个Git blob，先组合已由主Agent验收的#34（8b29a27008e64e0cce6615a2135edda1125a435d）、#35（a73bedd24c228b61c9f1ccd4290152af2bace57b）与#36（fbbc8479b039fc69ea41260c7bdd298484effa16）相对于各自PR基线的变更。task及本批报告由主Agent维护；未修改原PR/main或根工作区。当前INT-03 IN_PROGRESS，后续未核验切片不视为本组合实现。

prepare_batch_three.py先完成#34与#35锁/报告；#35依赖说明的五行上下文跨到了已交付FMT工具独立段落，保守退出1。人工对照确认为无逻辑重叠的相邻文档新增后，resume_batch_three.py按唯一原段落插入pytest说明并完成#36，退出0。未覆盖FMT或原报告；第一次辅助命令的引号错误亦保留，没有影响源码。组合数据和精确sha位于根artifacts/goal-20261112/batch-three-manifest.json。

#36主Agent另核双Python各84、实际19743文件/351PE/18延迟边、277未知partial及三项真实加载根负例，发行门禁仍拒绝未知。其CI43092944364第二次三组44步成功，首次仅upload-artifact同类错误保留。#34原API-01/a要求已满足，不将未要求的业务码细化新增为永久退出前置；其旧Office偶发测试失败继续保留，不因新CI通过宣称该偶发根因已修复。

本组合实现尚待全量/冻结/桌面检查、独立PR与当前head CI。审查暂缓，人工测试取消，完整SBOM/许可/漏洞/Office整包与签名发行继续，未合并或发行。


继续纳入已验收的#39（2da4306ab5637a8f1389a697c92b570e13d28f52）、#40（b48b711d0ee1bdc5e2aa507e1e08852be73829ae）和#41（218cfc235f3d7655c39764085aab3477ddb11bdf）。主Agent分别核当前head CI43359332568、43359261755、43359882156，均三组44步成功；#39的102×2及53入口/223未知/5负例，#40的905条JUnit×2（828加77子测试）/89×2/23×2及原始OSV哈希/新exe，#41的57×2和246原文逐引用hash/453本地远端blob均已核验。完整Office/许可/最终漏洞检查仍未完成；每项原报告和失败继续保留。

extend_batch_three.py及extend_batch_three_license.py按各PR基线的精确blob应用，退出0，无源码逻辑重写或冲突。#41摘要对应其当时Starlette0.50源锁，只是历史实采；当前组合锁为pytest9.0.3/Starlette1.3.1，后续实采必须用当前锁/实际环境。许可补全另需处理latex2mathml项目MIT与内嵌LPPL；不能将本地原文收集成功当完整义务通过。

在仅#34/#35/#36已组合时，IQ35 -m pytest backend/tests/test_api_errors.py backend/tests/test_native_dependencies.py backend/tests/test_office_java_bundle.py -q --basetemp=.local/batch-q-target01 --junitxml=artifacts/batch03/target01.xml，退出0，58通过。当前完整组合改用IQ40（starlette-fix/.local/starlette-q-isolated/Scripts/python.exe），实际Starlette1.3.1/pytest9.0.3，不改变共享Q/P环境。

为桌面测试建立本副本.venv到IQ40的新目录链接：普通权限尝试拒绝、目标仍不存在；受控原生权限成功后版本断言退出0。两份pubspec.lock逐字hash一致，复制#37已生成的package_config供--no-pub；第一轮Flutter测试因缺package_graph.json退出1，日志flutter-full01.txt保留。补同一锁的package_graph后用新测试数据目录重跑，不执行flutter clean或改变系统Developer Mode，不复制个人数据/测试库。

### INT-03 本地核验结果

本轮IQ40指starlette-fix/.local/starlette-q-isolated/Scripts/python.exe（3.13.17，实际Starlette1.3.1/pytest9.0.3）；Q为根.local/release-venv/Scripts/python.exe，仅用于既有Ruff/核证辅助脚本；D/F为固定Flutter3.47.1的Dart与flutter_tools.snapshot。全部测试使用本组合backend及全新隔离数据目录，不改变共享依赖或个人库。

- PYTHONPATH=backend; IQ40 -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch03/backend.xml，原生测试权限退出0，971通过、77子测试通过，1195秒；JUnit1048条无失败/错误/跳过。三条警告为httpx TestClient、anyio别名弃用及重复ZIP负例，不降低断言。完整Python3.12与远端环境另由当前head CI核对。
- D F --no-version-check test --no-pub --concurrency=1 --dart-define=STUDY_ROOT=<本组合> --dart-define=STUDY_DATA_DIR=<本组合>/.local/flutter-full02，退出0，203通过；D format --output=none --set-exit-if-changed lib test integration_test退出0，88文件无变化；D F --no-version-check analyze --no-pub原生权限退出0，无问题。最初普通权限analyze不能访问固定SDK lockfile，退出-1073741816，日志保留后原生重跑，不改系统设置。
- IQ40 -m ruff因只读共享包环境缺自身Scripts/ruff.exe退出1；改用已有Q -m ruff check backend tools退出0，未安装或改变任何依赖。前述测试使用隔离IQ40不受此开发工具入口影响。
- ./packaging/windows/build-backend.ps1 -Python <IQ40>日志显示干净构建完成且44个业务模块含嵌套代码/常量均与本组合源码相等；原包装调用返回在上下文截断后无法恢复退出码，不据日志虚构数字，实际新exe及下列独立运行均已核。新exe 22577830字节，SHA256 16d3c2242fac5eb5a9d8c52775140669c1672d885485779531de9206cc8032ea。当前head CI仍须重新构建验证。
- IQ40 -X utf8 tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/api-frozen01，退出0，34检查/18独立错误ID、重启/幂等收据及媒体Range兼容通过。IQ40 tools/check_backend_lifecycle.py --exe同exe退出0，恶意Host/Origin、连接重置后EOF、重启/崩溃/两次迁移/原件与学习数据保持等原完整链通过。
- IQ40 tools/check_office_previews.py --exe同exe --test-root .local/office-frozen01 --runtime <根.local/release-tools/libreoffice-java-26.8.1-21.0.13> --docx <formats/.local/fmt-samples01/复杂分节.docx> --pptx <同目录/复杂图表.pptx> --complex-xlsx <同目录/复杂工作簿.xlsx>，退出0。固定组合运行时中DOCX/PPTX各3页，PDF108085/77988字节，逐页非空/边界/公式/图表及取消重试/缓存/重启/原件hash通过，XLSX2表15格只读值、XML预算拒绝与SQLite完整性通过。不是人工视觉或任意Office保真证明。
- IQ40 tools/source_sbom.py --syft <根.local/release-tools/syft-1.57.1/syft.exe> --output artifacts/batch03/source-sbom退出0，136源包及8个SDK未知；源锁和全部组件与#40逐项相同，BOM SHA256 bc41c7389b5b7cbf53869cf5ce716b352b699b5e696bf70ac9ae0d83c59e86ca，comparison.json SHA256 6070202c65f99832db70e28ae81596d3006b8af6ddbd2f07b9b9d23d6a79594f。未发生依赖变化，沿用#40当时135包无返回公告的有限在线证据，不冒充本轮新漏洞查询或已知数据库快照。
- IQ40 tools/source_licenses.py --package-config apps/desktop/.dart_tool/package_config.json --output artifacts/batch03/source-licenses退出2（缺证），136源包/246原文引用/182唯一文本；每份副本重新核长度/hash，report.json SHA256 26762874b1b6db994d509f482238d6e02fd022ca01f3ed82fc8a3b168165be76。唯一已观测缺文仍latex2mathml3.81.1，内嵌LPPL另需处理；完整产品许可/归档来源/义务字段保持false。#41提交摘要是当时Starlette0.50旧锁历史，本轮实采为1.3.1，不改写旧证据。

根artifacts/goal-20261112/finalize_batch_three.py首次误用辅助证据字段名退出1，按实际report的files/text_path修正后退出0；实际证据未修改，生成本地summary.json。上述原始日志/XML/图片/许可文本均留忽略的artifacts或.local，不纳Git。没有重复完整回归或将失败改为跳过。

本轮另核#38最终842b19df5100e55960f98269283743d37d63433b和CI43362970857三组46步成功，直接比对桌面原日志与摘要cbdfa5cbe5211ca53dc9bcafdd707097fbfdc78c73fa6684542920cc7359fce8。源码真实206/同域跨域302、冻结恢复追加及hash/媒体复用通过；结合#24满足原DL-01，主Agent已在#38描述登记DL-01b及父DL-01 DONE。#38只有开发探针/CI/文档，未改生产下载代码；其工具未纳本INT-03。旧DNS/MIME/未知长度探针失败保留，LW-07其他规划继续。下一步DL-02a先明确站点与授权范围，未获答复前不代选。

当前INT-03实现与本地自动化完成，保持REVIEW等待独立草稿PR最终head CI；PR实时描述维护最终head/运行和验收结果，不为引用自己的最终SHA循环制造文档提交。审查暂缓、人工取消、未合并或发行；OFF-02配置继承及223未知、完整SBOM/许可/漏洞/签名与发行父项保留。

提交前35文件聚合检查首次在已接受输入test_native_dependencies.py发现新增EOF空行，git diff --check退出3；仅在本组合删去末尾多余空行，AST与#39逐字解析结果一致，原输入分支不动。功能源码仍与各已核输入精确相同，不重复业务测试；根Q -X utf8 artifacts/goal-20261112/check_batch_three.py重跑退出0：474文件来源核对、35变更空白检查、159本地链接和44个调度行唯一性通过，原报告与历史失败完整保留。


## 2026-11-14：INT-04 第四批组合

主Agent已独立核#43最终c666db99e54b5cd62d9f194a4357c9eea9051da9及CI43365961531三组45步成功，INT-03 DONE。复制其精确474份Git blob到新batch-four，不复制旧测试库、缓存或产物；根用户未跟踪文件与全部既有PR保持。当前先组合已验收#42最终fb5b7a2、#44最终f473abc和#45最终517bcd4；为完整保留实际公网证据和探针，再纳已验收#38最终842b19d。每项均先按各自PR基线核精确变更blob，原独立任务/报告仍保留。#46许可补充本地已验证并独立PR，但当前CI未终态，不作DONE或纳本组合，待核后再加入。

prepare_batch_four.py完成#42/#44后在#45 dependencies.md旧免责声明的上下文保守退出1；原因是本组合已有较新的OSV源范围查询/Starlette修复证据，而#45基线旧句称未查询，不能直接覆盖。resume_batch_four.py逐段核对后保留较新源查询说明，加入独立候选依赖说明/三站差异，退出0；未改任一功能实现。#38诊断差异及#45其余契约随后按精确来源合入，退出0。两份manifest记录每个输入base/head/文件sha，临时脚本和原始日志留根忽略artifacts。

当前INT-04 IN_PROGRESS，尚未将独立PR绿灯代替组合测试。OFF-02e配置隔离、新冻结SBOM覆盖、站点设计和公网探针已具备共同源码，后续全量/真实新冻结Office及来源/许可对照、独立PR/当前head CI继续。完整组件身份、LPPL原Work/最终许可、漏洞、签名与发行未完成；审查暂缓、人工取消，未合并或发行。


#46最终8bebad8896da83db4ac45ea6f7f4aa41142901cd的CI43569063314现已由root核三组45步成功：双Python各986及Windows/44模块冻结/API等通过，REL-02b1有限任务DONE，原LPPL义务仍未闭合。extend_batch_four_license.py按精确来源加入其九文件差异，退出0，无逻辑冲突。当前INT-04输入冻结为#38/#42/#44/#45/#46，不追逐尚未交付的下一Office/身份/站点功能。

为核组合版本的源码/新冻结公网续传与重定向，仅将已有固定--allow-public-fixtures CI步骤的分支条件追加codex/parallel-batch-four；原codex/public-download-range保留，其余分支条件保持。不改探针预算/来源/hash/生产网络保护。该步骤仍限pull_request事件，超时5分钟，实际来源媒体不进Git或发行包。

纳#46之前的专项：IQ40 -m pytest test_office_launcher.py test_office_previews.py test_native_dependencies.py test_frozen_sbom.py test_public_download_check.py -q --basetemp=.local/batch-q-target01 --junitxml=artifacts/batch04/target01.xml（均backend/tests/前缀），原生测试权限退出0，146通过/2弃用警告；当时全backend/tools Ruff退出0。下一完整回归使用已纳#46的最终源码，专项不是当前全量证明。


### INT-04 最终本地核验

本轮IQ40为starlette-fix/.local/starlette-q-isolated/Scripts/python.exe（3.13.17，pytest9.0.3/Starlette1.3.1），Q为根.local/release-venv/Scripts/python.exe用于已有静态/核证工具；D/F为固定Flutter3.47.1的Dart及flutter_tools.snapshot。任务内新.venv目录链接只读复用IQ40，先确认不存在后按已授权原生测试权限创建；共享环境未修改。pubspec.lock逐字等于#43，复用其同锁package_config/package_graph，不再重复旧缺图/缓存准备失败。

- PYTHONPATH=backend; IQ40 -X utf8 -m pytest -q --basetemp=.local/batch-q-full01 --junitxml=artifacts/batch04/backend.xml：原生测试权限退出0，1063通过及77子测试通过，423.92秒；JUnit1140条无失败/错误/跳过。三条警告为httpx TestClient/anyio别名弃用及重复ZIP负例，均保留，不降断言。两版远端完整回归以本PR当前head CI为准。
- D F --no-version-check test --no-pub --concurrency=1 --dart-define=STUDY_ROOT=<本组合> --dart-define=STUDY_DATA_DIR=<本组合>/.local/flutter-full01：原生权限退出0，203通过/1分41秒。D format --output=none --set-exit-if-changed lib test integration_test退出0，88文件无变化；D F --no-version-check analyze --no-pub原生权限退出0，无问题。Q -m ruff check backend tools最终退出0。
- ./packaging/windows/build-backend.ps1 -Python <IQ40>：退出0，新构建44业务模块（含嵌套代码/常量）与本组合源码全部匹配。exe22578633字节，SHA256 68f0a3cb710bb7bafb273c14ccfe44cd7b27b097ee228b11201976be0fc299c3；本次包装进程退出码已从实际运行handle取回，不借旧日志推断。没有用原#43或#44 exe冒充新组合。
- IQ40 tools/check_api_errors.py --exe dist/study_backend/study_backend.exe --test-root .local/api-frozen01：退出0，34检查/18独立错误ID、重启/幂等收据/媒体Range兼容通过。IQ40 tools/check_backend_lifecycle.py --exe同exe退出0，恶意Host/Origin、连接重置/EOF、重启/崩溃/两次迁移/原件和学习数据等完整链通过。
- IQ40 tools/check_office_previews.py --exe同exe --test-root .local/office-frozen01 --runtime <根.local/release-tools/libreoffice-java-26.8.1-21.0.13> --docx <formats/.local/fmt-samples01/复杂分节.docx> --pptx <同目录/复杂图表.pptx> --complex-xlsx <同目录/复杂工作簿.xlsx>：退出0，DOCX/PPTX各3页、PDF108085/77988字节，逐页边界/非空/公式/图表、取消/重试/缓存/重启/原件hash及XML预算拒绝通过；XLSX2表15格、SQLite完整性通过。本次为配置隔离与API改动同一冻结程序的实际转换，不等于人工视觉/任意Office保真。
- IQ40 tools/source_licenses.py --package-config apps/desktop/.dart_tool/package_config.json --output artifacts/batch04/source-licenses：退出2，136源包/248原文引用/184文本；逐引用hash/长度均核验，report.json SHA256 1ae042486dc0cb83303304ad9eda594022cf14780c1e48630d44e6cae5f29bea，与#46同锁/同采集器实采逐字一致。仍只有latex2mathml的上游缺文与LPPL义务待核issue，完整产品/全部归档来源/分发义务字段false。
- IQ40 tools/source_sbom.py --syft <根.local/release-tools/syft-1.57.1/syft.exe> --output artifacts/batch04/source-sbom：退出0，136源包/8SDK未知，与#40/#43源锁及组件集合完全相同。comparison.json SHA256 59bbe72990e306b6be67a1f88a8ec1a83bed5c46d6abf0be1d61dadaf1c02c7d，BOM SHA256 bad8df9e3d8d37caf910e6dc9fd2929557ace3e411c1a1f53151d8d557d67913。未发生依赖变化，不重复在线漏洞查询或声称新数据库快照；保留原有限查询边界。

根finalize_batch_four.py复用前批核证逻辑并按本批真实结果核1140条JUnit、原日志标志、34API/三页Office/许可副本/源BOM语义与exe字节，退出0，生成本地summary.json。所有原始日志/XML/页图/测试库/第三方许可副本留忽略artifacts或.local，Git只纳各任务原已筛证据与明确来源的许可文本。

root另已验收#47/REL-01c与#48/OFF-02f的当前head CI和实际证据，有限DONE，但其新身份工具/额外JRE域代码不纳本冻结输入。本组合原静态门禁仍223未知；独立#48减少至145是后续待组合结果，不混作本候选结论。REL-01d、OFF-02g和B站预览继续独立实施，整体完整SBOM/传递许可/最终漏洞/签名发行未完成。

当前INT-04实现与本地自动化完成，REVIEW，仍需本项独立草稿PR/当前head CI，以及本分支明确选择的固定公网源码/新冻结续传重定向闭环；最后以PR实时描述核定，不在报告中预写未知结果或为引用自身SHA循环提交。正式代码审查暂缓，人工/Computer Use取消，未合并或发行。

提交前核证最初假设Office测试只增加assert消息，AST比较退出1；实际#34已接受的诊断还把相同wait结果绑定到first/finished变量。逐字核出#44原测试只应用#34这段原有诊断变换，断言谓词/执行次序未改，不修改目标测试或降低断言。check_batch_four.py改为强制该精确已发布变换，其余测试文件字节必须等于#44；聚合重跑退出0，487文件/28变更、其余原blob、115本地链接/52调度行唯一和全部输入新增报告行/旧前缀保留通过。原LPPL原文仍用官方完整hash核原字节，其他27变更保持普通Git空白检查；两锁不变，CI仅增加已声明的本分支固定公网探针条件。
