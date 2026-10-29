param([Parameter(Mandatory=$true)][string]$Package, [Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$msi = (Resolve-Path -LiteralPath $Package).Path
$candidate = if ([IO.Path]::IsPathRooted($Destination)) { $Destination } else { Join-Path $taskRoot $Destination }
$target = [IO.Path]::GetFullPath($candidate).TrimEnd('\')
if (-not $target.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Extraction must stay in project' }
if (Test-Path -LiteralPath $target) { throw 'Destination already exists; no replacement allowed' }
if ((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ne 'C6298B10CFA1748BCBEDAD94C62CE771E240E5021BFD6D7A967CD571B04B5312') { throw 'Package hash differs' }
$signature = Get-AuthenticodeSignature -LiteralPath $msi
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'The Document Foundation') { throw 'Package signature invalid' }
# Administrative image only; never register a system installation or file associations.
$process = Start-Process "$env:SystemRoot/System32/msiexec.exe" -ArgumentList @('/a', ('"' + $msi + '"'), '/qn', '/norestart', ('TARGETDIR="' + $target + '"')) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Administrative extraction failed: $($process.ExitCode); partial output retained" }
& "$taskRoot/.local/release-venv/Scripts/python.exe" "$taskRoot/tools/lock_office_runtime.py" --root $target --package $msi
if ($LASTEXITCODE -ne 0) { throw 'Runtime lock failed; extraction retained' }
