# Office修补后的派生页图证据

来源运行：2026-11-06，tools/check_office_previews.py，冻结代码4cd157a870d557eb82d57204431b8642bf295ffd；新exe SHA256 a541135a5299e8cbea5b5c4c4e75ebf6f72d3fdbee5fad8a355edf5bff5026ce。原始PNG位于Git忽略的.local/lw06-final-中文-20261106-01/，不是从整个artifacts目录搬入。

固定LibreOffice26.8.1运行时指纹147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca；DOCX/PPTX各2页，派生PDF67520/46266字节。输入是项目自编中文/公式/表格/图表测试材料，未纳入导入原件、个人学习库、令牌、转储或完整日志。四张均逐张查看并核对原始/共享副本hash；不作裁切或内容修改。

仅筛选这四页，以便评审修补后的中文、公式、图表和尾页保留结论；不证明任意Office保真、不代表实际应用窗口、普通用户、安装或阶段验收。原失败/原组件转储继续保留在本机，详见[原报告](../report.md)。

| 证据 | 字节 | SHA256 | 筛选理由 |
|---|---|---|---|
| [docx-page1.png](docx-page1.png) | 41223 | 899b11d65750e018aee1b6078053172d797aaf14d220aa90fec111b9e287a30d | DOCX中文题干、OMML公式和表格未缺失 |
| [docx-page2.png](docx-page2.png) | 25341 | 547b6b4c3a813bde313b6658bc4bfae7a924504b25d63f2546b899e9ca88a4eb | DOCX第二页内容保留，补齐此前未检查的尾页 |
| [pptx-page1.png](pptx-page1.png) | 68532 | 5e4dd81253339faec61bd46509d501f616d79b66b4f89d45aa70b9bed1c3b5fc | PPTX中文表格和静态图表标签可见 |
| [pptx-page2.png](pptx-page2.png) | 40927 | 79d0135c16f2b14b3b18636370185f79d592355291aefecfdaf9f8c101067d32 | PPTX第二页中文和上标公式可见 |
