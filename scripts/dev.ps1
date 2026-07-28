$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run scripts\bootstrap.ps1 first."
}

.venv\Scripts\python -m semester_ops.web.main
