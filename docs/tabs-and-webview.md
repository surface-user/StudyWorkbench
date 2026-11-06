# 标签与WebView生命周期

## 当前已实现

EditorTabBar使用38px连续标签、112–220px宽度、活动/非活动/hover/焦点/加载/错误/未保存状态，横向溢出与菜单、拖动排序、右键批量关闭和减少动画。视觉目标原文见[用户规范](editor-tabs-spec.md)，有规范不等于逐项验收通过。

WorkspaceShell统一Ctrl+T（欢迎页）、Ctrl+W、Ctrl+Shift+T、Ctrl+Tab/Shift+Tab、Ctrl+1–8/9及空白双击；重复资源打开激活同一身份。活动页关闭优先左邻、再右邻，末页为空工作区；批量关闭逐页处理保存/放弃/取消，保存失败保留页面。每空间16开/10关，旧utility/layout与未知页兼容。

PageHost用Stack直接子项的稳定页ID Key与Offstage/ExcludeFocus/TickerMode保留已访问实例；不是IndexedStack。未访问页惰性创建，关闭立即释放页面和原生WebView环境，关闭动画仅保留标签外观。后台媒体继续播放，网页切换保持实例；重开只恢复已序列化URL/状态，不承诺原DOM实例。归档空间和应用退出释放对应页面。

布局保存串行，切空间/退出等待；后端意外退出保留内存草稿，重启后经业务接口恢复。文件草稿/基准hash与作答草稿分离；保存layout不等于保存文件/提交答案。资源移动改名不变tab_id，重开按身份恢复模式/位置。

外部HTTPS WebView拒绝本机/私网/file/data/javascript等，导航和重定向校验，阻止新窗、默认拒绝权限，不注册业务JS handler/host object、不传Authorization。插件自身内部脚本不等于已禁用，DNS预检存在TOCTOU。可信播放器只加载内置HTML与指定媒体capability，CSP限制远程加载，外网页面无业务桥/令牌。

内部链接的原生导航复用资源标签身份，前后返回每次重新resolve，保存失败/脏页不被定位覆盖。最多50条运行时URI/视图记录不含正文、令牌或capability，关闭窗口不承诺恢复该栈；文档返回位置先匹配显示版本，Office分页还匹配原预览。MD预览点击才跟随，外站页面不解析studyworkbench URI或获得业务桥。

## 规划中

固定标签、无限期独立资源阅读位置库、完整三方合并/网页进程恢复不属于已实现能力；按具体需求另行设计。下载队列及R6见[任务](task.md)。

## 待验证

原生WebView获得OS焦点后的完整快捷键矩阵、真实显示器多DPI/性能、中文IME、外站登录/验证码/DRM、硬件解码/休眠及全部导航子资源负面测试仍待验。插件0.6.0环境释放版本限定兼容见[ADR0002](adr/0002-webview-windows-disposal.md)，升级前复核并回测，不能修改上游缓存绕过。
