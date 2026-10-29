$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskCache = Join-Path $taskRoot '.local/release-tools'
New-Item -ItemType Directory -Force -Path $taskCache | Out-Null
$env:TEMP = Join-Path $taskRoot '.local/tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

function Get-VerifiedTool($Name, $Url, $Hash) {
    $path = Join-Path $taskCache $Name
    if (-not (Test-Path -LiteralPath $path)) { Invoke-WebRequest -Uri $Url -OutFile $path }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $Hash) {
        throw "Hash mismatch: $Name. Preserve the file and review an official version before updating this pin."
    }
    return $path
}

$pythonArchive = Get-VerifiedTool 'python.3.13.17.zip' 'https://api.nuget.org/v3-flatcontainer/python/3.13.17/python.3.13.17.nupkg' 'DCE409744B088F94C6E37BA41F8100C384C27E029E843237364C602D30D475E5'
$innoInstaller = Get-VerifiedTool 'innosetup-7.1.0-x64.exe' 'https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe' '0362A383ED217D4C4239B5933866DD96D3EB2102737DA92F80F6057A4B40DF2F'
$webviewInstaller = Get-VerifiedTool 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe' 'https://go.microsoft.com/fwlink/?linkid=2124701' '9B0142E22E8DAA92855D746AE4D1E9EEEF561CCAF67D1DD452165C4AF3DF3191'
$jsonLicense = Get-VerifiedTool 'nlohmann-json-3.11.2-LICENSE.MIT' 'https://raw.githubusercontent.com/nlohmann/json/v3.11.2/LICENSE.MIT' '86B998C792894CCB911A1CB7994F7A9652894E7A094C0B5E45BE2F553F45CF14'
$pythonHome = Join-Path $taskCache 'cpython31317'
if (-not (Test-Path -LiteralPath "$pythonHome/tools/python.exe")) { Expand-Archive -LiteralPath $pythonArchive -DestinationPath $pythonHome }
foreach ($tool in @(@("$pythonHome/tools/python.exe", 'Python Software Foundation'), @($innoInstaller, 'Pyrsys B.V.'), @($webviewInstaller, 'Microsoft Corporation'))) {
    $signature = Get-AuthenticodeSignature -LiteralPath $tool[0]
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch [regex]::Escape($tool[1])) { throw "Signature invalid: $($tool[0])" }
}
$innoHome = Join-Path $taskCache 'inno7'
if (-not (Test-Path -LiteralPath "$innoHome/ISCC.exe")) {
    # Official portable mode avoids registry entries, file associations and shortcuts.
    $installer = Start-Process -FilePath $innoInstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CURRENTUSER', '/NOICONS', '/PORTABLE=1', "/DIR=`"$innoHome`"") -WindowStyle Hidden -Wait -PassThru
    if ($installer.ExitCode -ne 0) { throw "Portable Inno installation failed: $($installer.ExitCode)" }
}
Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath '.local/release-venv/Scripts/python.exe')) {
        & "$pythonHome/tools/python.exe" -m venv .local/release-venv
        if ($LASTEXITCODE -ne 0) { throw 'Release venv failed' }
    }
    & .local/release-venv/Scripts/python.exe -m pip install --disable-pip-version-check -r backend/requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Release dependencies failed' }
} finally { Pop-Location }
Write-Output 'Verified project-local CPython, Inno portable compiler, pinned signed WebView Runtime, and release environment.'
