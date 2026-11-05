# Flutter_liquid_glass 审查（2026-10-23）

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

源码：[surface-user/Flutter_liquid_glass](https://github.com/surface-user/Flutter_liquid_glass)，本次 clone 的 main 提交 `a0bc51acf22db1b867294f810157cfeba7e951fb`，包名 `lightweight_liquid_glass` 0.1.0。

- LICENSE 为 MIT；发布时保留版权/许可。运行时依赖只有 Flutter SDK；dev 依赖 flutter_test。
- pubspec 要求 Dart >=3.12.0 <4、Flutter >=3.44.0。本机 3.47.1 / 3.13.1 满足。
- 公开入口 lib/lightweight_liquid_glass.dart 导出 style/theme/surface/backdrop/components/motion，隐藏 glassReduceMotion/glassTransition 内部辅助函数。
- GlassSurface(child, style, padding, margin, enabled, fallbackColor...)；GlassBackdrop；GlassGroup；LiquidGlassThemeData/ThemeExtension；GlassPerformanceConfig/GlassAccessibilityConfig；按钮和路由等公开组件。以实际源码参数为准。
- GlassSurface 使用限定区域 BackdropFilter、ClipRRect/ClipOval、CustomPainter，前景不模糊。减少透明度和高对比度可降级不透明，系统减少动画受到支持。
- test/style_test.dart、widget_test.dart、golden_test.dart；golden 图片有 light/dark/contrast/fallback，测试自带 Roboto 及许可证。源码存在不等于当前 Windows 通过。
- 仓库未见 .github 工作流；GitHub 元数据显示创建/推送于 2026-09-17，小型自有新库，不能称长期成熟项目。
- 纯 Flutter 无平台插件，因此具备 Windows 接入基础；桌面 GPU 性能、DPI、键盘焦点、WebView 合成仍必须实测。

审查副本在忽略的 .research 内；业务不引用该路径，也不修改上游。
