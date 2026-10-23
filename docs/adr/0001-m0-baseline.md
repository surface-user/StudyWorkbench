# ADR 0001：M0 架构基线

日期：2026-10-23；状态：采用（Windows 原生集成验收仍是阶段门禁）。

使用用户指定 Monorepo 模块化单体、Flutter/Python/SQLite。普通业务独立于 Agent。Flutter 不直接操作数据库；富内容块与作答记录独立；主观题待批改。

玻璃库以 Git SHA 锁定公开 API；不修改上游。WebView2 原型采用 flutter_inappwebview，HTML5 原生 video 先验证，不提前引入全套播放器框架。后端子进程使用 loopback/随机端口/私有 stdin 令牌，网页不获得业务身份。

代价：Python 打包、WebView2 原生依赖、进程生命周期、编码矩阵、安全隔离都需 Windows 实证。后备原生播放器/转码只有实际格式失败并评估许可证后才引入，不能借原型改变技术栈。
