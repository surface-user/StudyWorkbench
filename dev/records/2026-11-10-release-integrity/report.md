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
