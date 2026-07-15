param(
    [string]$SkillDestination = (Join-Path $HOME ".codex\skills")
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.12-3.14 first."
}

if (-not (Test-Path $Python)) {
    py -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python (Join-Path $Root "mcp\doctor.py")

$SkillSource = Join-Path $Root "skills\count-engineering-drawing-symbols"
$SkillTarget = Join-Path $SkillDestination "count-engineering-drawing-symbols"
New-Item -ItemType Directory -Force -Path $SkillDestination | Out-Null
New-Item -ItemType Directory -Force -Path $SkillTarget | Out-Null
Copy-Item (Join-Path $SkillSource "*") $SkillTarget -Recurse -Force

$EscapedPython = $Python.Replace("\", "\\")
$EscapedServer = (Join-Path $Root "mcp\server.py").Replace("\", "\\")
$Snippet = @"
[mcp_servers.drawing-estimate-reader]
command = "$EscapedPython"
args = ["$EscapedServer"]
startup_timeout_sec = 30
tool_timeout_sec = 300
"@

$SnippetPath = Join-Path $Root "codex-mcp-config.toml"
Set-Content -Path $SnippetPath -Value $Snippet -Encoding UTF8

Write-Host "Installed skill: $SkillTarget"
Write-Host "MCP config snippet: $SnippetPath"
Write-Host "Add the snippet to $HOME\.codex\config.toml, then restart the AI Agent."
