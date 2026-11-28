# REL-03h 可选 Office 安装包与上游安全公告

2026-11-28，准备的 Windows x64 LibreOffice 为 26.8.1.1。官方 19 条公告将 26.8.2 列为同一维护线的修复版本。当前可选整包的发行阻断保留。独立审查按本轮要求暂缓，人工测试已取消。[官方安全公告](https://www.libreoffice.org/security/)

## 归属与对照结果

- MSI 内部 ProductVersion 和准备目录的 `program/soffice.exe` 文件版本均为 26.8.1.1。MSI 模板平台为 x64，大小 374870016 字节，Windows 签名状态 Valid，发布者 The Document Foundation。安装包 SHA-256 为 `c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312`，同时匹配固定来源记录与官方历史归档。准备目录的 `program/version.ini` 与该包对应的本地锁一致，记录构建 `bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`，与上游 26.8.1.1 源码标签指向的提交一致。[源码标签](https://github.com/LibreOffice/core/tree/libreoffice-26.8.1.1) · [官方归档校验](https://downloadarchive.documentfoundation.org/libreoffice/old/26.8.1.1/win/x86_64/LibreOffice_26.8.1.1_Win_x86-64.msi.sha256)
- 本次供应商英文索引快照 SHA-256 为 `0b00e0ec036fa23dcf5bc3b88c97e92dc668852522c508f5b966b9b6b2165c22`。125 条公告中，29 条在自身的修复版本字段明确列出 26.8 系列。其余 96 条未凭其他维护线版本推定本系列状态。较早的历史公告、产品依赖和索引以外的漏洞覆盖均不能凭此核对结论排除。[官方索引](https://www.libreoffice.org/security/)

| 同线修复版本 | 条数 | 与准备包的关系 |
|---|---:|---|
| 26.8.0 | 6 | 已达到官方所列版本 |
| 26.8.1 | 4 | 已达到官方所列版本 |
| 26.8.2 | 19 | 准备包早于修复点 |

在 19 条中，CVE-2026-100101 描述 Unix 平台的邮件脚本，超出本 Windows 包的平台范围。CVE-2026-104933 取决于是否使用 GStreamer，当前检查没有证明此运行条件。其余 17 条保留为版本命中，涉及图像、字体、PDF、文档和数据库处理等功能。当前应用路径的可达性和严重性没有实测。企业签名有效、输入过滤或属于可选组件均不能替代版本修复。[邮件脚本](https://www.libreoffice.org/security/#cve-2026-100101) · [媒体后端条件](https://www.libreoffice.org/security/#cve-2026-104933)

## 可复核步骤

在 Windows PowerShell 7 中，`$msi` 指向待核 MSI，`$office` 指向其准备目录，`$catalog` 指向从官方安全公告索引保存的英文 HTML，`$checksum` 指向上述官方归档 SHA-256 文本。下面只读核对本地文件，并按每条公告自身的修复字段比较。运行时输出包含 CVE 编号，原始索引、本机锁和逐文件记录仅存本机。

```powershell
$ErrorActionPreference = 'Stop'
$wi = New-Object -ComObject WindowsInstaller.Installer
$db = $wi.OpenDatabase((Resolve-Path $msi).Path, 0)
$q = $db.OpenView('SELECT `Value` FROM `Property` WHERE `Property` = ''ProductVersion''')
$q.Execute()
$version = [version]$q.Fetch().StringData(1)
$platform = ($db.SummaryInformation(0).Property(7) -split ';')[0]
$sig = Get-AuthenticodeSignature -LiteralPath $msi
$hash = (Get-FileHash -LiteralPath $msi).Hash
$upstreamHash = ((Get-Content -LiteralPath $checksum -Raw).Trim() -split '\s+')[0]
$lock = Get-Content (Join-Path $office 'runtime-lock.json') -Raw | ConvertFrom-Json -AsHashtable
$versionFile = Join-Path $office 'program/version.ini'
$exe = Get-Item (Join-Path $office 'program/soffice.exe')
if ($hash -ne $upstreamHash -or $hash -ne $lock.package_sha256 -or
    $version -ne [version]$exe.VersionInfo.FileVersion -or $platform -ne 'x64' -or
    $sig.Status -ne 'Valid' -or $sig.SignerCertificate.GetNameInfo('SimpleName', $false) -ne 'The Document Foundation' -or
    (Get-FileHash $versionFile).Hash -ne $lock.files['program/version.ini'] -or
    (Get-FileHash $exe.FullName).Hash -ne $lock.files['program/soffice.exe']) { throw 'Package identity mismatch' }
"$version $platform $hash"
Get-Content $versionFile | Select-String '^buildid='
(Get-FileHash -LiteralPath $catalog).Hash
$html = Get-Content -LiteralPath $catalog -Raw
$entries = [regex]::Matches($html, '(?is)<details\s+id="([^"]+)"[^>]*>(.*?)</details>')
if (!$entries.Count -or $entries.Count -ne [regex]::Matches($html, '(?i)<details\b').Count) {
    throw 'Check vendor index structure before comparing'
}
$series = [regex]::Escape("$($version.Major).$($version.Minor)")
$rows = foreach ($entry in $entries) {
    $field = [regex]::Match($entry.Groups[2].Value, '(?i)<strong>Fixed in</strong>:\s*LibreOffice ([^<]+)')
    $same = [regex]::Match($field.Groups[1].Value, "(?<![\d.])$series\.\d+(?:\.\d+)?(?![\d.])")
    $state = 'unknown'
    if ($same.Success) {
        $state = if ($version -lt [version]$same.Value) { 'before-fix' } else { 'at-or-after-fix' }
    }
    [pscustomobject]@{ Id = $entry.Groups[1].Value; Fixed = $same.Value; State = $state }
}
if (!($rows | Where-Object Fixed)) { throw 'No same-series fields found' }
$rows | Group-Object State, Fixed | Select-Object Count, Name
$rows | Where-Object State -eq 'before-fix' | Select-Object -ExpandProperty Id
```

以上命令对官方索引和实际 MSI 执行，退出 0。替换为错误的校验摘要后退出 1。待整包改用达到上游修复版本的可验证 Windows 构建后，需要重新核对组件来源、公告和转换回归，再更新发行阻断。
