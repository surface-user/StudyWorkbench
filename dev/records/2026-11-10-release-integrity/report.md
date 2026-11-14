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

实际交付：[独立草稿PR #18](https://github.com/surface-user/StudyWorkbench/pull/18)，分支codex/license-copy-boundary，base=#17最终96678f482a5504263bc78a36bdcab1a5f2939068，实现295380020ab5c1146493e5587718d0162124c3f4。提交前父head再次核实未变，五份明确文本按规范UTF-8/LF Base64上传并逐项匹配Git blob SHA，远端实现commit差异仅五份；以expected_sha推进，无强推或覆盖他人分支。task/原报告补实际PR链接；最终两份记录差异、五份远端回读与正式自审COMMENT继续核对，最终head/完整CI运行/检查时间及交付结论在PR描述维护，不循环提交自身SHA。当前最终head全CI尚未确认，保持待交付；只有自审、无独立审查/批准。整个发行任务及task仍进行中，不合并/发行，不接模型/人工测试，不实施旧题目目录恢复，原工作区改动及全部失败证据保留。

## 2026-11-10：PLAN-03，本批分析与暂缓安排

本轮用户要求阅读agent/task并分析SBOM、传递许可、漏洞、签名/发行、Office Java缺口及复杂解析/下载等规划任务，要求暂缓审查/人工测试至任务完成并逐小任务PR。本切片仅完成现状分析、有限任务拆分和执行规则落地；以下方案均非实现/扫描/签名完成结论。既有本报告、各功能原报告和所有失败保留，不新建平行发行报告。

### 基线与本轮实测

根工作区仍为codex/recovery-note-copy/a959b9f，存在原未跟踪.vscode/和交付summary.md；保持原样。已读取根AGENTS/requirements/architecture/question-content-spec/task/dev规则，核对隔离源码与远端#19最终197a27695f6eef502c71e362248cbff0c31f1a96。AGENTS/requirements/路线/ADR0013与根同字节；后续architecture/question-content-spec已补读。代码/接口影响按最新源码定位，不在旧根重复实现#8–#19。本轮从GitHub连接器逐文件读取AGENTS、task、ADR0013和本报告，绑定该commit/blob；规划在新的忽略目录.local/release-task-analysis-20261110/work/准备，不改原隔离源码或用户包。

- GitHub查询#19当前head 197a276的PR工作流：run 42794594783 / #115，completed/success；本轮只核工作流级状态，未重读全部job日志，不把该父head CI当新切片CI。#16–#18内容已查阅，仅作为已实现边界依据。
- 固定Q（原根.local/release-venv/Scripts/python.exe）运行只读pefile检查：program/officebean.dll为AMD64/0x8664，导入jawt.dll、USER32.dll、KERNEL32.dll、VCRUNTIME140.dll及api-ms-win-crt-runtime-l1-1-0.dll；固定Office目录枚举jawt.dll/jvm.dll结果为空，退出0。未加载DLL或启动Office。原整包门禁日志manual-check-release01.log末行同为officebean.dll/jawt.dll，旧退出1保留。
- 已读取本地交付build-info.json：该包输入为37a8d55/CI #113，基础包与可选Office分开；installer_signature=NotSigned、整包Office=blocked。此为现有元数据读取，未本轮重跑其业务/安装/签名验证；独立Office的成功不证明整包或Java闭合。
- shutil.which只读检查syft/grype/trivy/pip-audit/cyclonedx-py/signtool在当前PATH均未发现，退出0。仅说明PATH可用性；不声称机器没有工具/证书，也未读取密钥或修改全局环境。
- 尝试本地git clone --no-hardlinks --no-checkout --local . .local/release-task-analysis-20261110，退出1，MSYS NtCreateDirectoryObject权限错误；未改变原库或重复提权。一次匿名GitHub Git commit GET退出1/HTTP403 rate limit；随后使用现有连接器成功取得相同commit/tree元数据。未关闭TLS或改网络配置。后续创建PR使用连接器，不依赖本地克隆。
- 文档检查与本切片PR/CI记录见下方；实际命令、错误输出与规范文本副本留在本切片artifacts，本报告不收整目录日志/个人数据库。

### 分析结论、影响范围与依赖

1. **发行准备是独立的多项工作。** 现有release_inventory收集构建环境元数据/许可并给payload hash，check_release检查集合、关键x64头及普通PE导入；它们不是完整依赖图、SBOM、漏洞匹配、分发义务或实际DLL搜索路径证明。REL-01分别从源码锁文件/包元数据和真实冻结payload/安装器payload取证，覆盖Python打包模块和native、Flutter/Dart编译内容、NuGet、CRT、WebView2离线安装器、Office、选定Java及嵌入媒体组件。版本、PURL/标识、许可、来源、文件hash和依赖关系可追溯，构建工具和实际分发组件区分；未识别组件标未知。最终包中没有的开发依赖不冒充运行组件，安装器额外带入的WebView2不得漏记。
2. **标准工具优先于自写扫描框架。** 候选Syft可作为多生态目录/二进制采集器；需先锁定版本/hash/许可证并验证Windows支持与识别缺口。其文档列出Dart/.NET/Python/C++等生态，不代表它能从Flutter app.so或PyInstaller压缩内容恢复全依赖图。锁文件证据与冻结源码/二进制清单必须对照。REL-03可评估Grype扫描标准SBOM，必要时pip-audit补Python锁定依赖；固定数据库快照、时间、扫描配置和不支持项。不能把工具零发现当“无漏洞”，不在本轮安装工具/扫描数据库或自动升级全部依赖。
3. **传递许可不能只复制根LICENSE。** REL-02将实际组件逐项映射通知、版权、嵌入native许可和来源/源码提供义务；特别覆盖PDFium、Python打包器例外、Office组合组件，以及未来Java/FFmpeg。未知许可或二进制来源必须保留未闭合状态。暂缓的是开发/PR代码审查，用户此次明确要求的许可与漏洞技术检查仍是任务；法务批准未取得时不声称已获批准。
4. **Java缺口有确定文件证据，但分发方案尚未确定。** 为保持“Office整包”完整，需要评估固定app-local x64 Java运行时及其完整递归依赖、许可/来源、隔离环境和真实加载路径；不能只复制jawt.dll、更不能把开发机JAVA_HOME/PATH当用户依赖。Office官方支持显式选择匹配架构的JRE；本地office_runtime.environment目前只给转换器目录及System32等受控路径，纳入Java后还必须设计只对子进程生效的路径/配置。另一条非Java精简组件路线必须另有组件规范、来源/新清单和禁用功能证明，不在本轮随意删除officebean.dll或把它加入忽略表。基础主包+独立可选组件仍可保留，但不据此关闭OFF-02整包缺口。OFF-01先诊断加载闭合并定方案，OFF-02再实现/真实转换复验，影响stage/lock/check_release、office_runtime、打包指南/依赖登记及测试。
5. **签名需要指定发行身份。** REL-04可先准备显式签名配置、失败停止及验签流程；签名证书/服务和发行者本轮未指定，这是实际签名所需输入，不猜测用户没有证书、不申请付费服务或伪造已签。采用SHA256与RFC3161时间戳，分别验证项目exe/安装器，第三方有效签名不抵销项目未签名。payload签名后再生成payload hash/SBOM及清单；安装器编译/签名后才生成外置交付hash，避免签名改变已登记字节或清单自引用。REL-05只在实际纳入候选包的组件固定后收口；正式发布/合并另需授权。
6. **复杂解析拆成可测的小项。** 当前documents采用25秒子进程、PDF拆题20页上限和显式题号单栏裁切；question_splitting.START/块流不等于OCR/多栏理解。FMT-01先补复杂Office/XLSX与无短名卷样本，PAR-01在原候选/预览链扩复杂题号和共享材料，PAR-02将多栏/OCR分别设计与实现，PAR-03才处理较大文档分块。先确定原件/页区间/阅读顺序、标注来源、置信或拒绝提示、预算和恢复协议，再扩worker/服务/UI/样本/测试/备份关系；不直接提高上限、不猜标准答案、不改旧确认版/历史。OCR离线组件/语言资源/许可尚未选定，不自动下载模型或发送文档。
7. **下载已有核心，先补真实证据。** 当前标准库实现HTTPS直链、持久队列/attempt、暂停/显式恢复/入库与备份。DL-01在允许公网DNS环境对有权获取的公开来源核独立hash和恢复/入库/备份；旧Commons DNS失败继续保留，不能为了联网测试放宽禁止网段。DL-02再明确目标站点和固定提取组件、质量选择及UI，DL-03再纳入固定FFmpeg实际构建/许可与受控合流/转码，复用原队列/入库/取消预算，分别PR。站点名单未定不等于全站、登录/DRM绕过被授权。
8. **其他规划保持有限边界。** M2-05已实现的三方合并、容量报告和旧题巡检不重复；未登记目录恢复/清理仍需身份、关系、收据与用户同意规则。M3-03按作答/知识/复习/规模分别设计；WebView/媒体只继续可自动化矩阵。R6维持已授权的本地受控读取和候选确认，暂不接模型/凭据；通用资料/新场景先明确，不把“其他功能”解释为无限新增。原任务、失败、未完成项继续保留。

任务编号/状态/下一项只在task维护，报告解释取舍与命令。各实现PR必须覆盖实际调用方、测试/夹具、打包配置和相应契约；没有接口/模型变化时不批量重写规范。此文档切片只修改AGENTS、task、ADR0013替代关系、新ADR0014及本原报告五份文件；不改业务、测试、依赖、安装包或个人数据。

### 官方资料与使用边界（本轮联网核实）

- [Syft支持生态](https://oss.anchore.com/docs/capabilities/all-packages/)与[Windows安装说明](https://oss.anchore.com/docs/installation/syft/)：用于工具候选评估，不表示本轮已选定版本或完成扫描。
- [Grype官方仓库](https://github.com/anchore/grype)、[pip-audit官方仓库](https://github.com/pypa/pip-audit)：用于明确SBOM/已知漏洞的工具分工，不据此声称覆盖所有嵌入二进制。
- [LibreOffice 26.8 Java配置](https://help.libreoffice.org/latest/en-US/text/shared/optionen/java.html)：JRE选择及架构匹配；未以此代替当前officebean.dll的本地导入检查。Wiki FAQ被反爬拒绝，未引用其不可读内容。
- [微软SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)及[验签策略](https://learn.microsoft.com/windows/win32/seccrypto/using-signtool-to-verify-a-file-signature)：SHA256/时间戳及/pa验签；实际发行身份尚未指定。

本轮代码审查按用户要求暂缓，不执行独立审查/请求review；只做文档一致性和自动化校验，不称自审通过。人工/Computer Use暂停，不等待旧反馈，不运行用户应用或安装器。完整SBOM/传递许可/漏洞、Java整包修复、复杂解析/下载和签名均仍未完成；只交付分析/任务拆分PR，不销掉父任务。未合并/发行。

### PLAN-03 文档自动化与交付准备

本轮Q执行文档assert检查退出0：五份明确文件UTF-8/LF/末尾换行/无尾空格、60处相对链接解析、全部46条原任务表行逐字保留、原报告历史前缀保留、15个后续实施/设计切片存在；与#19远端读取的base及当前隔离源码一致。收据为.local/release-task-analysis-20261110/artifacts/docs-check01.json，包含五份规范Git blob SHA。git diff --no-index --check base work未发现空白错误；仅提示本机autocrlf可能转换LF，不修改该全局设置。随后git -c core.autocrlf=false diff --no-index --check base work返回1且无错误输出（no-index检测到两目录有差异的返回码），不将其记录为退出0；换行/尾空格由上述assert明确校验。git status --short仍只有原.vscode/与交付summary.md两项未跟踪内容。

本轮只改文档，未改业务/测试/依赖或包，故本地不重复后端/Flutter/冻结/Office运行及安装器全量，保留原CI配置并要求本PR当前head CI。代码审查按要求暂缓，未提交review或自行冒充审查完成；人工测试暂停。本小任务实现为分析/任务文档交付，不代表15个后续切片完成。独立草稿PR及当前head CI待创建后核实，后续结论在本报告/PR描述维护。

实际交付：[独立草稿PR #20](https://github.com/surface-user/StudyWorkbench/pull/20)，分支codex/release-and-capability-task-plan，base为#19的197a276，分析实现提交37d09c8b14b1a8fa21cb0f86d4190487563bc6e4，仅五份文档。已附加到当前聊天；task/本报告补实际链接，最终head CI以PR当前记录为准，不循环提交自身SHA。代码审查暂缓、人工暂停；整个发行/规划任务仍未完成，未合并/发布。

## 2026-11-10：PLAN-05，任务遗漏补登与后续拆分

用户在“检查task.md是否还有遗漏的任务”之后要求推进，并明确选择“补齐任务表并交付PR”。本轮只补登记和交付文档，不实施新功能，不把新行登记为功能完成；代码审查/人工测试沿ADR0014继续暂缓。此为PLAN-03分析的补漏跟进，续写本原报告，不另造任务流水账。

### 依据、范围与设计

以#20最终defd9d4695e79cd030eb14ed9251ce0326ea0d91为基线，当前父head的CI #120（42797730833）本轮查询为completed/success，仅作为父基线，不抵销新PR的CI。已完整读取现行AGENTS、requirements、architecture、question-content-spec、task及dev记录规则，补读ADR0014、契约/API/打包指南与Agent边界；不依据根目录仍在#7的旧task重复开发。原根两项未跟踪内容及原隔离源码/交付包保持。

四项缺少明确承接的依据与补登：契约第6节“TXT资料全文另列后续”→LW-04a；契约第8节下载UI最多100条及更广历史→LW-07a；packaging-windows规划中的自动升级/完整回滚→UPD-01；api-spec规划中的error.code/message/request_id未形成公共契约→API-01。TXT搜索和下载历史继承原范围，统一错误协议仍须兼容现有detail；升级/回滚须保护旧库，不自动执行数据库降级。现行契约保留、不改业务协议或UI。

PLAN-04保留为汇总，新增有限后续切片：M2-05i恢复/重新登记设计、05j留存/清理策略设计；M3-03a富内容作答、b知识体系、c复习校准、d规模回归；WEB-01可自动化网页安全/生命周期矩阵、MED-01媒体编码/状态矩阵；R6-01授权受控读取设计、R6-02模型/凭据/其他候选场景的后排评估。所有项标待设计/细化/确认且未实施，原M2-05a–h和M3/WebView/R6条目不删或重写。清理、模型、新场景和发行仍保留各自授权边界。

按ADR0014单列REV-01集中代码审查收尾，当前不执行/请求审查；依赖最终确定的开发/自动化切片，REL-05先做候选组装验证，再在正式发行准备阶段依赖集中审查，避免自循环。人工/Computer Use不自动恢复。单空间备份合并、精细选区、外部目录原地工作区/监听仅保留后排候选状态，不塞进本批实现。原失败/未知证据保留，不补记通过。

本轮影响仅docs/task.md和本原报告两份文件：任务表新增PLAN-05、4项补登、10项原总项细化及REV-01，共16行，分别列范围/依赖/状态/退出证据；本报告记录依据、命令与交付。调用方、夹具、配置、导出、依赖、业务/数据库/API、安装包均不变，无须同步改一串规范或引入测试框架。后续代码功能仍逐项独立PR和相关自动化，不预建未定实体/接口。

### 本轮校验与交付边界

规范文本及基线副本在新的Git忽略目录.local/task-gap-plan-20261110，原始校验收据/命令日志写artifacts/task-gap-plan-20261110。验证仅针对文档：UTF-8/LF/空白、相对链接、编号唯一、全部原任务行与原报告历史前缀、范围/依赖/待实施状态、预定两份差异及远端blob一致性。实际校验结果与本PR链接后补，不沿用此前数字。无业务/依赖改动，本地不重复后端/Flutter/冻结/安装器全量；新PR当前head CI照原完整工作流执行，查询前保持待交付。代码审查暂缓，人工暂停，未合并/发布。

### PLAN-05 实际文档自动化

工作目录为原仓库根，Q=.local/release-venv/Scripts/python.exe；验证脚本/日志仅在Git忽略的artifacts/task-gap-plan-20261110，不入产品或PR。首轮Q -X utf8 artifacts/task-gap-plan-20261110/check_docs.py退出1：检查器把新表头也计为任务，得到17行而非16；这是文档检查器计数错误，已保留docs-check-first-failure.txt。修正为明确核验16个唯一任务ID加1个精确表头，未删除文档条目或降低状态/历史保持要求。

随后同命令退出0：两份明确文件UTF-8/LF/单末尾换行/无尾空格、60处相对链接、3处新增锚点、64条原表格行逐字保留、新增16个ID唯一且功能项均未实施/未执行、原task前后正文及原报告全部历史前缀保持。输出docs-check01.json包含实际规范Git blob SHA；补PR链接后的最终字节会再次校验并对照远端。没有运行业务/安装/窗口测试；本PR当前head完整CI另核，不拿#20结果代替。代码审查和人工测试暂缓，尚未合并或发行。

实际交付：[独立草稿PR #21](https://github.com/surface-user/StudyWorkbench/pull/21)，分支codex/task-gap-followup，base为#20最终defd9d4，实现提交f0a70189680a7d1c31de077ed4168ffc03312165，仅两份文档。已附加当前聊天，task/本报告补实际链接；最终head、CI运行/核对时间及PLAN-05开发交付结论在PR描述维护，不为写入自身SHA反复提交。其余新增功能/设计仍未实施，代码审查暂缓、人工暂停，不合并或发行。

## 2026-11-11：OFF-01，固定Office加载链诊断与OFF-02输入

承接持续开发授权，本轮仅完成OFF-01有限诊断。先核最新#21仍为2010bda927f9abb2f0900ee325e8ae60a6c5235b，其CI #125 / 42803117625为success；根仍为#7且仅原.vscode/和交付summary.md未跟踪，两处工作树与原包不改。相关聊天状态核对未发现另一项正在修改Office的工作，源协调聊天处于idle，不重复派发。完整阅读现行开发约束/requirements/architecture/question-content-spec/task，补读ADR0009/0014、Office执行/准备/清单/发行校验及dev规则。代码审查与人工/Computer Use仍暂缓，不接模型，不执行安装或用户窗口，不恢复旧题目录。

### 范围和证据方法

无生产代码、UI、协议、依赖或固定组件变更。只读核官方固定组件，复用现有OfficeRuntime.verify、输入门禁、profile_configuration、WindowsProcessJob及受控命令/环境，对自编DOCX/PPTX在新隔离目录运行自动化转换；数据只写本轮artifacts/off01-20261111和.local/off01-run-20261111。Q为原根.local/release-venv/Scripts/python.exe，cwd为原仓库根；不碰个人库，不终止其他进程。

静态扫描检查.exe/.dll/.pyd/.com/.bin的MZ文件、普通/延迟导入、程序目录候选递归图和重名路径；系统DLL作为叶节点，不冒充Windows loader完整模拟。首轮辅助扫描器按大小写敏感的字典找程序目录，误报8条候选缺失；static-first-case-sensitive.json保留。按Windows名称语义修正casefold路径索引并增加实际大小写断言后重跑；原DLL、清单、生产检查器均未改，最终图不含该误报。

运行采样仅查询每次转换自己持有的Windows Job进程列表，再用Toolhelp快照取其中模块；不收集其他进程名称/模块。10ms为请求间隔，枚举耗时与模块生命周期使覆盖不完整，不能保证捕获所有短命加载。探针先核Win64结构大小和本进程Python模块读取，再断言两种真实格式页数/原件字节、模块采样及Job清理；句柄/线程均有结束处理。进程切换时snapshot错误299/24/87/18计数原样保留，不将缺少观察解释为绝不加载。源进程使用现有Office命令/profile/Job；本轮冻结证据仅43模块源码一致性，未重跑冻结Office HTTP全流程，不将源采样冒充冻结加载全跟踪。

### 本轮结果

- 固定runtime-lock SHA256为147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca；19417文件、声明1577045386字节前后完整核验通过。组件version.ini的buildid为bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1。未新增Java，jawt.dll/jvm.dll不在组件中。
- 244个PE中，普通导入在全包名称+本机系统可用性范围仅发现officebean.dll缺jawt.dll；4条延迟导入是cli_cppuhelper.dll的cppu3/cppuhelper3MSC/sal3，以及mergedlo.dll的shell32。它们与Java动态加载是不同证据，不能把无额外延迟缺口推成Java闭合。
- soffice.com/soffice.bin为实际启动链；程序目录候选递归图含54个组件PE，本机系统DLL作叶节点时无未解析普通/延迟边。officebean独立根仍缺jawt。现有check_release仅遍历.exe/.dll/.pyd普通导入，不遍历上述.com/.bin或延迟导入，而且用全包basename判断存在；本轮不修改它。该覆盖限制是OFF-02/发行校验设计输入，不以诊断绕过原门禁。
- 同名PE有13组：Office/program与嵌入Python子树的OpenSSL/SQLite/Python，以及System/System64的CRT等。System为x86（0x14c），System64为AMD64（0x8664）；全包同名并不证明加载了正确目录/架构。嵌入Python的_ctypes.pyd还从其lib目录关联libffi，不宜把所有子进程强行当同一程序目录解析。
- 两个自编输入各生成2页PDF，源字节/hash保持。Job内8个进程取得6544次模块快照、2243次Job查询；共观测170个不同模块，其中74个来自Office目录。模块枚举错误299=120、24=17、87=1、18=1，属于不完整采样证据，保留在原JSON。
- 采样中soffice.com与soffice.bin来自固定program；jvmfwklo.dll/jvmaccesslo.dll已加载，但未观察到officebean/jawt/jvm。这只说明两条受测静态转换未观察到Java运行分支，不证明所有Office功能不需要Java。Office/program/python313.dll及pythonloaderlo.dll也被加载；禁用Python脚本不等于可以从SBOM或分发包中排除这些二进制。
- MSVCP140、MSVCP140_1、MSVCP140_2、VCRUNTIME140及VCRUNTIME140_1实际观察路径为Windows/System32；未观察到从组件System64加载这些CRT。宿主机有CRT时转换成功不能证明无开发依赖环境闭合。另有1个未分类宿主扩展模块AudioDevProps2.dll，未断言其提供者或可分发性；后续环境隔离验证必须保留这一限制。
- 在独立Q子进程中清除继承DLL目录并限定DLL_LOAD_DIR|SYSTEM32，固定officebean.dll加载失败，WinError126；探针对该预期负例断言通过。未加载Java或改变系统搜索路径配置。此为桥接负例，不是Office全功能通过。

### 分发方案与OFF-02必须明确的输入

诊断结论：**目前证据支持继续保留基础包+未经裁剪的独立Office静态转换组件；该分发边界继续明确Java桥接/整包依赖未闭合。** 若目标为包含完整Office的安装器，必须补充真实Java与CRT方案，不能通过删officebean.dll、复制单个jawt.dll或忽略缺失项来销项。本次只给出方案与输入，不替用户决定新增Java或重制非Java组件。

| 后续路线 | 需要明确/验证的事项 | 当前结论 |
|---|---|---|
| 维持基础包+独立完整Office | 继续只声明受测静态DOCX/PPTX分页及现行边界；依赖/许可/SBOM持续如实登记 | 已有分发可保持；不称整包缺口修复 |
| 完整Office整包 | 用户确定允许新增固定x64 Java运行时；再评估发行者/精确版本、官网来源/hash/签名/许可与来源义务、维护更新和体积。核JVM、AWT/jawt及递归native依赖；设计仅对子进程生效且可被Office识别的Java配置、CRT加载根/架构，避免借宿主JAVA_HOME/PATH/已装CRT蒙混通过 | OFF-02仍未实施；来源/版本/布局和依赖方案未选定，不下载、不注册系统Java、不修改全局环境 |
| 新的非Java转换组件 | 单独定义来源/构建开关/许可/功能删减、组件布局与新清单，复验输入门禁、字体/公式/图表、进程/缓存及不支持项 | 改变固定组件需另行方案确认，不能直接删原组件DLL或改旧锁冒充同包 |

OFF-02还须决定新增组件与原Office锁的关系：原组件字节/官方锁保留，新增依赖独立锁定；若布局或组件本体改变，应按新的明确组件规范生成新锁，不能静默改原锁。发行检查须按实际加载域区分backend、Office/program及嵌入helper，考虑.com/.bin、delay和已识别动态分支、重名/架构及系统前置条件；检查加强也要保留原失败/断言，不能加入忽略名单。随后才验证无开发Java/CRT借用的自动化环境、实际加载路径、冻结DOCX/PPTX/Calc、取消/重试/重启、源hash、许可/SBOM与升级配置。当前没有已选JRE可扫描，不能声称Java递归闭合或全功能兼容。

### 版本绑定的官方依据

直接依据为上述固定二进制、配置和本轮采样。另已读取与本地version.ini相同buildid的上游源码： [vendorbase.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/jvmfwk/plugins/sunmajor/pluginlib/vendorbase.cxx)、[sunjavaplugin.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/jvmfwk/plugins/sunmajor/pluginlib/sunjavaplugin.cxx)、[framework.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/jvmfwk/source/framework.cxx)和[Windows Office Bean](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/bean/native/win32/com_sun_star_comp_beans_LocalOfficeWindow.c)。源码说明从所选JRE路径查找运行库、动态加载并查找JNI入口，Bean通过AWT接口取窗口；固定jvmfwk二进制的LoadLibraryW导入、jvm.dll/JNI字符串与此一致。源码关联不是Java候选的实际运行兼容证明。

[LibreOffice Java官方帮助](https://help.libreoffice.org/latest/en-US/text/shared/optionen/java.html)要求架构匹配并说明Java选择配置；[微软DLL搜索顺序](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)说明依赖按加载规则解析，不能以任意子目录同名文件代替实际路径证据；[Toolhelp快照说明](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot)明确加载变动可能导致失败/不完整。最初web请求26.8.1.1标签两个源码URL返回cache miss，未引用其不可读内容；后改用本地buildid的GitHub连接器读取成功，master内容仅作查找线索，不当成该版本证据。

### 实际命令、退出码与限制

| 命令（Q如上，原仓库根） | 退出/结果 | 原始产物 |
|---|---|---|
| Q -X utf8 artifacts/off01-20261111/scan.py（首轮） | 0；244PE/唯一jawt缺口正确，程序目录图因扫描器大小写误报8条，保留后修正 | static-first-case-sensitive.json；非生产故障 |
| 同命令，修正casefold索引并加真实路径断言后 | 0；19417文件核验、244PE/4delay/13重名组、54节点候选图 | static.json、static-final.log；辅助源码scan.py |
| Q -X utf8 artifacts/off01-20261111/sample_loads.py | 0；真实受控Job转换及模块采样、自编DOCX/PPTX各2页、源字节/线程/句柄/组件核验；错误计数保留 | loads.json；辅助源码sample_loads.py；隔离.local/off01-run-20261111 |
| Q -X utf8 -，固定officebean LoadLibraryEx负例 | 0；加载预期失败126；未引入Java或复制DLL | bridge-load.json |
| Q -X utf8 .local/markdown-merge-followup-src/tools/check_frozen_sources.py --exe dist/StudyWorkbench-Release-20261110-37a8d55/app/backend/study_backend.exe | 0；43冻结模块与当前业务源码一致 | 本轮命令输出；现有包保持不替换 |
| Q -X utf8 -，筛选诊断摘要 | 0；筛选与脱敏来源/理由写入摘要，未复制完整原始目录 | [精选证据](evidence/off01-summary.json) |

精选JSON只保留具体结论所需的计数、缺失/延迟/重名路径、Java/CRT/Python观察、来源hash和局限；移除全部原始模块路径表、PID、profile、PDF、二进制及测试数据库。scan.py/sample_loads.py及原始数据仅在本地artifacts，以摘要中的hash标版本，不自动将原始目录晋升evidence。该证据是诊断，不是完整SBOM、许可/漏洞、独立审查、干净机或正式发行证明。

本轮交付仅task两行/日期、本报告追加和一个精选JSON；没有代码/测试/依赖/配置/旧组件变更。独立草稿PR与最终head CI待创建后核验；代码审查暂缓、人工暂停，不合并或发布。OFF-01诊断不取消OFF-02、发行总项或其他未完成任务。

### OFF-01 文档与证据校验

Q -X utf8 artifacts/off01-20261111/check_docs.py退出0：三份明确文件UTF-8/LF/尾空格、62处相对链接、原82条表格行数量不变（只更新OFF-01/02两行）、其他任务正文逐字保持、原报告全部历史前缀保留。精选JSON解析/唯一jawt缺口、无误报的启动候选图、两格式各2页及负例126/采样错误保留断言通过；Git blob收据在docs-check.json。git diff --check退出0，根status仍仅原两项未跟踪内容；本轮未改变原工作区/固定组件/交付包。本地没有重跑未修改的后端/Flutter业务全量，新PR当前head完整CI仍须核验；父#21绿灯不代替该结果。没有代码审查或人工测试通过结论。

实际交付：[独立草稿PR #22](https://github.com/surface-user/StudyWorkbench/pull/22)，分支codex/office-loader-diagnosis，base为#21最终2010bda9，实现e0469205ac62bbd97a46c601e94cacd876f4ef3f，三份明确文件；task/本报告补实际链接，已附加聊天。最终head/当前head CI运行与核对时间在PR描述维护，避免为记录自身SHA循环提交。OFF-01仅诊断交付，OFF-02与发行整体继续未完成；代码审查与人工暂缓，不合并或发布。
## 2026-11-12：PLAN-06，并行调度与依赖核验

用户设定持续实施目标并明确由主 Agent 同时启动三个子 Agent。当前有效入口为 docs/task.md，目标中的 doc/TASK.md 与 doc/tasks.md 不存在，不创建平行目录。根工作区仍位于 #7，保留原两项未跟踪文件；通过远端 Git tree 与 blob hash 从现有副本重建 #22 ae4ecf5 的444个文件，作为隔离基线，不依赖旧根任务状态。

已逐项核对当前未完成任务的依赖，新增调度状态表；父任务和旧失败保持。先领取 REL-01a、PAR-01、LW-07a，分别使用 .local/goal-20261112 下 sbom/parsing/downloads 独立目录，进入 IN_PROGRESS；实现后 REVIEW，主 Agent 检查自动化、文档、独立草稿 PR 及当前 head CI 后才能 DONE。代码审查依 ADR0014 暂缓，REVIEW 不冒充独立审查批准，人工测试继续取消。OFF-02缺分发决定；REL-02至05、DL-03、UPD-01、M2-05j、R6-02及REV-01的前置或外部决定明确保留，其余可先开展的有限设计/实现为READY。

本轮核实 #22 最终 head 的 CI 43007287613 为 completed/success，因此 OFF-01诊断开发交付记DONE，整包仍未闭合。REL-01a仅覆盖可独立开展的源码锁文件标准SBOM，REL-01父任务仍进行中，不能抵销最终冻结/原生/Office/安装器覆盖。主任务持续有效，不因本次调度文档交付缩小为三个子项。

PLAN-06仅修改AGENTS.md、docs/task.md和本报告。准备脚本逐blob验证444文件退出0；首次文档补丁因工具拒绝同路径双操作、后续日期上下文不符均未改动文件，改用精确上下文完成。文档检查核对原任务行/报告历史、状态与引用、UTF-8/空白及仅三份改动；命令与收据放artifacts/goal-20261112。业务代码未变，本地不重复业务全量，独立PR仍执行完整当前head CI。PR创建后在其描述补最终head/CI结论，未核实前保持REVIEW，不合并或发行。

## 2026-11-12：REL-01a 源码锁文件标准SBOM

本切片依据REL-01和并行调度，状态IN_PROGRESS→REVIEW；基线为#23的2645366ca4f37cced53f41119ccebd732239a123，完整REL-01仍进行中。影响仅新构建命令tools/source_sbom.py、backend/tests/test_source_sbom.py、依赖/打包说明、本task条目及原报告；无产品调用方、API/数据库/运行依赖/打包门禁变更。读取的输入固定为backend/requirements.lock.txt与apps/desktop/pubspec.lock，不扫描机器环境或个人资料。

### 设计与实施

固定Anchore官方Syft 1.57.1 Windows amd64（发布2026-11-09）：官方zip 30255314字节、SHA256 3a01fe865076bb548352195b77e88fa4649277861ea458efe165c3a810b6dcc7；checksums文本SHA256 92466b2b1a4695ee908f8a1567f4ff074e0fbb4f34da28463927a2630901fe2c；实际exe SHA256 42deb23bff7852997bf0316a540d3dcb364953273152749205e47881dd270c53。官方发布资产digest与既有下载核对一致，exe每次执行前核验；保留Apache-2.0 LICENSE，工具不随产品分发。Authenticode为NotSigned，Sigstore未验证，不把hash当签名证明。来源与维护链接在dependencies.md，工具生态/安装依据为Anchore官方文档。

真实探针发现Syft会将Dart sdk占位0.0.0推断成Flutter约束下界3.44.0，不能据此宣称实际SDK版本。本实现以PyYAML（既有依赖）读取精确锁，将SDK项明确列入excluded_sdk_components，再仅把Python锁原字节和Dart hosted/Git投影交给两个指定cataloger；报告分别记录原锁与投影hash。Python拒绝非精确pin/重复；Dart hosted要求当前pub.dev/hash，Git要求HTTPS无凭据、完整resolved-ref与根包，不支持的来源明确失败。SDK仍未知，整个产品SBOM完整状态恒为false。

配置显式禁用更新与联网补全，清除继承的SYFT_*配置影响；不下载包/Git源、不触碰Office或Java。生成固定CycloneDX 1.6后逐项比对PURL、名称/版本、Git commit或host、来源位置以及两份投影文件SHA256，缺失/额外/重复/错误均失败。读取前拒绝链接/重解析路径与超过1MiB的锁文件，输出必须为新目录，结束复核原锁字节。超时、工具非零、结果不一致保留现场但不写成功comparison.json。标准BOM含时间戳/UUID，重复性指包集合和输入hash，不承诺逐字节相同；非恶意构建机器沙箱或原子文件系统快照。

### 实际自动化与失败保留

工作目录为隔离源码.local/goal-20261112/sbom；Q为根.local/release-venv/Scripts/python.exe（3.13.17），P为根.venv/Scripts/python.exe（3.12.7）。原始日志和所有生成BOM/Schema留本目录artifacts/rel01a，不入Git。

- Q -m pytest backend/tests/test_source_sbom.py -q --basetemp=.local/sbom-q-final --junitxml=artifacts/rel01a/q-final.xml：退出0，35通过。P同命令使用.local/sbom-p-final及p-final.xml：退出0，35通过。覆盖身份/Git pin/host、重复/未知/不支持锁、SDK未知保留、缺失额外/名称版本/来源/hash错误、格式/结构、错误exe、配置隔离、已有输出保留、超时/非零/原锁变化无成功收据及大小/重解析拒绝。
- Q -m ruff check tools/source_sbom.py backend/tests/test_source_sbom.py：退出0。未改业务逻辑，本地未重复全部业务/Flutter/冻结；PR仍执行原完整当前head CI。
- Q tools/source_sbom.py --syft D:/computer_work/project/StudyWorkbench/.local/release-tools/syft-1.57.1/syft.exe --output artifacts/rel01a/real03，以及另一次real04：均退出0，70个PyPI和66个Dart hosted/Git包共136项全相等，8个SDK项明确未知；BOM含另外2个输入文件组件。两轮组件/排除项/源与投影hash精确相同。real04 BOM SHA256为525157773a9834361b021bf3458d5605275966d1c74739d9027c9e2b5f36329d。
- 真实real03 BOM用jsonschema Draft7Validator及本地Registry验证CycloneDX官方1.6 schema及spdx/jsf引用，退出0，138组件有效。Schema来源为CycloneDX/specification的1.6 tag下schema目录；bom-1.6.schema.json SHA256 3e92dddbc30cf7f6a02b80f0942b1a4cfd4fb1c26f1dfc4310afa9d613cafb93，spdx.schema.json baa9d3bd1ed57b6751b0887edead6b5063ff53ff7429cf85d476c6c94af0166e，jsf-0.82.schema.json 8bae002c25e723db7ee1f26afde680ae1a2b1a8f6b4b4b0fd65dc3becb090aae。CLI自身执行范围/身份对照；完整schema验证是本次实际工具输出证据，并非CLI新增联网步骤。
- 初轮pytest为24通过/9个fixture错误：默认临时目录不可创建；首次显式basetemp仍因隔离目录未建.local父目录退出1。保留sbom-tests.xml、tests01.xml/log，建立明确父目录后复跑33通过，新增畸形结果用例后末轮35通过，没有删除断言。首次工具默认输出1.7被1.6对照拒绝（real01），随后显式输出1.6；real02暴露pub版本+号需PURL百分号编码，修复并补+版本断言后real03/04通过，原失败输出保留。
- 辅助查找既有conftest.py/ci.yml路径不存在，未用于结论；不将错误路径的shell整体退出码混作测试结果。各次pytest真实退出码单独记录。

源requirements锁SHA256 f4aba068d138a8097d5b4cfefa44552edf742f5645bfd705d2e7270bac41a3d6；pubspec锁SHA256 c1ab979d33d15197f1018cae7ec752cfb0244523e26f3ed2c73ee1f761be2ce5；Dart投影SHA256 8e3232e332919be2d0dbc96fa90cb40fccfa1ba11c6cf1e7c8ec2a1cb4c57d53。无新增依赖下载或模型，既有Syft官方工具复用；source.cdx.json与comparison.json是构建产物，未提交整个artifact目录。

### 交付边界

源码锁包含开发/构建/非Windows包，不识别最终运行时成员；Flutter/Dart SDK实际版本、冻结/原生/CRT/WebView2/NuGet/Office/Java/安装器payload、依赖边、许可原文/义务、漏洞和签名均未完成。Syft推断CPE不当作已确认漏洞匹配，锁中archive hash/Git commit并不证明已取得对应内容。REL-01a只能作为后续源清单基线，不能让REL-01/02/03整体销项。代码审查与人工测试按要求暂缓；独立草稿PR/最终head CI待核，主Agent核对前保持REVIEW，未合并或发行。

实际提交[独立草稿PR #25](https://github.com/surface-user/StudyWorkbench/pull/25)，codex/source-lock-sbom基于#23的2645366，实施提交d0c4eac12fffda7da95b75895cd44b7f1ff58d41。发PR前Python文档assert退出0：明确六份文件UTF-8/LF/尾空白及相对链接、原报告前缀保留、所有非REL-01条目逐字保持、其余基线文件字节保持；辅助聚合读取工具输出截断曾使JSON解码失败，改为逐文件读取后成功，没有发布不完整文件。最终head/CI在PR描述维护，避免为记录自身SHA反复提交；主Agent验收前保持REVIEW。

## 2026-11-12：OFF-02a 固定Java组件准备

用户将技术判断委托主Agent后，主Agent已选择项目内Eclipse Temurin 21.0.13+9 Windows x64 HotSpot JRE；本切片从IN_PROGRESS进入REVIEW，父OFF-02继续进行。基线为#25最终1b52eb30785de734e7d5149d3198c5ee80bb78cf，独占源码.local/goal-20261112/java。主Agent已核#25的双Python35项/真实136包与8个SDK未知/官方schema及本地远端blob，最终CI #141（43060243273）三job/44步全部成功；按主Agent验收将REL-01a记DONE，源清单前置可供后续有限范围使用，完整REL-01仍未完成。

### 设计与范围

新增tools/prepare_java_runtime.py和backend/tests/test_java_runtime_preparation.py，同步依赖/打包指南、本task及原报告；无Office启动参数、运行环境/CRT搜索路径、数据库、安装器/默认发行包或新Python依赖变化。官方发布资产来源与版本实核，固定zip文件名OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip，49106397字节、SHA256 2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628，官方发布于2026-10-22，所有事实取自固定官方release/实际包，不以开发机安装情况替代。

在创建目标前校验原zip普通文件/大小/hash、完整ZIP目录及预算；固定顶层jdk-21.0.13+9-jre，仅去掉包裹目录层，内部bin/lib/conf/legal等不删减。拒绝路径越界、空段、盘符/ADS、Windows保留名/尾点空格、大小写重名、文件目录冲突、原名被ZipFile规范化、链接/特殊条目/加密、超过1024条/200MiB预算。目标必须不存在，包/目标父目录不含链接/重解析点；流式独占写文件并核实际解压长度/CRC/hash，中断保留现场不回滚或覆写旧目录。重核原zip后复用stage_files逐文件闭合枚举（显式拒绝其排除的根build-inventory.json），核release声明和java.exe/jawt.dll/server/jvm.dll的AMD64/PE32+。成功才独占写java-runtime-lock.json，字段version/package_sha256/source_url/bytes/files与已有组件清单风格一致；锁本身非签名或来源证明。

完整保留NOTICE及179个legal文件，登记GPL2/Classpath与Assembly Exception及混合第三方通知；已定位同版本官方源代码资产URL/发布digest，但未下载核验或制作源码提供包，REL-02义务未完成。不执行系统安装、不修改PATH或Office配置；准备脚本本身不执行Java。更新必须重选固定来源/hash并重建清单、回归，禁止静默就地替换组件。

### 实际命令、结果和保留失败

工作目录.local/goal-20261112/java，Q/P分别为根.local/release-venv/Scripts/python.exe（3.13.17）与根.venv/Scripts/python.exe（3.12.7）；所有测试/生成现场放本目录artifacts/off02a或.local。

- Q tools/prepare_java_runtime.py --package D:/computer_work/project/StudyWorkbench/.local/release-tools/temurin-jre21.0.13-9/OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip --destination .local/temurin21-verified：退出0，315文件/151829828字节；完整清单SHA256 159433e3a2fc9f2a9c4f633a613d3db5aaca29d1b52caa64e3a63755ac8e1907。原zip未改。初轮real01因校验集合已casefold但必需NOTICE/LICENSE未统一大小写而拒绝，目标尚未创建；修正匹配后real02通过，原失败log保留。
- 最终源码下用package_entries重新核官方378个ZIP条目，再用verify_runtime核同315文件/架构/版本，并将ZipFile逐文件原始字节SHA256与清单全部相等对照：退出0，179个legal文件均在清单。此为固定zip真实输入，不使用夹具pin替代。
- .local/temurin21-verified/bin/java.exe -version：退出0，实际Temurin 21.0.13+9，64-Bit Server VM；这是命令行自动验证，不是系统安装、Office加载或人工窗口测试。
- Q -m pytest backend/tests/test_java_runtime_preparation.py -q --basetemp=.local/java-q-final --junitxml=artifacts/off02a/q-final.xml：退出0，37通过；P同命令使用java-p-final及p-final.xml：退出0，37通过。保留1个重复ZIP名称自编负例的标准库警告。覆盖完整布局/legal/hash、大小写/恶意路径/NUL/反斜杠/重复及类型冲突、特殊文件、预算、错误包大小/hash、已有目标保留、失败无成功锁、重验缺失/额外/字节/架构/release及重解析父路径。
- Q -m ruff check tools/prepare_java_runtime.py backend/tests/test_java_runtime_preparation.py：退出0。首次排序检查1项后自动调整import排序，不改行为。
- tests01/tests02均34通过/1失败：Windows ZipFile构造和读取均会规范化反斜杠，先保留原始恶意ZIP路径夹具，再增加orig_filename与filename一致性拒绝，tests03的35项及末轮新增NUL/空目录段后37项通过。原日志/JUnit保留，未删除负例或降低断言。
- 尚未做Office/CRT集成或应用冻结Java转换；相关工作由主Agent后续承担。新工具不参与运行时调用，本地未重复业务/Flutter全量；独立PR继续完整当前head CI。源码/报告/许可文档会检查UTF-8、相对链接、原报告历史及非本项任务行保持，PR/CI核实前不记DONE。

### 限制与交付

关键PE与java-version通过只证明本机固定JRE准备和入口运行；不证明Office能识别JVM、JavaBean/AWT/CRT递归依赖已闭合，不支持删除DLL或放宽既有发行门禁。签名（zip GPG未验）、完整传递许可/源码分发、漏洞、最终包SBOM、干净机与正式发行仍待后续。代码审查/人工测试依用户安排暂缓，OFF-02a由主Agent在独立PR/最终head CI核验后决定DONE，整体OFF-02继续进行，未合并或发行。

实际交付[独立草稿PR #28](https://github.com/surface-user/StudyWorkbench/pull/28)，分支codex/pinned-java-preparation，base为#25最终1b52eb3，实现提交616b2f9c5600ac2922e623ec5186aa987ddc43e8。文档assert退出0，核六份明确改动的UTF-8/LF/尾空白/相对链接、原报告前缀与非本项任务行保留；新task只额外按主Agent验收更新REL-01a为DONE，完整父项保持进行。首次PR创建工具未返回正常结构，查询该分支无PR后重试成功，没有重复创建。最终head/CI在PR描述维护，当前REVIEW等待主Agent验收。

## 2026-11-12：REL-03a 源码锁文件漏洞查询

基线为OFF-02a草稿PR #28最终2187fec21fee25472124aa97a2b1ea524d85e357，独占副本.local/goal-20261112/source-vulns的448个基线文件逐Git blob核验复制，没有复制构建产物或修改其他工作区。主Agent已核#28双Python37项、315个官方JRE文件及最终CI #153（43065303373）三job/44步全部成功，本task将OFF-02a记DONE，父OFF-02不因此完成。REL-03a由IN_PROGRESS进入REVIEW，等待独立PR最终head CI与主Agent验收；完整REL-03仍依赖实际发行组件清单与后续修复。

### 设计与实现

新增tools/source_vulnerabilities.py 1.0及其专项测试，同步依赖/打包指南、本task和原报告共六文件。复用REL-01a的lock_inventory/read_lock/no_links，同一两份锁、精确PyPI/pub.dev身份；Git不能冒充同名hosted发行版，8个SDK占位没有真实SDK版本。只将公开包名、生态与版本发往[OSV v1官方API](https://google.github.io/osv.dev/api/)，续页只带服务返回token，详情只带返回的受限ID；无源码、锁全文、hash、Git仓库URL/commit或个人数据上传。标准库HTTPS，无代理继承/重定向/凭据；没安装其他扫描器或运行依赖，没有改任何锁版本。

固定的是项目查询器版本/文件hash、API v1、原锁hash和本次HTTP原始证据，不冒称使用OSV-Scanner二进制。在线API无可固定的完整数据库快照/hash/更新时点，database_snapshot=null、database_freshness=unknown_live_api始终保留；UTC查询时间及响应Date只证明本次观察。缺Date标未知，超过24小时或超前5分钟拒绝；服务离线、非200、超8MiB、重复JSON键/畸形批次、身份无法映射、分页循环或8轮/1000包/1000公告预算越界均不生成成功结论。返回ID另取完整公告，保留原范围/fixed事件/别名/severity/来源/withdrawn/modified；详情身份不匹配、查询后修订、撤回各有显式状态，不从原始证据删掉。批次modified为微秒而详情可能纳秒，按微秒比较并保留两种原值和精度字段。

输出必须为新目录，原始编号request/response文件与SHA256、报告落于忽略的artifacts；已有目标、链接/重解析路径拒绝，结束重核锁字节未变。失败留下已有现场及不完整报告。退出1为查询/验证失败，2为有公告需判定，3为查询完成但无公告返回；没有代表全产品安全的0，发现不冒充测试失败或已修复。CI用离线受控响应验证，联网查询为显式构建动作，不添加发行门禁或自动批准。

### 实际命令与证据

工作目录.local/goal-20261112/source-vulns，Q/P分别为根.local/release-venv/Scripts/python.exe（3.13.17）与根.venv/Scripts/python.exe（3.12.7）。原始现场位于本副本artifacts/rel03a，未入Git。

- Q -m pytest backend/tests/test_source_vulnerabilities.py -q --basetemp=.local/vulns-q-01 --junitxml=artifacts/rel03a/q01.xml：退出0，42通过；P同专项使用.local/vulns-p-final和p-final.xml：退出0，42通过。覆盖公开字段/不发送Git、源锁/hash/未知边界、发现范围不升级、分页/循环/预算、畸形/缺失/额外批次、ID注入、详情映射/修订/撤回、微秒/纳秒、网络/HTTP失败/陈旧Date/原始字节hash、源变化、已有目录保留及私有URL拒绝。
- Q -m ruff check tools/source_vulnerabilities.py backend/tests/test_source_vulnerabilities.py：退出0。首次I001 import排序检查失败，使用--fix只调整排序后通过；没有删失败测试或降低断言。
- Q tools/source_vulnerabilities.py --output artifacts/rel03a/real02：原生及显式PowerShell透传退出2，这是发现标志；queries_complete=true，135包（70 PyPI、65 Pub），2个包12条公告，133个包无公告返回且映射/收录仍未证实，另1个Git/8个SDK未查询。2026-11-11T17:32:43.034461Z至17:33:04.139703Z（本地11-12 01:32–01:33），13次HTTP均200且Date在时限内；数据库新鲜度仍未知。
- Python独立assert复核13对原始request/response SHA256、135查询恰为package(name/ecosystem)+version且70/65分布一致、12条详情均映射并保留requires_triage状态：退出0。real02/report.json SHA256 d32d5ab76cc9bfbb128b96ae40992a4a3ce6fd48ed31f3e1440eaf1213282f3f；批次response SHA256 b0a0693cec061db8dabf92dd34c74e826f23426632f5949135121b11fb85f9f8；其余12份原始公告各hash完整保存在该report.evidence，不把此hash称完整数据库hash。
- 本次查询器SHA256 d896295851ef4b21a30e911ba614f2660159315682137b0cc1f9ee441dd63ebc；复用source_sbom.py SHA256 492ecb1b9765cd23dc2b816c3be5995e5f80b6b33233c4104c63045f5e6710d0。requirements/pubspec锁hash仍为前述f4aba068…/c1ab979d…，未变。
- 首次real01已命中相同2包/12公告，但批次与详情时间精度不同使部分状态保守标为changed_since_query_unknown；保留原结果，显式微秒比较并补测试后real02修正。首次PowerShell未显式exit透传使外壳显示1，报告内原生exit_code为2；real02显式透传确认为2。前置小探针使用非本项目requests2.32.5与archive4.0.7，仅验证生态/API响应，不计入本项目发现。
- 辅助rg曾指定不存在backend/pyproject.toml、requirements.txt及错误workflow路径而退出1；后续以rg --files确定根pyproject.toml和requirements.lock.txt，再只查实际业务目录。GitHub连接器不支持security-advisories REST端点，未取得结果；随后读取官方OSV原始公告与上游公开公告页。没有把这些工具失败当作漏洞验证通过。

### 真实发现与后续修复

保留12条公告，GHSA与PYSEC互为别名，按CVE汇总为6项；下面的“修复版本”来自公告，尚未确认与现有FastAPI/冻结环境兼容。扫描命中是锁版本处于公告范围，不证明本项目存在可利用路径、已遭利用或修复完成。

| 锁依赖与CVE | 公告范围/修复版本 | 上游触发条件与本项目证据边界 |
|---|---|---|
| pytest 9.0.1，CVE-2025-71176 | <9.0.3，修复9.0.3；[GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g)，别名PYSEC-2026-1845 | UNIX默认/tmp测试目录的本地攻击；本次Windows专项不证明该路径可触发，pytest为开发工具，仍保留源依赖发现，未据此豁免 |
| Starlette 0.50.0，CVE-2026-48710 | <1.0.1，修复1.0.1；[GHSA-86qp-5c8j-p5mr](https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr)，PYSEC-2026-161 | 非法Host污染request.url.path，影响依该值做安全判定；app.py:116确实用其拒绝Origin，同时有TrustedHost及鉴权。中间件顺序/畸形请求入口仍需专门回归，不能只因存在TrustedHost宣布免疫 |
| Starlette 0.50.0，CVE-2026-48817 | <1.1.0，修复1.1.0；[GHSA-x746-7m8f-x49c](https://github.com/Kludex/starlette/security/advisories/GHSA-x746-7m8f-x49c)，PYSEC-2026-2280 | 无methods约束的HTTPEndpoint子类按非常规HTTP方法调用属性；业务目录文本检索未发现此类，未做传递/动态可达性证明 |
| Starlette 0.50.0，CVE-2026-48818 | <1.1.0，修复1.1.0；[GHSA-wqp7-x3pw-xc5r](https://github.com/Kludex/starlette/security/advisories/GHSA-wqp7-x3pw-xc5r)，PYSEC-2026-2281 | Windows StaticFiles默认realpath处理UNC先触发SMB/NTLM再拒绝；业务目录未发现StaticFiles，已有FileResponse不因此被判成同一触发入口；传递路径仍未确认 |
| Starlette 0.50.0，CVE-2026-54282 | <1.3.0，修复1.3.0；[GHSA-jp82-jpqv-5vv3](https://github.com/Kludex/starlette/security/advisories/GHSA-jp82-jpqv-5vv3)，PYSEC-2026-248 | ASGI提供无前导/的path，使request.url authority污染；现有Origin中间件读取url，实际服务器接收/传播此路径未验证 |
| Starlette 0.50.0，CVE-2026-54283 | >=0.4.1,<1.3.1，修复1.3.1；[GHSA-82w8-qh3p-5jfq](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq)，PYSEC-2026-249 | request.form对urlencoded未执行字段数/字段大小限制；业务目录未发现request.form/Form调用，已有JSON/请求预算不构成完整传递可达性证明 |

已通知主Agent并按其指令登记独立REL-03b（pytest最小兼容修复）和REL-03c（Starlette/FastAPI兼容组合与Host/path/相关入口回归）。本PR不改锁、不安装新版依赖、不默默升级全栈。Git/SDK、Python冻结/native、Flutter/NuGet/CRT/WebView2、Office/Java/安装器实际payload以及完整库更新/修复复扫均未闭合。代码审查暂缓、人工测试取消；完整SBOM/传递许可/签名/发行、合并均不在本切片结论内。

实际提交[独立草稿PR #32](https://github.com/surface-user/StudyWorkbench/pull/32)，codex/source-lock-vulnerabilities基于#28的2187fec，实现提交75971a02007e5f992e344f8220cbc465cc2deb63。六文件文档/范围assert退出0，保持全部其余基线文件、原报告前缀和非本项task行；原始artifacts未入Git。首次create_tree未返回结构，重试相同内容的幂等tree操作后成功，没有移动错误ref或重复创建PR。最终head与完整CI在PR描述维护，主Agent核实前保持REVIEW；下一项按独立03b/c处理。


## 2026-11-12：OFF-02b Office与Java/CRT组合运行时

基线为OFF-02a的#28最终2187fec21fee25472124aa97a2b1ea524d85e357，448份源码逐Git blob核对后复制到.local/goal-20261112/office-bundle。主Agent已核#28的37×2专项、315文件及最终[CI #153](https://github.com/surface-user/StudyWorkbench/actions/runs/43065303373)三组44步成功，OFF-02a在task登记DONE。用户委托技术判断后采用项目内Temurin，不安装系统Java、不改全局环境。OFF-02b实现与本地自动化完成，当前REVIEW，整体OFF-02及发行准备仍未完成。

### 范围与实现

新tools/compose_office_runtime.py复用已有OfficeRuntime/prepare_java_runtime逐文件核验，要求固定的原Office与Java清单hash，目标全新、非输入内部且无重解析路径。Office所有原文件及清单保留；Java完整复制到java/；仅另从原Office System64逐字复制8份VC运行库到program/，不覆盖原件。组件二次复核原文件/清单保持，再生成组合清单并完整核对目标；失败不删现场，非零退出不能当成功。

后端OfficeRuntime新增固定组合清单校验和进程专用JAVA_HOME/UNO_JAVA_JFW_JREHOME/headless环境；原无Java组件路径继续支持。调用方为原预览worker/冻结内部launcher及stage工具；唯一绕过构造器的launcher测试夹具同步java_home=None。转换前逐文件核验、输入门禁、宏/脚本/外链保护、独立profile/Job预算均保持；不修改主进程DLL搜索状态、不继承外来Java参数、不引入产品Python依赖。Java识别依据固定LibreOffice源构建bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1的framework.hxx/framework.cxx/fwkbase.cxx直接模式；未改变厂商配置XML。

### 实际命令与结果

以下工作目录为隔离office-bundle源码；Q为D:/computer_work/project/StudyWorkbench/.local/release-venv/Scripts/python.exe（3.13.17），P为根.venv/Scripts/python.exe（3.12.7）。原组件O=D:/computer_work/project/StudyWorkbench/.local/release-tools/libreoffice-26.8.1，J=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/java/.local/temurin21-verified；新组合C=D:/computer_work/project/StudyWorkbench/.local/release-tools/libreoffice-java-26.8.1-21.0.13。F=D:/computer_work/project/StudyWorkbench/.local/goal-20261112/formats/.local/fmt-samples01，为本批自编样本，未读取个人文档。

- Q -m pytest -q backend/tests/test_office_java_bundle.py backend/tests/test_office_launcher.py backend/tests/test_office_previews.py --basetemp=.local/off02b-test03 --junitxml=artifacts/off02b/test03.xml：退出0，38通过，20.65秒；P使用.local/off02b-p-test01与p-test01.xml：退出0，38通过，24.24秒。覆盖原文件保持、来源/锁/组合清单篡改、遗漏Java标记/CRT、额外成员、嵌套/已有目标拒绝、包内Java环境与不继承外来参数，保留旧组件/冻结launcher测试。Starlette弃用警告保留。
- Q tools/compose_office_runtime.py --office O --java J --destination C：退出0，19742文件/1732478884字节；组合清单2417775字节、SHA256 156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9。原Office19417与Java315、两份原清单和8份CRT复制均在固定集合内；日志artifacts/off02b/compose01.log。不含任何原包就地修改或DLL移除。
- 原生诊断在根artifacts/goal-20261112编译：VS2022 x64 cl.exe /nologo /std:c++17 /EHsc /MT /W4 /Fe:probe_office_java.exe /Fo:probe_office_java.obj probe_office_java.cpp，退出0；INCLUDE/LIB使用同一MSVC及Windows SDK的x64/ucrt目录。Q -X utf8 artifacts/goal-20261112/run_office_java_probe.py（根目录）：退出0，先完整核C，再以OfficeRuntime.environment启动静态CRT诊断进程。Office自己的JFW选出Eclipse Adoptium21.0.13并启动JVM，JavaBean/AWT加载成功，所有列出的私有模块均在C内，JVM关闭返回0。诊断源与7个模块位置等精选结论见[evidence/off02b-java-summary.json](evidence/off02b-java-summary.json)和[诊断源](evidence/off02b-jfw-probe.cpp)。源hash f3cfa29b8b1bd4d7cc952890f59a44e9adad431599b4065e7eb3de1ac4dd4a33。该有限诊断使用固定私有C++ ABI，只是开发证据，不进入产品/自动兼容未来版本；其DLL目录配置只影响自身，不把它当作真实Office转换进程的模块采样。
- PYTHONPATH=backend; Q -X utf8 tools/check_office_previews.py --test-root .local/off02b-source01 --runtime C --docx F/复杂分节.docx --pptx F/复杂图表.pptx：退出0，DOCX/PPTX各3页，PDF108084/77986字节；公式/图表标签、原件hash、取消重试、缓存与重启、数据库完整性及XML预算拒绝通过（source01.log）。运行源码中包含本次组合环境与校验，不借旧后端冒充。
- ./packaging/windows/build-backend.ps1 -Python Q：退出0，114.7秒构建完成，43个冻结模块与本次源码精确一致；exe SHA256 bad0e600989de0f85d3b0ded02b195078c83c921ba0bebaa85cc512bde6d1642，22565938字节，freeze01.log。随后的冻结实际转换另见下项，构建通过本身不等于运行成功。
- 同一check_office_previews命令增加--exe dist/study_backend/study_backend.exe，test-root为.local/off02b-frozen01：退出0，DOCX/PPTX仍各3页、108084/77986字节；公式/图表、XML预算拒绝、取消重试、缓存/重启/源hash和数据库检查均通过，frozen01.log。该工具将PATH限制到System32，清除PYTHONPATH/PYTHONHOME；包内Java由本次冻结OfficeRuntime设置，没有使用开发机Java环境。
- Q -m ruff check backend tools：退出0。对改变的原文件执行git -c core.autocrlf=false diff --no-index --check：无诊断，退出1仅表示有差异，聚合检查退出0。新增代码与文档在提交前另核UTF-8/LF/尾空白/相对链接。

保留失败：首次lint报告import排序1项，修正后通过；test02误写不存在的test_office_runtime.py导致退出4/0项执行，改为实际存在的test_office_previews.py后上述38×2通过，原test02.log保留。初次diff驱动把Git全局LF→CRLF警告当失败，明确关闭该命令的autocrlf后复核，无断言降低。最初Python进程JNI探针曾加载开发机CRT，只作为不闭合的旧证据保留；本次原生/MT进程补证，不改写旧结果。

### 剩余退出条件

源码与新冻结真实转换均通过；独立草稿PR/最终head CI待核，OFF-02b保持REVIEW。OFF-02c将独立检查实际PE进程加载域/.com/.bin/延迟导入，原check_release不降低或跳过；尚未声称最终安装/免安装整包已闭合。完整SBOM、许可/源码提供义务、漏洞修复与签名在REL系列继续，现成系统DLL/文件hash不能代替这些条件。审查按ADR0014暂缓，人工/Computer Use取消；没有合并或公开发行，没有删除原组件/测试失败/个人数据。原始日志、生成PDF/样本及exe保持Git忽略，只筛选本节所需摘要与诊断源作为共享证据。
## 2026-11-12：REL-03b pytest已知漏洞修复

主Agent已核#32最终89f0d775d847981b97a70c1a88281e140756c8f2的CI #168（43071363779）completed/success、双Python专项各42、真实查询报告hash及snapshot未知边界，REL-03a有限查询任务验收通过；本task记DONE，原漏洞/未知继续保留。以该head逐Git blob复制450文件到独立.local/goal-20261112/pytest-fix；本项从IN_PROGRESS进入REVIEW，独立PR/当前head CI及主Agent验收前不记DONE。

### 范围与依据

仅backend/requirements.lock.txt中pytest==9.0.1改为9.0.3，另更新依赖文档、task及本原报告共四文件；没有新测试代码、业务入口、数据库、CI门禁或其他锁版本变化。原test_source_sbom.py中的9.0.1是自编解析夹具，继续保留，不能把夹具值误当运行环境版本。

[官方9.0.3发行说明](https://github.com/pytest-dev/pytest/releases/tag/9.0.3)记录2026-04-07修复CVE-2025-71176（#14343）；[PyPI固定版本元数据](https://pypi.org/pypi/pytest/9.0.3/json)要求Python>=3.10，既有3.12/3.13锁依赖满足，不需传递升级。沿用03a原始官方元数据，SHA256 d2d51b1dc8bdb0844b51d95144bce4c0c38daa72d00417ebf771cdac7cd1b0a2。官方files.pythonhosted.org的pytest-9.0.3-py3-none-any.whl实取375249字节，SHA256 2c5efc453d45394fdd706ade797c0a81091eccd1d6e4bccfcd476e2b8e0ab5d9，与官方digest/大小一致且未撤回；原始来源URL/HTTP Date/hash存artifacts/rel03b/download-provenance.json。wheel内MIT LICENSE完整留存，SHA256 ca836a5f9ecca3b2f350230faa20a48fb8b145653b5568d784862df864706b9b；未将安装包或原始artifact提交Git。

pytest是开发工具；原公告说明UNIX默认/tmp目录的本地攻击，不把本项目Windows通过记为UNIX漏洞复现或全平台认证。上游修复版本与源锁复查只是关闭该已知包版本发现的依据，不清除03a原发现，也不把未验证可达性变成误报。Starlette0.50.0/FastAPI0.161.1保持原锁，五个Starlette CVE仍由03c独立承担。

### 隔离环境与实际验证

工作目录为上述pytest-fix。共享Q/P仍为根.local/release-venv/Scripts/python.exe（3.13.17）和根.venv/Scripts/python.exe（3.12.7）。新IQ/IP分别为本副本.local/pytest-q-isolated/Scripts/python.exe及.local/pytest-p-isolated/Scripts/python.exe。新venv仅安装官方固定hash pytest wheel，其他现有依赖经本venv的shared-build-dependencies.pth只读引用对应Q/P site-packages；实际断言pytest.__file__位于新sys.prefix且版本9.0.3。不是重新安装整栈或改写共享环境；CI仍会从锁文件创建新的完整依赖环境。

- Q/P -m venv --without-pip .local/pytest-{q,p}-isolated，然后Q/P -m pip --isolated --disable-pip-version-check --python <新解释器> install --no-index --no-deps --no-cache-dir --no-user artifacts/rel03b/pytest-9.0.3-py3-none-any.whl：均退出0。新解释器版本/pytest路径断言及pip --python <新解释器> check：均退出0，其他版本保持FastAPI0.161.1/Starlette0.50.0，No broken requirements。
- IQ/IP -m pytest backend/tests/test_source_sbom.py backend/tests/test_source_vulnerabilities.py -q --basetemp=.local/pytest-{q,p}-targeted --junitxml=artifacts/rel03b/{q,p}-targeted.xml：退出0，各77通过。
- IQ/IP -m pytest -q --basetemp=.local/pytest-{q,p}-full --junitxml=artifacts/rel03b/{q,p}-full.xml：原运行均退出1，各809通过/12失败/77子测试通过/2警告；Q约403秒，P约449秒。原始JUnit统计898条（821测试加77子测试）；初次证据核验脚本误将JUnit总数预期为821而退出1，按实际子测试结构更正核验预期后继续，未改变测试断言。逐JUnit核两边失败节点集合相同，全部是mklink/J或os.link因本地权限拒绝创建夹具。旧共享pytest9.0.1同一junction用例也退出1，原失败及诊断日志/JUnit保留。
- 原Q/P完整失败节点12项从JUnit提取为failed-nodes.json，未删改测试；以允许真实目录/硬链接的受控权限运行IQ/IP -m pytest <该12个节点> -q --basetemp=.local/pytest-{q,p}-permitted --junitxml=artifacts/rel03b/{q,p}-permitted.xml：均退出0，各12通过。新目标目录事先确认不存在，不复用/删除原失败目录。此为809通过加12项复验，不把原始完整运行改记一次全绿；完整当前head CI另核。
- Q -m ruff check backend tools：退出0。起初用IQ -m ruff因只读引用模块无法找到新venv中未安装的ruff.exe而退出1，原ruff.log保留；改为直接调用已有共享Q的静态工具，不增装或升级Ruff，成功记录ruff-shared.log。
- Python逐文件SHA256复核Q/P各74个pytest/_pytest非缓存文件与测试前指纹相等，共享解释器实际pytest仍为9.0.1：退出0。测试过程设置PYTHONDONTWRITEBYTECODE=1，使用各自新basetemp及本副本TEMP/TMP，未写共享包或清理个人目录。
- 初次普通venv创建的ensurepip子进程两边均退出1，根因未确证；保留两个部分环境与执行摘要。随后新目录使用--without-pip和显式pip --python定向安装成功，不覆盖失败环境或擅自修复系统Python。

### SBOM与漏洞复查

IQ tools/source_sbom.py --syft D:/computer_work/project/StudyWorkbench/.local/release-tools/syft-1.57.1/syft.exe --output artifacts/rel03b/source-sbom：退出0，仍匹配136个源包及8个SDK排除项。独立assert对照03a前源清单，集合仅移除pkg:pypi/pytest@9.0.1并增加pkg:pypi/pytest@9.0.3，其他135包身份及SDK未知完全相同；comparison.json SHA256 a1a305b86c3eae99e13845a1942cb40e772b14534ba3f0581b6b50f76aada8ed，BOM SHA256 8777bd5bff163d46487fe1fa31f64e55f55a11ce7847c27a4d21267d813454dc。新requirements锁SHA256 4e6de78b36b6daab6fae0f407cdfca09e1a7ac8f533798b6ffb413cac3a9c8e7；pubspec锁仍c1ab979d33d15197f1018cae7ec752cfb0244523e26f3ed2c73ee1f761be2ce5。

IQ tools/source_vulnerabilities.py --output artifacts/rel03b/source-vulns：退出2，表示仍有发现；2026-11-11T18:03:48.206873Z至18:04:02.242271Z查询135包完成，pytest9.0.3无公告返回，仅Starlette保留10条公告（五CVE），Git/8SDK排除不变。所有原始请求/响应hash独立复核通过；report.json SHA256 56b653316ee2067d19125aa0173063240ef7d0e4ae36d788b3acbb322e07b87f。

另复用固定查询器exchange，将公开pytest9.0.1与9.0.3在同一querybatch做对照：2026-11-11T18:05:11.755490Z完成，旧版本仍返回GHSA-6w46-j5rx-g56g/PYSEC-2026-1845，新版本为空；assert退出0，原始response SHA256 a8f2d9bf1fec0bf0527603d31e351f242420780c6369f16d6172fd516b9f8ffc，comparison.json SHA256 d45e642ff05a4737d3f188164c76dcbac45b08a921273a49e880891096b461ca。这加强了对应已知公告/包映射的修复证据，但在线数据库snapshot/freshness仍未知，没有全产品安全结论。

代码审查暂缓、人工测试取消，完整发行SBOM/传递许可/二进制漏洞/签名和正式发行仍未完成。新依赖只影响开发测试，未做UNIX攻击复现；原查询发现、权限失败、初始环境失败与工具失败均保留。03b需独立草稿PR/最终head CI及主Agent核验后决定DONE，下一项为03c，未合并或发行。

实际提交[独立草稿PR #35](https://github.com/surface-user/StudyWorkbench/pull/35)，codex/pytest-vulnerability-fix基于#32最终89f0d775，实现提交e90e659fcd149b35f47ca8830a67989e1895c5a2。四文件范围/精确单行锁差异、原报告前缀、非03a/b任务行、UTF-8/LF/尾空白/相对链接检查通过；JUnit898条含77子测试的计数已核。最终head与完整CI在PR描述维护，主Agent核验前保持REVIEW；不为记录自身SHA反复触发提交。



## 2026-11-12 OFF-02c：按实际加载域检查PE依赖（设计）

基于固定Java准备PR #28最终2187fec21fee25472124aa97a2b1ea524d85e357，tree e05bda1920978a0e666b4c8b77270ce0177158fa；448个Git blob从已有java副本逐字节验证后复制到独占.local/goal-20261112/native-closure。AGENTS/requirements/architecture/question-content-spec与已完整读取基线字节一致，重读task和发行/组件契约。#28最终CI #153/43065303373已success，主Agent验收OFF-02a，本次任务表记DONE；父OFF-02及REL-01不销项。代码审查暂缓、人工/Computer Use取消，不授权发行/合并。

现有check_release在完整文件集合/hash之后仅检查.exe/.dll/.pyd普通导入，以全包basename或本机System32文件存在作为可用条件。调用方为build-release.ps1的安装器编译前门禁，专项为test_release_inventory.py；原OFF-01辅助scan.py只读诊断曾扫描.com/.bin和延迟导入，但未进入产品门禁。本次不改OfficeRuntime/compose；组合加载实现由主Agent独立OFF-02b负责。原库存hash、无个人.db、CPython身份、主程序/后端原x64/PE32+检查及失败保留顺序均保持。

只读盘点使用固定Q=根.local/release-venv/Scripts/python.exe（3.13.17），PYTHONDONTWRITEBYTECODE=1，内存pefile解析导入目录1/13，不运行待检PE或写原组件：

- 新组合组件.local/release-tools/libreoffice-java-26.8.1-21.0.13含351个PE，321 AMD64、26 x86、4 ARM64；x86/ARM64包含Office内Python安装模板和独立辅助，不等于主Office架构错误，也不能称整包全x64。旧检查遗漏soffice/unopkg的.com/.bin四项；18条延迟边来自Java AWT/java/net/splashscreen和原Office。
- Office候选域program、java/bin、java/bin/server，入口soffice.com/bin+officebean+jvm的递归图64节点，无候选缺边/架构冲突，CRT落在program。Java.exe+jvm+jawt域java/bin、server图9节点，CRT落java/bin。仅在内存去掉Office域的Java根时，officebean→jawt明确缺失，虽然组件其他目录仍有同名DLL；没有移动或删除组件。
- FMT新冻结产物（.local/goal-20261112/formats/dist/study_backend）159PE全AMD64；只用插件目录/_internal/后端目录会留下5条NumPy/Pandas依赖。其已锁初始化源码实际调用os.add_dll_directory注册numpy.libs/pandas.libs；从冻结PYZ提取整个初始化代码并用check_frozen_sources.equivalent与本机固定源码比较通过。因此需识别有代码证据的注册目录，不能按缺边新增任意搜索目录。
- 既有11-10基础包app根15PE，根目录/本机OS候选下无缺边，并额外发现Flutter/WebView2Loader四条delay。此为旧候选包的路径规则样本，不作为本次新完整发行证明。

### 最小实现与验证范围

1. 共用PE解析器列出全部.exe/.dll/.pyd及MZ格式.com/.bin，读取普通和delay导入；严格闭合句柄、大小写路径索引、拒绝错误PE/非法导入名/同域架构不符。未证明会执行的独立helper/安装模板列为非运行候选或未知，不套上全包AMD64结论。
2. 对明确入口和插件分别建立加载域：主应用根；PyInstaller后端及_internal、插件自身目录；Office程序目录与显式Java根；独立Java.exe域。普通VC运行库必须位于对应进程的app-local根，不能靠别的进程目录或本机System32救缺失。后端带重命名的包私有CRT只能在已证明的注册目录中解析。
3. NumPy/Pandas.libs不凭名称放行：固定当前冻结初始化代码的规范化指纹及其来源版本，实际PYZ匹配后才采用已核注册路径；版本/初始化代码变更须重新取证，未知注册不静默推断。AddDllDirectory多个目录顺序无保证，同名候选字节不一致时拒绝歧义，不以全包basename兜底。
4. API set单独列为Windows契约叶节点，不能当作普通可分发DLL；本机System32的OS叶节点与私有CRT分开。静态图不模拟所有已加载模块、SxS、运行期LoadLibrary、导出转发或最低Windows版本；未映射运行边失败，未知范围在报告明确列不完整，不写全产品加载认证。
5. 安装器编译前调用新加载域检查；提供可复用的只读实际组件/后端诊断入口，不调用本分支旧OfficeRuntime来“验证”新组合格式。原输入组件、清单和字节保持，错误诊断给出来源、导入种类、搜索域及其他不可达位置。
6. 自动化覆盖错域CRT、System32掩盖、延迟边缺失、.com/.bin漏扫、错误架构、API-set/OS叶、图环/大小写/未知范围、已验证与变更的冻结注册代码、顺序不明重名DLL。真实正例用固定组合与新冻结产物，负例仅改内存图/加载根，原文件hash复核；双Python专项、全量Ruff、最终head CI另行记录。

规则依据为[Microsoft DLL搜索顺序](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)、[LoadLibraryEx标志](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexa)及[API sets](https://learn.microsoft.com/en-us/windows/win32/apiindex/windows-apisets)，本轮已打开核对；加载根还来自实际OfficeRuntime受控环境和已比对的固定冻结初始化代码。文档设计先落地，当前IN_PROGRESS，尚未把方案当作实现或测试通过。

### 实施结果与范围收紧

新增native_dependencies.py共享静态图，check_release在原清单/hash/CPython/无数据库校验之后调用；新增check_native_dependencies.py提供只读组件/冻结后端诊断，不执行待检入口或依赖本分支旧OfficeRuntime。PE普通与delay边、实际Office .com/.bin、大小写/非法导入路径、进程域CRT、已注册目录与进程内同名不同字节歧义均有断言。全包同名仅用于缺边错误中的elsewhere提示，绝不满足依赖。未新增依赖、未修改Office运行时/组合脚本、原组件或任何安装器产物。

主Agent进一步明确完整覆盖门禁：闭包外文件不能因不可达就归为非运行模板。本实现输出pe_coverage=partial与全部未分类路径/架构；check_release遇到任一未知PE即拒绝发行，没有跳过开关或按路径免责名单。原独立helper用例仍验证不会被误套主进程架构，进一步要求发行覆盖错误；ARM未知用例核输出partial并拒绝，原文件保持。诊断命令退出0仅代表声明域解析完成，不代表组合可发行。父OFF-02仍需对277项逐项形成可审计运行域/非运行分类及其余实际加载证据；父REL-01不因本切片销项。

check_frozen_sources保留原equivalent的逐字段及嵌套常量比较，将相同字段表共用给code_fingerprint，忽略构建路径/源码行偏移但不忽略嵌套行为。NumPy 2.5.4、Pandas 3.1.0完整初始化代码与固定安装源码及实际PYZ比较后登记指纹；变化/未知.libs拒绝，不通过源码substring猜测动态注册。已注册同名候选字节不同以及各插件域解析到同名不同字节均拒绝，避免不确定AddDllDirectory/已加载模块顺序产生虚假闭合。

### 命令与自动化证据

工作目录.local/goal-20261112/native-closure。Q为根.local/release-venv/Scripts/python.exe（3.13.17），P为根.venv/Scripts/python.exe（3.12.7）；原始日志/JUnit/实际图均位于忽略的artifacts/off02c，临时夹具位于本副本.local。只读真实扫描设置PYTHONDONTWRITEBYTECODE=1，不把产物/组件复制进Git。

- Q -m pytest backend/tests/test_native_dependencies.py backend/tests/test_release_inventory.py -q --basetemp=.local/off02c-gate313 --junitxml=artifacts/off02c/gate313.xml：退出0，84通过（3.48秒）；P同命令使用gate312：退出0，84通过（3.41秒）。覆盖普通/延迟错域CRT、System32不能补私有依赖、Java桥不可达、.com/.bin、错误架构、OS/API-set区分、图环、注册代码变更、两类DLL冲突、未知覆盖阻断、组件清单缺/增/变/hash/路径/版本，以及现有许可复制和重解析保护。
- Q -m ruff check backend tools：退出0，ruff-gate.txt记录全量静态检查通过；不是业务全量运行测试。本地只跑相关专项，独立PR最终head继续完整CI。
- Q tools/check_native_dependencies.py --office D:/computer_work/project/StudyWorkbench/.local/release-tools/libreoffice-java-26.8.1-21.0.13：退出0，office-final.json；先核19743个实际文件（19742个锁内文件+runtime-lock.json），清单SHA256 156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9。解析351 PE/18条delay；Office域69节点850边，Java域9节点109边，重叠节点不重复宣称覆盖。Office CRT落program、独立Java CRT落java/bin；仍有277未分类PE（247 AMD64、26 x86、4 ARM64），结果明确partial，不能通过check_release完整覆盖门禁。
- Q tools/check_native_dependencies.py --backend D:/computer_work/project/StudyWorkbench/.local/goal-20261112/office-bundle/dist/study_backend：退出0，backend33-final.json；#33最终e0a3fcf对应新冻结exe SHA256 bad0e600989de0f85d3b0ded02b195078c83c921ba0bebaa85cc512bde6d1642，1001文件/159 PE/1条delay，声明后端域没有剩余未分类PE。此前FMT新冻结样本同159 PE通过；后端独立诊断并不核完整发行清单或证明安装包成员。
- Q tools/check_release.py D:/computer_work/project/StudyWorkbench/dist/StudyWorkbench-Release-20261110-37a8d55/app：退出0，base-release-gate.txt；旧基础包1304文件清单/hash、CPython、无DB、主进程x64与174 PE/5条delay声明静态域通过，没有未分类PE。它不含本次Office组件，仅是既有基础发行门禁回归，不称新整包构建/安装或干净机通过。
- Q artifacts/off02c/real-negative.py：退出0，real-negative.txt；在真实351 PE内存图中分别移除Office的Java搜索根、Office私有CRT根、Java私有CRT根，三项均出现对应Unresolved import，即使同名文件仍在其他目录或System32。原runtime-lock、officebean、jawt及两个vcruntime140的5项hash前后相等，且Office/Java的vcruntime字节确实不同；原组件没有删除、移动或修改。
- Q读取本分支共享check_frozen_sources，将源码定位到#33 office-bundle（只调整内存__file__），运行原main对实际exe比较：退出0，frozen-sources-final.txt，43业务模块及嵌套代码/常量匹配。另对numpy/pandas的整个PYZ初始化分别与固定安装源码equivalent比较并核规范化指纹，均通过。两指纹为e4f5a942c031e942cb3d44e0f38adedba8c24dd51ae9cbc0c5788c998647e31a、0786ce19ddf69547b54b04728688dad0c8d36b2d54c275ed9bedc608a4d14572。

### 保留失败与限制

target01退出1：71通过/2失败，均为受限环境不能创建Windows链接（child_reparse_directory与collector_license_directory_junction）；原txt/xml保留。获准原生目录复验native313/native312分别73通过、退出0，后续新增边界用例的final313/final312各84通过；上列gate末轮在加强未知覆盖拒绝后再次各84通过。没有删除失败测试或降低断言。Ruff首轮3项unused/import冲突、后续新增用例1项排序均修正，最终全量通过；记录保留。

实际Office初轮office01退出1：普通导入名校验过窄，真实pythonloaderlo.dll导入pyuno.pyd被拒绝。核PE实表后将通用导入扩展到已支持PE扩展名，保留路径/ASCII/非法字符保护并增加pyuno用例；office02与office-final完整hash/图通过。该修正基于合法PE导入形式，不是对缺失DLL增加豁免。第一次小型汇总命令括号遗漏造成SyntaxError，仅统计脚本，修正后重新读报告；不混为产品成功证据。最初全图输出重复每个后端插件闭包，改为保留各插件搜索根、去重边并拒绝跨域不同字节，完整图仍留诊断输出，发行摘要避免重复刷屏。

静态规则不证明所有动态LoadLibrary、已加载模块/SxS、导出转发、API-set的最低Windows可用性或所有helper/插件实际行为。真实Office诊断的277未知项继续阻断完整发行，不能只凭69/9节点给OFF-02整包完成结论。代码审查暂缓，人工/Computer Use已取消；没有合并、签名、安装、发布、清理旧失败或新的模型/下载。实现和专项已完成，任务进入REVIEW，草稿PR及最终head CI核验前不记DONE。

实际交付[独立草稿PR #36](https://github.com/surface-user/StudyWorkbench/pull/36)，分支codex/native-loading-domains，base为#28最终2187fec；实现提交b03d990ddfc9a8fcc1bcd13b9e0688ec4ec2a5cd。九份明确改动的UTF-8/LF/尾空白与git diff --no-index --check通过，原报告前缀、非本项任务行和全部其他基线blob保持。首次聚合传输JSON因输出截断而失败，分块后检测到控制台中文编码长度不符；改用ASCII转义分块并核完整长度后才创建远端tree，没有提交不完整或乱码内容。最终head/CI在PR描述维护，待主Agent核验有限检测/拒绝能力后决定DONE；父项未知范围继续阻断，未合并或发行。

## 2026-11-13 OFF-02d：固定UNO注册入口（设计）

基线为#36最终fbbc8479b039fc69ea41260c7bdd298484effa16/tree ec39c923f1e17e5c443be30fae8ddb6124e7e497，451个tracked blob逐字节核对后复制至独占.local/goal-20261112/office-uno-closure。原根、原Office/Java组件及#36源码不改；共享Q/P环境不升级。首次复制因默认GBK读取UTF-8清单退出1，尚未写目标；使用PYTHONUTF8=1重新执行prepare_next.py office-uno-manifest.json后退出0，451文件匹配。#36的CI43092944364两组后端成功，desktop上传产物步骤失败由主Agent继续处理；本分支不把父项记DONE，不改CI。

读取本副本AGENTS、requirements、architecture、question-content-spec、task及打包/依赖规范、dev规则，并盘点native_dependencies的两个调用方check_release/check_native_dependencies、对应测试、build-release编译前调用。影响只限共享依赖图、专项测试、打包说明、任务和本报告；不改Office进程配置、API/数据库或用户资料，不新增依赖。

已有静态PE导入图遗漏通过UNO注册表装载的入口。固定Office buildid bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1的[ServiceManager](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/cppuhelper/source/servicemanager.cxx)读取注册文件/目录，并在801–818行展开SharedLibrary URI后调用装载函数；[shlib](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/cppuhelper/source/shlib.cxx)在307–310行使用该URI打开模块。官方源Git blob分别为09273863097ba162b830f6c46c18030d2b73d300和5bbefd436833aae5c053c9022197b66c329b2ed5。普通网页读取Cache miss，随后官方GitHub API按固定提交完整获取成功，没有改用未固定版本。

本切片只纳入组件自带的固定UNO注册范围：核program/uno.ini与fundamental.ini完整hash，确定URE_INTERNAL_LIB_DIR/LO_LIB_DIR均指向program、UNO_SERVICES由主services.rdb及program/services内6文件构成；注册目录文件集合及7文件完整hash必须与已核版本一致。随后解析这些已验证字节，SharedLibrary只接受两种已证明变量前缀与单个DLL/PYD文件名，得到53个唯一原生入口及各自注册来源。全部入口加入既有Office进程域，用原有架构/普通与delay/私有CRT守卫解析，不添加全包搜索目录。配置变化、未知注册文件、URI路径越界、入口/传递库缺失或错架构必须失败；Java/Python脚本注册不假装是原生库。

预期专项包括注册来源可追溯、缺/改/增文件、文件预算、跨目录/错误变量URI、非原生注册不混算、已注册入口及传递依赖缺失、原x64/未知覆盖阻断。真实组件先重核19742 payload hash，再比较旧/新覆盖集合，仍未知的CLR/模板/helper等继续列出；twain32shim.exe真实x86/CRT缺口不予免责。原组件、旧失败、源文件身份与发行未知范围保持。独立草稿PR及当前head CI由主Agent核验后才能记本有限切片DONE；不是整包OFF-02或发行完成。

### 实现与自动化

native_dependencies内复用同一closure，新增固定UNO配置核验与注册来源映射，无新执行器/运行时依赖/搜索目录。注册文件每份限1MiB，先校验完整hash再解析同一份字节；非预期文件集合、配置变更及不支持URI均拒绝。主应用/后端/独立Java规则保持，check_release原有未知PE严格拒绝未修改。静态检查扩大了已证明的可加载入口集合，不声称全部入口都在转换样本中实际调用。

工作目录为.local/goal-20261112/office-uno-closure，Q=根.local/release-venv/Scripts/python.exe（3.13.17），P=根.venv/Scripts/python.exe（3.12.7）；设置PYTHONUTF8=1/PYTHONDONTWRITEBYTECODE=1。实际命令和退出码：

- Q/P -m pytest backend/tests/test_native_dependencies.py backend/tests/test_release_inventory.py -q --basetemp=.local/uno-native313（P为uno-native312）--junitxml=artifacts/off02d/native313.xml（P为native312.xml）：均退出0，各102通过，分别3.30/4.87秒。18个新增用例覆盖注册来源/脚本排除、缺改增/预算、URI路径/变量拒绝、未核XML不解析、入口/传递边/架构与未知保留；原84项守卫保持。测试中的目录链接仅在本任务临时目录原生复验，不改系统配置。
- Q -m ruff check backend tools：退出0，全量通过，artifacts/off02d/ruff.txt。没有产品业务/桌面改动，本地不重复业务/Flutter全量；独立PR当前head完整CI仍执行。
- Q tools/check_native_dependencies.py --office D:/computer_work/project/StudyWorkbench/.local/release-tools/libreoffice-java-26.8.1-21.0.13：退出0，完整结果artifacts/off02d/office01.json。核19743实际文件（19742 payload加清单），清单SHA256仍156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9；351 PE/18条delay。53个唯一UNO入口并入Office后，Office域65根/123节点/1528边，独立Java仍3根/9节点/109边。与#36旧图相同输入逐项对照，新增覆盖54项，未知277→223，pe_coverage仍partial。原静态域/已知文件没有丢失，twain32shim.exe仍为I386未知项，整包不能通过发行门禁。
- Q artifacts/off02d/real-evidence.py：退出0，使用真实组件PE/配置数据，仅在内存分别去掉sclo.dll入口、libpq.dll传递库、改sclo架构、去掉fundamental.ini映射、增一条注册映射；五项分别触发缺入口/缺导入/x64/配置缺失/注册集合拒绝。原runtime-lock、9份配置及twain32shim共11个文件前后hash相同，未删除/移动/覆盖原组件。完整结果real-summary.json，执行输出real-evidence.txt。
- Q artifacts/off02d/select-evidence.py：退出0，逐项筛选[off02d-uno-summary.json](evidence/off02d-uno-summary.json)，11599字节，SHA256 923c06b191089c7243733a48be352b2bbfd7e69abf13b5ff574469e3e1ae0c86。仅保留固定配置hash、53入口对应注册来源、覆盖计数/负例与TWAIN未知示例，附原始报告hash/版本/筛选理由；不提交整个artifacts、原组件、完整原始图或个人数据。首轮文档检查发现该新JSON采用Windows默认CRLF，显式LF重新生成后才交付，旧检查失败保留。

原失败保留：target01第一次pytest因未建立独立.local父目录而1通过/47个夹具错误，pytest实际退出1（外层打印命令曾掩盖该退出码，未当成通过）；建立父目录后target02退出1，100通过/2失败，仍是原Windows链接夹具创建被受限执行拒绝。后续两套原生102通过，没有降低或删除断言。实际组件检查运行期间提前读取尚为空的输出曾触发汇总JSONDecodeError，未作为产品失败/成功结论；完整扫描最后退出0后读取458721字节完整JSON并核对，原空读取错误保留于本轮执行记录。

### 基线验收、限制与交付

主Agent已核#36的双Python各84、原277未知/三项实际负例及严格发行拒绝，最终fbbc847的CI43092944364 attempt2三组44步全部成功，接受OFF-02c有限门禁DONE；attempt1上传产物CreateArtifact失败保留，不说该历史运行通过。本OFF-02d只叠加注册入口，没有吸收其他功能或改变父head。

剩余223项仍需独立证明实际运行域或有可审计来源条件的非运行分类；包括CLR、Python启动器资源、独立JRE其他PE、Shell/其他helper。twain32shim的真实x86/CRT问题继续阻断，不能凭当前DOCX/PPTX未调用而豁免。固定注册图不覆盖用户/扩展配置变化、全部动态LoadLibrary/导出转发/SxS、OS最低版本或干净机运行。未执行人工/Computer Use、合并/发布/签名、注册Office/Java或改个人数据。代码审查继续暂缓，任务进入REVIEW；独立草稿PR、最终head CI及主Agent验收另核，完整OFF-02/REL任务不销项。

提交前Q artifacts/off02d/validate-docs.py退出0，核仅6份明确改动，其余基线blob、原报告前缀和非本项任务行保持，UTF-8/LF/无尾空白及本地链接有效；逐文件git diff --no-index --check无任何诊断。首轮辅助脚本误要求存在差异的no-index也必须退出0，因正常差异返回1而失败；修正为仅接受0/1且stdout/stderr均空后通过，未忽略空白错误，docs.txt/docs02.txt保留。PR最终head/当前CI结论在PR描述维护，避免记录自身SHA导致反复变更head。

实际交付[独立草稿PR #39](https://github.com/surface-user/StudyWorkbench/pull/39)，分支codex/office-uno-loading依赖#36最终fbbc847；实现提交35b225e8ad5813ffab63cdf26b6628ae5100d772，452个远端blob与本地逐项匹配后创建PR。随后仅补本交付链接；最终head/本head CI和主Agent验收以PR描述及实时检查为准，未核验前保持REVIEW，不合并或发行。

## 2026-11-13：REL-03c Starlette已知漏洞修复

### 需求、设计与有限范围

主Agent接受REL-03b后，依#35最终a73bedd24c228b61c9f1ccd4290152af2bace57b/tree7fb22b6ea827a0206e4c3a248467611615cd66e1建立独立副本.local/goal-20261112/starlette-fix，450个源码blob逐字节核对。根checkout和其他任务保持。先阅读AGENTS、requirements、architecture、question-content-spec、task及本切片相关API/依赖/证据规则；只修复03a已经记录的Starlette版本发现，不扩大成全栈升级或新框架。

仅将backend/requirements.lock.txt的Starlette0.50.0升至1.3.1，FastAPI0.161.1与其他69个Python锁保持。官方同版本PyPI元数据说明FastAPI要求Starlette>=0.46.0，Starlette要求Python>=3.10、AnyIO>=3.6.2,<5和Python<3.13时typing-extensions>=4.10.0；现锁已满足。未启用full extra或新引入httpx2；TestClient兼容httpx0.28.1，但保留上游弃用警告。

[官方1.3.1发行](https://github.com/Kludex/starlette/releases/tag/1.3.1)日期2026-06-12，[官方包元数据](https://pypi.org/pypi/starlette/1.3.1/json)记录OS Independent/Python3.12/3.13支持，wheel未撤回。官方files.pythonhosted.org下载73632字节，SHA256 c7372aae11c3c3f26a42df7bd626cec2f47d03483d261d369516a615a53714c6；BSD-3-Clause原文SHA256 dcb95677a02240243187e964f941847d19b17821cf99e5afae684fab328c19bf。维护/许可/Windows声明、真实回归和完整分发义务分开记录，不把包许可证标签视为完整发行审核。

调用方检索覆盖backend业务中所有starlette、request.url、StaticFiles、HTTPEndpoint、request.form/Form引用：实际app.py读取request.url.path用于Origin拒绝；app/imports/media_library复用run_in_threadpool，request_limits复用JSONResponse。未发现业务直接使用后三类漏洞入口，不声称已复现这些攻击或证明全部传递可达性。影响范围为一个锁行、原API测试、原真实进程探针、依赖文档/任务/本报告；不改应用业务代码、错误契约、数据库、UI、CI配置或导出接口。

### 旧红新绿与隔离环境

以下工作目录均为该副本，原始日志/JUnit/包与查询字节位于artifacts/rel03c，未提交完整日志、下载包或测试数据。IQ/IP分别为本副本.local/starlette-{q,p}-isolated/Scripts/python.exe（3.13.17/3.12.7）；共享Q为根.local/release-venv/Scripts/python.exe、P为根.venv/Scripts/python.exe。设置PYTHONDONTWRITEBYTECODE=1与PYTHONUTF8=1；新venv仅安装固定官方Starlette1.3.1与既定pytest9.0.3，其他依赖通过本地.pth只读引用共享site-packages。

- Q/P -m venv --without-pip .local/starlette-{q,p}-isolated；Q/P -m pip --isolated --disable-pip-version-check --python <新解释器> install --no-index --no-deps --no-cache-dir --no-user <已核Starlette wheel> <已核pytest9.0.3 wheel>；同一pip --python check：均退出0。记录setup-{q,p}.log及provenance.json。实际环境为FastAPI0.161.1/Starlette1.3.1/AnyIO4.15.1/httpx0.28.1/pytest9.0.3；共享Q/P各109个Starlette/pytest非缓存文件SHA256前后相同，未升级共享环境。
- Q -m pytest backend/tests/test_api.py -q --basetemp=.local/rel03c-old-baseline --junitxml=artifacts/rel03c/old-api.xml：旧Starlette0.50退出1，6失败/6通过。含有效测试令牌的特制Host使Origin校验看见错误路径；畸形IPv6 Host造成未处理URL错误；无前导斜杠ASGI path能污染URL authority。原失败日志/JUnit保留。这是隔离测试入口的具体缺陷，不推断无需令牌的外网攻击能力。
- IQ/IP -m pytest backend/tests/test_api.py backend/tests/test_source_sbom.py backend/tests/test_source_vulnerabilities.py -q --basetemp=.local/rel03c-{q,p}-targeted --junitxml=artifacts/rel03c/{q,p}-targeted.xml：均退出0，各89通过。7个新增用例覆盖五种Host的Origin拒绝、畸形Host受控400/合法带端口Host、ASGI path与authority分离；旧鉴权/判分/追加/重启/媒体206及416继续通过。ASGI直接构造的无斜杠路径不冒充实际HTTP服务器接受该输入。
- IQ/IP -m pytest -q --basetemp=.local/rel03c-{q,p}-full --junitxml=artifacts/rel03c/{q,p}-full.xml：在允许创建隔离测试目录链接的受控权限运行，均退出0，各828通过及77子测试通过（JUnit905条，无失败/跳过）；Q375.68秒、P578.48秒。保留httpx/AnyIO弃用与重复ZIP夹具警告；未删除测试、降低断言或改写03b历史权限失败。
- Q -m ruff check backend tools：退出0。锁内容assert确认精确一行版本变化；其余源码/锁未改。

另从API-01的#34最终8b29a27008e64e0cce6615a2135edda1125a435d精确复制449文件至本任务.local/api-combination，仅覆盖本切片新锁与test_api.py。IQ/IP -m pytest backend/tests/test_api.py backend/tests/test_api_errors.py -q，分别使用独立basetemp及api-combo-{q,p}.xml：均退出0，各23通过，包含新error包装、原detail兼容、关联ID、401/403/400/404/409/413/422/500、脱敏和本次Host/path边界。此为明确组合的源码专项，不把#34全部功能或其他组合分支视为已经合并。

### 真实进程与新冻结包

IQ tools/check_backend_lifecycle.py：退出0。原探针增加6个真实HTTP Host/Origin断言，坏Host不能掩盖API Origin或引发未处理URL异常；其余独占锁、鉴权、客观/中文主观作答、EOF、重启/异常退出、两次搬迁的原件hash/收据/记录保留、DOCX/PDF拆题、媒体capability/状态及迁移父管道取消全部通过。未使用个人数据库。

./packaging/windows/build-backend.ps1 -Python .local/starlette-q-isolated/Scripts/python.exe：退出0，干净新构建，43个冻结业务模块与当前源码一致。dist/study_backend/study_backend.exe为22568458字节，SHA256 3fba079e510e4550d086b7786973f937fa3c2a92e28efcd0e112d6bec82d50a2。独立读取PYZ并复用check_frozen_sources.equivalent核对全部23个已收集Starlette模块与固定官方wheel源码编译结果，嵌套代码/常量一致，明确__version__=1.3.1；记录frozen-starlette.json，不只凭构建命令推断新版已入包。

IQ tools/check_backend_lifecycle.py --exe dist/study_backend/study_backend.exe：退出0，真实新冻结进程在去除开发Python/源码PATH条件下通过同一完整生命周期及新增Host/Origin检查。没有执行人工窗口、安装/干净机或Office整包验收，冻结成功不关闭这些范围。

### SBOM与实际漏洞复查

IQ tools/source_sbom.py --syft <根.local/release-tools/syft-1.57.1/syft.exe> --output artifacts/rel03c/source-sbom：退出0，136源包/8个SDK未知保持。独立对照03b源BOM，集合仅从pkg:pypi/starlette@0.50.0改为pkg:pypi/starlette@1.3.1；BOM SHA256 21a145015875e8d0c62cab8a2a11c886c1b0eb48bc6258fe79a799029abed340，comparison.json SHA256 f89e1c20be9b16f922a5d915b57f96dfb45243d9f5467e897f22e5fc5355488c。Python锁SHA256 8823dec8bd36cedab44ad894dbb018d442590187b23d5af837c1dbb2f2cb2512，pubspec锁仍c1ab979d33d15197f1018cae7ec752cfb0244523e26f3ed2c73ee1f761be2ce5。

IQ tools/source_vulnerabilities.py --output artifacts/rel03c/source-vulns：2026-11-13T03:02:59Z起查询，退出3（设计语义为有限查询完成且无返回公告，不是全产品通过）；135包查询完成、无返回公告，9个Git/SDK排除不变。report.json SHA256 f7a6d67fe4c97d1d97145fa93c17a950b0c8f0db258b46c73bb694d93a3e56df，逐原始请求/响应hash已复核。数据库仍为在线观察，无固定snapshot或完整新鲜度证明；无公告返回不自动证明全部包映射/覆盖或不存在漏洞。

另用原固定querybatch查询器在2026-11-13T03:13:54Z同时查Starlette0.50.0/1.3.1：旧版本仍返回03a所列五CVE对应10个GHSA/PYSEC记录，新版本为空，无分页遗漏。原response SHA256 3cf1641d60f1d668d4a1bafb5dcfc164ac16cd6cf3b9fd70bb66387e0161ebf8；comparison.json SHA256 4e3e2a0db95ac109831aaa02881daeda33b955e7b922ee4169ea9eec0c7d065d。该同批对照加强已知版本发现的关闭依据；不删除03a原发现，不声称Windows StaticFiles/HTTPEndpoint/form三类未使用入口均已复现。

### 保留失败、限制与交付

初次准备脚本按系统GBK读取含中文路径manifest退出1，显式-X utf8后450文件核验成功，未改共享编码。本机PyPI元数据连接先后出现TLS EOF及curl连接超时（exit28），受控权限重试仍失败；使用03a已存官方元数据并经当前官方网页核对相同版本/约束/下载hash，随后从其官方files.pythonhosted.org URL实际下载并核验成功，未关闭TLS证书校验。setup-run02.log保留完整TLS失败。初次证据核验误将BOM中的file组件当作均含purl而KeyError退出1，保留evidence-check.log；改为仅比较有purl的包身份后全部assert通过，未改BOM或产品断言。组合测试首次相对解释器路径拼写错误未启动测试，纠正为任务内实际解释器后才记录23项通过。

REL-03b已由主Agent核验#35最终head CI三组成功，登记DONE。REL-03c实现/本地自动化已完成，状态REVIEW；需本项独立草稿PR、当前head CI和主Agent核验，不能据父#35绿灯销项。代码审查按用户要求暂缓、人工测试取消；本切片不合并或发行，不修改共享环境，不升级不相关依赖。完整最终组件SBOM/传递许可、Office/Java及冻结原生组件漏洞、签名/发行准备仍由父REL任务继续。

实际提交[独立草稿PR #40](https://github.com/surface-user/StudyWorkbench/pull/40)，分支codex/starlette-vulnerability-fix，base为#35最终a73bedd，实现提交d66f636a81acbc0dc4082cf8c809b31cd2fa3f59；最终head与对应CI在PR描述维护，不为记录自身SHA反复提交。精确六文件变更、其余444个base blob未变、锁单行、文档相对链接/UTF-8/LF/尾空白及原报告前缀检查通过。首次检查脚本将Git的CRLF提示/差异退出码与文件换行混淆而退出1，保留diff-check.log及diff-check02.log；显式关闭本次diff的autocrlf并将本任务六文件写为LF后，git diff --no-index --check无诊断，完整检查退出0（diff-check03.log），没有修改Git配置或旧分支文件。

## 2026-11-13：REL-02a 锁定源码依赖的本地许可证据

主Agent从#35最终a73bedd24c228b61c9f1ccd4290152af2bace57b按远端Git blob复制450文件到独立.local/goal-20261112/source-licenses。#35已核CI43092294564三组通过，有限pytest修复DONE，原漏洞/权限失败保留。本项按现行REL-02a范围建立版本、许可原文、声明来源及缺失映射；完整REL-02仍依实际发行成员及官方归档/组合义务，不因本工具交付销项。

范围为tools/source_licenses.py、其独立测试、打包指南/task、本报告和精选摘要；无产品调用方、API/UI/数据库、运行依赖、CI或发行stage变化。复用现有source_sbom锁解析/no_links/PyYAML/packaging，Python标准库读取metadata/RECORD，Dart只读指定package_config及缓存pubspec。新目录内按内容hash保存原字节、逐版本PURL记录原文相对路径/hash及声明来源。拒绝越界/链接/已有输出/异常长度或SHA256；没有下载或替换依赖/原件，没有解释许可标签为完整法律义务。

### 命令与实证

工作目录如上。Q为根.local/release-venv/Scripts/python.exe（3.13.17），P为根.venv/Scripts/python.exe（3.12.7）；实包采集IQ为pytest-fix/.local/pytest-q-isolated/Scripts/python.exe，已安装9.0.3但只读复用Q其他锁依赖。所有命令启用UTF-8/PYTHONDONTWRITEBYTECODE，不改变共享环境。

- 根Q -X utf8 artifacts/goal-20261112/prepare_next.py source-licenses-manifest.json：退出0，450基线文件逐blob一致。首次未加-X utf8，读取含中文路径manifest时默认GBK失败；保留命令结果，未形成副本，改用显式UTF-8后成功。
- Q/P -X utf8 -m pytest backend/tests/test_source_licenses.py backend/tests/test_source_sbom.py -q --basetemp=.local/licenses-{q,p}04 --junitxml=artifacts/rel02a/{q,p}04.xml：各退出0，57通过（22个新证据用例及35个既有锁解析用例）。新用例覆盖原文字节与hash、SDK/产品未知、精确版本缺失/歧义、RECORD变更/长度/路径、缺文/声明自定义文件、重复config/远端URI、超预算、原输出保留、锁变更、vendored metadata身份和CLI缺证非零。
- 首轮q01因未创建.local父目录出现21个夹具建立错误；创建父目录后q02/p02各20通过/1失败，原始JUnit/log保留。失败揭示importlib.metadata.files()会过滤不存在的RECORD项，从而隐藏越界许可路径。修复为直接读取/验证原始RECORD后q03/p03各56通过；未降低断言或删除负例。Ruff初轮import排序1项按既有规则修正。
- IQ -X utf8 tools/source_licenses.py --package-config ../batch-two/apps/desktop/.dart_tool/package_config.json --output artifacts/rel02a/real-final：退出2（明确缺证），136个精确源包、246个原文引用/182个唯一文本，8个SDK占位明确排除；仅latex2mathml3.81.1没有许可原文。Python其余选中文件的本地RECORD SHA256及长度一致；Dart版本与缓存pubspec一致。这是本地证据，未证明归档来源、缓存Git内容、许可完整性或分发义务。
- 实包首轮real01遇setuptools84.2.1携带其他包的嵌套dist-info/METADATA，工具保守拒绝歧义，退出1且无成功report；将发行包身份限定为顶层dist-info、仍保留嵌套许可后real02退出2。为此新增独立vendored metadata回归，没有排除嵌套许可证。real02、real-final原始产物均保留。
- 根Q -X utf8 artifacts/goal-20261112/record_source_licenses.py：逐246引用重新读副本核长度/SHA256，并检查摘要不含本机绝对路径；退出0。精选evidence/source-license-summary.json只保留公共包PURL、文件数、缺证/未知及原报告hash；用于可共享覆盖核验，不提交全部原始日志、缓存或第三方安装内容。

最终report SHA256 192006c171592c548ddd460bcab8aaa4d567ab2ff2678b9d74190b331d68cac3，collector SHA256 1bc9799594876a597e26dbd1e70ee08c28c6c6b83c7a5fcaa446876ce9cf85cd。原文目录与完整逐文件映射在忽略的artifacts/rel02a/real-final；新工具可对后续精确锁与环境重新生成，不复用旧版本结果。当前Starlette仍为该基线0.50.0，独立03c修复需在组合后重采，不能把此清单冒充最终候选。

### 退出边界

本工具是有限证据映射，不是完整许可证审查。latex2mathml缺原文、官方wheel/pub归档/Git来源认证、源码提供/NOTICE/组合义务、SDK/冻结/native/Office/Java/安装器及运行时成员均继续由REL-02后续处理。缺文及未验证原样保留，不以元数据许可证标签或下载链接补记通过。代码审查暂缓，人工测试取消，未合并/发行。本项实现/专项/实际采集与文档完成后REVIEW，独立草稿PR与当前head完整CI核验前不记DONE；最新head/CI由PR描述维护，不为记录自身SHA反复提交。

最终源码（含报告schema_version/采集器hash字段）再次运行同57项，Q/P的licenses-{q,p}-final及q-final/p-final日志均退出0；Q -m ruff check backend tools退出0。六文件范围、原报告前缀、未改依赖锁、UTF-8/LF/尾空白及Markdown相对链接检查通过。首次检查驱动把git diff --no-index --check的有差异退出1误作失败（stdout/stderr均空）；按该命令差异语义接受0/1且必须无诊断，未更改源码或忽略空白报错，保留首次驱动失败。

实际交付[独立草稿PR #41](https://github.com/surface-user/StudyWorkbench/pull/41)，分支codex/source-license-evidence基于#35最终a73bedd，实现提交0506a79e4a11370a0afed8c5a05cda173bb263e7。首次共享摘要采用Windows默认CRLF，被提交检查拒绝；仅将新摘要规范化为LF后，六文件/69链接检查退出0。原始采集report及hash未改。最终head CI和有限交付结论在PR描述持续更新，不记完整许可义务已完成。


## 2026-11-14：OFF-02f 固定JRE动态库加载根

从INT-03/#43精确c666db99e54b5cd62d9f194a4357c9eea9051da9/tree590513029371e666192c4e52f4c67890923731af逐Git blob复制474文件到独立office-jre-domain，原根、#43/#44和组件不动。主Agent已核#43当前CI三组45步成功；#44配置隔离另已核三组44步、45×2及实际进程证据DONE，但本副本不假称已纳其代码。完整读取现行规范及工具/调用方后，任务先登记IN_PROGRESS，设计与只读试探由主Agent确认后实施。

范围为native_dependencies.py、专项测试、打包指南/task、原报告及一份精选摘要。两个调用方check_native_dependencies/check_release继续复用共享工具；不改产品、包布局、组件/原清单或Windows设置。新增精确Java原锁/86DLL路径/hash/AMD64校验，仅把这些包内DLL作为保守额外入口，沿用Java的bin/bin-server及bin私有CRT、Office的program/bin/bin-server及program私有CRT。12个其他JRE EXE、TWAIN/x86/托管程序集/模板等未知不豁免。

只读诊断在根artifacts/goal-20261114。office_static_domains_probe.py退出0，351 PE/223未知与原锁一致；JRE90候选在假设域内闭合，其中78 DLL/12 EXE。其他program、System64及Python目录的假设闭合不作为已证路径；11个CLI/策略PE另核CLR header，policy.1.0.cli_cppuhelper.dll确实32BITREQUIRED，不能据托管格式推定宿主存在或x64兼容。

固定java/release的SOURCE=2ab10ca20c19解析到官方adoptium/jdk21u完整2ab10ca20c191701c3a9f3153bfc6e93d63714c1。Windows java_md.c、HotSpot os_windows.cpp、NativeLibraries.c/java均取固定源并按Git blob核原bytes：JRE由java.home形成bin的boot路径，NativeLibraries先SYS后USER，JNI转JVM_LoadLibrary，Windows实现使用普通LoadLibrary。USER_PATHS仍可含Windows/Sun/Java及系统/当前目录；本项只保守核包内静态导入，不宣称全部DLL都实际运行或任意动态路径已隔离，SxS/已加载模块/转发与系统来源限制继续。

jre_dll_scope_probe.py按原两个域各追加固定86DLL，退出0：Java87根/87节点/390边，Office147根/205节点/1844边，原未知精确新增覆盖78、剩145。首次辅助计算误将两个域各自新增节点并集当全局新覆盖，断言失败；改为与原unknown集合求交后通过，没有改组件/门禁。取源曾遇web缓存/404和文本当JSON错误，artifact写入多余EOF识别后恢复原Git bytes；GitHub一次瞬态无结构返回同端点重试成功，失败均保留。

实现须拒绝Java锁/集合/hash/路径/架构变化，普通与延迟导入全核，不能借另一域或主机CRT补缺口。145剩余仍使check_release拒绝，完整Office/SBOM/许可/漏洞/签名发行不销项。代码审查暂缓、人工取消，不合并或发行。


### OFF-02f 实际验证与交付准备

工作目录为office-jre-domain。IQ/IP分别使用starlette-fix/.local/starlette-q-isolated/Scripts/python.exe（3.13.17）与starlette-p-isolated/Scripts/python.exe（3.12.7），pytest9.0.3；只读复用既有环境，不升级共享Q/P。Q为根.local/release-venv/Scripts/python.exe，仅用于已有静态工具。

- IQ -X utf8 -m pytest backend/tests/test_native_dependencies.py -q --basetemp=.local/off02f-initial --junitxml=artifacts/off02f/initial.xml：退出0，先核48项旧用例。新增13项后，IQ/IP -X utf8 -m pytest backend/tests/test_native_dependencies.py backend/tests/test_release_inventory.py -q --basetemp=.local/off02f-q02或p02 --junitxml=artifacts/off02f/q02.xml或p02.xml：各退出0，115通过，无失败/跳过（61原生域、54发行清单）。覆盖精确Java锁/集/路径/hash/架构/release、两个原域的不同CRT实际目标、额外EXE未知与原保护。初轮q01的113通过/2失败均为旧mklink /J在受限进程权限拒绝，原断言保留，换本任务新目录与已授权本机测试权限后通过，不将原失败计入成功。
- IQ tools/check_native_dependencies.py --office <根.local/release-tools/libreoffice-java-26.8.1-21.0.13>，退出0；先完整核19743文件和原组件hash，再得到351 PE、86固定DLL、Java87根/87节点/390边、Office147根/205节点/1844边。普通与延迟导入均沿原目录/CRT规则，原223未知精确新增78、剩145，12个额外JRE EXE及TWAIN仍未知。输出632306字节，SHA256 bc533a095743014549a8981b43305ebcda905a91bbc4420a25701e66702b3762。这是有限诊断成功，pe_coverage仍partial，不是发行通过码。
- IQ artifacts/off02f/verify_real.py：退出0，原新报告集合/目录/CRT规则逐项相符；9项负例包括真实PE内存元数据的缺失/hash/架构/移动/新增、两份新小副本的Java锁/release篡改，以及Java/Office各自缺CRT不得借另一域或系统填补。原89份选中文件（完整86DLL、Java锁、release及组合锁）前后hash相同。没有写原组件、启动Java工具/Office、执行扫描器或删除字节；这些负例不冒充OS实际加载失败。
- Q -m ruff check backend tools及Q tools/export_question_schema.py --check：各退出0。产品源码与打包参数逐base blob保持，不在本地重复构建/运行已测业务，当前head CI仍须执行完整双Python、桌面/Windows与冻结检查。两个共享调用方及check_release的任何unknown拒绝代码保持原样；本诊断没有组装完整产品stage或执行该发行stage检查，145非空仍构成其阻断输入。
- IQ artifacts/off02f/select_evidence.py：退出0，生成[精选摘要](evidence/off02f-jre-dll-summary.json)，SHA256 24e375c85de51ef74da231fdf3e6a8b01ae388c1a3de88d8c72392745ec3319d；包含固定上游4源文件URL/blob/hash、86 DLL原映射、真实计数/新增路径、负例、JUnit/hash与限制。全部原始632KB图、PE/CLR试探、日志和上游全文留忽略的artifacts，不提交整个原始目录。

实现/相关自动化/文档完成，OFF-02f保持REVIEW；独立草稿PR/当前head CI和主Agent核验后才登记DONE。完整Office剩145候选、未知动态加载/系统叶子及完整SBOM/许可/漏洞/签名发行继续，审查暂缓、人工取消、未合并或发行。

提交前IQ artifacts/off02f/check_docs.py退出0：精确6文件范围、其余469个base blob不变、原报告完整前缀、UTF-8/LF/逐文件git diff --check、84本地引用与45调度行唯一性通过；两份依赖锁、产品Office源码和check_release/check_native_dependencies调用方字节与#43相同。即将创建独立草稿PR，最终head/CI及主Agent验收在PR实时说明维护，不为写自身最终SHA反复提交。
