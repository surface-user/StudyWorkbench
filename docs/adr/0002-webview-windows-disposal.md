# ADR 0002：Windows WebView 环境释放兼容

日期：2026-10-23；状态：M0 版本限定兼容措施。

实证：Windows 集成测试播放断言通过，但卸载 widget 后抛出 MissingPluginException，环境 dispose 通道不存在。固定依赖 flutter_inappwebview_windows 0.6.0 的 lib/src/webview_environment/webview_environment.dart 中 create()：原生 create 参数使用 env.id，返回实例的 channel 却使用静态接收者 `$id`，导致两个环境的 dispose 都访问错误通道。

决策：不修改第三方缓存、不隐藏测试异常。在应用适配器 webview_lifecycle.dart 中，Windows 通过固定插件原生通道前缀加公开 environment.id 调用 dispose，其他平台仍用公开 dispose。调用异步错误由 Flutter 错误框架报告，集成测试包含清理后的等待和异常检查。

这是依赖内部通道命名的临时兼容，不是通用公开 API。后续升级插件必须首先核对是否修复，并移除此措施后重测创建/退出/动态关闭。Dart 侧静态错误 handler 不承载应用事件，会随进程退出释放；M0 固定两个环境，M1 动态标签前应升级修复版本或采用正式适配器，不能无限创建。

原始失败摘要保留在 m0-validation.md；最终回归以该文件记录为准。
