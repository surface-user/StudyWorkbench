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

## PAR-02b 原生双栏单页预览

业务入口要求当前空间的资料节点、预期原件摘要和原始页号。复用分块任务的 PDF 身份与 8 MiB 读取检查、文档查看的两个并发槽和 20 秒子进程。在明确选择双栏时，按页边框中线划分左右两栏，按纵坐标从上到下排序，返回文字、原页归一化包围框、页号及原件摘要。单独文字对象跨中线、文字行重叠、空栏、嵌套版式或旋转等不确定情况返回 available=false 与原因。仅支持可分开的水平文字行，图片和题干的跨栏归属另行实施。未引入依赖。

自编 ASCII PDF 在对象流中交错写入右下、左下、右上、左上四行，期望顺序由测试独立断言。业务 HTTP 同时验证版本、空间、页号、两栏坐标和原件字节。首轮双 Python 各 1 通过、5 失败，发现固定版 PDFium 的文本页没有上下文管理器协议；改用 closing 明确释放。专项复验 6 项通过。最终在 pdf-column-preview 副本用 Python 3.12.7 和 3.13.17 各运行 `python -X utf8 -m pytest -q backend/tests/test_document_files.py backend/tests/test_pdf_chunks.py backend/tests/test_markdown_questions.py`，每版各 27 项通过、2 项既有警告，退出 0。原始与最终日志、JUnit 均在副本 artifacts。

`python -m ruff check backend tools`、`python tools/export_question_schema.py --check` 以及源码 `python tools/check_document_workers.py` 均退出 0。冻结包 CI 使用同一份交错双栏样本和独立顺序断言。按本批安排暂缓独立审查，人工测试已取消。此项只交付后端预览，OCR 和双栏拆题另有任务。

## PAR-02c 可选 Windows x64 OCR 开发组件

离线输入为 Tesseract 5.5.4 固定提交源码归档（1971321 字节，SHA-256 445603ab1d0a63df552e193a600d9d5c4021aff36e144f3091af149e5efb381a，解出 748 个普通文件逐一对上官方 Git blob），Leptonica 1.87.0 发布源码包（14802808 字节，c73363397f96eb1295602bf44d708a994ad42046c791bf03ea0505d829bdb6a7），上一节两个语言模型，以及编译工具许可。所有构建、样本、原始日志位于隔离开发副本的 .local 和 artifacts。

在 VS 2022 x64 Native Tools 环境（cl 19.44.35219，CMake 3.31.6，Ninja，CL=/utf-8）使用以下参数；src-lept、src-tess 表示已核来源的解包目录，prefix 为绝对开发目录，以下示例在 PowerShell 中运行。

```powershell
$prefix = Join-Path $PWD 'prefix'
$common = '-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DCMAKE_POLICY_DEFAULT_CMP0091=NEW','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded','-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF','-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF'
$codecs = 'ZLIB','PNG','GIF','JPEG','TIFF','WEBP','OPENJPEG' | ForEach-Object { "-DENABLE_$_=OFF" }
cmake -S src-lept -B build-lept @common @codecs -DSW_BUILD=OFF -DBUILD_PROG=OFF "-DCMAKE_INSTALL_PREFIX=$prefix"
cmake --build build-lept --parallel 3
cmake --install build-lept
cmake -S src-tess -B build-tess @common "-DCMAKE_PREFIX_PATH=$prefix" -DCMAKE_CXX_FLAGS=/DTESSERACT_DISABLE_DEBUG_FONTS -DWIN32_MT_BUILD=ON -DGRAPHICS_DISABLED=ON -DDISABLED_LEGACY_ENGINE=ON -DBUILD_TESTS=OFF -DBUILD_TRAINING_TOOLS=OFF -DDISABLE_ARCHIVE=ON -DDISABLE_CURL=ON -DDISABLE_TIFF=ON -DENABLE_NATIVE=OFF -DOPENMP_BUILD=OFF -DINSTALL_CONFIGS=OFF
cmake --build build-tess --target tesseract --parallel 3
```

首次 CMake 编译器检测遇到 PDB 服务 C1902。获得本机编译权限后，首次链接遇到 /MD 与 /MT CRT 冲突，保留两个失败日志。两项目改用同一静态 CRT。起初引擎认出英文，但调试字体初始化请求未编入的 TIFF，首个中文样本也没有词。用显式 Unicode 字符生成新样本，在同一引擎识别出“中文学习”和“今天天气很好”；上游 DebugPixa 构造器支持编译时停用调试字体。应用该开关重编后，PGM 识别过程 stderr 为空。最终 exe 2473472 字节，d825d9d9e94ab996f735e7eba9d199c009481ca9895ad16b1e1b6acfdeb343c0。pefile 检查为 x64 PE，普通导入仅 KERNEL32.dll，无延迟导入。编译器产生的文件按这一次实际哈希锁定，跨机器重编的字节一致性待验证。

在此开发副本执行下列命令（Python 使用既有项目隔离解释器）。阶段目录含中文及空格，准备、全量复核、三个实际识别样本均退出 0。所有模型、程序和许可置于开发副本；Git 只保存工具、测试、固定摘要和报告。

```powershell
python tools/prepare_ocr_runtime.py prepare --directory '.local/OCR 组件' --engine .local/build-tess-pgm/bin/tesseract.exe --tessdata ../document-layout-plan/artifacts --engine-license .local/src-tess/LICENSE --leptonica-license .local/src-lept/leptonica-license.txt --compiler-license ../ffmpeg-msvc-component/.local/compiler-license/Visual-Studio-2022-Community-License-EN.docx
python tools/prepare_ocr_runtime.py verify --directory '.local/OCR 组件'
python tools/check_ocr_component.py --directory '.local/OCR 组件'
python -X utf8 -m pytest -q backend/tests/test_ocr_component.py backend/tests/test_java_runtime_preparation.py
```

实测 Tesseract 从管道读自编灰度图，整行英文与简体中文各返回三个词区，文本完全匹配，所有区域位于图内且分值在 0–100；空白图返回零词。双 Python 3.12.7/3.13.17 各 45 项通过，退出 0，含原有 Java 重复 ZIP 项提示。准备测试覆盖被替换的引擎、模型和许可、缺件、额外文件或目录、目标已存在和失败时不会发布半成品。人工测试取消，独立审查暂缓。下一项接入用户指定扫描页，产品安装包、发行签名和完整传递许可另行跟踪。
静态检查首轮隔离解释器的 python -m ruff 找不到其 Scripts/ruff.exe，退出 1。改用项目原有 release-venv/Scripts/ruff.exe check backend tools 通过，协议检查 python tools/export_question_schema.py --check 通过，均退出 0。

## PAR-02d 指定扫描页 OCR 预览

活动资料节点接收原件摘要、页号、固定语言和请求 ID。实际子进程读取原件受控快照，复用 PDFium 阅读器的单页像素上限。Tesseract 只收到该页的灰度图。接口返回原页号、原件摘要、模型摘要、词区、置信分和可读文字，结果标记待确认。25 秒限时与显式取消覆盖渲染器和识别器，退出后工作区、资料绑定和原件字节再核一次。运行请求只存在内存。Windows Job 使用挂起后加入再运行的方式，选择性传入三个标准流句柄，临时输入/输出由系统在句柄关闭时清除。

在 ocr-page 隔离副本分别用 Python 3.12.7 和 3.13.17 执行以下命令。OCR、文档查看、Office 原入口各项合计每版 61 项通过，随后增加父进程异常退出反例，单项两版各 1 通过，均退出 0。父进程直接退出前实测工作进程及其原生子进程模拟器均存活，随后用原先持有的两个系统句柄分别验证均已退出。初次扩展专项误填不存在的 test_office_runtime.py，两个解释器都以退出 4 结束，没有运行测试，原日志 final-p/q 已保留。

```powershell
python -X utf8 -m pytest -q backend/tests/test_ocr_page.py backend/tests/test_ocr_component.py backend/tests/test_document_files.py backend/tests/test_office_launcher.py backend/tests/test_office_previews.py
python -X utf8 -m pytest -q backend/tests/test_ocr_page.py::test_abrupt_owner_exit_reaps_the_worker_and_its_child
ruff check backend tools
python tools/export_question_schema.py --check
python tools/check_ocr_component.py --directory '../ocr-runtime/.local/OCR 组件'
```

Ruff、题目协议与真实组件的中英文和空白输入均通过。packaging/windows/build-backend.ps1 使用项目独立的 Python 3.13.17 和 PyInstaller 构建 Windows 后端。收紧取消及超时边界后重新构建，48 个冻结应用模块逐一与最终源码匹配，退出 0。另用下面的实际 HTTP 检查在两个全新目录验证源码和最终冻结包。源码 79 次请求，冻结包 78 次请求，均含 31 个不同错误 ID，退出 0。计数随异步轮询而异。

```powershell
python tools/check_api_errors.py --ocr-component '../ocr-runtime/.local/OCR 组件' --test-root artifacts/source02
python tools/check_api_errors.py --ocr-component '../ocr-runtime/.local/OCR 组件' --test-root artifacts/frozen02 --exe dist/study_backend/study_backend.exe
```

自编三页 PDF 走正常资料添加、节点选页、英文和中文模型、空白、运行中取消、后端重启与取回原件。每页精确比对预期文本，核对页码、结果来源、引擎与模型版本、原页包围框、分值、未确认状态。错误预算、过期摘要、跨空间请求、被替换的原件、格式或语言不符、低置信和文本截断另有专项回归。原始输出保存在 artifacts。该路径依赖另行准备的固定 Windows 组件。本项仅交付后端预览，桌面按钮、安装包分发、双栏题目归组和题库确认各由对应任务跟踪。独立审查暂缓，人工测试取消。
