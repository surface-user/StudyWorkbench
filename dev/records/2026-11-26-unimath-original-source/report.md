# REL-02b 数学符号表的原始版本和修改

原作者 Günter Milde 的项目主页同时列有符号表、辅助数据和处理脚本。符号表的作者声明为 LPPL-1.3-or-later，页首修订日期为 2011-11-08，正文记录了 2015-09-21 的格式变更，文件未给数字版本。可按完整文件摘要区分历史版本。[作者项目页存档](https://arquivo.pt/noFrame/replay/20200308035750id_/http://milde.users.sourceforge.net/LUCR/Math/)

| 比对 | 结果 |
|---|---|
| 作者网址的 2015 年快照与 latex2mathml 在 2016 年首次引入的数据 | 215899 字节全部相同。 |
| Internet Archive 2018 年快照、Arquivo.pt 2020 年快照及供应方 2020 年更新 | 216332 字节全部相同，SHA256 为 `ed310b43f2b4e5cae8b53fce7443e429d4e826c01f90c59d709af07e6806c3a9`。供应方历史中的 152 行增加、149 行删除属于同步作者数据。 |
| 上述原表与 latex2mathml 3.81.1 的 wheel、sdist 和固定标签 | 2021-06-20 的变更在 U+00A7 的命令字段插入两字节 `\S`。撤销这处插入后完整摘要恢复。原作者日期和声明原样保留。 |

两个档案馆分别保存原作者网址的响应。采集器使用固定的完整摘要离线复核，并将出处和单行修改说明纳入许可索引。[2015 年抓取](https://web.archive.org/web/20150113064243id_/http://milde.users.sourceforge.net/LUCR/Math/data/unimathsymbols.txt) · [2018 年抓取](https://web.archive.org/web/20180314032527id_/http://milde.users.sourceforge.net/LUCR/Math/data/unimathsymbols.txt) · [2020 年独立抓取](https://arquivo.pt/noFrame/replay/20200308035800id_/http://milde.users.sourceforge.net/LUCR/Math/data/unimathsymbols.txt) · [供应方的单行修改](https://github.com/roniemartinez/latex2mathml/commit/ecef40e0519ee477f660d44e217c325a0cc552e7)

## 普通测试安装器

在 [基础安装器](https://github.com/surface-user/StudyWorkbench/pull/110) 中核到七个冻结 latex2mathml 模块，已盘点的后端文件与内嵌模块不含符号表数据文件。实际随包许可 ZIP 已有 MIT 和 LPPL 两份完整原文、作者、日期和数据供应方修改过的标记。新增的历史来源与具体修改说明已进入本次复建的许可 ZIP。其余 54 个包、全部 121 份原文及 134 条原文引用保持字节或记录相同。旧测试安装器维持原构建状态。

原作者项目页提供其他资料，当前证据可以固定符号表本身，未取得界定完整 LPPL Work 的权威文件清单。若以后随产品分发修改表或衍生物，还须依据实际载荷核对作品范围、原作获取途径、修改通知和支持责任。当前材料不足以得出已获再分发许可的结论。[LPPL 1.3c 原文及第 2、6、7 条](https://www.latex-project.org/lppl/lppl-1-3c/)

## 自动验证

```shell
python -m pytest -q backend/tests/test_source_licenses.py backend/tests/test_frozen_member_licenses.py backend/tests/test_staged_python_licenses.py
python -m ruff check backend tools
python tools/export_question_schema.py --check
python tools/frozen_member_licenses.py --payload <实际冻结后端> --source . --output <新的本机归档>
python tools/frozen_member_licenses.py --payload <实际冻结后端> --verify-bundle <新的本机归档> --sha256 <预核摘要>
```

Python 3.12.7 和 3.13.17 各通过 95 项。Ruff、Schema、普通许可归档收集和独立校验退出 0。四项新增回归覆盖原表摘要、原表长度、重复或缺失修改行。首次使用另一构建环境时三项安装包版本与证明不符，收集器拒收，核对全部 55 项构建包后从匹配环境复建成功。完整档案馆响应、逐字节差异、安装器和归档留在本机。
