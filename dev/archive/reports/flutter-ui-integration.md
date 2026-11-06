# UI 复用方案

> 历史记录：保留当时范围、失败和结论；不作为当前规范。现行状态见[task](../../../docs/task.md)。报告中的原命令路径不改写为本次新位置。

pubspec 使用 HTTPS Git 依赖，ref 固定 `a0bc51acf22db1b867294f810157cfeba7e951fb`，提交 pubspec.lock。仅 import 包公开入口；不复制 src 或改原库。

MaterialApp 使用 LiquidGlassThemeData 扩展；GlassBackdrop 提供静态背景，GlassSurface 放侧栏和导航。主体高密度阅读区保留清晰对比，不在 WebView 视频上叠加模糊；高对比/减少透明度通过主题配置降级。

M0 中文导航、公式、答题状态与后端状态；M1 补键盘标签切换、关闭/恢复、窗口尺寸、100/150/200% DPI 与深浅色、无障碍人工验证。不凭 golden 测试推断真实 WebView 叠层性能。
