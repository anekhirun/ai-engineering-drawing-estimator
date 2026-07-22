# Installing TakeoffLens

TakeoffLens v0.2.1 is distributed as a local Codex Plugin for Windows. The
archive contains the Skill, MCP server, runtime launcher, templates, and public
documentation.

## Requirements

- Windows 10 or later
- PowerShell 5.1 or later
- Python 3.12-3.14
- Codex with local Plugin and MCP support
- Internet access during the first managed-runtime launch

## Option 1: Install the release Plugin

1. Open the [latest release](https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/latest).
2. Download:
   - `takeoff-lens-plugin-v0.2.1.zip`
   - `takeoff-lens-plugin-v0.2.1.zip.sha256`
3. Verify the ZIP in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\takeoff-lens-plugin-v0.2.1.zip
```

4. Extract the ZIP. It contains this structure:

```text
plugin-marketplace/
  .agents/plugins/marketplace.json
  plugins/takeoff-lens/
```

5. Add the extracted marketplace and install the Plugin:

```powershell
codex plugin marketplace add "C:\path\to\plugin-marketplace"
codex plugin add takeoff-lens@takeoff-lens
```

6. Start a new Codex task. Plugin skills and MCP tools are discovered at the new
   task boundary.

On first use, `plugin-mcp.ps1` creates a private runtime under
`%LOCALAPPDATA%\TakeoffLens\plugin-data` and installs `requirements-mcp.txt`.

## Option 2: Use an existing Python environment

Set `TAKEOFFLENS_PYTHON` to a compatible Python executable that already contains
the packages in `requirements-mcp.txt`:

```powershell
$env:TAKEOFFLENS_PYTHON = "C:\path\to\python.exe"
```

The launcher then skips environment creation and dependency installation. The
legacy `ENGINEERING_DRAWING_ESTIMATOR_PYTHON` variable remains accepted during
migration, but new installations should use `TAKEOFFLENS_PYTHON`.

## Option 3: Manual source installation

Clone the repository and run the installer:

```powershell
git clone https://github.com/anekhirun/Takeoff-Lens-Plugin.git
Set-Location .\Takeoff-Lens-Plugin
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

The installer creates `.venv`, installs the full requirements, runs the MCP
doctor, copies the Skill, and writes `codex-mcp-config.toml`.

Add the generated MCP block to `%USERPROFILE%\.codex\config.toml`, then restart
the agent and start a new task.

## Generic MCP client configuration

TakeoffLens currently exposes a local stdio MCP server. After installing
`requirements-mcp.txt`, configure an MCP client to run:

```text
command: C:\path\to\python.exe
args:    C:\path\to\Takeoff-Lens-Plugin\mcp\server.py
```

Example configuration shape for clients that use YAML:

```yaml
mcp_servers:
  takeoff_lens:
    command: "C:\\path\\to\\python.exe"
    args:
      - "C:\\path\\to\\Takeoff-Lens-Plugin\\mcp\\server.py"
```

Other MCP clients may use the same local stdio shape.

## Hermes Desktop setup

Hermes Desktop requires the Skill and MCP registration separately. In a new
Hermes session, install the versioned Skill:

```text
/skills install https://raw.githubusercontent.com/anekhirun/Takeoff-Lens-Plugin/v0.2.1/skills/count-engineering-drawing-symbols/SKILL.md --now
```

Then open **Capabilities > MCP > Servers** and add `takeoff-lens` to the
existing `mcp.json`. Keep any servers already present:

```json
{
  "mcpServers": {
    "takeoff-lens": {
      "command": "C:\\path\\to\\Takeoff-Lens-Plugin\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\Takeoff-Lens-Plugin\\mcp\\server.py"
      ]
    }
  }
}
```

Click **Save**, then **Reload MCP**. The server should report ten enabled tools.
Start a new session and ask:

```text
Use the count-engineering-drawing-symbols skill and TakeoffLens.
Show the active and planned discipline catalog.
```

The Hermes **Settings > Plugins** pane is for Desktop UI extensions. It does
not install this Agent Skill or MCP server automatically.

## Upgrade from the legacy Plugin

The legacy Plugin IDs are:

- `drawing-estimate-reader`
- `engineering-drawing-estimator`

Install and test `takeoff-lens` first. Confirm that `mcp/doctor.py` reports
TakeoffLens v0.2.1 and ten tools, then uninstall the legacy Plugin through the
Codex Plugins UI.

For manual configurations, keep only this MCP registration:

```toml
[mcp_servers.takeoff-lens]
```

Remove legacy MCP blocks so the agent does not discover duplicate tools.
Project PDFs and exported reports are separate from the Plugin cache and should
not be removed during migration.

## Verify the installation

From a source checkout or extracted Plugin root with a compatible environment:

```powershell
.\.venv\Scripts\python.exe .\mcp\doctor.py
```

Expected identity:

```text
version: 0.2.1
server_name: takeoff-lens
tool count: 10
```

Then start a new task and ask:

```text
Use TakeoffLens to show the active and planned discipline catalog.
```

## Troubleshooting

### Python was not found

Install Python 3.12-3.14, restart Codex, or set `TAKEOFFLENS_PYTHON` to a
compatible executable.

### First startup takes longer than expected

The managed launcher may be creating a virtual environment and installing
binary packages. Later launches reuse the dependency hash.

### Tools do not appear

- confirm the Plugin is installed and enabled;
- start a new task after installation;
- verify that only one TakeoffLens or legacy MCP registration exists;
- run the doctor with the same Python environment used by the launcher.

### Raster drawing returns no automatic candidates

This is expected in v0.2.x. Render the page at high resolution and use visual
review. The bundled matcher is designed primarily for vector and hybrid PDFs.
