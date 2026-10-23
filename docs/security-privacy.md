# 本地安全与隐私

威胁边界：外部网页、导入文档、下载 URL、AI 输出均不可信。同一 Windows 用户的恶意进程不属于会话令牌能完全抵御的攻击者；不承诺对已失陷账户保密。

后端 loopback 随机端口 + 强随机会话令牌 + Host/Origin 检查，无公开 docs/openapi 路由，无全局 CORS。令牌只 stdin/内存流转。媒体 capability 与业务令牌独立，仅可读一个配置文件；URL 可能被有权读取 profile 的进程看到，因此 session 生命周期结束后作废。

生产 WebView 的导航、子资源、DNS 私网访问、新窗口、下载、权限和 profile 隔离均要有负面测试；M0 代码防护不代替该验收。用户主动在系统浏览器打开 URL 前仍校验 scheme。插件 6.1.5 没有 javaScriptBridgeEnabled 参数；M0 不注册任何应用 JS handler/主机业务对象，但插件自身内部脚本不能据此称为已禁用。DNS 解析预检与实际 Chromium 请求存在时序差，尚不构成 DNS 重绑定防护证明。

导入未来采用路径约束、扩展名/MIME/文件头联合检查、大小/解压比限制、沙箱/超时；原文 HTML 不直接执行。下载防 SSRF、仅授权来源、参数列表调用 yt-dlp/FFmpeg，不用 shell=True。

数据目录将设置用户 ACL；备份包含隐私，默认本地；导出时提示范围。数据库不默认加密，M1 明示保护边界。不得记录 API 密钥、题库原件、URL 中凭据。升级前备份，失败保留现场。
