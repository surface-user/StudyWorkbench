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
