# PAR-02 双栏与离线 OCR

## 首批设计和固定来源评估

原生 PDF 已使用固定 PDFium，选区、页号、向上计数的 PDF 坐标和预览图的向下计数坐标需要统一。先支持用户明确选择的等宽双栏单页预览。把正文识别、不可判定的布局和后续拆题分开验证。既有单栏预览与原件读取入口继续走现有行为。[行为契约](../../../docs/question-markdown-spec.md#columns-and-ocr)

扫描页优先评估可随项目独立分发的 Tesseract。上游分别提供引擎源码与语言数据。GitHub 发行标签 5.5.4 解析到提交 `7e548e6eff172f38f97664afe7f7ce40db36c8d6`，本次查询 release assets 为空。Windows 二进制的编译配方、Leptonica、实际编解码集合、传递许可和运行时仍须验证。Windows 自带 OCR 可枚举设备已安装的语言，对当前安装/便携包的调用及用户设备的中文可用性尚无实证。[引擎发布](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.4) · [官方安装说明](https://tesseract-ocr.github.io/tessdoc/Installation.html) · [Windows OcrEngine](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine)

在开发副本 artifacts 中用 urllib.request 从上游锁定的 tessdata_fast 4.1.0 提交读取三个原件。对每个文件限制最多读取声明长度加一字节，同时断言长度与官方 Git blob SHA-1，再独立计算 SHA-256；退出 0。模型和许可不随本次文本 PR 上传。[上游固定目录](https://github.com/tesseract-ocr/tessdata_fast/tree/65727574dfcd264acbb0c3e07860e4e9e9b22185)

| 上游文件 | 字节 | SHA-256 |
|---|---:|---|
| chi_sim.traineddata | 2469156 | a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730 |
| eng.traineddata | 4113088 | 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2 |
| LICENSE | 11358 | cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 |

引擎与固定语言仓的 LICENSE 同为 Git blob `d645695673349e3947e8e5ae42332d0ac3164cd7`，内容为 Apache License 2.0。该对应关系只覆盖两个上游根许可。此次没有执行 OCR，识别效果以及最终发行物的传递许可继续由后续小项验证。新项目依赖尚未加入。人工测试取消，独立审查暂缓。
