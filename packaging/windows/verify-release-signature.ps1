param(
    [Parameter(Mandatory)][ValidateSet('Backend', 'Installer')][string]$Artifact,
    [Parameter(Mandatory)][string]$Directory,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedFileSha256,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSignerSha256
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1')
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1')
$name = if ($Artifact -eq 'Installer') { 'StudyWorkbench-M1-setup.exe' } else { 'study_backend.exe' }
$role = $Artifact.ToLowerInvariant()
$directoryItem = Get-Item -LiteralPath $Directory -Force
if ($directoryItem -isnot [IO.DirectoryInfo] -or $directoryItem.FullName -notmatch '^[A-Za-z]:\\') {
    throw "Expected a local $role directory."
}
$file = Get-Item -LiteralPath (Join-Path $directoryItem.FullName $name) -Force
if ($file -isnot [IO.FileInfo]) { throw "Expected a $role executable file." }
for ($entry = $directoryItem; $null -ne $entry; $entry = $entry.Parent) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked $role directory." }
}
if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked $role executable." }

# Hold the same bytes against replacement or writes during Windows trust verification.
$stream = [IO.File]::Open($file.FullName, 'Open', 'Read', 'Read')
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $digest = [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '')
    if ($digest -ne $ExpectedFileSha256) { throw "$role file SHA256 mismatch." }
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or $signature.SignatureType -ne 'Authenticode') {
        throw "Valid embedded $role signature required. Windows status $($signature.Status)."
    }
    $signer = $signature.SignerCertificate
    $timestamp = $signature.TimeStamperCertificate
    if ($null -eq $signer -or $null -eq $timestamp) { throw 'Signer and timestamp certificates required.' }
    $signerHash = [BitConverter]::ToString($sha256.ComputeHash($signer.RawData)).Replace('-', '')
    if ($signerHash -ne $ExpectedSignerSha256) { throw "$role signer certificate SHA256 mismatch." }
    [ordered]@{
        file = $name
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
