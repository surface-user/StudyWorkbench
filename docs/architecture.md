# 系统架构

状态基线：2026-11-05本地代码。下列“当前已实现”表示代码存在，不代表全部人工、发行或阶段验收通过。当前安排见[task](task.md)，决策见[ADR](adr/)。

## 当前已实现

模块化单体：Flutter UI → 受控loopback HTTP → Python业务/文件服务 → SQLite和受管文件。Flutter使用固定提交lightweight_liquid_glass公开API，不改上游；普通业务不依赖LLM。

| 模块 | 当前责任 | 实现入口 |
|---|---|---|
| 工作空间与布局 | 空间隔离/归档、v1/v2布局、旧utility及未知页兼容 | workspaces.py、workspace_layout.dart、workspace_shell.dart |
| 资源目录 | 稳定逻辑ID、树/搜索、改名移动、删除墓碑、旧资源适配 | explorer.py、resource_explorer.dart |
| 统一添加 | 原生多选/OLE回调→暂存预检→明确确认→后台受管复制 | resource_picker.dart、add_resources_dialog.dart、Windows runner、Explorer |
| 内容提取 | 原件哈希校验→ImportJob解析→候选预览/调整→显式确认 | imports.py、documents.py、question_splitting.py、draft_editing.py |
| 查看与编辑 | PDF/PNG/JPEG、DOCX结构、MD工作副本、冲突保存/恢复收据；TXT及JSON/CSV/LOG/VTT/SRT严格UTF-8只读原文，新增文本仅资源级位置 | document_files.py、document_view_worker.py、document_page.dart |
| 自由笔记（LW-01） | 受管目录新建MD原件/可编辑副本、持久幂等创建/中断核对、目录及资料/媒体页入口；旧notes不迁移 | markdown_notes.py、markdown_note_dialog.dart、resource_explorer.dart、resource_page.dart |
| 位置书签与备注（LW-02） | 版本化资源/页/原文行/媒体时间锚点、标记修订/墓碑、同空间笔记关系和来源回跳；失效位置不自动重定位 | learning_marks.py、media_duration.py、learning_marks_dialog.dart、document_page.dart、media_page.dart |
| 内部链接（LW-03） | 严格版本URI、受鉴权解析、复制/MD插入跟随、最多50条运行时往返；目标/返回位置重验，不注册系统协议 | internal_links.py、internal_links.dart、document_page.dart |
| 集中查找（LW-04） | 活动MD当前正文、旧笔记及书签备注的有界纯文本扫描/分页，显式截断；跳转重验版本，无搜索正文镜像 | learning_search.py、learning_search_dialog.dart |
| 完整库备份恢复（LW-05） | 离线SQLite快照/全文件包、受控新空目录恢复、旧schema保留后升级、表/文件/关系校验、草稿落盘/停服/取消/配置激活；人工/发行仍待验 | backup_archive.py、backup_store.py、backup_dialog.dart、main.dart、__main__.py |
| XLSX只读查看 | 有界OOXML ZIP/XML在既有查看子进程读取，多表稀疏单元格/缓存值；不执行公式/宏或外链，不提供Office编辑/样式保真 | spreadsheet_view.py、document_view_worker.py、spreadsheet_view.dart、document_page.dart |
| Office分页 | 可选固定LibreOffice进程→派生PDF→PDFium页图 | office_inputs.py、office_runtime.py、office_previews.py |
| 题目文件 | 检查/旧内容显式转换/确认快照/资产完整性/按确认版作答 | question_files_format.py、question_files.py、app.py |
| 学习与记录 | 判分、追加作答/评分、组卷、统计、事件、笔记关系和投影 | learning.py、learning_records.py、study_page.dart |
| 标签和媒体 | EditorTabBar/PageHost稳定实例、关闭释放、独立WebView和播放器能力 | page_host.dart、web_page.dart、media_library.py |
| 授权与人工候选审核 | 内存显式授权/有界作答与确认版读取；外部候选修订、拒绝和独立MD采用收据；无模型调用 | agent_access.py、analysis_review.py、analysis_review_dialog.dart |
| 直接媒体下载 | 持久任务/单worker/独占attempt、固定下载子进程/暂停与显式恢复、受管原件入库/媒体身份复用；首批无站点解析/转码 | media_download_http.py、media_download_worker.py、media_downloads.py、media_download_dialog.dart |

资源身份、原件blob、题目ID、确认版ID、tab_id分开，不能用标题/hash代替身份。资源树是受管逻辑目录，不是任意系统文件夹的原地工作区。

### 文件与数据库权威

Resource原件不可变，按大小/hash验证。工作副本保存校验expected hash，独占写旧版本和待写内容、fsync、提交prepared收据、同目录replace，再提交索引；重启依据old/new/外部hash对账，不自动覆盖冲突。文件与SQLite不构成跨介质原子事务，恢复点及失败字节保留。

QuestionFile普通保存只改编辑内容。显式确认冻结MD、标题、编译题目/材料和附件，回读校验后写不可变版本并更新questions缓存。提交按确认版读取和核验资产；旧作答不补造版本、不重算旧分数。当前文件失效时可读取最后确认快照，但不得重新发布。

学习事件追加且不可更新/删除；记录标签按完整事件流最后明确修订重建，掌握/到期仍依真实作答和最新人工评分计算。关联笔记显示当前笔记，不伪造历史笔记快照。

### 界面、原生资源与安全

PageHost用稳定页ID的Offstage/ExcludeFocus/TickerMode保留访问过的页面，关闭立即释放原生资源。每空间16个打开页、10条关闭历史；文件草稿和作答草稿分开。网页/播放器切换不重建，后台媒体沿用继续播放策略。

外部WebView与本地可信播放器隔离，不注册业务JS桥/host object，不传业务令牌。播放器仅取得指定媒体的临时capability。HTTP执行Host/Origin/令牌与同空间校验；导入、Office内容及模型输出都视为不可信。

Office运行时可缺省；显式转换、独立profile和Windows Job、固定参数/版本、输入预算/宏外链拒绝。内部静态图表/OMML例外按门禁受控启用，选项v3；控制不等于完整OS沙箱。缓存核对源和产物hash，重启中断不自动重跑。

### 兼容与数据保护

0001–0016增量迁移；升级前SQLite backup、事务迁移、完整性/外键检查、失败保留备份和旧文件。旧JSON/提取MD不在打开时升级；旧布局不猜测资源绑定。删除只标记节点，已打开编辑器仍可按ID操作保留工作文件；树/搜索/当前关系入口过滤墓碑。标记改写先追加旧修订，移除来源/笔记不级联清除标记、修订或学习历史。

## 规划中

普通学习流程采用[契约](learning-workbench-contracts.md)与[ADR0012](adr/0012-learning-notes-anchors-and-backup.md)，LW-01至05本地能力见上文，实际窗口/阶段状态查task。内部链接由受控业务解析；完整恢复采用离线整库包到新空目录，无HTTP任意路径恢复接口。格式/下载及R6剩余按[路线](learning-workbench-roadmap.md)推进，沿用受管资源、UI/后端分层和固定技术栈；任务进度仅查task。

- R6：模型/凭据适配、通用资料读取及其他候选场景仍规划中；当前本地授权/分析上下文和人工候选审核已实现，详见agent-design.md。
- 单空间备份合并、站点提取/质量选择/转码、OCR及更广文档解析。
- 外部目录原地工作区、监听、MD三方合并等方向另行设计，尚未确定的实现细节不视为现有契约。
- 不预建微服务、通用任务平台、插件框架或Agent专属题库。

## 待验证

- Windows Explorer真实跨窗口拖放、多屏DPI及提权差异；回调注入/COM自检不替代该验证。
- 普通Explorer启动/原默认目录历史故障、中文IME、原生WebView焦点快捷键、真实显示器性能。
- 无Python/无WebView2干净机、安装升级卸载保留数据、组合包前后端一致性及签名/许可/SBOM。
- Office复杂字体/版式/第三方文件、网页登录/DRM/休眠、音轨和编码矩阵、安全负面测试。

这些待验证项不取消已有自动化结果，也不能因整理文档改成已通过。验证出处见[开发索引](../dev/README.md)和[任务](task.md)。
