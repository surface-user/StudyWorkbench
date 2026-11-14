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

## 2026-11-13：REL-01b 冻结后端SBOM与覆盖对照

### 基线、设计与有限范围

主Agent已核#40最终b48b711d0ee1bdc5e2aa507e1e08852be73829ae及CI43359261755三组44步成功，接受REL-03c有限开发交付DONE。此任务基于该head/tree de75bcd2a5e6782400ef1964cacf5570a7e7970a，新建.local/goal-20261112/frozen-sbom副本，逐Git blob复制450个受跟踪文件；不改变旧根、starlette-fix、其他任务或共享环境。相关现行规范、release_inventory/check_frozen_sources/source_sbom与打包规则已读取；任务先登记IN_PROGRESS，实扫后设计获主Agent确认再实施。

输入仅#40本机新冻结后端dist/study_backend，exe22568458字节/SHA256 3fba079e510e4550d086b7786973f937fa3c2a92e28efcd0e112d6bec82d50a2。复用官方固定Syft1.57.1/现有PyInstaller静态格式能力和锁/文件hash函数，不新增扫描器、不上传源码、不执行包内代码、不落地提取、不重新打包或补当前未用的HTML/MathML功能。原始扫描、输出及失败在本任务artifacts/rel01b；只提交[精选摘要](evidence/frozen-backend-sbom-summary.json)，选择理由/来源/hash/未知均在摘要，目录与输出路径不含本机个人路径。

首次Syft真实默认目录实扫在关闭更新/enrich/远端许可、全部文件摘要配置下退出0：969实体文件/145089570字节，扫描前后完全相同。73候选为15实际dist-info声明与58 PE资源候选；CDX另含969 file组件。原始Syft JSON的1106个filesystem条目还包括137目录，不能把目录计作额外文件或包。Syft没有恢复2721个PYZ模块或154个base_library.zip成员的完整包身份；103个PYD也没有scanner包候选。原始探针保留，不凭Scanner支持生态文档推定覆盖。

### 实现与来源界限

tools/frozen_sbom.py输出原始CycloneDX1.6及syft-json，并单独生成coverage.json。固定三种Python installed/PE/binary cataloger、exe SHA256、配置hash、源锁hash、完整实体输入指纹；逐项校对文件集合/hash、实际METADATA名称/版本/唯一性/源锁，以及两份扫描输出中的候选和位置。源锁中的70个PyPI包不直接投影成发行成员；55个没有随包METADATA的锁项只是“未观测元数据”，不是“没有打包”。完整product_sbom_complete恒false，CLI退出1为失败、2为有限对照成功而完整产品仍不完整，不返回发行通过码。

CArchive/PYZ目录检查cookie/TOC/成员范围、预算、重叠/重复、名称和当前解释器字节码；合法runtime option只作为字面元数据保留。每个内嵌条目可追溯到容器/偏移/长度。PYZ的hash明确仅针对压缩字节；9个namespace条目无内容，允许其offset保留写入位置。只对全部43个业务模块解压并静态比较嵌套代码/常量/异常表，不执行code object。ZIP检查原始名称，防止Python将反斜线或NUL静默规范化后隐藏异常；只读取有界成员并核实际解压字节，无提取目标。source head及预期exe hash在工具中明确为调用者声明，source_head_authenticated=false，不把字符串或hash当来源认证。

本次真实来源另由GitHub git/commits接口核b48b711→de75bcd2，并对旧构建源码450个blob及当前43份业务源码逐项核远端tree；43份源码又与实际exe的PYZ代码相等。精选摘要保存这些源码blob/hash及提交/tree证据，未推定一般工具能认证任意远端构建。使用既有CArchiveReader独立对照12项CArchive/2721项PYZ目录的名称、类型、偏移/长度，均相同；所有969实体文件仍等于首次探针前清单。

15个随包metadata仅证明包内声明；58 PE候选的名称、版本、PURL/CPE均保持未认证，不自动推导官方来源或漏洞匹配。4个版本UNKNOWN为libffi-8、两份OpenBLAS DLL及主exe，完整候选位置在coverage.json及精选摘要中保留。2721个PYZ中43个业务模块已与源码比较，2678个其余模块身份仍未映射；154个基础ZIP成员同样不凭文件名补造CPython分发身份。58个DLL/EXE候选加103个PYD后缀文件不是完整原生传递依赖关系或所有内嵌库清单。

latex2mathml3.81.1的既有只读跟进继续保存在starlette-fix/artifacts/rel02-followup：官方wheel/sdist均缺项目LICENSE，固定tag的MIT原文已核；上游unimathsymbols.txt有独立LPPL1.3-or-later声明，原Work固定来源及vendor修改义务未闭合。当前同一冻结exe包含7个模块但不含该数据，既有三个DOCX调用链/冻结文档探针未复现当前已支持流程失败，不能据此声称永久不可达或将项目归为单一MIT。本切片仅列缺口，不向产品补资源或关闭REL-02。

### 实际验证与失败保留

工作目录为上述frozen-sbom。Q为根.local/release-venv/Scripts/python.exe（3.13.17）；IQ/IP只读复用starlette-fix任务内starlette-q-isolated（3.13.17）/starlette-p-isolated（3.12.7），pytest9.0.3。均设置PYTHONDONTWRITEBYTECODE=1，不升级共享依赖。命令与原始JUnit/log在artifacts/rel01b。

- IQ/IP `-X utf8 -m pytest backend/tests/test_frozen_sbom.py backend/tests/test_source_sbom.py backend/tests/test_release_inventory.py -q --basetemp=artifacts/rel01b/tmp-iq05或tmp-ip05 --junitxml=artifacts/rel01b/combined-iq05.xml或combined-ip05.xml`：各退出0、140项通过，无失败/跳过；其中52项新测试、原35项source SBOM与53项inventory保持。覆盖不执行夹具代码、压缩/ZIP预算、namespace、危险原名/重叠/重复/越界、错误解释器、源代码漂移、metadata重复/错版本、缺失/额外/篡改扫描结果、错工具hash、输出嵌套/已有输出、扫描中源与payload变化及超时。全产品业务全量不在本次本地重复，独立PR当前CI继续执行全量。
- Q `tools/frozen_sbom.py --payload <#40原冻结目录> --source-head b48b711d0ee1bdc5e2aa507e1e08852be73829ae --exe-sha256 3fba079e510e4550d086b7786973f937fa3c2a92e28efcd0e112d6bec82d50a2 --syft <根.local/release-tools/syft-1.57.1/syft.exe> --output artifacts/rel01b/real05`：退出2（预期有限成功），969实体/15 metadata/58 PE候选及全部内嵌条目对照通过；扫描前后原包、锁和源码均不变。
- Q `-X utf8 artifacts/rel01b/verify_real.py`：退出0；实际1042个CDX组件通过官方1.6 Schema及本地引用校验，三份Schema来自CycloneDX/specification固定1.6 tag，其SHA256与REL-01a已记录原文一致；同时核上述Git来源、现有reader目录一致及第一次探针至最终文件清单相同。无Schema网络解析回退。
- Q `-m ruff check backend tools`及`tools/export_question_schema.py --check`：均退出0。此工具不改产品调用方/数据库/打包参数，既有冻结包只读复用；不额外构建产品或声称新的运行时功能通过。

real05 coverage.json SHA256 59ee081298406076d537aeac7dfd0b6fe72a6f79218b12a44116cf8cdad32956；backend.cdx.json SHA256 3404363c91bb6f298d9a72211f5e186f683b36986d949b4a4a1181c9ac2147c2；backend.syft.json SHA256 44078d9c154bb87b73b7a45b03ae2b90bf3c7fcf344ba3f5755caa3617d83406。精选摘要SHA256 45a4d09fdab080528bffa0f3711109a05e903fdccb6d09d9aab793411d717e63，包含输出、配置、工具、源码和扫描输入的关联；只保留未知候选的名称/版本/位置，全部推断CPE仍在原始输出，不复制为已核身份。

原失败保留：最初误读不存在的spec路径退出1，随后核实际build-backend.ps1；real01先拒绝合法PyInstaller runtime option、real02拒绝Rich动态模块连字符、real04误要求namespace零offset，均退出1，按实际固定格式补齐支持后real05通过，不跳过目录/版本/字节码保护。初轮双Python新测试各43通过/1失败：Windows ZipFile在创建夹具时规范化反斜线；改为保留实际原名的夹具，并让解析同时核orig_filename/filename，旧日志保留。初轮合跑双Python各130通过/2失败均为旧mklink /J夹具在受限进程中访问被拒，未删改旧断言；改用任务内全新临时目录和已授权本机测试权限后各132、139及最终140通过。早期ruff仅导入排序失败，修正后全量静态检查通过。原始失败不进入成功计数。

实现、相关自动化及文档完成，REL-01b保持REVIEW；独立草稿PR/当前head CI与主Agent核验后才DONE。审查按用户要求暂缓、人工测试取消，未合并或发行。源码锁切片/此目录文件覆盖不关闭REL-01：剩余Python/native身份与来源、完整组件关系、前端/SDK/NuGet/CRT/WebView2/Office/Java/安装器payload仍需后续逐项核验，许可/漏洞/签名父任务保留。

实际创建[独立草稿PR #42](https://github.com/surface-user/StudyWorkbench/pull/42)，分支codex/frozen-backend-sbom，base为#40最终b48b711，实现提交064a033444b7187967564ce330b5951c6391441d。精确六文件范围/其余447个base blob不变、原报告完整前缀、UTF-8/LF/尾空白与本地文档链接检查退出0；源码与候选均未改写。最终head/对应CI结果在PR实时说明维护，不为记录自身SHA反复提交；当前CI未知不能记通过。

## 2026-11-13：OFF-02e 受控Office配置来源（设计，尚未实施）

本切片在新的.local/goal-20261112/office-config目录，以#33最终e0a3fcf66f18752df4c67b19151b21ef94f2f0f4/tree a5d7d8253f71a28fc5cdb38bacb2ef8dfdd437f4的452份文件逐blob核对创建，未改根checkout、其他独立副本或原Office/Java组件。主Agent已接受OFF-02b有限组合交付（上述#33的CI 43072881498三组44步成功）；另接受#36最终fbbc847的OFF-02c及#39最终2da4306的OFF-02d有限门禁交付，后两者是独立分支，本副本没有合入其实现。#39当前head CI 43359332568三组44步成功，102×2专项、53个UNO注册入口及新增54项覆盖成立，但223项未知及TWAIN实际x86/CRT缺口继续保留，完整Office/发行未完成。

### 问题与固定版本依据

本产品只提供有界、无宏/外部关系的DOCX/PPTX headless转PDF，不承诺扫描器、GUI或任意UNO调用。固定LibreOffice源构建bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1的desktop/source/app/appinit.cxx:105-115先从org.openoffice.Setup/Office/ooSetupConnectionURL建立acceptor，再处理命令行--accept；app.cxx:1658-1661投递EnableAcceptors。因此命令中没有--accept不证明配置途径无法启用监听。原fundamental.ini的CONFIGURATION_LAYERS包含HKLM/HKCU winreg及bundled/shared/user扩展层；configmgr/source/winreg.cxx把策略Final=1转为oor:finalized，临时profile仅设宏安全标志不能覆盖已finalized的值。本轮没有读取或改变宿主注册表，不能声称本机已存在该策略/实际监听。

已通过GitHub读取同一固定构建源：sal/rtl/bootstrap.cxx（blob 7073ba6aa1e8a2f6fb01a079afbeaf9eec79a12c）:154-196解析-env:键=值；:476-575、:602-620的普通查找优先级为fundamental.override.ini、进程内rtl_bootstrap_set、命令行、环境，再普通ini/fundamental。固定组件内没有fundamental.override.ini，原逐文件集合/hash核验会拒绝额外文件；不能把命令行优先级概括为无条件最高。configmgr/source/components.cxx（85e66a1f27f6b1e5713134090ce1f0f860130a42）:499-635只按显式CONFIGURATION_LAYERS逐层解析，winreg仅在对应token存在时读取；用户可写层必须最后。cppuhelper/source/defaultbootstrap.cxx（e66052af42db7a13f9a58ea76df1044e4727609b）:48-59从bootstrap取得UNO_SERVICES/UNO_TYPES并初始化注册表；pyuno_module.cxx（b1eb13ec659cd1f79963d5ca16115d733c6d8db8）:232-273可在独立进程创建本地UNO上下文，无需网络listener。

### 最小设计与受影响调用方

拟在现有OfficeRuntime.command统一构造固定bootstrap参数：CONFIGURATION_LAYERS只含包内share/registry的xcsxcu与res层，以及本任务profile/user/registrymodifications.xcu可写层，完全不枚举winreg或扩展配置层。路径用本地绝对file URI编码，避免中文/空格被配置层分隔符解释。UNO_SERVICES/UNO_TYPES明确限于包内现有注册文件（7份services、3份types），Java类型classpath限于现有libreoffice.jar/ScriptFramework.jar，不读取user/shared/bundled扩展unorc；保留官方文件/SBOM/许可清单，不删服务注册或组件。profile另显式写空ooSetupConnectionURL，作为受控层内的声明，不以它单独抵消强制策略。

源转换和冻结launch_office均已调用同一command，沿用原输入复验、profile字节复验、清洁子进程环境和Job预算；不用新框架、不加依赖、不改全局环境或注册表。OPTIONS需升级以使旧配置产生的预览缓存不冒充新策略转换：office_previews.OPTIONS_HASH已用于ready缓存匹配，原件/旧派生保留。受影响自动化为test_office_launcher/test_office_previews/test_office_java_bundle、现有check_office_previews与冻结构建；文档仅更新实际Office配置边界、task及本报告。

### 验证计划及限制

先验证固定包Python/UNO本地上下文探针可读取引擎最终配置，利用本项目临时自编XCU模拟含oor:finalized=true的外来层：对照证明不受控层会覆盖/冻结宏或连接值，再证明固定配置层忽略该文件；不创建acceptor、不操作宿主策略。探针需记录使用的实际DLL/源版本、bootstrap值及最终配置值；如仅能借环境传参而不能直接覆盖实际soffice命令行，则明确将其作为同引擎配置解析证据，与真实源码/冻结转换及实际子进程环境/命令行探针分开，不冒称完整实际进程证明。扩展unorc注入/未知注册来源需有实际拒绝或忽略反例，不能只做字符串断言。

相关双Python自动化覆盖固定层/URI编码、外来环境清除、源与冻结helper同参数、配置篡改先拒绝、旧缓存不复用；随后用既有自编DOCX/PPTX执行源码与新冻结真实转换，继续检查各3页、公式/图表、取消重试、缓存重启、原件hash及XML预算拒绝，保留旧失败。完整冻结构建核模块，Ruff和文档检查、独立草稿PR及当前head CI均必须实际完成。设计仍待主Agent确认，尚未实施代码或宣称验证成功。

此切片不新增扫描支持、不运行TWAIN、不据配置限制自动豁免其依赖，不改变check_release。它不等于Windows文件/网络沙箱、任意恶意文档安全、完整扩展/动态调用不可达证明、完整SBOM/许可/漏洞/签名或干净机发行结论；尚未证实的路径继续未知。人工/Computer Use取消、审查暂缓，未合并或发行。

### OFF-02e 实施与中间自动化记录

主Agent确认上述有限方案后，office_runtime.py的command增加固定CONFIGURATION_LAYERS、UNO_SERVICES、UNO_TYPES、URE_MORE_JAVA_TYPES四项，与原UserInstallation共五项；7/3/2个注册/类型/jar路径来自原固定包，旧无Java组件含相同Office文件，未改其支持范围。profile写空连接，OPTIONS升v4。environment原本就只取SystemRoot/WINDIR再显式填充任务/Java环境，本轮无须再造清洁环境框架；新增回归覆盖URE_BOOTSTRAP/INIFILENAME/UNO_*等不继承，原进程变量保持。源码和冻结helper仍复用同一command；缓存测试保留旧PDF与ready记录、禁止旧选项复用/分页，重新生成另建任务。

以下工作目录为office-config副本，Q/P/C/F含义沿OFF-02b；Q实际3.13.17、P实际3.12.7（本机Anaconda旧开发环境，不作为发行Python），未升级共享环境。

- Q -m pytest -q backend/tests/test_office_java_bundle.py backend/tests/test_office_launcher.py backend/tests/test_office_previews.py --basetemp=.local/off02e-target02 --junitxml=artifacts/off02e/target02.xml：退出0，44通过，74.85秒。P同组、basetemp=.local/off02e-py312-02、XML py312-02.xml：退出0，44通过，89.81秒。后续新增原运行时清单用例中fundamental.override.ini额外文件拒绝断言，Q/P分别以-k runtime_inventory、basetemp=.local/off02e-override313/312、XML override313/312.xml补跑：各退出0、1通过。没有增加依赖或减少原断言；Starlette弃用警告保留。
- Q -m ruff check backend tools：退出0。Q artifacts/off02e/validate_docs.py：退出0；452个基线blob中仅预期7个既有文件变化，其他blob保持、UTF-8/LF/空白/文档链接、原报告前缀与其他任务行保持；最终精选证据加入后还需复核。
- ./packaging/windows/build-backend.ps1 -Python Q：退出0，277.98秒完成构建，43个冻结业务模块（含嵌套常量/异常表）匹配本次源码；exe SHA256 2f4c9a30c092ee7f049530090b8ed599717acc0c0b8a1e251db0694492941ee8。只更新测试/报告不影响该源码证明；冻结实际转换仍需单独成功。
- Q artifacts/off02e/configuration_probe.py：退出0。固定包program/python.exe加载本地UNO配置上下文，只实例化ConfigurationProvider；bootstrap参数来自本次command并以该诊断进程环境传递。自编只读foreign-finalized.xcu能使有效MacroSecurityLevel=0、DisableMacrosExecution=false、ooSetupConnectionURL=固定未使用pipe字符串；受控层返回3/true/空，其他脚本/OLE/Python/链接配置值也读取核对。自编user unorc注册的虚构服务在默认注册来源可枚举，在固定服务来源不能枚举；没有实例化虚构DLL、Desktop、acceptor或扫描器。日志/JSON为config-engine01，不能将此环境传参探针充当真实soffice CLI观察。
- Q artifacts/off02e/reject_changed_profile.py：诊断退出0，实际新冻结--launch-office退出1且明确“转换配置已变化”；输出目录空、原自编DOCX SHA256保持69169843ffc5c1335bf08cbb58523b9f272b74006f3f2839f30a91f9610b8f1b。只修改本探针临时profile，不改原Office/Java。
- Q artifacts/off02e/observe_conversion.py --mode source --test-root .local/off02e-source02：内层既有check_office_previews退出0，源码DOCX/PPTX各3页、PDF108085/77986字节，公式/图表、取消重试、缓存/重启、XML预算拒绝、原件hash及数据库检查通过。外层进程观察器退出1，因假设Office命令最后一项为源文件而全部1293次拒绝；不得把内层转换通过当作实际命令/环境采样通过。正在单独核真实argv后修正诊断比较规则，产品五项参数及90秒引擎限制未改。

保留早期失败：新增回归先红5项/原环境隔离1项通过；首次44项中43通过，新增缓存用例用最小伪DOCX调用正文接口导致KeyError，改用已有真实自编original-study.docx并增加HTTP200断言后44×2通过。误标target312b的一次命令实际仍使用Q（44通过），不拿该记录代替P，P证据以py312-02为准。桥接Python原生argv计数为0，直接传-env没有覆盖环境，已据实保留；尝试手工初始化native argv先因DLL定位失败，随后子进程返回3221226356，停止该私有初始化路线，不把它作为产品结论。辅助PowerShell替换脚本引号错误没有改目标，改用明确补丁后继续。首次source01观察器逐UTF-16字符读取变化中的环境时ValueError，终止测试驱动；该任务在数据库保留interrupted，不能据此判断产品转换成败。第二版改为受限单次内存快照/指针复核并重采样；观察器总等待改为1800以容纳既有两份文件各600秒等待，产品90秒与原工具600秒均未上调。只读CIM查询被环境拒绝，未申请系统变更，继续用本探针拥有的后代进程读取。

### OFF-02e 实际进程复验与交付准备

Q artifacts/off02e/inspect_office_arguments.py：退出0，仍调用OfficeRuntime.convert完整核验后实际转换自编DOCX。确认soffice.com为soffice.bin追加转义后的-env:OOO_CWD=2<本任务cwd>，并增加ATTACHED_PARENT_PROCESSID环境项；固定构建[desktop/win32/source/loader.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/desktop/win32/source/loader.cxx#L86)（blob 4246f3f7b7c21b7870f44b3a5b522411240ddc9d）86–125、303–327行解释这两项。观察器据实改为精确验证这两个派生值及所有原参数，不使用任意尾参数豁免。

- Q artifacts/off02e/observe_conversion.py --mode source --test-root .local/off02e-source03：内层实际转换与外层观察均退出0。源码DOCX/PPTX各3页，PDF108085/77986字节；公式/图表、取消重试、缓存/重启、XML预算拒绝、原件hash及数据库完整性通过。只采样本诊断后代的实际soffice.bin，核对目标exe身份、每项产品参数、官方内部cwd/父PID及全部环境集合/值；采得4个实际进程，覆盖两种格式，采样错误0。
- 同一命令--mode frozen --test-root .local/off02e-frozen01：内层调用现有check_office_previews.py并传入本次dist/study_backend/study_backend.exe，内外均退出0。DOCX/PPTX仍各3页、108085/77986字节及同组业务断言通过；另外4个实际soffice.bin参数/环境核验通过，采样错误0。原工具将后端PATH限System32且清除PYTHONPATH/PYTHONHOME；观察驱动故意向后端继承12个外来bootstrap sentinel，实际Office中均未出现。没有在产品代码植入观察或探针入口。
- 冻结exe为22566741字节，SHA256保持2f4c9a30c092ee7f049530090b8ed599717acc0c0b8a1e251db0694492941ee8，43模块源码匹配。固定7份services/3份types/2份jar在原Office清单、组合清单及实际组合文件的hash一致，组合19742个payload文件仍由每次真实转换前完整核验；本次另精选4份启动INI、12个注册/类型/jar、TWAIN及3份清单的实际hash，没有改原组件。
- Q artifacts/off02e/select_evidence.py：退出0，生成[精选摘要](evidence/off02e-configuration-summary.json)，17699字节，SHA256 e49c79e01c02cca10c07e30088a0cadff6179fa524cd9b34e192bda486c1c051。仅选择支持本切片的实际配置值/反例、JUnit摘要与hash、源码/冻结转换结果、进程参数/环境hash、组件hash及限制；原始100KB采样失败、全日志、临时profile/PDF/样本/exe仍在忽略的artifacts/.local/dist。三个独立诊断源逐字筛入[配置引擎探针](evidence/off02e-configuration-probe.py)、[进程观察器](evidence/off02e-process-probe.py)、[冻结配置拒绝探针](evidence/off02e-profile-rejection-probe.py)，重现须按摘要executed_path放回artifacts/off02e并使用本节固定组件；没有把整目录或个人资料提交。

进程诊断只读本次后代，不读/写其他进程或宿主策略。其NtQueryInformationProcess/PEB命令布局依据[微软接口](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess)和[参数结构](https://learn.microsoft.com/en-us/windows/win32/api/winternl/ns-winternl-rtl_user_process_parameters)；environment偏移是本机x64有界校验的诊断ABI，微软明确内部结构可变，不能当跨Windows版本的产品接口或完整执行轨迹。成功采样与同引擎配置解析是互补证据，未在真实soffice内部读取最终配置对象，也未做宿主策略注入/监听测试，不扩大为完整OS隔离或任意第三方文件安全结论。

实现及上述本地自动化已完成，task进入REVIEW；独立草稿PR/最终head CI与主Agent有限验收仍待完成。完整Office的未知原生组件/TWAIN真实依赖缺口保持，配置限制不自动给任何文件豁免；完整SBOM/许可/漏洞/签名、集中审查、正式发布仍分别未完成。人工/Computer Use取消，未合并或发行。

OFF-02e已创建[独立草稿PR #44](https://github.com/surface-user/StudyWorkbench/pull/44)，分支codex/office-config-sources依赖#33精确e0a3fcf；首实现提交fe3b233c0d26e0bb2c65f48e3d4c279f58d26632/tree 6f7f749abb4e776753a33f97f2d4b75e734beda6，仅11份范围文件（7份既有源码/测试/文档、4份逐项精选证据）。随后仅补本交付链接；最终head/CI与主Agent有限验收以PR描述/实时检查为准，未核实前保持REVIEW，不把待核CI写成通过。未提交artifacts整目录、样本/PDF/个人库或二进制，不合并/发行。


## 2026-11-13：REL-02b1 固定上游许可原文及内嵌声明

从INT-03/#43精确c666db99e54b5cd62d9f194a4357c9eea9051da9/tree590513029371e666192c4e52f4c67890923731af复制474个已核Git blob到独立source-license-supplement，保留原分支/根文件与历史失败。该组合本地回归通过、其当前head CI仍跟进；本切片依赖已交付#41许可采集能力，不将父CI未知当成功。读取现行任务、规范及工具/调用方后，先登记IN_PROGRESS。

范围限定已有source_licenses开发采集器、其专项测试、三份固定许可来源资料、打包指南/task和本报告。不改产品下载/解析/运行依赖、打包payload或原第三方文件。复用现有文件边界、内容hash及证据复制，只针对精确latex2mathml3.81.1九个已核package文件追加仓库来源的许可原文；元数据的原MIT声明保留，同时独立记录unimathsymbols数据的LPPL-1.3-or-later及未闭合义务。原发行归档缺文事实不清除，不把补充原文伪装为installed RECORD中的文件；全产品许可/归档来源/分发义务仍false，LPPL原Work来源及vendor修改条件保留在父REL-02b。

来源沿用并独立重核#40只读调查的官方wheel/sdist哈希、固定tag九文件Git blob及MIT原文；两归档均缺LICENSE。MIT原文来自固定fb724a91658cf41d2fad0192da0845b05446f208/LICENSE，LPPL1.3c原文来自latex-project.org固定版本URL，逐原字节复制，不重新排版许可文本。LPPL许可明确允许原样复制许可文本；这不等于其数据分发条件已满足。根辅助prepare_license_supplement.py逐九文件核wheel/sdist/tag一致，退出0，不解包到共享环境或修改产品。

本轮再次读取官方LPPL原文和原作者LUCR入口；后者仍跳到个人主页，不把HTML或第三方镜像自动当原Work。需要保留原作取得方式、修改通知等未闭合事项，不能仅补MIT就关闭完整REL-02。


### 2026-11-14：REL-02b1 实际核验与交付

调用方只在collect→python_evidence中增加精确latex2mathml3.81.1补充，其余版本/包保留原缺文行为。采集器只读本仓库来源配置/原许可和本地package九文件；核PURL、九文件hash、文本hash/长度与路径边界，采集中再次核来源配置和package不变。不存在通用main许可证兜底、联网下载、执行源代码、修改installed RECORD或产品payload。输出明确标记repository_supplement，原MIT元数据、数据独立LPPL声明/作者/旧头日期和原分发缺文事实保留；任何原文补充不将分发义务字段设为true。

Q为根.local/release-venv/Scripts/python.exe（3.13.17）；IQ/IP为starlette-fix/.local/starlette-q-isolated与starlette-p-isolated中的Python3.13.17/3.12.7，实际pytest9.0.3/Starlette1.3.1，只读复用既有依赖，不安装/升级共享环境。设置PYTHONDONTWRITEBYTECODE=1，工作目录source-license-supplement，全部本地日志/XML保留artifacts/rel02b1。

- IQ/IP -X utf8 -m pytest backend/tests/test_source_licenses.py backend/tests/test_source_sbom.py -q --basetemp=.local/supplement-q03或p03 --junitxml=artifacts/rel02b1/q03.xml或p03.xml：各退出0，72通过、无失败/错误/跳过；原57项保持，15项新增覆盖精确来源/独立范围和未闭合条件、九文件篡改/缺失、原文篡改/长度、PURL/数量/路径、来源缺失/采集中变化、其他版本不得兜底及CLI仍为2。加入独立数据作者声明后执行最终03轮，早先02轮同样72通过不是累计计数。
- Q -m ruff check backend tools及Q tools/export_question_schema.py --check：均退出0。产品API/数据库/UI/运行依赖未改变，不重复完整本地业务/桌面/Office转换；独立PR当前head CI继续执行原完整回归和冻结检查。
- IQ tools/source_licenses.py --package-config ../batch-three/apps/desktop/.dart_tool/package_config.json --output artifacts/rel02b1/real02：退出2，136精确源包、248原文引用/184唯一文本；所有副本逐引用核长度/SHA256，源码锁与#43相同。两份新增原文是固定MIT和LPPL1.3c；仅latex2mathml有两个保留issue：上游分发缺文、LPPL原Work和vendor修改条件待核。完整产品许可/全部归档来源/分发义务始终false。
- real02/report.json SHA256 1ae042486dc0cb83303304ad9eda594022cf14780c1e48630d44e6cae5f29bea；collector SHA256 8890dd279ce5193f1d2167fcbccb95b361dfb845315677944f2969ae614455f8；provenance.json SHA256 2b9d2a05a7bdbe72bf9395f76793d4678b7bbbb39b0dd7f6da693a28db294b8e。精选摘要evidence/latex2mathml-license-summary.json为14a81b8b82ca0eb8e74ce25140988e0d5fa77f6dac075f6a5d337d8678e673d8，只含公开来源/hash/范围/缺证及计数，未含本机绝对目录或全部第三方安装内容。

失败保留：q01首次--basetemp的.local父目录未建立，26通过/46个setup错误，退出1；没有产品断言失败，也未记通过。建立任务内父目录后用新q02/p02及最终03目录重跑，不删除第一次日志。real01为追加数据作者/旧日期元数据前的旧快照，同样退出2，保留但不混作最终real02。新增许可原文逐字节保留官方文件，MIT1071字节/hash4ac1e1da07f6b343d54191c5e1716840534e08591b3f9eaec90d6800cdc47543，LPPL19036字节/hashc1ae6e179a6d28bbd5c483fbacc744acc75e922d598281dc3390aab26126e163，没有重排版权或许可文本。

父INT-03/#43已由root核最终c666db9的CI43365961531三组45步成功，有限组合DONE。兄弟REL-01b/#42、OFF-02e/#44及DL-02a/#45已分别核验当前head CI登记DONE；本切片只同步交付状态，不含这些兄弟工具/产品代码或站点契约。用户明确的B站/抖音/爱奇艺范围与B站先行继续；预览不是整个DL-02下载目标，格式交接与DL-03避免循环依赖。真实实现/后续组合继续独立PR。

当前REL-02b1实现/相关自动化/文档完成，REVIEW，等待独立草稿PR/当前head CI；LPPL原Work/修改条件及实际payload许可仍在父REL-02b/REL-02，不能因取得两份文本销项。审查暂缓、人工取消、未合并或发行。PR最终head/运行和有限验收结果在PR描述维护，不为写入自身SHA循环制造提交。

提交前逐文件Git空白检查首次在官方LPPL原文末尾空行报告退出3；该文件许可明确禁止修改许可文本，因此保留原19036字节及官方SHA256不变，不将这条原版格式诊断记为修复或普通空白通过。辅助核证改为对这一个逐字原件强制官方完整hash，其他8份变更继续原git diff --no-index --check；源码/测试/文档没有放宽。Q -X utf8 artifacts/goal-20261112/check_license_supplement.py聚合退出0：478文件/预期9变更/469原blob保持、84本地引用、46调度行唯一及旧报告完整前缀、两锁不变核对通过。


## 2026-11-14：REL-01c 冻结Python成员与构建源身份对应

主Agent已核#42最终fb5b7a2e44377abc7b53c7eb4a3ed54166112a67及CI43366003202三组44步成功，登记REL-01b有限开发交付DONE。其文件目录覆盖不是全部包身份，2678个非业务PYZ模块、103PYD和其他非PE数据归属仍待核；完整REL-01不关闭。继续使用既有.local/goal-20261112/frozen-identities副本，开始前逐453个本地文件核对#42远端tree62d7092a309713630d3f103fd97b3b0d9b59dd20，全部Git blob相等，没有覆盖旧实现。root、#42、共享环境及原冻结payload保持。

已读本副本AGENTS、现行需求/架构/题目协议/task、打包指南和dev证据规范。实现前先运行忽略artifacts/rel01c/probe.py的只读探针：固定#40原冻结exe SHA2563fba079e510e4550d086b7786973f937fa3c2a92e28efcd0e112d6bec82d50a2，复用现有嵌入目录/业务静态核验；从精确源锁版本的实际安装METADATA/原始RECORD建立本地来源索引，只在实际PYZ静态代码等价或实体文件字节hash相同且RECORD hash/长度通过时记候选对应，优化等级0/1/2分别记录。不会执行包内代码，不以所有环境包或模块名前缀直接认定发行成员；探针结果用于最小设计，产品实现尚未开始，先报主Agent。


### 实现和实际边界

主Agent确认上述只读设计后，实现tools/frozen_python_members.py及独立测试，另同步打包指南/task/本报告和[精选摘要](evidence/frozen-python-members-summary.json)，共六文件；不改原扫描器/打包参数、产品入口/数据库、依赖锁或其他任务。调用方只有新增显式开发CLI，无产品路径或exports需要接入。复用原inventory/embedded/metadata/bounded_inflate/equivalent/no_links与重复JSON键守卫，Python标准库读取实际构建环境，不增加依赖或联网。

消费REL-01b coverage后先重新核固定payload集合/hash、锁、随包metadata、内嵌目录和43业务源码。以实际PYZ名/实体路径筛选RECORD后才读取构建文件；不会扫描所有环境文件当成发行内容。原始METADATA必须名称/版本唯一且与源锁匹配，候选源文件先核RECORD SHA256及长度，再进行静态code等价或实体字节比较；代码从不执行。每条匹配保存PURL、实际位置、源文件/metadata/RECORD hash及所有等价编译优化等级，多候选则保留歧义。最终源复核保持每个输入原有大小预算，不能用较宽的二进制预算读增长后的metadata/源码。

输入coverage上限16MiB，RECORD/metadata各4MiB、全RECORD共100000行；选中构建证据20000文件/逻辑1GiB，编译输入8MiB/文件，其他源文件256MiB/文件。复用内嵌8MiB有界解压。记录预算计算只含需要读取的构建证据；合法../Scripts或其他不安全RECORD路径不沿出site-packages读取，没有SHA256的候选明确未验证。输出新目录保留失败现场，但观察到任一源/payload/锁/coverage变化不写最终JSON。

members.json完整列出本地包与逐成员证据/未知；python-members.cdx.json仅为唯一对应成员的CycloneDX1.6子集，以occurrence关联实际位置。元数据hash不是包归档hash，不放在component hashes冒充归档。固定product_sbom_complete、upstream_provenance_verified、source_head_authenticated=false；退出1为失败、2为有限对应完成，不返回发行通过码。namespace、stdlib/基础ZIP、CArchive启动脚本/bootloader及其他未映射内容继续。METADATA/RECORD和字节/代码相等不证明官方来源、完整所有权、整包随带、运行时可达性或完整依赖边。

### 当前结果与实际命令

工作目录为本frozen-identities副本。IQ/IP为starlette-fix/.local/starlette-q-isolated（3.13.17）/starlette-p-isolated（3.12.7），pytest9.0.3，只读复用而不升级共享Q/P；Q为根.local/release-venv/Scripts/python.exe，仅运行既有Ruff或辅助验证。命令均设置PYTHONDONTWRITEBYTECODE=1，原始JSON/JUnit/log均在artifacts/rel01c，不提交完整日志/安装内容。

- IQ/IP -X utf8 -m pytest backend/tests/test_frozen_python_members.py backend/tests/test_frozen_sbom.py backend/tests/test_source_sbom.py backend/tests/test_release_inventory.py -q --basetemp=artifacts/rel01c/tmp-q03或tmp-p03 --junitxml=artifacts/rel01c/q03.xml或p03.xml：原生测试权限各退出0、176通过（当时36新+原140），11.70/12.04秒，无失败或跳过。新增对应覆盖不执行夹具代码、实际成员与未使用环境包分离、共享归属歧义、原件不变、源码/数据差异不归属、RECORD/metadata完整性、输入/输出边界、精确版本、预算和期间变更拒绝。没有删除旧测试或降低断言。
- 后续只调整fixture模块复用/import后，IQ/IP新专项各36通过；补充末尾来源复核继续遵守各自原预算的保护及2负例后，IQ/IP -X utf8 -m pytest backend/tests/test_frozen_python_members.py -q --basetemp=artifacts/rel01c/tmp-q05或tmp-p05 --junitxml=artifacts/rel01c/q05.xml或p05.xml：各退出0、最终38新专项通过，8.58/9.40秒。先前原140测试对应函数未变，不以旧176当成一次最终178全跑；完整本head全量另由CI执行。
- Q -m ruff check backend tools：最终退出0（ruff03.log）；IQ tools/export_question_schema.py --check：退出0，Schema无漂移。工具未改业务代码，不在本地重复全产品功能/窗口/新冻结构建，独立PR当前CI仍须运行全部后端/桌面/冻结链。
- IQ -X utf8 tools/frozen_python_members.py --payload ../starlette-fix/dist/study_backend --coverage ../frozen-sbom/artifacts/rel01b/real05/coverage.json --output artifacts/rel01c/real04：退出2（设计语义为有限成功），70个精确锁版本的实际环境包中只有55个获得实际唯一成员对应，2358个非业务PYZ模块与861实体，另有43业务源码原核；320非业务模块、108实体、154基础ZIP成员保持未映射，无歧义。检查14072条RECORD、3344份选中构建证据/124220456字节，前后payload/锁/coverage/业务源码及构建证据不变。pytest9.0.3和setuptools84.2.1均在实际成员中，不因开发分类漏掉。匹配源码的等价优化等级可不唯一，不声称真实编译选项已认证。
- IQ -X utf8 artifacts/rel01c/verify_real.py：退出0（verify-real01.log）。本次55组件CDX通过原固定官方1.6 Schema及离线spdx/jsf引用；三份Schema的hash与REL-01a/01b记录一致，无网络解析回退。全部2358模块/861实体/PURL/源文件hash/等价等级及全部未映射集合与先前独立probe.py算法逐项一致；另核70包原metadata/RECORD hash、代码本身hash、CDX occurrence集合与所报匹配精确一致。不是只核组件数量。

real04 members.json SHA256 77a42b28da7b3db61309a43146bdcebe67a0016e23454299d59a81e30a6efb5f；python-members.cdx.json SHA256 7b0c7b10f0e0fa7b53791082d14b1314dfafcc8879253df1512d0a149ecc0ef2；精选摘要SHA256 ebfb23c50531fb999ed09308bd8c74d07628b9c188d2110659fd392a81c64d9b。摘要只保留公共PURL、源/输入/输出hash、计数及未知，不含个人路径或安装源全文；完整成员位置/原始输出留artifacts。

### 保留失败和交付状态

首轮新增专项q01为34通过/2失败：共享来源夹具未将其METADATA列入RECORD，以及长度负例误按不匹配的字节数替换；仅修正夹具，保留原断言和日志。q02/p02各174通过/2失败，均为既有mklink /J夹具在受限进程中访问拒绝；改用全新任务目录及已授权原生测试权限后上述176×2通过，未跳过链接保护。早期Ruff仅import排序、未用Path和pytest fixture导入遮蔽；复用既有fixture模块对象后最终无诊断，未加广泛忽略。real01/02/03为中间实现的有限成功，原目录保留；最终以末尾输入预算保护的real04和本次校验为准。

当前REL-01c实现/相关自动化和文档完成，REVIEW；仍需独立草稿PR、其最终head CI和主Agent核验后DONE。原REL-01b的2678非业务模块身份缺口本次有限减少为320，108实体（含53 DLL/19 PYD/17 PY/其他）仍未归属，完整来源/关系及其他发行组件仍未闭合，父REL-01/02/03保持。审查暂缓、人工取消，未合并或发行，不做数据清理或接模型。

Q -X utf8 artifacts/rel01c/check_changes.py退出0：六文件范围、其余450个base blob保持、456最终文件、71本地文档链接/33调度行唯一性、UTF-8/LF/逐文件git diff --no-index --check及原报告前缀检查通过；两份运行依赖锁不变。检查/发布辅助文件仅在忽略artifacts中，不纳产品或Git。

实际创建[独立草稿PR #47](https://github.com/surface-user/StudyWorkbench/pull/47)，分支codex/frozen-python-members，base为#42最终fb5b7a2，实现提交5d0e7d90f30d6cdcd4f03e19a67120f846d107ee；本次仅补PR链接，功能和原自动化证据保持。最终head与当前CI在PR说明维护，不为写入自身最终SHA重复生成文档head，未核CI前保持REVIEW。


## 2026-11-14：REL-01d 固定Python归档与剩余成员来源

主Agent已核#47最终d6bef38cda64a4c643bbceb58ef95be6c3363245、CI43570337629三组44步、双Python918及最终38专项，并在只读副本重跑全部身份/未知/官方Schema校验后登记REL-01c有限开发交付DONE。使用#47远端tree90b1082a7886d52efbe207a7bcda92edc3cd2809的456个精确blob，在新frozen-origins副本继续，旧#47和原冻结包保持。此前只读remaining-probe/record/relocated诊断作为输入，尚不视为本工具已支持。

已读取现行task/AGENTS及对应需求、架构、题目协议、打包与证据规范；本切片先IN_PROGRESS，先报最小设计再实现。范围针对固定CPython NuGet源码/二进制、项目迁移及HTML/入口、RECORD元数据自身、扁平DLL的共同来源和无代码namespace。必须单独列CArchive启动代码，不把外层PE bootloader、全部CRT/native或签名混作已认证；完整REL-01/02/03继续。


### REL-01d实现与实际结果

主Agent批准六文件有限设计后新增tools/frozen_python_origins.py和专项测试，更新打包指南/task/本报告及[精选摘要](evidence/frozen-python-origins-summary.json)。只提供显式开发CLI，无产品调用方/exports/API/数据库或打包payload变化，无新增依赖或共享环境修改。复用既有成员生成器、文件/归档/静态code比较、RECORD与defusedxml等已锁定组件；旧#47及原冻结包只读保持。先重新执行#47全体对应，再补来源，旧局部JSON存在不代表增强整体成功。

实际CArchive12项中11项代码全有静态来源：struct来自固定NuGet；4份pyimod、bootstrap及4个runtime hook共9项来自实际PyInstaller6.22.3分发的metadata/RECORD/源文件；frozen_entry来自项目Git blob。PYZ是容器。对应来源均比较完整嵌套code/常量/异常表及各等价优化等级，不执行模块，不因名字像PyInstaller就赋予版本。9个namespace均无存储代码，分别描述已证子模块的构建分发关联，namespace版本null、不认证所有权。

固定NuGet SHA与prepare-tools.ps1一致，核python.nuspec唯一id/version及解释器补丁版本。压缩64MiB、20000成员、声明与实际读取各256MiB、每成员16MiB/编译8MiB，拒绝原名规范化、路径/大小写重复、链接/特殊/加密成员及DTD/实体；不解包。XML包括UTF16实体和重复标识拒绝。Windows单一大小写无关匹配仍记录真实成员名，不能用大小写差异漏掉同字节的CRT文件。Git声明最多16MiB/20000普通文件，source head/tree只是caller声明；逐本地源、payload及声明Git blob/代码对应，远端认证继续由实际交付单独核验。

15份RECORD self行的hash/size本来为空，依据[安装记录规范](https://packaging.python.org/en/latest/specifications/recording-installed-packages/#the-record-file)将其原metadata文件与实际分发字节另行对应，明确record_self_hash_declared=false，不写回第三方文件或生成伪self hash。自报非空错误hash仍被原成员门禁拒绝，不将例外推广到普通无hash源码。两个移位DLL按字节追溯原RECORD路径，MSVCP保留NumPy及pandas两来源，不任选owner。CArchive初始化代码与外层native bootloader是不同证据，背景参考[PyInstaller启动说明](https://pyinstaller.org/en/stable/advanced-topics.html#the-bootstrap-process-in-detail)，本工具不把前者相等当后者已认证。

增强阶段在末尾复核所有选中构建输入，包括前阶段已读但未能匹配的输入；另核原payload/coverage/锁、固定档案、Git清单、项目源及前阶段生成的两份JSON。沿用每输入原有大小上限、总20000源文件/逻辑1GiB与100000 RECORD行，失败不生成增强origins.json/CDX。所有证据字段为原字节/hash和实际位置，未认证项保持false，无发行通过0返回码。

工作目录为frozen-origins。IQ/IP指starlette-fix/.local/starlette-q-isolated（3.13.17）/starlette-p-isolated（3.12.7，pytest9.0.3），只读复用。Q指根.local/release-venv/Scripts/python.exe用于现有Ruff。命令均设PYTHONDONTWRITEBYTECODE=1；原始日志/JSON/JUnit在artifacts/rel01d，不纳Git。

- IQ/IP -X utf8 -m pytest backend/tests/test_frozen_python_origins.py backend/tests/test_frozen_python_members.py backend/tests/test_frozen_sbom.py backend/tests/test_source_sbom.py backend/tests/test_release_inventory.py -q --basetemp=artifacts/rel01d/tmp-q03或tmp-p03 --junitxml=artifacts/rel01d/q03.xml或p03.xml：原生测试权限各退出0、216通过（当时38新+原178），26.46/26.94秒，无失败/跳过。覆盖不执行样本代码、所有来源类型/共享DLL/namespace类型、caller Git边界、ZIP名字/大小写/链接/元数据/UTF16实体、各种预算、阶段输出/源变更拒绝、错误runtime源码不按前缀归属、base pyc魔数及真实代码差异、假RECORD self hash拒绝和CLI非发行成功码。
- 随后补强前阶段未匹配源的增强末尾稳定性，并加1项负例；IQ/IP -X utf8 -m pytest backend/tests/test_frozen_python_origins.py -q --basetemp=artifacts/rel01d/tmp-q04或tmp-p04 --junitxml=artifacts/rel01d/q04.xml或p04.xml：各退出0、最终39新专项通过，23.55/24.51秒。未把早期216写成一次最终217全跑；既有178函数未改，完整本head全量另由CI执行。
- Q -m ruff check backend tools最终退出0（ruff-final2.log）；IQ tools/export_question_schema.py --check退出0。没有业务/构建输入变化，不在本地重复全产品/桌面/冻结运行；当前head CI仍须完整执行。
- IQ -X utf8 tools/frozen_python_origins.py --payload ../starlette-fix/dist/study_backend --coverage ../frozen-sbom/artifacts/rel01b/real05/coverage.json --python-package <根.local/release-tools/python.3.13.17.zip> --source-tree ../frozen-sbom/artifacts/rel01b/source-tree.json --output artifacts/rel01d/real04：退出2（有限来源成功），无解包或执行。新增311 PYZ代码、154基础ZIP代码、62实体，11 CArchive代码来源与9无代码namespace描述。实体含19项目资产、15 RECORD自身、26 NuGet及2移位DLL；后者为3条来源证据（MSVCP共同来源）。新认出的NuGet26比原探针24多2，为VCRUNTIME140/140_1实际小写文件名的完整字节对应；这不证明内嵌native各自身份/许可/签名已完成。58个增强CDX组件，仍未知46实体，即44 CRT文件及EXE/ZIP生成容器两项，完整产品/上游/Git认证均false。
- IQ -X utf8 artifacts/rel01d/verify_real.py退出0（verify-real01.log）。58组件通过固定官方1.6 Schema和离线spdx/jsf引用；每个新增PYZ/ZIP/source hash/优化等级、19Git资产、15 RECORD与移位DLL所有来源、11启动代码及9namespace描述都与此前独立只读探针逐项相等，另重核NuGet原档/所有493个实际读取成员及实际payload文件hash。增强CDX每个occurrence集合与来源和旧55组件精确相等；Git/metadata hash未充当包归档hash。没有只凭数量验证。

real04 origins.json SHA25626901b019cbe6356cf592ba58359fab78009bf28cb95bc17fbfc900804ffb0ed；python-origins.cdx.json SHA25664c2a8311bc4235d450e1bfa3c84d1f2845c9fbb03e1bdd55539fbe7e5f317dc；精选摘要SHA25684d25079d56550692ef9bde92cb8a57765127b149429a8078db139096ef5e24b。前阶段完整members/BOM分别仍等于#47的77a42b28...和7b0c7b10...原哈希；本次再次索引14072条RECORD，增强复核3416份源/124813247逻辑字节。NuGet原档14826465字节/1340成员/39613524展开字节。原目录、锁及payload前后无观察到变化；不是原子快照、完整依赖/来源或安全认证。

保留失败：只读CArchive探针初按四元组解包实际五字段toc而退出1，按实际reader结构改为读取末项类型后全部11代码对应；carchive-probe01.log保留。增强real01因NuGet对VCRUNTIME大小写保守拒绝，按唯一大小写无关成员并核完整字节修正，原失败不抹去。首轮新测试q01为35通过/1失败：测试误期待伪造的非空RECORD self hash继续生成报告，实际原门禁正确拒绝；修正为要求异常及无增强报告，未放宽产品断言。Ruff首轮只import排序等3项，自动整理后无诊断。real02/03是中间有限成功，最后以包括未匹配源稳定性保护的real04为准；首次该补强补丁因import排序上下文不匹配被工具拒绝，未改源文件，按实际位置应用后专项通过。所有旧日志保留。

当前实现/相关自动化/文档完成，REL-01d保持REVIEW；独立草稿PR/当前head CI和主Agent核验后才DONE。增强来源子集不关闭完整REL-01/02/03：外层bootloader、44 CRT/native独立身份、生成容器、嵌入库/完整依赖边、其余产品组件、许可/漏洞/签名仍未闭合。审查暂缓、人工取消，未合并或发行，不清理数据或接模型。

Q -X utf8 artifacts/rel01d/check_changes.py退出0：六文件范围、其余453个base blob保持、459最终文件、72本地文档链接/34调度行唯一性、UTF-8/LF/逐文件git diff --no-index --check及原报告完整前缀通过，运行依赖锁不变。辅助发布/原始证据均留忽略artifacts，最终PR与CI在实际交付后补充。

独立草稿[PR #50](https://github.com/surface-user/StudyWorkbench/pull/50)已建立，分支codex/frozen-python-origins基于#47最终d6bef38，首次实现提交8395bd21dc33621778f3ad76ea4e35d12d3b1c55/tree8d957b4037b02543ce5def850c2692d75262ed40。本文补交付链接形成后续文档提交；最终head/tree与该head CI结果登记在PR描述，避免为记录自身hash反复改head。当前任务仍REVIEW，未合并或发行。


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

实际创建[独立草稿PR #48](https://github.com/surface-user/StudyWorkbench/pull/48)，分支codex/office-jre-dll-domains，base为#43精确c666db9，首实现提交51471f79c275a1ad7e0d560c600ccf995e69d05f/tree589d16089258adea9abd7c48af8b70888b05d271。补本交付链接后核最终head CI，结果在PR实时说明维护，不再为写自身最终SHA改变head；当前REVIEW不因草稿PR存在而销项。六文件范围保持，未提交原始artifacts/组件或改变原产品，未合并/发行。


## 2026-11-14：OFF-02g Office Python模板来源与角色证据

主Agent已核OFF-02f/#48最终c1877b719889c28fc96e0504be5bc05ed7a2ffb8、CI43570645325三组45步/984×2、115×2及实际86DLL/78覆盖/145未知与原CRT规则，登记有限任务DONE。本任务从该精确tree094e7fd045526bb6b797e95fdc12e20e95136bab逐475 Git blob复制到独立office-template-evidence；原分支/组件不变。现行规范和工具/调用方已读取，先登记IN_PROGRESS，有限设计由主Agent确认后实施。

本项只新增离线来源/角色证据工具与测试，配套打包指南/task/本报告/精选摘要共6文件；native_dependencies与check_release、产品代码/依赖/打包不改。输入为固定Office-Java组件、固定23,160,540字节的官方CPython3.13.15源码及新输出目录。复用普通文件/重解析拒绝、固定hash及组件清单检查：完整核组件原清单/实际集合和文件hash，再逐两wheel对实际pip415/setuptools252成员验证。原source archive先后hash相等，selected wheel≤8MiB/4000成员、单成员≤4MiB、selected≤1500、manifest≤4MiB/组件≤20000文件、报告≤2MiB，不提取或执行源码。

实施前只读补证在根artifacts/goal-20261114。固定LO source bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1的download.lst/UnpackedTarball_python3.mk指定Python-3.13.15.tar.xz SHA1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76及setuptools79.0.1/pip26.2.1两个源wheel；只下载原包并核hash，内存读取wheel，未安装/执行。实际pip415全等同；setuptools252中250全同、jaraco/text/__init__.py精确等于LO单补丁效果、Lorem文本精确为单改名；无未解释实际文件。此为所选包目录的source-distribution对应，不能把其缺metadata猜成完整安装发行身份，其他分发内容与全部Python组件仍非本范围。

14个PE模板还与固定上游Git资产逐blob相同：setuptools v79.0.1→607f6be776db97d83c9cc54e0eaa578567dcc44c，launcher.c blob b87cb32ad65b70ddf53c59317eed2433d9b3bd42；distlib0.4.2→8183ea60e83bf021bf7d6903f4a6b3c8df0905a6，PC/launcher.c blob727f79165c8d328843598cace030e630045be066。对应C源用于解释成品启动器必要条件（distlib的附加archive/shebang，setuptools的同目录-script.py/pyw），不是可重现编译证明。producer从资源读bytes，生成另外命名exe/ZIP或配套脚本；原模板无ZIP/overlay，伴随脚本须另核。

不得据目录名、原样本未运行、源码关联或缺附加数据直接豁免runtime。当前#48产品仍v3，#44受控配置只在独立分支；本工具固定runtime_classification=unclassified、runtime_exclusion_verified=false、product_release_ready=false，145未知保留。后续须在含#44+#48的共同已验head另绑定实际产品入口和运行时分类。无新增模型/依赖/命令执行，审查暂缓、人工取消、未合并或发行。

### OFF-02g 实际验证与交付准备

工作目录office-template-evidence；IQ/IP仍只读复用starlette-fix/.local/starlette-{q,p}-isolated/Scripts/python.exe（3.13.17/3.12.7，pytest9.0.3）。新增27项自写惰性样本，不含可运行启动器或个人原件；producer/package fixture若被执行立即抛错。普通/延迟导入及发行清单115项旧检查全部保留。

- IQ/IP -X utf8 -m pytest backend/tests/test_office_template_evidence.py backend/tests/test_native_dependencies.py backend/tests/test_release_inventory.py -q --basetemp=.local/off02g-q06或p06 --junitxml=artifacts/off02g/q06.xml或p06.xml：各退出0，142通过，失败/错误/跳过均0。覆盖固定输入/hash、源metadata、缺producer/模板、精确patch/rename、合法空包文件、重复/规范化NUL/越界/链接ZIP、tar链接/重复/越界/展开预算、已有/组件内输出保护、源/选中成员/伴随脚本在采集时变化，以及生成成品ZIP/trailer/脚本不得混为原模板。重复ZIP的预期构造警告保留。链接边界在本任务全新临时目录按既有本机测试权限核验，不触碰原组件或共享环境。
- 首轮q01为25通过/1失败：ZipInfo构造器先移除NUL，未生成预期畸形输入；改成在本地/中心文件名原字节注入NUL，拒绝断言不变。q04为141通过/1失败：Python3.13的tar写入器不再接受非零size但无fileobj，Python3.12当时通过；改为只写超预算原header，不分配声称的65MiB内容，两个版本均核由采集器先拒绝。其余中间q02/q03/p03/p04/q05/p05均保留，最终q06/p06为本轮证据。不删除或把旧失败改为成功。
- IQ -X utf8 tools/office_template_evidence.py --office <根.local/release-tools/libreoffice-java-26.8.1-21.0.13> --python-source <根.local/release-tools/cpython31315-source/Python-3.13.15.tar.xz> --output artifacts/off02g/real02：退出0。固定23,160,540字节源码SHA256 1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76、组合清单SHA256 156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9及19743实际文件核验通过；只读tar≤50000成员/单64MiB/总声明展开512MiB、wheel≤8MiB/4000成员/总64MiB/实际单4MiB，重核CRC/实际长度和所有路径。原输出real01退出1，因14个合法空__init__.py被read_file误拒；仅为与固定源和组件hash相符的成员允许空字节，锁/归档仍拒空，并补fixture回归，原失败目录/log保留。
- real02逐实际pip415文件全等；setuptools252中250全等，唯一patch精确输入636614a9747fa2b5280da6384a43d17ba65985be4750707f021f5108db15ca1a→输出c9e90f78f9ca8155e9fbc24fa46c33ffc0c50553f4f8a96f855233da5eba5991；唯一Lorem改名内容SHA256 37fedcffbf73c4eb9f058f47677cb33203a436ff9390e4d38a8e01c9dad28e0b。没有模糊patch或未解释的实际成员，source distribution版本来自精确源wheel METADATA，未声称完整安装分发。14PE均无ZIP/overlay，6个distlib原模板缺archive trailer，8个setuptools原模板缺同名-script.py(w)；两个producer源码身份均与源wheel相同。
- distlib C源的APPENDED_ARCHIVE分支先从自身查archive/shebang，再走Python启动；setuptools C源先按自身路径派生-script.py(w)，缺脚本在调用Python前失败。14模板同时逐Git blob核固定上游资产相同，相关C源、LO download/unpack/patch的原bytes也逐Git blob核对。但该关联不构成从C重编译PE的证明，必要成品数据缺失也不构成产品运行时不可达证明；没有执行源码、PE模板、生成启动器、pip安装或Office。
- Q（根.local/release-venv/Scripts/python.exe）-m ruff check backend tools与Q tools/export_question_schema.py --check均退出0。首次Q路径少算一级目录而命令未启动、一次rg范围倒置而搜索报错，修正路径/表达式后通过，未改环境/断言。产品、依赖、native_dependencies/check_release/check_native_dependencies与#48全部逐blob保持；不重复构建未变业务，本PR当前head仍须执行完整CI。
- IQ artifacts/off02g/select_evidence.py退出0，筛出[共享摘要](evidence/off02g-python-template-summary.json)，15,623字节/SHA256 243e04df4ae1671f2c570470a8b1562b486fa8fba8e6367e786189c045fb1d69。原完整report 280,945字节/SHA256 b61561d36bac3bb09fbe668987ed1d80661e77b923bef4f9e0d88a6b59310870及667行映射、源C全文、tar/wheel试探和全日志只留忽略的artifacts；精选仅保留支持来源/结构结论的版本/hash/条件、14资产、2producer、JUnit和限制，未提交源码归档或组件。

有限实现/自动化/文档完成，OFF-02g保持REVIEW，待独立草稿PR/当前head CI及主Agent核验。原145未知继续阻断check_release；模板仍unclassified，runtime_exclusion_verified/product_release_ready均false。后续在包含#44+#48共同head再研究受控实际入口，Python/managed/x86各自独立切片，完整Office/SBOM/许可/漏洞/签名发行继续；审查暂缓、人工取消、未合并/发布。

IQ artifacts/off02g/check_docs.py退出0：6文件范围、472个未变base blob、旧报告完整前缀、UTF-8/LF/逐文件git diff --check、85本地引用及46唯一调度行均通过。实际创建并附加[独立草稿PR #51](https://github.com/surface-user/StudyWorkbench/pull/51)，分支codex/office-template-evidence，首实现提交6a95b146701f13d1cb7e322b056abddd68d8d572/treefe3e19292117d33ba797887896f725b45de31e87。补入本交付链接后保持6文件，最终head/完整CI及有限核验结论在PR实时描述维护，不为记录自身最终SHA反复改变head；未改#48、原组件或门禁，未合并/发行。

## 2026-11-14 REL-01f：当前桌面实际文件及复制来源SBOM

基于主Agent已接受的#53最终b09da16b9ea23f4fcb81eb016f9602d84afa451c/treec2747215a6ae9187b28706234b70662190f54252建立desktop-origins精确497 blob副本，原根/所有旧包和失败不动。完整读此基线AGENTS、requirements、architecture、question-content-spec、task及相关打包/依赖/报告规范，先调查再经主Agent批准有限范围。#54原head已由主Agent只读核969实体/44TOC源/五节/DEBUG/双RECORD/58组件Schema及CI双1000/44步骤后有限接受DONE；该证据是#40旧43业务模块冻结源，不冒充本片#53的44模块。#54不并入本分支实现，任务表只同步已验收状态。

本片7文件：新desktop_sbom.py/反例、现行打包/依赖指南、task、原报告及精选摘要。没有新依赖/缓存/系统设置/业务、锁或构建流程变化。不是完整staging/安装器SBOM，不执行应用、AOT、插件、CMake或新构建，不恢复人工/审查，不合并或发行。

先核batch-three/four的本机desktop/build只有native_assets/test_cache/unit_test_assets，所留package_config为75项、Flutter3.47.1/Dart3.13.1，用于--no-pub组件测试；batch-five没有本地桌面Release。没有把它们或37a8d55旧包当当前发行。转用#53当前成功CI43580584516的artifact14108587888，名称精确windows-release-inputs-b09da16…、96034786字节、GitHub digest5610f2638ba945822171047d56d529bbd852b6335c1b2b04297f7a3ab05c2953。通过GitHub连接器下载原ZIP，文件provider临时下载链接不进Git/报告，不读本机凭据/gh/token。完整ZIP实际hash/长度等于服务元数据；原件只存忽略artifacts/rel01f。该3天产物截至2026-11-17，服务元数据不是签名构建证明。

CI原desktop日志明确checkout merge8339e520574f34b13accc33e5384a2089cbcfc80；另读GitHub commit元数据，其tree精确等于#53 c2747215…，父为#49及#53。故tracked源码树一致，不只据artifact命名认源；实际工作区换行、编译器/SDK/全部头输入仍不能由tree证明。新工具另逐Git blob/SHA256核66个tracked lib/windows/assets/pubspec/工作流等项目输入，原路径大小写保留，不把此选择写成完整编译输入捕获。

真实ZIP1151成员/214297444声明展开字节；所选Release实际41文件，排除1110非桌面文件（backend及构建依赖），不投影为桌面运行成员。data/app.so是实际9831304字节ELF，hashc33eefcdac5429ec316cbf7c6410232e7159688cf4c4a5dd1eae096809e0a344；runner141312字节、两插件968704/98304字节均按实际hash/AMD64 PE32+与生成角色记录，源等价/签名false，不能由文件名或package_config为其填入已认证包版本。NativeAssetsManifest声明空也不用于排除实际存在的插件。

实际复制来源：

- 官方Flutter3.47.1固定tag engine.version为5d531788691ec3404cac0cee66ead4007b177363；官方同revision Windows x64 Release ZIP70289419字节/SHA256 a553d14c6087cf3f049ab1ddeedaf9e3216d341b39b036f7dc29cee52119fc4e，目标flutter_windows.dll21273088字节/hash2d2e5e0b791c46afaefa1d159c92dda0a120a9d3f4a365d9dd91808fe0d24898与原档完整字节相同。只把该实际二进制作为engine provider，独立Dart运行时/整个SDK/内嵌库来源不因此认证。
- 官方Microsoft.Web.WebView2 1.0.2792.45 NuGet8474494字节/SHA256 02ffd77440c09b5ff60f5f06defdc3fb07fb5630077c7cf6115bf6be793f91e3，与CI构建包内原nupkg完整相等。实际WebView2Loader.dll165440字节/hash9468470d6a4d11179ec179183d130465a380e0dedfdbe1fc2ab404c86c45a85e，对应同档build/native/x64及runtimes/win-x64/native两条路径，全部保留，不任选一个；其他架构不并入实际x64成员。
- 官方pub.dev的cupertino_icons1.0.9、flutter_inappwebview6.1.5、flutter_inappwebview_web1.1.2、flutter_math_fork0.7.4完整tar.gz分别核原锁SHA256，档内pubspec唯一精确名称/版本。仅24个真实字体/HTML/CSS/JS资产逐字节对应，4包进入复制provider子集；Windows实际携带Web资产也保留，不按平台标签漏掉。包内原路径或lib路径均依实际命名空间比较，多个相同候选不任选归属；不认为这些包的全部Dart代码都进入AOT。
- 两个Windows插件官方源档另外核原锁及CMake原字节，试探确认与本地缓存相同。生产报告仅作锁定producer源码关联，binary_source_equivalence_verified=false；不把CMake或NuGet构建目录存在当对应代码已嵌入证明。WIL/nlohmann等构建输入不投影为额外实际runtime组件。
- ICU864880字节仅与本地SDK同路径缓存相同，报告其source identity仍null/官方档案false；本地版本字段不能认证独立ICU或Dart VM。三个项目Schema JSON与Git原LF文件只有CRLF换行差异，逐文件hash/原Git blob及source_bytes_identical=false保存，不规范化后算成逐字节相同。子集Material字体、编译shader/manifest/NOTICES等保留未知，未把NOTICES存在当完整许可通过。

因此全部41物理文件有hash/角色；26与固定档成员精确相同（24 Pub+engine+loader），其余15身份未知，含1份只有本地ICU字节链。CDX1.6共47组件=41个file+6个实际provider，occurrences只指实际文件，未知无伪版本、无UNLICENSED，不擅造完整依赖边。copied_source_bytes_verified只描述复制来源的字节相等，AOT/原生机器码与源码等价仍false；整个产品/上游/签名/可重现/许可/漏洞均不认证。

实现复用safe_name/no_links/bounded_file、原锁解析/重复键拒绝及既有PE库，标准CDX直接输出后另核官方Schema，不引入新scanner或依赖。ZIP/TAR原件只读、有数量/声明及实际展开/成员/总读取/源输入预算，拒绝危险原名、大小写重复、链接/特殊/加密成员，tar不落地extractall。NuGet XML禁DTD/实体并核唯一id/version；所有输入/锁在结束时再读核hash，出错不建最终输出。完整命令/上限与声明边界见打包指南，CLI只给1失败或2有限范围完成。

工作目录desktop-origins；IQ/IP指starlette-fix/.local/starlette-q-isolated（CPython3.13.17）/starlette-p-isolated（3.12.7），pytest9.0.3；Q是根.local/release-venv/Scripts/python.exe，仅静态/辅助，环境不改。命令设PYTHONDONTWRITEBYTECODE=1，原始ZIP/源档/服务快照/完整报告/JUnit/日志只存artifacts/rel01f。各正式性能窗口期间仅文本/远端操作，在office_1114释放窗口后才运行本机hash/自动化，未为本片重构建Windows。

- IQ/IP -X utf8 -m pytest backend/tests/test_desktop_sbom.py backend/tests/test_frozen_python_origins.py backend/tests/test_frozen_python_members.py backend/tests/test_frozen_sbom.py backend/tests/test_source_sbom.py backend/tests/test_release_inventory.py -q --basetemp=artifacts/rel01f/tmp-q03或tmp-p03 --junitxml=artifacts/rel01f/q03.xml或p03.xml：Windows原生测试权限各退出0，261通过（新增43+基线218），30.98/30.95秒，无失败/跳过。启动前估计260未作结果使用，按真实JUnit261记录。43新专项包括全物理范围/不投影构建包、caller源声明冲突、ZIP/TAR名称/链接/重复/预算、完整pin/元数据/PE不符、共享原档两路径、末尾每类输入变化拒绝、不执行自编PE/源码、CLI永不返回发行成功0。
- IQ -X utf8 tools/desktop_sbom.py --artifact artifacts/rel01f/windows-release-inputs-b09da16b.zip --provenance artifacts/rel01f/provenance.json --source-tree artifacts/rel01f/source-tree.json --engine-archive artifacts/rel01f/sources/windows-x64-release-flutter.zip --webview-package artifacts/rel01f/sources/microsoft.web.webview2.1.0.2792.45.nupkg --pub-archives artifacts/rel01f/sources --sdk-root <既有固定Flutter根> --output artifacts/rel01f/real01：退出2，41文件/26复制/6provider；79输入/182802342逻辑字节末尾核，ZIP读出及Pub实际展开67717274字节。源/包/缓存/其他报告均不改。
- IQ -X utf8 artifacts/rel01f/verify_real.py退出0：独立重读所有41文件、66项目Gitblob、26对应的原档字节/所有路径候选、15未认证状态、两插件源码关联、实际3JSON换行差异、NuGet CI原nupkg、每个CDX文件hash/身份occurrence集合，47组件通过固定官方1.6 Schema与离线spdx/jsf引用。支持--read-only完整核验并断言现有精选摘要字节，不写任何文件。没有只比数量或以旧包绿灯代替当次结果。
- Q -m ruff check backend tools退出0；IQ tools/export_question_schema.py --check退出0。代码/协议/构建输入未变，本地不重复Flutter组件或Windows构建；本head CI仍完整执行对应步骤。

real01 desktop.json SHA256 aa9eb107846077ef914eaba26995dba2c0cee085d9d5f7f8696bf24cf4d33b27；desktop.cdx.json SHA256 6b48db677eec04e8f984f6b97cd74fe65ef4e3292ec5c77f54175737b1fac0ed；精选desktop-sbom-summary.json SHA256 a1f30eaa34ce918ae810dcd457e3e748b5573fabf25e14ef56161eb83efcd28f。精选包含全部41路径/hash/角色、实际6provider与来源/未知范围、CI/Git/pin/报告摘要；绝对缓存路径、二进制/原源码档及完整日志不进Git。原件可过期，摘要不能替代重新读取或签名认证。

保留失败：首次新目录下载因缺artifacts父目录退出1，未读写原包，补建本任务父目录后以xb成功下载；只读索引最初把Pub资源都按根路径查找，遇实际lib/assets路径退出1，按真实pubspec/档案成员核两个有依据候选，不模糊扫描任意相同文件；第二探针误要求Loader只能有一个来源，官方档实际两条x64同字节，改为保留两条后matches-probe03退出0。官方Flutter完整SDK release列表URL通过浏览及直接请求均不可取，直接请求404，未据本地SDK填造完整官方SDK认证；只采用已实际取得固定engine档及官方tag revision的有限证据。首轮Ruff报一处测试未使用变量，去掉后全量通过；43项首轮/修正后均通过。宽泛输入清单文本打印曾被工具截断，未将截断文本当读全，必读task分段完整重读；原输出/失败保留。

有限实现、相关自动化、独立真实/Schema与文档就绪，REL-01f保持REVIEW；独立PR/本head CI及主Agent核验后才可登记DONE。后续--analyze-size须独立新编译才能产生新AOT包trace，不套给本次app.so；完整Dart/native源码等价、SDK/内嵌库/许可/签名及最终发行仍待其各自切片，审查暂缓、人工取消，未合并或发行。

Q -X utf8 artifacts/rel01f/check_changes.py退出0：7文件范围、493个未变base blob、500最终文件、104本地文档引用、56唯一调度行、UTF-8/LF/逐文件git diff --no-index --check、旧报告完整前缀及两份锁保持均通过。完整原始输入和辅助发布文件留忽略artifacts。

独立草稿[PR #59](https://github.com/surface-user/StudyWorkbench/pull/59)已建立，codex/desktop-artifact-sbom基于#53最终b09da16，首次实现提交db00f1ee7dd6035001b9cdb49ca19a6c862821d8/treedce369d725b084b9c49a0c0772cd492442e0559c。补入实际交付链接形成后续文档提交；最终head/tree及该head CI登记在PR描述，避免为记录自身hash反复改head。REL-01f仍REVIEW，不合并或发行。

发布后末尾边界核对发现总源输入预算可进一步收紧：原先先按stat预检，读取间隙若增长，虽然源hash或后续读取会拒绝整体，仍可能先读过剩余逻辑预算。首次新输入现在把单次bounded_file上限收紧为剩余总预算；新增真实增长负例，验证小于新文件长度的剩余预算在读取前即拒绝，没有超预算read返回。未弱化已有完整性断言，范围仍7文件；此前984fcfd的CI43586212699保留，但不能代替必要修正后新head的CI。

- 最终IQ/IP同上六个关联文件的pytest命令，改用tmp-q04/tmp-p04及q04.xml/p04.xml：各退出0，262通过（新增44+基线218），30.09/29.84秒；既有261/43结果作为历史保留，不冒充最终计数。Q全Ruff退出0（ruff-final02.log）。
- IQ同一真实CLI改用新output artifacts/rel01f/real02：退出2。41文件/26复制/15未知、47组件及CDX字节、66项目/79输入/原件hash和预算计数均保持；report因collector修正更新为SHA256 35fa55e8b146b060883236a36f8b200dc13358a485d8cc5baca4070083c5a9fb，CDX仍6b48db677eec04e8f984f6b97cd74fe65ef4e3292ec5c77f54175737b1fac0ed。
- IQ artifacts/rel01f/verify_real.py再次退出0（verify-real02.log），按最终real02完整逐项核证及官方Schema；最终精选摘要SHA256 243b3401fabbe05099d8040ac2cf8e80ab10f493d44656f2fd059b2e6125ea81。初版摘要a1f30eaa…另留artifacts/rel01f/summary-real01.json，原real01/日志及helper快照保留；当前helper的--read-only核最终real02和新摘要且零写入。

task/指南同步最终262/44及预算边界，独立PR随后追加必要修正提交并核该head完整CI；最终状态仍REVIEW等主Agent退出核验。实际产物仍是已明确的#53 CI artifact，未改源包/缓存或把新计数当完整发行认证。

## 2026-11-14 REL-01g：桌面ICU官方共享归档来源

### 基线与有限设计

主Agent已有限接受REL-01f/[PR #59](https://github.com/surface-user/StudyWorkbench/pull/59)最终727b03845e1efb8c83c13e48fc11c4ae77c6356a/tree beec48021554440351f4be22a32584ce08b35b21及[当前CI43586932756](https://github.com/surface-user/StudyWorkbench/actions/runs/43586932756)：双Python1224/desktop203/44新冻结模块核源，独立只读核41文件/26复制/15未知、66Git blob、47组件官方Schema和所有原件/精选字节。旧实现、原失败、原归档和精选摘要不改。本片从精确500 blob新建desktop-icu隔离副本；批准7文件为既有工具/专项、task/依赖/打包指南、原报告及新精选ICU摘要。没有新依赖、缓存/编译器/系统/业务、锁或构建流程变化，不新建通用框架、不执行外来内容、不合并或发行。

固定Flutter3.47.1官方engine.version为5d531788691ec3404cac0cee66ead4007b177363。实际SDK engine.stamp与本地版本上下文相符，但不据此认证归档。原release ZIP不含ICU；核固定版本FlutterSdk.getBinaryDirs、EngineCachedArtifact.updateInner、Artifact.icuData解析、UnpackWindows与unpackDesktopArtifacts：共享host配方取windows-x64/artifacts.zip，Windows unpack取ICU不传mode，将其复制到ephemeral，项目既有CMake再安装到data/icudtl.dat。debug/profile/release的windows-x64-flutter.zip另外选择，不能凭profile/release目录猜该共享ICU源。

六份固定官方HTTPS原始配方（engine.version、flutter_cache.dart、cache.dart、artifacts.dart、windows.dart、desktop.dart）各≤1MiB保存URL/长度/SHA256，见artifacts/rel01g/recipes、recipe-probe.json和[精选摘要](evidence/desktop-icu-summary.json)。实际SDK六份仅LF/CRLF转换后对应，原始hash不同，只作上下文关联。浏览工具对windows.dart返回cache miss，随后直接只读官方固定raw URL成功；未改缓存、不把转换当原byte认证或整个SDK认证。

真实只读试探取得[官方共享归档](https://storage.googleapis.com/flutter_infra_release/flutter/5d531788691ec3404cac0cee66ead4007b177363/windows-x64/artifacts.zip)：30535798字节/SHA256 fd626db3afddcc37dcf052f1a26cc43834ac6dcc4c45d8e0a5c10e6a2272b3df，32成员/82279623声明展开字节，最大成员40429056字节。唯一icudtl.dat为864880字节/SHA256 325a86063d26334c2eabe1743cea073b612540fbf3d8fc2ef0b5708e3763a8c7，与#53实际CI归档内data/icudtl.dat逐字节相同；不由本地SDK相等推出此结论。HTTP长度/Last-Modified/ETag只是下载记录，未认证签名或可信构建证明。

### 实现与剩余未知

既有generate尾部新增兼容可选icu_archive/CLI --icu-archive。未提供时保持本地缓存比较/未知身份；提供时完整长度/SHA先核，复用危险名/重复/加密/特殊项、ZIP条数/声明/实际读取预算，唯一选中成员与实际ICU必须相等。配置错、路径缺失、成员缺失/目录、pin或实际字节不符都拒绝，不回退；有归档时不读取本地ICU缓存。原档按剩余总源输入预算有界读取并末尾重新hash，和所有旧输入/两锁共同保持稳定；全程内存读取，不落地解包或执行档内compiler。

source_identity=flutter-host-artifacts@固定engine仅指提供该数据的归档。CDX provider的完整hash/URL/唯一occurrence及identity-scope明确其含义，不把档内其他31条工具/数据投影为产品成员；独立ICU version=null、independent_icu_identity_verified=false、license_obligations_verified=false、publisher_signature_verified=false。LICENSE.artifacts.md存在不等于ICU传递许可/再分发义务闭合；不是ICU上游源码或版本认证。全局产品/上游/AOT源码等价/签名/可重现仍false。

结果41文件/27复制（原26+ICU）/7归档provider/48组件；14归属未知集合等于#59原15减去此ICU归档来源，其余40项proof完全保持。3项目JSON换行差异、AOT/runner/插件机器码、font/shader/manifest/NOTICES与独立ICU上游身份/许可分开保留，没有猜版本、UNLICENSED、白名单或删文件，父REL-01完整SBOM仍未完成。

### 实际命令与证据

Q为既有release-venv Python；IQ/IP为starlette-fix/.local/starlette-q-isolated及starlette-p-isolated/Scripts/python.exe，环境未改，PYTHONDONTWRITEBYTECODE=1。完整输入、输出、JUnit与辅助文件留忽略artifacts/rel01g；复用只读../desktop-origins/artifacts/rel01f的#53 artifact/provenance/source-tree及原engine/WebView2/Pub档，不复制/改写它们。

- IQ -X utf8 -m pytest backend/tests/test_desktop_sbom.py -q --basetemp=artifacts/rel01g/tmp-q01 --junitxml=artifacts/rel01g/q01.xml：退出0，59通过/8.16秒。新增15验证不读缓存/不投影档内工具、provider与ICU版本许可边界、错pin/路径无回退、全档危险名/重复/链接/加密、缺失/目录成员、实际字节不符、声明/实际预算、末尾原档变化及可选CLI；44原专项未弱化。
- IQ/IP -X utf8 -m pytest backend/tests/test_desktop_sbom.py backend/tests/test_frozen_python_origins.py backend/tests/test_frozen_python_members.py backend/tests/test_frozen_sbom.py backend/tests/test_source_sbom.py backend/tests/test_release_inventory.py -q --basetemp=artifacts/rel01g/tmp-q02或tmp-p02 --junitxml=artifacts/rel01g/q02.xml或p02.xml：Windows原生测试权限各退出0，277通过/38.44、38.08秒，无失败/跳过（新增15+原262）。
- Q -m ruff check backend tools、IQ -X utf8 tools/export_question_schema.py --check：各退出0，All checks passed / Question schemas are current。产品/锁未改，不需新本地Windows构建，当前head CI另核。
- IQ -X utf8 tools/desktop_sbom.py --artifact ../desktop-origins/artifacts/rel01f/windows-release-inputs-b09da16b.zip --provenance ../desktop-origins/artifacts/rel01f/provenance.json --source-tree ../desktop-origins/artifacts/rel01f/source-tree.json --engine-archive ../desktop-origins/artifacts/rel01f/sources/windows-x64-release-flutter.zip --webview-package ../desktop-origins/artifacts/rel01f/sources/microsoft.web.webview2.1.0.2792.45.nupkg --pub-archives ../desktop-origins/artifacts/rel01f/sources --sdk-root <既有固定Flutter根> --icu-archive artifacts/rel01g/windows-x64-artifacts.zip --output artifacts/rel01g/real02，末尾exit $LASTEXITCODE：退出2有限结果，41/27/14/48。首次real01未显式转交退出码，外层返回1且输出完整，保留该调用；规范转交的real02独立新目录明确2，未重写首次输出。
- IQ artifacts/rel01g/verify_real.py：最终退出0，独立不用collector函数逐核41实体/全部复制源、精确ICU归档/成员、原件和66Git blob、14未知集合/其余40proof与#59一致、两插件producer、48组件官方CycloneDX1.6 Schema及原精选摘要字节。首次helper目录变量original被项目JSON原字节变量覆盖导致TypeError/退出1，只更名辅助变量后通过，collector/断言未改，保留verify-real01-failure.txt。

79输入/212473260逻辑字节、ZIP读出及Pub实际展开68582154字节；替换本地ICU输入为完整host原档，预算未放宽。最终desktop.json SHA256 a2d3a92da99a0da700a32048468a4b6fb9fbae263e8253503d7b0ea3d7d348e6；CDX 81b340db3240d5e36339284a3672359640d1db29a5a0c16c9fe20c9fdefc00cb；新精选摘要188fc39e73b07cca88dcf952748b4a3500c7a6f77da026b096865220531c4c4c。helper --read-only可核当前原件/摘要且零写入；原#59精选SHA256 243b3401fabbe05099d8040ac2cf8e80ab10f493d44656f2fd059b2e6125ea81及旧输出保持。

有限实现及相关自动化/原件核证就绪，独立PR/当前head CI和主Agent退出核验仍待交付。审查暂缓、人工取消不记通过；不合并或发行。后续按剩余真实缺口继续，不能把归档来源闭合扩写成独立ICU版本/许可、SDK或整个SBOM完成。
