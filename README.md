# AI Engineering Drawing Estimator v0.1.3

**AI Agent MCP + Skill for reviewed symbol counting and quantity takeoff**

An assisted-review MCP server and Agent Skill for counting Power and Fire Alarm symbols in engineering PDF drawings with ChatGPT Codex, Hermes, and other MCP-compatible AI agents. The MCP + Skill workflow is the primary interface in v0.1.3; the experimental Windows Desktop App remains available but is not the current development focus.

> This is not a fully automatic quantity takeoff system. Every candidate must be reviewed before reporting a final count.

## Supported workflow

- Inspect vector, hybrid, and raster PDF pages.
- Render pages for visual review.
- Prepare a complete one-sheet audit with one MCP call for:
  - Power: Duplex Socket Outlet and Single Socket Outlet.
  - Fire Alarm: control panel, smoke detector, 135/200 F heat detector, bell,
    manual station, strobe light, and end-of-line accessory.
- Use bundled starter templates for Power and project-specific legend templates for Fire Alarm.
- Suppress candidates whose center overlaps PDF text by default.
- Create project-specific symbol templates from a clean legend ROI.
- Export candidate crops, markup, CSV, JSON, and an HTML review page.
- Confirm reviewed candidates and add manually verified points.
- Record accepted, rejected, uncertain, and unresolved candidates in the audit report.
- Mark a result final only when `review_complete` is true.

No project drawings, customer files, marked-up plans, test outputs, or machine-specific paths are included in this repository.

## Windows Desktop App

The desktop app is an experimental interface over the same local detection engine. Development currently focuses on MCP + Skill accuracy and auditability before expanding the desktop UI.

1. Open a PDF and inspect its page classification.
2. Select a page, symbol, resolution, and optional project-specific template.
3. Detect candidates and review every crop as Accept, Reject, or Uncertain.
4. Click the drawing to add visually verified misses as manual points.
5. Confirm the wall/door sweep before exporting the final CSV, JSON, and markup.

After installation, launch it with:

```powershell
.\start-desktop.ps1
```

Mouse wheel zooms the drawing. Drag to pan; enable **manual point mode** before clicking a missed symbol. Raster pages are classified and shown, but the bundled automatic matcher remains intended for vector/hybrid PDFs.

## Requirements

- Windows
- Python 3.12-3.14
- PowerShell
- An MCP-compatible AI agent such as Codex or Hermes (optional for the Desktop App)

## Install

Clone or download this repository, then run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

The installer:

1. Creates `.venv` and installs the Python dependencies.
2. Runs the MCP doctor check.
3. Installs the PySide6 Windows Desktop App dependencies.
4. Installs the Skill to `~/.codex/skills/count-engineering-drawing-symbols` by default.
5. Generates `codex-mcp-config.toml` with the local MCP command.

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
Run prepare_sheet_audit for POWER or FIRE_ALARM and count its supported symbols by floor.
Create markup and review every candidate before reporting the quantities.
If any symbol or candidate is uncertain, show its crop, markup ID, or coordinates and ask me before finalizing.
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
| `prepare_sheet_audit` | Inspect, render, detect all ready symbols, and create one review contact sheet |

## v0.1.3 scope and performance target

- Supported systems: **Power** and **Fire Alarm** only.
- Data/Communication and all other systems are deferred to v0.2.0.
- Routine target for one vector/hybrid sheet and one system: no more than three
  minutes and approximately 500k agent tokens or less.
- The time and token figures are workflow targets, not accuracy guarantees. Local
  geometry processing does not consume model tokens; contact-sheet review and
  clarification are the main token cost.
- A representative vector Fire Alarm sheet prepared the audit in 20.8 seconds
  locally. It returned 42 high-recall candidates for 11 visually confirmed
  symbols, so candidate review remains mandatory, especially for Manual Station.

## v0.1.3 review contract

`confirm_symbol_count` accepts `accepted_ids`, `rejected_ids`, `uncertain_ids`,
`manual_points`, `floor_or_region`, review notes, and an explicit
`wall_door_sweep_completed` flag.

The generated report includes:

- `review_complete`: true only when every detector candidate has a final decision,
  no candidate remains uncertain, and the wall/door sweep is confirmed.
- `clarification_required`: true when unresolved or uncertain candidates require
  a user decision. The agent must show their crop, markup ID, or coordinates and
  ask before finalizing the affected count.
- `unresolved_ids` and `uncertain_ids`: items that prevent a final result.
- Accepted, rejected, detector, and manual counts.
- Floor/region metadata on every confirmed detection.

Older calls remain valid, but they return `review_complete: false` until the new
review evidence is supplied.

## Important review rules

- Treat starter templates as search aids, not universal standards.
- Prefer the legend from the current project.
- Check every wall face, wall corner, and both sides of doors.
- Support rotated symbols at 0, 90, 180, and 270 degrees.
- Use OCR only for text context, never for detecting symbol geometry.
- A nearby `4` can be a circuit number; `C` can identify CCTV.
- A zero result remains provisional until the candidate set and wall/door regions are reviewed.
- Use `manual_points` for visually confirmed misses.
- Never guess an unknown or ambiguous symbol. Mark it uncertain, show its location,
  and ask the user to verify it before reporting the affected subtotal as final.

## Limitations

- The bundled matcher is intended mainly for vector/hybrid PDFs.
- Raster scans require high-resolution tiling and a vision/object-detection workflow.
- Different companies and projects may use different symbol geometry.
- Final results require human or agent-assisted visual confirmation.

## License

MIT
