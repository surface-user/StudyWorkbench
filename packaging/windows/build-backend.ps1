$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $taskRoot
try {
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --name study_backend --paths backend --collect-submodules study_workbench --add-data 'backend/migrations;migrations' --add-data 'backend/study_workbench/player.html;study_workbench' tools/frozen_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
} finally { Pop-Location }
