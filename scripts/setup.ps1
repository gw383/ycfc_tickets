# One-time setup on Windows, for running or changing the checker on your own PC.
# (The every-5-minutes checks run on GitHub and don't need any of this.)
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    py -3 -m venv venv
}

Write-Host "Installing package..."
& venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& venv\Scripts\python.exe -m pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - open it and set NTFY_TOPIC."
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. Edit .env (set NTFY_TOPIC)"
Write-Host "  2. venv\Scripts\python -m ycfc_tickets --test-alert"
Write-Host "  3. venv\Scripts\python -m ycfc_tickets --dry-run"
