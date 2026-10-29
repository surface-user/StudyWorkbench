param(
    [string]$Iscc = '.local/release-tools/inno7/ISCC.exe',
    [string]$CrtDirectory = 'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Redist/MSVC/14.44.35112/x64/Microsoft.VC143.CRT',
    [string]$WebViewInstaller = '.local/release-tools/MicrosoftEdgeWebView2RuntimeInstallerX64.exe',
    [string]$OfficeRuntime = ''
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $taskRoot
try {
    $compiler = (Resolve-Path -LiteralPath $Iscc).Path
    $appVersion = ((Select-String -LiteralPath 'apps/desktop/pubspec.yaml' -Pattern '^version:\s*(\S+)').Matches[0].Groups[1].Value -split '\+')[0]
    $runtime = (Resolve-Path -LiteralPath $WebViewInstaller).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $runtime
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'WebView Runtime signature invalid' }
    . ./tools/prepare-windows.ps1
    $env:PATH = "$taskRoot/.local/bin;" + $env:PATH
    Push-Location apps/desktop
    try {
        flutter build windows --release --no-pub
        if ($LASTEXITCODE -ne 0) { throw 'Flutter release failed' }
    } finally { Pop-Location }
    & ./packaging/windows/build-backend.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Backend build failed' }
    $previewBackend = Join-Path $taskRoot 'apps/desktop/build/windows/x64/runner/Release/backend'
    if (Test-Path -LiteralPath $previewBackend) {
        $resolvedBackend = (Resolve-Path -LiteralPath $previewBackend).Path
        $preservedBackend = Join-Path $taskRoot ('.local/previous-release-backend-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        if (-not $resolvedBackend.StartsWith($taskRoot + '\') -or -not $preservedBackend.StartsWith($taskRoot + '\')) { throw 'Unsafe preview backend path' }
        Move-Item -LiteralPath $resolvedBackend -Destination $preservedBackend
    }
    Copy-Item -LiteralPath 'dist/study_backend' -Destination $previewBackend -Recurse
    $stage = Join-Path $taskRoot ('dist/StudyWorkbench-M1-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    # Copy into a new staging directory. Never remove or reuse a user's install/data directory.
    Get-ChildItem -LiteralPath 'apps/desktop/build/windows/x64/runner/Release' | Where-Object Name -ne 'backend' | Copy-Item -Destination $stage -Recurse
    if (Test-Path -LiteralPath "$stage/backend") { throw 'Release output contains a stale backend; build in a clean output directory' }
    Copy-Item -LiteralPath 'dist/study_backend' -Destination "$stage/backend" -Recurse
    foreach ($dll in Get-ChildItem -LiteralPath $CrtDirectory -Filter '*.dll') {
        $crtSignature = Get-AuthenticodeSignature -LiteralPath $dll.FullName
        if ($crtSignature.Status -ne 'Valid') { throw "Invalid CRT signature: $($dll.Name)" }
        Copy-Item -LiteralPath $dll.FullName -Destination $stage
    }
    if ($OfficeRuntime) {
        & .local/release-venv/Scripts/python.exe tools/stage_office_runtime.py --runtime $OfficeRuntime --stage $stage
        if ($LASTEXITCODE -ne 0) { throw 'Office runtime staging failed; incomplete stage preserved' }
    }
    & .local/release-venv/Scripts/python.exe tools/release_inventory.py --stage $stage
    if ($LASTEXITCODE -ne 0) { throw 'Inventory failed' }
    & $compiler "--define=BuildRoot=$stage" "--define=WebViewInstaller=$runtime" "--define=AppVersion=$appVersion" packaging/windows/setup.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
    Get-FileHash -LiteralPath 'dist/StudyWorkbench-M1-setup.exe' -Algorithm SHA256
    Write-Output "Staging directory: $stage"
} finally { Pop-Location }
