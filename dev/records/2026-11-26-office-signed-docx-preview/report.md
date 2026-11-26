# OFF-02s 带包签名的 DOCX 普通预览及原生依赖边界

基于 [OFF-02r](https://github.com/surface-user/StudyWorkbench/pull/121)。检查目标是确认带包签名的文档经过现有预检和 Writer PDF 导出时，能否观察到整包中尚未归属的库。这里验证的是文档正文预览。应用没有向用户承诺校验签名、证书链或签名人身份。

## 样本与结果

三个样本均取自固定版本 LibreOffice 自身的签名测试。使用公开样本是为了让其他开发者能取得同一份输入；文档、签名数据、证书及本次 PDF 均不随报告提交。[上游样本目录](https://github.com/LibreOffice/core/tree/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/xmlsecurity/qa/unit/signing/data) · [上游测试](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/xmlsecurity/qa/unit/signing/signing.cxx)

| 样本 | 固定输入 SHA256 前 12 位 | Office-Java | Office-Java 与自包含 Python |
|---|---|---|---|
| partial.docx | e334ba5653c8 | 1 页，正文匹配 | 1 页，正文匹配 |
| multi.docx | ed50bdff1917 | 1 页，正文匹配 | 1 页，正文匹配 |
| signatureline.docx | d1a6e277e3b7 | 图片格式预检拒绝 | 图片格式预检拒绝 |

两个可转换样本都含包签名。源模式后端的 OfficeRuntime.convert 在两份组件上各运行两例，核对原文同一段文本在 PDF 唯一一页出现，并复核源字节。第三例触发现有只允许 PNG/JPEG 的图片限制。组件清单分别为 19,743 和 19,746 个文件，运行前后均核验。

另以相同参数和配置在 Windows Job 中执行四次转换。通过 Job 成员身份、进程映像和文件摘要确认普通 soffice.bin。筛选的模块包含已归属的 jvmaccesslo 和 jvmfwklo，四次采样均未取得额外未知文件的正向加载证据。个别进程启动或退出期间，Windows 返回 5 或 299，相关快照舍弃。这种采样不能排除短暂加载，也不能据此放宽发行检查。

## 剩余文件的区分条件

下表按自包含组件的固定依赖图分组，仅用于安排后续验证。

| 数量 | 文件类型 | 尚需要的证据 |
|---:|---|---|
| 22 | 随包 CRT 副本 | 对应体系结构的实际消费者、私有加载目录及已加载文件身份。同名系统或其它目录副本不能互证。 |
| 16 | Python 稳定 ABI 转发库及安装工具的启动器模板 | 核实转发目标或模板生成后的实际安装程序和解析路径。已有模板来源记录。 |
| 11 | CLR 程序集及版本策略 | 托管宿主和相应版本策略的实际绑定。 |
| 7 | Windows Shell、COM、ActiveX、SharePoint 集成 | 相应宿主或注册上下文，以及正确的位数。 |
| 4 | 其余 NSS 库 | 确认具体证书、旧数据库、邮件加密或 TLS 消费者加载固定组件内的文件。 |
| 3 | 额外 UNO 模块 | 实际相应加载方式、环境或服务及模块路径。 |
| 2 | Java 管道桥 | 正式 Java 客户端已经验证。将它独立纳入图时仍需检查 Java 与原生 Office 各自的加载域和重复 CRT。[客户端专项](https://github.com/surface-user/StudyWorkbench/pull/121) |
| 2 | 数据库引擎和字符集模块 | 对应嵌入式数据库的实际访问和插件加载。 |
| 1 | 扫描辅助进程 | 32 位扫描宿主及其 CRT 解析；历史缺口继续保留。 |

自包含组件仍有 68 项，原组件仍有 69 项。原组件独有两份未归属的内置 Python 启动器，自包含组件独有另一份未归属的稳定 ABI 转发库。批准的普通分页输入只有 DOCX/PPTX；外部关系、主动对象和宏等仍受现有预检限制。没有把安装、注册、向外连网或手工操作引入普通预览。

## 自动复验

在项目的 Windows 后端环境，用固定组件和上游样本目录设置 OFFICE_COMPONENT 和 OFFICE_FIXTURES，将 PYTHONPATH 设为 backend。以下 Python 代码直接调用源模式后端入口。运行时应使用全新的工作目录作为 OFFICE_OUTPUT。

```python
import hashlib
import os
import time
from pathlib import Path
from zipfile import ZipFile

import pypdfium2
from study_workbench.office_inputs import validate_office
from study_workbench.office_runtime import OfficeRuntime

runtime = OfficeRuntime(Path(os.environ["OFFICE_COMPONENT"]).resolve(strict=True))
fixtures = Path(os.environ["OFFICE_FIXTURES"])
output = Path(os.environ["OFFICE_OUTPUT"]).resolve()
output.mkdir()
deadline = time.monotonic() + 540

def checkpoint():
    if time.monotonic() >= deadline:
        raise TimeoutError("Preview verification exceeded its time budget")

for name, marker, digest in [
    ("partial", "Hello world!", "e334ba5653c858e0cfdd843f30c03a37b8129e631e9a7fdc8649a5a97739d88e"),
    ("multi", "Hello multi", "ed50bdff191746b859a1665abc88ce8e09d5d8b3421cffc10ee0d8b76242edc7"),
]:
    case = output / name
    case.mkdir()
    source = case / "source.docx"
    original = (fixtures / (name + ".docx")).read_bytes()
    assert hashlib.sha256(original).hexdigest() == digest
    source.write_bytes(original)
    with ZipFile(source) as archive:
        assert "_xmlsignatures/sig1.xml" in archive.namelist()
    pdf = runtime.convert(source, case, checkpoint)
    with pypdfium2.PdfDocument(pdf) as document:
        assert len(document) == 1
        assert marker in document[0].get_textpage().get_text_range()
    assert source.read_bytes() == original
third = (fixtures / "signatureline.docx").read_bytes()
assert hashlib.sha256(third).hexdigest() == "d1a6e277e3b7790cb2ebf488db2b2ab2af14adcbb8ed5b68d94cd5f8ff35dd0c"
try:
    validate_office(third, ".docx")
except ValueError as error:
    assert "PNG/JPEG" in str(error)
else:
    raise AssertionError("Unsupported signature-line image was accepted")
runtime.verify(checkpoint)
```

本机直接转换、同命令进程采样和两份既有依赖图对照均退出 0。逐文件清单与原始模块记录保存在忽略目录。本项独立审查暂缓，人工测试已取消，发行门禁维持部分覆盖。
