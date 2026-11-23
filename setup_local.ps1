$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$pythonExe = Join-Path $venv "Scripts\python.exe"
$pipExe = Join-Path $venv "Scripts\pip.exe"
if (-not (Test-Path $pythonExe) -or -not (Test-Path $pipExe)) {
    $venv = Join-Path $root ".venv-supportfusion"
    $pythonExe = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) { python -m venv $venv }
}
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $root "requirements.txt")
if (-not (Test-Path (Join-Path $root ".env"))) { Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env") }
& $pythonExe -c "from backend.app.db import init_db; init_db(); print('SQLite schema ready')"
Write-Host "SupportFusion AI local environment is ready."

