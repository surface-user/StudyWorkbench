# 标签页与 WebView2

M0 标签：题目、网页、播放器；IndexedStack 保留页面状态。M1 才实现任意标签新增/关闭/排序/持久化，M4 实现完整网页多标签。

候选对比：[webview_windows 0.4.0](https://pub.dev/packages/webview_windows)（BSD-3-Clause、Windows 专用、Windows.Graphics.Capture 合成，版本较旧）与 [flutter_inappwebview 6.1.5](https://pub.dev/packages/flutter_inappwebview)（Apache-2.0、多平台公开 API、有 Windows 实现）。M0 先试后者，Windows SDK/NuGet/Runtime 和导航拦截能力需要构建确认；尚未授予生产可用结论。

外部页面仅 HTTPS，拒绝 loopback/私有 IP/本机、file/data/javascript；每次导航和重定向校验。阻止新窗口，权限请求默认拒绝，不注册 JS handler/host object，不传 Authorization、不允许任意本地资源。生产版还要验证 DNS 重绑定、弹窗/下载/重定向和存储 profile 隔离；不能仅凭初始 URL 白名单声称安全。

播放器只加载内置可信 HTML 与一个会话媒体 capability；不共享业务令牌。HTML CSP 禁止远程 connect/frame/object，视频源限定 loopback。媒体能力只读单个启动时指定的文件，没有目录列表/任意路径。业务 API 即使外部网页访问 loopback 也必须认证且拒绝外部 Origin。

导航提供前进/后退/刷新与系统浏览器回退。DeepSeek 登录、验证码、DRM、硬件解码、睡眠恢复待实际站点/硬件验证。
