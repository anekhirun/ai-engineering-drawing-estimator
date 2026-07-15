# AI Engineering Drawing Estimator v0.1.2

**AI Agent MCP for Symbol Counting and Quantity Takeoff**

An assisted-review MCP server and Agent Skill for counting electrical and communication symbols in engineering PDF drawings with ChatGPT Codex, Hermes, and other MCP-compatible AI agents.

> This is not a fully automatic quantity takeoff system. Every candidate must be reviewed before reporting a final count.

## Supported workflow

- Inspect vector, hybrid, and raster PDF pages.
- Render pages for visual review.
- Detect vector candidates for:
  - Duplex Socket Outlet
  - Single Socket Outlet
  - Data Outlet
- Suppress candidates whose center overlaps PDF text by default.
- Create project-specific symbol templates from a clean legend ROI.
- Export candidate crops, markup, CSV, JSON, and an HTML review page.
- Confirm reviewed candidates and add manually verified points.

No project drawings, customer files, marked-up plans, test outputs, or machine-specific paths are included in this repository.

## Requirements

- Windows
- Python 3.12-3.14
- PowerShell
- An MCP-compatible AI agent such as Codex or Hermes

## Install

Clone or download this repository, then run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

The installer:

1. Creates `.venv` and installs the Python dependencies.
2. Runs the MCP doctor check.
3. Installs the Skill to `~/.codex/skills/count-engineering-drawing-symbols` by default.
4. Generates `codex-mcp-config.toml` with the local MCP command.

Add the generated MCP block to `~/.codex/config.toml`, then restart the agent.

When upgrading from v0.1.1, remove the old `[mcp_servers.drawing-estimate-reader]` block and use the generated `[mcp_servers.engineering-drawing-estimator]` block.

For another agent, register a `stdio` MCP server using:

```text
command: .venv\Scripts\python.exe
args:    mcp\server.py
```

## Agent prompt

```text
Use $count-engineering-drawing-symbols to inspect this PDF.
Count Duplex Socket Outlet, Single Socket Outlet, and Data Outlet by floor.
Create markup and review every candidate before reporting the quantities.
```

## MCP tools

| Tool | Purpose |
|---|---|
| `inspect_drawing` | Classify PDF pages before analysis |
| `render_page` | Render a page for legend and plan review |
| `get_symbol_rules` | Return supported symbol/context rules |
| `build_symbol_template` | Build a project-specific vector template |
| `detect_symbol_candidates` | Generate a high-recall candidate shortlist |
| `confirm_symbol_count` | Export confirmed counts and auditable markup |

## Important review rules

- Treat starter templates as search aids, not universal standards.
- Prefer the legend from the current project.
- Check every wall face, wall corner, and both sides of doors.
- Support rotated symbols at 0, 90, 180, and 270 degrees.
- Use OCR only for text context, never for detecting symbol geometry.
- A nearby `4` can be a circuit number; `C` can identify CCTV.
- A zero result remains provisional until the candidate set and wall/door regions are reviewed.
- Use `manual_points` for visually confirmed misses.

## Limitations

- The bundled matcher is intended mainly for vector/hybrid PDFs.
- Raster scans require high-resolution tiling and a vision/object-detection workflow.
- Different companies and projects may use different symbol geometry.
- Final results require human or agent-assisted visual confirmation.

## License

MIT
