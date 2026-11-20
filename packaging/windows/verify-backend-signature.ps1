param(
    [Parameter(Mandatory)][string]$BackendDirectory,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedFileSha256,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSignerSha256
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1')
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1')
$directory = Get-Item -LiteralPath $BackendDirectory -Force
if ($directory -isnot [IO.DirectoryInfo] -or $directory.FullName -notmatch '^[A-Za-z]:\\') {
    throw 'Expected a local backend directory.'
}
$file = Get-Item -LiteralPath (Join-Path $directory.FullName 'study_backend.exe') -Force
if ($file -isnot [IO.FileInfo]) { throw 'Expected a backend executable file.' }
for ($entry = $directory; $null -ne $entry; $entry = $entry.Parent) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked backend directory.' }
}
if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked backend executable.' }

# Hold the same bytes against replacement or writes during Windows trust verification.
$stream = [IO.File]::Open($file.FullName, 'Open', 'Read', 'Read')
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $digest = [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '')
    if ($digest -ne $ExpectedFileSha256) { throw 'Backend file SHA256 mismatch.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or $signature.SignatureType -ne 'Authenticode') {
        throw "Valid embedded backend signature required. Windows status $($signature.Status)."
    }
    $signer = $signature.SignerCertificate
    $timestamp = $signature.TimeStamperCertificate
    if ($null -eq $signer -or $null -eq $timestamp) { throw 'Signer and timestamp certificates required.' }
    $signerHash = [BitConverter]::ToString($sha256.ComputeHash($signer.RawData)).Replace('-', '')
    if ($signerHash -ne $ExpectedSignerSha256) { throw 'Backend signer certificate SHA256 mismatch.' }
    [ordered]@{
        file = 'study_backend.exe'
        file_sha256 = $digest
        signer_certificate_sha256 = $signerHash
        timestamp_certificate_sha256 = [BitConverter]::ToString($sha256.ComputeHash($timestamp.RawData)).Replace('-', '')
        signature_type = $signature.SignatureType.ToString()
        windows_status = $signature.Status.ToString()
    } | ConvertTo-Json -Compress
} finally {
    $sha256.Dispose()
    $stream.Dispose()
}
