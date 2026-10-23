# 系统架构

采用 Monorepo + 模块化单体。`apps/desktop` 是 Flutter 窗口、导航、交互和渲染；`backend/study_workbench` 是本地业务/持久化；`contracts` 为协议样例；`packaging/windows` 为发行脚手架；`tools` 为开发验证；`docs/adr` 为决策。

Flutter → 受保护 HTTP API → Python 应用服务 → SQLAlchemy → SQLite。文件处理服务通过资源 ID 访问数据根目录，原文件不放 BLOB。导入、学习、媒体、AI 将按业务模块拆分，M0 不建立空抽象层。

桌面父进程启动后端，stdin 交接随机令牌；后端预绑定 127.0.0.1:0，stdout 只返回实际端口；不会扫描或复用未知服务。Dart 请求均带 Bearer。关闭时终止自有后端；后端也监测 stdin EOF 防止孤儿。M0 不处理多实例，M1 要采用独立会话或带身份的单实例协调。

外部网页无主机桥、无令牌；本地播放器仅获得专用媒体能力令牌，不能调用业务。不同 WebView 生命周期与页面状态分开，玻璃容器不覆盖视频绘图区，避免原生视图合成问题。

M0 仅建立示例题、健康检查与持久化作答链路。工作空间、导入、下载任务、AI 均未实现。数据库 schema 由 Alembic 管理，禁止生产启动时 create_all 或静默删除重建。
