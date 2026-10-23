# API v0 / M0

HTTP 地址由后端启动握手返回，固定绑定 127.0.0.1 随机端口。除专用媒体路由外均需 `Authorization: Bearer <session>`；不启用 CORS；带 Origin 的 API 请求拒绝；Host 仅允许 127.0.0.1。令牌不打印、不持久化、不进入 URL。

| 方法 | 路径 | 结果 |
|---|---|---|
| GET | /api/health | api_version、status、SQLite 可用性 |
| GET | /api/questions/demo | 公开展示题目与解析，非考试保密 API |
| POST | /api/attempts | question_id、response；返回 id/status/score |
| GET | /api/attempts | 演示作答列表，用于验证重启持久化 |
| GET | /api/player | 可信 HTML，内含独立只读媒体 capability |
| GET/HEAD | /media/demo?cap=... | 单个指定视频，支持 Starlette FileResponse Range |

错误：401 鉴权，403 Origin/能力错误，404 未知题/媒体，422 请求或选项不合法。M0 使用 FastAPI 统一错误结构；M1 定义稳定 error.code/message/request_id 和分页/幂等策略。

启动协议：stdin 第一行 JSON {token}（>=32 字符），stdout 一行 {port,api_version}；后端 stderr 为日志，stdin EOF 退出。不允许命令行传密钥。启动超时/版本不符在 Flutter 显示错误，不能静默接入任意端口。
