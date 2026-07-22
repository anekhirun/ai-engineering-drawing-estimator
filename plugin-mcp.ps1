param()

$ErrorActionPreference = "Stop"
$PluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Requirements = Join-Path $PluginRoot "requirements-mcp.txt"
$Server = Join-Path $PluginRoot "mcp\server.py"

function Invoke-SetupCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $Messages = & $Command @Arguments 2>&1
    $ExitCode = $LASTEXITCODE
    foreach ($Message in $Messages) {
        [Console]::Error.WriteLine([string]$Message)
    }
    return $ExitCode
}

if ($env:PLUGIN_DATA) {
    $RuntimeRoot = $env:PLUGIN_DATA
} elseif ($env:LOCALAPPDATA) {
    $RuntimeRoot = Join-Path $env:LOCALAPPDATA "EngineeringDrawingEstimator\plugin-data"
} else {
    $RuntimeRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "EngineeringDrawingEstimator\plugin-data"
}

$ManagedRuntime = -not $env:ENGINEERING_DRAWING_ESTIMATOR_PYTHON
if ($ManagedRuntime) {
    $Venv = Join-Path $RuntimeRoot "venv"
    $Python = Join-Path $Venv "Scripts\python.exe"
    $DependencyMarker = Join-Path $RuntimeRoot "requirements.sha256"
    $RequirementsHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Requirements).Hash
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

    if (-not (Test-Path -LiteralPath $Python)) {
        $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($PyLauncher) {
            $SetupExitCode = Invoke-SetupCommand $PyLauncher.Source @("-3", "-m", "venv", $Venv)
        } else {
            $SystemPython = Get-Command python -ErrorAction SilentlyContinue
            if (-not $SystemPython) {
                throw "Python 3 was not found. Install Python 3.12-3.14 and restart the plugin."
            }
            $SetupExitCode = Invoke-SetupCommand $SystemPython.Source @("-m", "venv", $Venv)
        }
        if ($SetupExitCode -ne 0) {
            throw "Could not create the plugin Python environment."
        }
    }

    $InstalledHash = if (Test-Path -LiteralPath $DependencyMarker) {
        (Get-Content -LiteralPath $DependencyMarker -Raw).Trim()
    } else {
        ""
    }
    if ($InstalledHash -ne $RequirementsHash) {
        $SetupExitCode = Invoke-SetupCommand $Python @(
            "-m", "pip", "install", "--disable-pip-version-check", "-r", $Requirements
        )
        if ($SetupExitCode -ne 0) {
            throw "Could not install the local MCP dependencies."
        }
        Set-Content -LiteralPath $DependencyMarker -Value $RequirementsHash -Encoding ASCII
    }
} else {
    $Python = [System.IO.Path]::GetFullPath($env:ENGINEERING_DRAWING_ESTIMATOR_PYTHON)
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "ENGINEERING_DRAWING_ESTIMATOR_PYTHON does not point to a Python executable."
    }
}

& $Python $Server
exit $LASTEXITCODE
