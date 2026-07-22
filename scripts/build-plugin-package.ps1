param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
$ReleaseRoot = Join-Path $Root "release"
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $ReleaseRoot "plugin-marketplace"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
if (-not $OutputRoot.StartsWith($ReleaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must stay inside $ReleaseRoot"
}

$PluginName = "engineering-drawing-estimator"
$PluginRoot = Join-Path $OutputRoot "plugins\$PluginName"
$MarketplaceDirectory = Join-Path $OutputRoot ".agents\plugins"
$MarketplacePath = Join-Path $MarketplaceDirectory "marketplace.json"
$ZipPath = Join-Path $ReleaseRoot "$PluginName-plugin-v$Version.zip"

if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $PluginRoot, $MarketplaceDirectory | Out-Null

foreach ($Directory in @(".codex-plugin", "mcp", "skills")) {
    $SourceDirectory = Join-Path $Root $Directory
    $DestinationDirectory = Join-Path $PluginRoot $Directory
    New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
    foreach ($SourceItem in Get-ChildItem -LiteralPath $SourceDirectory -Force) {
        Copy-Item -LiteralPath $SourceItem.FullName `
            -Destination $DestinationDirectory -Recurse -Force
    }
}
foreach ($File in @(
    ".mcp.json",
    "plugin-mcp.ps1",
    "requirements-mcp.txt",
    "LICENSE",
    "README.md",
    "VERSION"
)) {
    Copy-Item -LiteralPath (Join-Path $Root $File) -Destination $PluginRoot -Force
}

Get-ChildItem -LiteralPath $PluginRoot -Directory -Recurse -Force |
    Where-Object { $_.Name -eq "__pycache__" } |
    Sort-Object FullName -Descending |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $PluginRoot -File -Recurse -Force |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force

foreach ($RequiredPath in @(
    ".codex-plugin\plugin.json",
    "skills\count-engineering-drawing-symbols\SKILL.md",
    "mcp\server.py",
    ".mcp.json",
    "plugin-mcp.ps1"
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $PluginRoot $RequiredPath) -PathType Leaf)) {
        throw "Plugin package is missing required file: $RequiredPath"
    }
}

$Marketplace = [ordered]@{
    name = $PluginName
    interface = [ordered]@{
        displayName = "AI Engineering Drawing Estimator"
    }
    plugins = @(
        [ordered]@{
            name = $PluginName
            source = [ordered]@{
                source = "local"
                path = "./plugins/$PluginName"
            }
            policy = [ordered]@{
                installation = "AVAILABLE"
                authentication = "ON_INSTALL"
            }
            category = "Productivity"
        }
    )
}
$Marketplace | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $MarketplacePath -Encoding UTF8

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $OutputRoot -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Output ([ordered]@{
    version = $Version
    plugin_root = $PluginRoot
    marketplace_json = $MarketplacePath
    zip_path = $ZipPath
} | ConvertTo-Json -Depth 4)
