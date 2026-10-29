param([string]$Python = '.local/release-venv/Scripts/python.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $taskRoot
try {
    $env:TEMP = Join-Path $taskRoot '.local/tmp'
    $env:TMP = $env:TEMP
    & $Python -c 'import sys; assert "Anaconda" not in sys.version and "conda" not in sys.base_prefix.lower(), "Release requires independent CPython"'
    if ($LASTEXITCODE -ne 0) { throw 'Invalid release interpreter' }
    & $Python -m PyInstaller --noconfirm --onedir --name study_backend --paths backend --collect-submodules study_workbench --copy-metadata docling-slim --copy-metadata docling-core --copy-metadata doclang --copy-metadata pypdfium2 --copy-metadata python-docx --copy-metadata pylatexenc --add-data 'backend/migrations;migrations' --add-data 'backend/study_workbench/player.html;study_workbench' --add-data 'backend/study_workbench/library_player.html;study_workbench' tools/frozen_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
} finally { Pop-Location }
