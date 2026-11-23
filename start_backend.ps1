$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$venv = Join-Path $root ".venv"
$pythonPath = Join-Path $venv "Scripts\python.exe"
$pipPath = Join-Path $venv "Scripts\pip.exe"
if (-not (Test-Path $pythonPath) -or -not (Test-Path $pipPath)) {
    foreach ($candidateName in @(".venv-supportfusion", ".venv-check")) {
        $candidate = Join-Path $root $candidateName
        if (Test-Path (Join-Path $candidate "Scripts\python.exe")) { $venv = $candidate; break }
    }
}
$pythonPath = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $pythonPath)) { throw "Python environment not found. Run .\setup_local.ps1 first." }
& $pythonPath -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

