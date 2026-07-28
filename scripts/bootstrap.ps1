$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -m venv .venv
}

.venv\Scripts\python -m pip install uv
.venv\Scripts\uv sync --locked --extra dev
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
.venv\Scripts\python -m alembic upgrade head

Write-Host "Semester Ops is ready. Run scripts\dev.ps1 to start it."
