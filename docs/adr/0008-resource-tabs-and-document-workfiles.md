# ADR 0008：资源身份标签与可恢复Markdown工作副本

现行关系（2026-10-30整理）：Word/PPT分页的未实现边界已由[ADR0009](0009-offline-office-previews.md)接续；旧DOC/PPT和动态内容限制仍保留。

状态：2026-10-26用户授权从R1复核后按R1–R6顺序继续开发、自动测试和审查；人工及阶段统一待验。

R2不改表，layout v2扩展资源身份与受控视图，兼容v1旧utility和有预算的未知标签。节点ID与文件名/hash分开，旧标签不猜测绑定。外部网页复用隔离WebView，媒体复用按MediaEntry授权的播放器；能力URL只在内存，后端重启重新申请。

R3追加0008的document_workfiles与document_saves，Resource原件继续不可变。明确创建工作副本后才能编辑；磁盘正文为当前权威，索引hash只是缓存。保存expected hash校验，旧版本/待写内容fsync后先提交prepared收据，再同目录原子替换，最后更新索引。重启将当前hash与old/new对账，标记committed/interrupted/conflict；不自动覆盖外部内容，不删失败字节或恢复点。文件和SQLite不是跨介质原子事务；本地外部程序仍可能在最后hash检查与replace之间竞争，恢复点保留检查时的旧内容，尚未提供OS级排他外部编辑锁。

MD草稿与expected hash、模式/位置保存在layout v2（与作答草稿区分）；保存layout不等于文件已保存，关闭仍确认。每份文本/草稿最多1MiB UTF-8，layout实际请求上限32MiB（16开/10关），document PUT上限8MiB；旧题目草稿仍最多16000字符，不放宽其协议。页码/缩放/滚动为受限版本化字段。

复用PDFium/Pillow子进程及DOCX结构提取，不增加原生转换器。PDF阅读上限128MiB/2000页，逐页最长边2048像素；旧8MiB/20页拆题限制保持。图片PNG/JPEG最多16MiB/1600万像素；DOCX结构预览沿用8MiB/25秒；读取/渲染最多并发2份，忙时429可重试。MD预览最多200000字符，源文/工作副本上限1MiB。

Flutter固定flutter_markdown_plus 1.0.12与markdown 7.3.1（BSD-3-Clause），复用flutter_math_fork，不运行HTML/TeX引擎。覆盖默认图片构造器，只允许同空间逻辑树相对PNG/JPEG，拒绝网络/绝对路径/跨根；链接仅显示地址，不自动打开。完整依赖审查见[dependencies.md](../dependencies.md)。

此批Word只做结构预览；DOC/PPT/PPTX分页转换、无Office离线包验证仍是R3未完成项，不能宣称完整查看器阶段通过，也不跳至R4。迁移只用生成的隔离旧库，原0001–0007不改；旧行/文件和历史验收失败保留。
