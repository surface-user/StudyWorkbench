# M0-02 / M1-04 发行文件清单完整性

## 需求与范围

依据现行task.md的M0-02/M1-04发行自动检查，以及packaging-windows.md规定的全新staging/文件hash/PE依赖校验。原tools/check_release.py只对manifest.files逐项校验，没有核对实际文件集合；原release_inventory.py按basename排除了所有build-inventory.json，连合法嵌套文件也被漏记；build-release.ps1只生成清单后即编译安装包，没有运行已有检查器。属于既有发行校验的具体假阴性，不引入新产品需求或SBOM标准选择。

先核PR #15最终d2c98e4fdd225d2435d1c4905eefae359a969295：open/draft/unmerged，当前head PR CI #93（42760968920）成功；仅一个明确标注的自审COMMENT，无独立审查/批准或未解决线程。独立分支codex/release-inventory-closure以此head为base。用户尚未决定的未登记旧题目目录恢复继续规划，本任务不修改该目录或学习数据；原工作区保留codex/recovery-note-copy/a959b9f及原未提交内容。

Q -X utf8 artifacts/release-file-gap-repro.py退出0：在全新.local/release-file-gap-repro01中复制已安装固定CPython3.13.17的python313.dll及两份CRT（共约6MiB），为三份真实二进制生成正确hash清单，再添加自编unlisted.txt。原check_release真实CLI仍退出0，打印PASS: 3 file hashes；实际payload为4份，前后字节保持。没有安装/发布、读取个人库或伪造PE通过；原日志/JSON和假阴性最小复现保留于artifacts/release-file-gap-repro01.*，不进Git。

建立分支前第一次读取结果未能通过head核验，后续未执行；重新只读核对仍为d2c98e4，确认没有分支或文档写入后，才首次创建独立分支并保存六份现有文件到artifacts/release-inventory-base。不把预检失败当成父分支实际发生变化，未覆盖他人内容。

## 设计、任务与退出边界

复用现有release_inventory模块提供同一份staging枚举：只排除根build-inventory.json，其余普通文件（含嵌套同名文件）全部登记；子目录符号链接/重解析点及特殊文件明确拒绝，不展开到外部。检查器先核manifest与实际相对路径集合完全相等，再按实际枚举路径核hash，不能由清单提供任意读取路径；保留既有CPython版本、无.db、CRT和PE依赖断言。构建脚本在清单生成后、Inno编译前运行现有check_release，非零即停止并保留stage。

顺序：新增完整集合/只读/路径/嵌套清单/原PE和版本守卫回归先红→最小共享枚举修补并接构建→双Python相关自动测试、真实DLL CLI样本和PowerShell语法→自审、文档、独立草稿PR/最终head全CI。无业务模块、表、迁移、UI、模型或新依赖。不以此宣称完整发行SBOM、许可证/漏洞认证、签名或干净机通过；人工测试已取消，不执行安装或发行。此报告是该独立发行校验工作的原报告，后续重测及PR跟进持续追加，不按重试另造报告。

## 实施与自动化

共享stage_files放在既有release_inventory模块，不创建新模块/框架；使用lstat和显式目录栈，拒绝链接/重解析点与特殊文件。生成前先检查，防止先沿licenses链接复制再拒绝；检查器同样先枚举再读manifest，防止根manifest链接先被读取。只从枚举得到的路径打开文件，清单仅用于键集合和期望hash。原CPython、.db、CRT和PE依赖断言保留，PE句柄仍finally关闭；不把环境包列表当冻结模块集。生成器输出改为只说明清单类型，不再笼统声称“No personal data included”。构建脚本新增检查命令和退出码门禁，未改变安装器/卸载数据规则。

自动化用PE stub隔离文件清单单元逻辑，并另以真实固定DLL做完整CLI文件hash/PE检查，不混淆这两种证据；许可证收集测试为自编配置/许可夹具，不构成真实传递许可审查。新16项覆盖完整集合、额外/缺失/变化、绝对/../路径守卫、嵌套同名清单、原版本/数据库/PE/CRT拒绝和句柄关闭、真实Windows junction、非普通文件、manifest先检查后读取以及licenses链接先拒绝后复制；检查器前后文件字节保持。没有删除或降低既有测试断言。

cwd=.local/markdown-merge-followup-src；P=.venv/Scripts/python.exe（3.12.7），Q=D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（3.13.17）。实际命令与结果：

| 命令 | 退出/结果 | 副本artifacts/ |
|---|---|---|
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rc-red01 --junitxml=artifacts/release-closure-red01.xml | 1；初14项中7失败/7通过，1.05秒；验证旧工具漏检，失败现场保留 | release-closure-red01.log/xml |
| Q -m ruff check backend tools | 0；当时完整静态通过，随后新增两项前置拒绝回归另核 | release-closure-ruff01.log |
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rc-q01 --junitxml=artifacts/release-closure-q01.xml | 0；初14项通过，0.75秒；不冒充最终16项 | release-closure-q01.log/xml |
| P -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rc-p01 --junitxml=artifacts/release-closure-p01.xml | 0；最终16项通过，0.83秒 | release-closure-p01.log/xml |
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rc-q02 --junitxml=artifacts/release-closure-q02.xml | 0；最终16项通过，1.11秒 | release-closure-q02.log/xml |
| Q -X utf8 artifacts/release-closure-cli-probe.py | 0；原真实DLL假阴性目录现被1个unlisted拒绝，正确4文件hash/真实PE通过，随后修改嵌套文件被hash拒绝；三个检查均只读 | release-closure-cli01.log/json |
| PowerShell Language.Parser.ParseFile(packaging/windows/build-release.ps1) | 0；没有语法错误，未执行安装器编译 | release-closure-powershell01.log |

junction用例沿用此前已核实的系统权限，在全新自编目录运行；无权限拒绝重试或降低断言。本地不重复未改动业务模块的全量/桌面/冻结构建，最终head CI仍运行项目完整双Python全量、R1–R5及桌面/Windows/冻结流程。没有执行本次完整build-release/安装器编译（需完整产品staging和现有发行工具），构建门禁接入目前证据为脚本语法、调用顺序自审和真实检查器CLI，不能记为完整打包/安装/发行验证。M0-02/M1-04整体仍未完成。

## 自审与交付状态

已审全部调用方、共享枚举的根manifest排除/嵌套文件包含、前置链接拒绝、清单不提供实际打开路径、集合/hash/原PE守卫顺序、失败保留及编译前退出码。无新增依赖或读取学习数据的路径；该工具用于稳定staging，不承诺并发外部编辑的原子快照，也不构成完整运行时DLL搜索路径或SBOM/供应链认证。当前自审未见本范围阻断代码问题；独立审查未取得。独立草稿PR与最终head CI尚待完成，不合并/发布；未登记题目目录恢复继续规划，不改原目录、现有未提交内容或旧失败证据。

提交前补核：Q -m ruff check backend tools退出0（release-closure-ruff02.log），Q tools/export_question_schema.py --check退出0（release-closure-schema01.log），Q -X utf8 artifacts/release_inventory_validate.py退出0：八份明确文件，其余433份#15基线保持，49文档相对链接/UTF-8/LF/尾空白及规范字节git diff --no-index --check无告警（有差异返回1为正常语义，辅助程序0），详情release-inventory-diffcheck.json。本轮实现/相关自动化/自审完成，独立草稿PR及最终head完整CI继续；不将父#15或本地相关测试代替本项最终head。整个M0-02/M1-04及task未完成，不合并/发行。

实际交付：[独立草稿PR #16](https://github.com/surface-user/StudyWorkbench/pull/16)，分支codex/release-inventory-closure，base=#15最终d2c98e4fdd225d2435d1c4905eefae359a969295，实现6db9f7dee5543b5f0dc480d25828049eb6a1a345。推送前再次核对父head，八份明确文本文件Base64上传并逐项匹配规范UTF-8/LF Git blob SHA，远端commit差异仅八份，其余433份基线保持；以expected_sha推进分支，不强推。task/本报告补实际链接后，最终head/正式自审COMMENT/完整CI运行及核对时间和交付结论记PR描述，不为记录自身SHA循环提交。CI不计独立审查，独立审查未取得；最终head全CI未核实前保持待交付。原工作区分支、未提交内容、学习数据及失败/恢复证据保留，不合并/发布，不实施旧题目目录恢复。

## 2026-11-10 固定x64目标的二进制头校验

### 依据、实证和范围

先核PR #16最终b459f981ca5ba9c22ef8c621ee4ae7914f53cb96：open/draft/unmerged，最终CI #98（42766782388）成功，仅自审COMMENT，无独立审查/批准或未解决线程。原根工作区仍#7/a959b9f，仅原.vscode/summary.md两项未提交，开发继续在隔离副本。独立分支codex/release-x64-guard基于该head，五份现有文件的修改前副本保存artifacts/release-x64-base。本项沿用同一M0-02/M1-04原报告，不新建另一份报告。

现行dependencies明确CPython 3.13.17 x64；Windows构建固定build/windows/x64，安装器ArchitecturesAllowed=x64compatible。现有check_release虽核hash及导入名，但不核PE Machine/OptionalHeader Magic，无法拒绝关键主进程组件混入x86/ARM64。依据[微软PE规范](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)，AMD64 Machine为0x8664，PE32+ Magic为0x20b；它们是文件头声明，不构成文件身份/签名或可运行认证。

先用全新.local/release-architecture-gap01保留x86系统DLL错误候选，随后在新.local/release-architecture-gap02用真实SysWOW64/where.exe（x86、PE32、非DLL）复制为错误的study_workbench.exe候选；另三份为已有固定CPython x64 DLL/CRT，清单与全部hash正确。两次原检查器均退出0/PASS，Machine=0x14c、Magic=0x10b仍被放行。源文件仅复制、不改系统文件，候选从未执行，不代表真实产品已经混入错误架构，也不把系统程序当作产品程序。命令Q -X utf8 artifacts/release-architecture-gap-repro.py及Q -X utf8 artifacts/release-architecture-exe-repro.py均退出0；日志/JSON与错误候选目录保留，不进Git。

只对当前主进程范围施加固定x64门禁：根目录已枚举的PE文件、backend/study_backend.exe，以及backend内.dll/.pyd；要求AMD64且PE32+，在导入表处理之前拒绝错误并finally关闭PE。不会把这一目标强套到可选转换器或嵌套独立helper exe，不从“不检查架构”推断它们可运行。沿用现有集合/hash/版本/数据库/CRT/导入守卫，不加新模块/依赖、CLI选项、布局强制或平台支持；不验证签名/来源身份/CPython DLL真实版本/完整运行时加载行为。

顺序：新架构回归先红→最小门禁→双Python相关测试、真实PE只读CLI及既有16项保持→自审、任务/指南/本报告、独立草稿PR和最终head全CI。业务模块未改，本地不重复业务/GUI/冻结全量，最终CI仍执行项目完整流程。未登记旧题目目录恢复保持规划，不改原目录；不接模型，人工测试已取消，不合并或发布。

### 实施、验证与自审

续接先核现有远端codex/release-x64-guard仍指向#16最终b459f981ca5ba9c22ef8c621ee4ae7914f53cb96，未重复建分支。五份修改前备份齐全，原两份错误架构复现JSON/日志/候选现场保留；报告中的预先设计是当时唯一未提交变化。原根两份未提交文件SHA256仍等于此前值。首次只读GitHub查询连接失败，随后只读核查成功；分支搜索首次参数校验失败未执行，按实际owner/repo_name参数查到既有分支，无远端写入或权限拒绝重试。

生产改动只在既有check_release的try/finally内增加范围判断及Machine/Magic拒绝，使用现有pefile常量，无新模块/依赖；原枚举、清单/hash、版本、数据库、CRT及导入检查不变。通过信息仅增加主进程x64文件头项。既有16项保留，新21项覆盖六个关键位置的x86/ARM64/错误Magic（18项）、正确AMD64/PE32+及两种独立helper范围排除（3项）。PE stub只模拟文件头/导入表，不当作真实二进制或加载测试；断言错误目标在导入表解析之前拒绝、句柄关闭和所有字节保持。

cwd仍为隔离源码副本，P/Q定义沿用上文。实际命令及结果：

| 命令 | 退出/结果 | artifacts/ |
|---|---|---|
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rx-red01 --junitxml=artifacts/release-x64-red01.xml | 1；旧生产实现18失败/19通过、2.23秒，全部失败为预期未拒绝错误架构；旧日志/XML/目录保留 | release-x64-red01.log/xml |
| P -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rx-p01 --junitxml=artifacts/release-x64-p01.xml | 0；37通过、1.63秒 | release-x64-p01.log/xml |
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/rx-q01 --junitxml=artifacts/release-x64-q01.xml | 0；37通过、1.47秒，P结束后串行 | release-x64-q01.log/xml |
| Q -X utf8 artifacts/release-x64-cli-probe.py | 0；旧真实x86 EXE假阴性stage现退出1；新三份真实固定x64 DLL缩小stage退出0；新backend/study_backend.exe错误x86候选退出1，三次文件字节均保持，任何候选均未执行 | release-x64-cli01.log/json，两个新stage及原失败stage保留 |
| Q -m ruff check backend tools | 0；完整静态通过 | release-x64-ruff01.log |
| Q tools/export_question_schema.py --check | 0；无协议漂移 | release-x64-schema01.log |

既有junction断言在全新自编样本目录按已核实权限执行，无跳过或降低；测试未碰个人学习库、原件或原工作区包。真实CLI的正确样本仅三份固定CPython/CRT DLL，不是完整产品staging，不宣称前端/后端组合运行、完整打包/安装器或ABI通过。前序完整build-release接入不变，本轮只审该调用及生产try/finally顺序，本地不重复未修改业务/桌面/冻结全量；最终head CI仍必须完整执行原工作流。

自审已读取完整检查器、既有枚举、全部调用方和相关夹具，核对路径范围（Windows大小写按lower）、根PE范围、后端主EXE与原生DLL/PYD、helper排除、错误先拒绝/关闭资源、既有安全检查保留及失败字节保持。未见本范围阻断问题。只有自审，无独立审查/批准，CI不替代审查；不把此切片冒充整个发行任务完成。交付需独立草稿PR及最终head全CI，未确认前保持待交付，不要求或授权合并/发行；旧题目目录恢复仍规划，不接模型或已取消人工测试。

提交前Q -X utf8 artifacts/release_x64_validate.py退出0：五份现有文件，其余436份#16基线保持；五份修改前备份匹配父head Git blob SHA，49份文档相对链接、UTF-8/LF/尾空白与规范字节git diff --no-index --check无告警。直接查看生产/测试差异时git diff返回1仅表示有差异，非验证失败。没有将artifacts、二进制或个人数据加入提交。

实际交付：[独立草稿PR #17](https://github.com/surface-user/StudyWorkbench/pull/17)，分支codex/release-x64-guard，base=#16最终b459f981ca5ba9c22ef8c621ee4ae7914f53cb96，实现c4019bc112050c259578e28d5e6a87d12d201178。复用既有分支，五份明确文本按规范UTF-8/LF Base64上传并逐项核Git blob SHA，远端实现commit差异仅五份；以expected_sha推进，无强推。task/原报告补实际链接，最终两份记录差异、远端五份回读及正式自审COMMENT随后核；最终head/完整CI运行/核对时间及交付结论在PR描述维护，不循环提交自身SHA。当前最终head CI尚未确认，待交付；只有自审，独立审查未取得，不因CI或切片交付销掉发行整体。原工作区两份改动、所有历史失败与恢复字节保留，不接模型/人工测试、不合并或发行，旧题目目录恢复继续规划。

## 2026-11-10 许可复制目标边界

### 需求、工具及设计范围

续接先核#17仍open/draft/unmerged，最终96678f482a5504263bc78a36bdcab1a5f2939068的CI #103（42772794606）success，仅有自审COMMENT。远端task blob ccf36dc71f8086274655157fbf766e200e7f1719匹配隔离源码；原根仍#7，仅原两份未提交，SHA256保持。既有五份x64改动及其余436份基线校验通过。独立分支codex/license-copy-boundary基于#17，不重复x64门禁。

依据AGENTS发行前审查传递依赖/实际二进制、task中M0-02/M1-04许可/SBOM未完成项及packaging-windows已有Python/Dart/native许可复制。先核工具：PATH无syft/grype/trivy/pip-audit/cyclonedx-py，固定Q环境也无相应包，未发现已配置漏洞数据库或标准SBOM生成链；不据此宣称它们不可安装或擅自引入。现有stdlib importlib.metadata、package_config.json、本地NuGet许可文件和已安装pefile/PyInstaller可用；本项不需新增工具、依赖或远端数据来源，不传输依赖元数据到第三方。

实际代码把Python分发名/RECORD路径、Dart包名直接拼为复制目的地，前置stage链接检查不能约束之后由这些元数据指定的路径。下一步用自编元数据及隔离哨兵复现写出许可根/覆盖，原源缓存和系统文件不改；仅修复制目的地：包目录名限普通ASCII包组件，文件必须相对并解析后仍位于该包目录；Python/Dart/native三个可变路径共用同一小函数。既有Python含..记录跳过、许可证筛选、Python/Flutter/固定JSON副本、stage重解析点及完整hash/x64门禁保持，不扩大为许可合规/漏洞/SBOM认证，也不承诺恶意构建依赖的完整沙箱。

计划为先红→最小修补→双Python相关回归、现有本地真实许可CLI、Ruff/Schema→自审、五份现有文件及独立PR/最终head全CI。修改前五份副本在artifacts/license-copy-base，继续本M0-02/M1-04原报告；原工作区、失败证据/学习数据保留。旧题目目录恢复仍规划，不接模型，人工测试已取消，不合并或发行。

### 实施、失败及自动化

补核数据来源后更正上述初步可用性描述：现行收集器确实设计读取本地NuGet目录，但当前隔离副本与原根的apps/desktop/build/windows/x64/packages均不存在；原根固定nlohmann JSON许可存在，隔离副本没有。故本次真实CLI只验证可用的Python/Dart/Flutter和固定JSON许可，NuGet复制行为用明确自编夹具验证，不把空目录冒充真实原生许可验证，不运行完整build-release或安装器。该缺失不阻碍本项目标路径修补；完整原生许可/SBOM仍未完成。

生产只在既有release_inventory内加license_destination小函数，三处动态目标共用：校验普通包目录名；拒绝许可文件驱动器/根路径、冒号（含ADS）和尾点/尾空格歧义；resolve后必须仍在该包目录。Python目标检查放在locate_file/复制之前，Dart/native在复制之前；不改变已有..项跳过、许可文件筛选、固定副本、元数据字段和hash枚举。无新依赖/模块/HTTP/UI/业务数据变化。既有收集测试的准备代码提为同文件fixture，原断言完整保留；新增16项，原37项保持。

初轮新增测试插在原x64用例最后一条断言之前，导致一条原断言误落在新正常用例里并产生NameError；这是本代理测试编辑错误，已把原断言归位，未删除或降低。首轮13失败中12项是未拒绝异常元数据，一项是上述测试错误，不能全部当产品缺口。保留日志、XML及目录。修正后旧生产实现12失败/38通过；只读检查保留的隔离escaped/LICENSE，确认3份哨兵变为self-authored license，未动用户文件。另补3个Windows歧义路径后，用新进程仅加载修改前工具副本（不回滚生产源码）复核：15个负例均失败，正常许可复制1通过，37未选。

包名负例覆盖Python/Dart的父路径、绝对路径、正/反斜线嵌套及点目录；另覆盖Python绝对RECORD在包内/包外、ADS及尾点/尾空格。断言源/哨兵和既有stage字节保持、stage外没有新文件；允许Dart失败之前已经生成的合法Python许可副本留在失败stage，不假装整个生成器原子回滚。正常例核Python嵌套dist-info许可、Dart/native许可、原始来源字节和输出hash。旧junction/x64/集合/路径/数据库/CRT守卫全部执行。

cwd为隔离源码副本，P/Q沿用前文。实际命令：

| 命令 | 退出/结果 | artifacts/ |
|---|---|---|
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/lc-red01 --junitxml=artifacts/license-copy-red01.xml | 1；13失败/37通过、3.86秒，其中1项测试编辑错误，不全算产品失败 | license-copy-red01.log/xml |
| 同命令，basetemp=lc-red02，junitxml=license-copy-red02.xml | 1；12预期产品失败/38通过、3.46秒；哨兵现场保留 | license-copy-red02.log/xml |
| Q -X utf8 artifacts/license-copy-baseline-red.py | 1；15负例失败/1正常通过/37未选、2.63秒；只在该进程加载父工具，无生产源码回滚 | license-copy-red03.log/xml，lc-red03 |
| P -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/lc-p01 --junitxml=artifacts/license-copy-p01.xml | 0；最终53项、3.18秒 | license-copy-p01.log/xml |
| Q -X utf8 -m pytest backend/tests/test_release_inventory.py -q --basetemp=D:/computer_work/project/StudyWorkbench/.local/lc-q01 --junitxml=artifacts/license-copy-q01.xml | 0；最终53项、2.99秒，P结束后串行 | license-copy-q01.log/xml |
| Q -X utf8 artifacts/license-copy-cli-probe.py | 0；在全新合成构建根运行原CLI，71个真实Python分发、75个本地Dart包及真实Flutter/固定JSON许可，262文件（261许可）hash集合匹配；四份抽样来源字节保持 | license-copy-cli01.log/json |
| Q -m ruff check backend tools | 0；完整静态通过 | license-copy-ruff01.log |
| Q tools/export_question_schema.py --check | 0；协议无漂移 | license-copy-schema01.log |

真实CLI将package_config中的相对rootUri换为原位置对应的绝对URI，仅写新合成构建根的配置，不改原配置/依赖缓存；复制当前工具到该根后按其真实参数入口运行。NuGet目录明确为空夹具；固定JSON许可从原根已下载文件复制，源不变。样本不是完整产品或SBOM，不以71个构建环境包数量推断发行模块/传递依赖完整性。本地未重复未改业务/桌面/冻结全量，最终head CI仍必须执行原完整工作流；本轮没有执行漏洞数据库扫描、完整setup编译/安装或取消的人工测试。

### 自审及交付

完整审查收集器全部复制点、build-release唯一生产调用及check_release的stage_files调用，确认三处动态目标经同一门禁，Python检查在locate_file之前；固定Python/Flutter/JSON目标无元数据路径输入，现有stage链接前置拒绝不变。初次异常名称在Python之前未复制，在Dart之前可能已有合法副本，测试如实容许该非原子行为；失败不删除或覆盖用户数据。Windows歧义拒绝及现有格式输入的实际CLI已核。该工具仍要求稳定staging，不承诺并发恶意目录替换或不可信构建环境完整隔离，也不验证许可法律义务或源缓存可信性。

本项只有自审、无独立审查/批准，自审未见本范围阻断代码问题。下一步核五份差异与其余基线保持，创建独立草稿PR、补实际链接并核最终head完整CI，未确认前待交付；CI不计独立审查，发行整体仍进行中。原工作区两份改动、学习数据及所有旧失败保留；不接模型、旧题目目录恢复不实现，不合并或发行。

提交前Q -X utf8 artifacts/license_copy_validate.py退出0：五份现有文件，其余436份#17基线保持；修改前备份匹配父head Git blob SHA，49文档相对链接、UTF-8/LF/尾空白与规范字节git diff --no-index --check无告警（差异查看返回1仅表示有变化）。全部原始日志/夹具/许可副本均留在忽略的artifacts或.local，不随PR上传，不读取个人库。
