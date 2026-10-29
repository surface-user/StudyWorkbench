# 标签页与 WebView2

2026-10-25最新M5：采用38px连续EditorTabBar与PageHost，支持横向溢出/列表、右键批量关闭、活动左邻规则、未保存确认、数字定位快捷键与空白双击。下文IndexedStack为历史实现：当前Flutter包装不保留直接子页Key，真实Windows关闭兄弟页会重建原生实例，已用Stack直接Key的Offstage/ExcludeFocus/TickerMode修复。网页同控制器/DOM标记、视频2秒保留与后台继续播放均通过原生自动化。Ctrl+T现新建默认学习页，其他键保留；操作系统原生焦点矩阵仍待验。[设计](editor-tabs-design.md)、[验证与截图](editor-tabs-validation-2026-10-25.md)。

2026-10-24 后续：已实现鼠标拖动标签排序并通过冻结 Windows 自动交互；下段“尚未实现”是首批历史。目录迁移先销毁页面并等待原生环境释放，再复制 profile；真实 WebView 已创建后的迁移通过。崩溃恢复保留内存草稿，通过业务 API 写回新后端。完整当前状态见 [持续开发报告](m1-completion-2026-10-24.md)。

M0 旧标签为题目/网页/播放器三个固定入口。M1 首批现已支持动态新增、关闭、重开和持久化，按工作空间隔离；可开多个同类页面。IndexedStack 保留已打开页的标签内状态，未访问的恢复页延迟创建；关闭后重新实例化，WebView profile 按空间/标签 ID 独立保存。关闭历史最多10项，打开页最多16项；主观草稿、网页最后成功加载地址、活动空间/标签重启恢复。原生视频的字幕选择与播放进度不纳入本批持久化，完整媒体状态属 M4。拖动排序尚未实现，不将其算作 M1-02 已通过。

Flutter 获得键盘焦点时提供 Ctrl+T 新网页、Ctrl+W 关闭、Ctrl+Shift+T 重开、Ctrl+Tab/Ctrl+Shift+Tab 切页；外部原生 WebView 焦点下的快捷键转发仍待专门验证。自动保存串行执行，避免旧请求覆盖新草稿；切换空间及正常退出先等待保存，失败保留当前状态并提示，不自动丢弃。WebView 原生生命周期已回归关闭/重开播放器的真实解码，不代表 DPI/焦点矩阵完成。

候选对比：[webview_windows 0.4.0](https://pub.dev/packages/webview_windows)（BSD-3-Clause、Windows 专用、Windows.Graphics.Capture 合成，版本较旧）与 [flutter_inappwebview 6.1.5](https://pub.dev/packages/flutter_inappwebview)（Apache-2.0、多平台公开 API、有 Windows 实现）。M0 先试后者，Windows SDK/NuGet/Runtime 和导航拦截能力需要构建确认；尚未授予生产可用结论。

外部页面仅 HTTPS，拒绝 loopback/私有 IP/本机、file/data/javascript；每次导航和重定向校验。阻止新窗口，权限请求默认拒绝，不注册 JS handler/host object，不传 Authorization、不允许任意本地资源。生产版还要验证 DNS 重绑定、弹窗/下载/重定向和存储 profile 隔离；不能仅凭初始 URL 白名单声称安全。

播放器只加载内置可信 HTML 与一个会话媒体 capability；不共享业务令牌。HTML CSP 禁止远程 connect/frame/object，视频源限定 loopback。媒体能力只读单个启动时指定的文件，没有目录列表/任意路径。业务 API 即使外部网页访问 loopback 也必须认证且拒绝外部 Origin。

导航提供前进/后退/刷新与系统浏览器回退。DeepSeek 登录、验证码、DRM、硬件解码、睡眠恢复待实际站点/硬件验证。
