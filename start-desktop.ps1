$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Desktop runtime was not found. Run .\install.ps1 first."
}

& $Python (Join-Path $Root "desktop\app.py")
