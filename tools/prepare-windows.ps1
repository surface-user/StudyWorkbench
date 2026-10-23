# Project-local fallback when Developer Mode is unavailable. No machine settings are changed.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$desktop = Join-Path $taskRoot 'apps/desktop'
# Use process-local writable scratch paths; do not alter machine/user environment settings.
$taskTemp = Join-Path $taskRoot '.local/tmp'
New-Item -ItemType Directory -Force $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:NUGET_SCRATCH = Join-Path $taskRoot '.local/nuget-scratch'
$metadata = Get-Content (Join-Path $desktop '.flutter-plugins-dependencies') -Raw | ConvertFrom-Json
$links = Join-Path $desktop 'windows/flutter/ephemeral/.plugin_symlinks'
New-Item -ItemType Directory -Force $links | Out-Null
foreach ($plugin in $metadata.plugins.windows) {
    $target = Join-Path $links $plugin.name
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Junction -Path $target -Target $plugin.path | Out-Null
    }
}
$bin = Join-Path $taskRoot '.local/bin'
New-Item -ItemType Directory -Force $bin | Out-Null
if (-not (Test-Path (Join-Path $bin 'nuget.exe'))) {
    Invoke-WebRequest 'https://dist.nuget.org/win-x86-commandline/v6.14.0/nuget.exe' -OutFile (Join-Path $bin 'nuget.exe')
}
$signature = Get-AuthenticodeSignature (Join-Path $bin 'nuget.exe')
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw 'NuGet signature validation failed'
}
Write-Output 'Prepared junctions, signed NuGet, and process-local TEMP/NUGET_SCRATCH. Add .local/bin to PATH for this build session.'
