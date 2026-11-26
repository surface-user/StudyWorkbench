param(
    [Parameter(Mandatory)][string]$BackendDirectory,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedFileSha256,
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSignerSha256
)
& (Join-Path $PSScriptRoot 'verify-release-signature.ps1') -Artifact Backend -Directory $BackendDirectory `
    -ExpectedFileSha256 $ExpectedFileSha256 -ExpectedSignerSha256 $ExpectedSignerSha256
