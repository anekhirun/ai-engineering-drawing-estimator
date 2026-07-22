# TakeoffLens v0.2.0

**AI drawing intelligence for reviewed, traceable quantity takeoff**

TakeoffLens is an installable Plugin that turns engineering drawings into reviewed quantities with source evidence. Electrical and ELV are the first active disciplines: Power, Lighting, Fire Alarm, Data/Voice, and CCTV/Security. Its shared Core + Discipline architecture is designed to expand to Mechanical/HVAC, Plumbing, Fire Protection, Architectural, Structural, and other building systems without presenting roadmap packs as already supported. The experimental Windows Desktop App remains optional.

> This is not a fully automatic quantity takeoff system. Every candidate must be reviewed before reporting a final count.

## Product scope

TakeoffLens does not claim to understand every PDF. It focuses on engineering
drawings and combines PDF inspection, vector/layer evidence, symbol candidates,
human review, provenance, and accuracy measurement.

- **TakeoffLens Core:** PDF inspection and rendering, vector-layer analysis,
  candidate detection, assisted review, traceable export, and benchmarking.
- **Active v0.2.0 disciplines:** Electrical and ELV.
- **Planned discipline packs:** Mechanical/HVAC, Plumbing/Sanitary, Fire
  Protection, Architectural, and Structural.
- `get_discipline_catalog` is the machine-readable source of truth for active
  and planned scope.

## Supported workflow

- Inspect vector, hybrid, and raster PDF pages.
- Classify pages with native Page Profiler v2, including confidence and evidence.
- Render pages for visual review.
- Prepare a complete one-sheet audit with one MCP call for:
  - Power: Duplex/Single Socket Outlet, 3P+N+E Power Receptacle, and Non-Fuse Disconnecting Switch.
  - Lighting: switches, junction/control devices, normal luminaires, emergency lighting, and exit signs.
  - Fire Alarm: control panel, smoke detector, 135/200 F heat detector, indoor
    and weatherproof bell/manual-station/strobe variants, and end-of-line accessory.
  - Data/Voice: panels, cabinets, telephone outlets, and RJ45 data outlets.
  - CCTV/Security: cameras, monitoring, access-control, alarm, and door-control devices.
- Use bundled starter templates where available and project-specific legend templates for every other class.
- Candidate Filtering v3 measures text coverage across the whole symbol ROI,
  not only its center.
- Preserve PDF/CAD layer metadata and suppress strong text, dimension,
  annotation, and non-outlet layer matches when a Power outlet layer exists.
- Reuse one native `SheetContext` for primitives, descriptors, text boxes, spatial
  index, and rendering across every symbol on the same sheet.
- Exclude explicit legend, note, detail, or title-block rectangles in PDF points.
- Optionally restrict detection to explicit plan rectangles with
  `included_regions`.
- Cache up to two prepared sheet contexts in memory without locking source PDFs on Windows;
  unusually large renders are released while geometry remains cached.
- Record template hashes, validation warnings, score breakdowns, and per-stage timing.
- Write a detection manifest that binds the PDF, page, template, candidates, and
  detector parameters with SHA-256 evidence.
- Preserve the complete post-NMS candidate pool so filtered and shortlist-limit
  false negatives can be measured instead of disappearing from the audit trail.
- Create project-specific symbol templates from a clean legend ROI.
- Export candidate crops, markup, CSV, JSON, and an HTML review page.
- Confirm reviewed candidates and add manually verified points.
- Record accepted, rejected, uncertain, and unresolved candidates in the audit report.
- Mark a result final only when `review_complete` and `provenance_verified` are true.
- Measure precision, recall, F1, and stage-attributed misses against fully
  reviewed PDF-point ground truth.

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

### Plugin installation (recommended)

v0.2.0 packages the repository as `takeoff-lens` with:

- `.codex-plugin/plugin.json` for one versioned install surface.
- `.mcp.json` for the bundled local MCP server.
- The existing `skills/count-engineering-drawing-symbols` workflow.
- `plugin-mcp.ps1`, which creates a private per-user MCP environment on first
  launch and installs only the headless MCP dependencies.

The plugin processes drawings locally and does not upload project PDFs. The
first MCP launch requires Python 3 and internet access to install the pinned
Python packages. Later launches reuse the dependency hash and start directly.
Managed or offline installations can set `TAKEOFFLENS_PYTHON`
to an existing compatible Python executable; the launcher then skips dependency
installation and starts the bundled server with that environment. The legacy
`ENGINEERING_DRAWING_ESTIMATOR_PYTHON` variable remains accepted as a
compatibility alias during migration.

Maintainers can build the public local-marketplace package with:

```powershell
.\scripts\build-plugin-package.ps1
```

The command creates
`release/takeoff-lens-plugin-v0.2.0.zip`. After extracting the
archive, add its `plugin-marketplace` directory as a marketplace and install
`takeoff-lens` from the Codex Plugins Directory. The archive
contains only the Plugin, Skill, MCP source, templates, runtime launcher, and
public documentation.

### Manual Skill + MCP installation

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

When upgrading, remove old `[mcp_servers.drawing-estimate-reader]` and
`[mcp_servers.engineering-drawing-estimator]` blocks before adding the generated
`[mcp_servers.takeoff-lens]` block. Keep only one MCP registration.

For another agent, register a `stdio` MCP server using:

```text
command: .venv\Scripts\python.exe
args:    mcp\server.py
```

## Agent prompt

```text
Use $count-engineering-drawing-symbols to inspect this PDF.
Run prepare_sheet_audit for POWER, LIGHTING, FIRE_ALARM, DATA_VOICE, or CCTV_SECURITY and count its supported symbols by floor.
Create markup and review every candidate before reporting the quantities.
If any symbol or candidate is uncertain, show its crop, markup ID, or coordinates and ask me before finalizing.
```

## MCP tools

| Tool | Purpose |
|---|---|
| `get_discipline_catalog` | Report active and planned TakeoffLens disciplines |
| `inspect_drawing` | Classify PDF pages before analysis |
| `render_page` | Render a page for legend and plan review |
| `get_symbol_rules` | Return supported symbol/context rules |
| `build_symbol_template` | Build a project-specific vector template |
| `analyze_vector_layers` | Group rotation-normalized vector signatures and apply a confirmed project mapping |
| `detect_symbol_candidates` | Generate a high-recall candidate shortlist |
| `confirm_symbol_count` | Export confirmed counts and auditable markup |
| `prepare_sheet_audit` | Inspect, render, detect all ready symbols, and create one review contact sheet |
| `evaluate_detection_accuracy` | Measure reviewed precision/recall and attribute misses to filtering or shortlist limits |

## v0.2.0 accuracy and provenance

- Every detection run writes `detection_manifest.json` with SHA-256 hashes for
  the source PDF, template, `candidates.json`, and `candidate_pool.json`.
- `confirm_symbol_count` automatically discovers the manifest beside the
  candidate file, or accepts `detection_manifest_json` explicitly. A hash,
  page, or symbol mismatch stops confirmation.
- Legacy candidate files without a verified manifest remain reviewable, but
  cannot return `review_complete: true`.
- `candidate_pool.json` contains shortlisted, filtered, and `ranked_out`
  candidates. A clean overlapping candidate is prioritized during NMS so a
  text/annotation-filtered match cannot hide it.
- v0.2.0 templates declare `symbol_id` and template type. Passing a template
  that declares a different symbol stops the run instead of silently applying
  the wrong geometry.
- `evaluate_detection_accuracy` accepts only ground truth with
  `review_complete: true` and no unresolved clarification. It writes exact
  TP/FP/FN IDs plus precision, recall, and F1.
- Maintainers can keep private drawing suites outside Git and run
  `scripts/run-accuracy-benchmark.py`; see `benchmarks/README.md`. The runner
  verifies the PDF hash before detection and can fail a quality gate.
- The first private, fully reviewed Fire Alarm baseline covers 8 symbol classes
  and 10 confirmed locations on one vector sheet. Layer-aware filtering reduced
  false positives from 83 to 25 while preserving recall at `1.000`; final
  shortlist precision is `0.286` and F1 is `0.444`. This is a regression
  baseline for one sheet, not a general production-accuracy claim.

## v0.1.4 native pipeline optimization

- `prepare_sheet_audit` prepares and renders a sheet once, then runs all ready
  symbol templates against the shared native context.
- Clean vector sheets can use `analyze_vector_layers` before template matching.
  It groups paths by layer, shape family, and rotation-normalized dimensions;
  it never assigns equipment names unless a project mapping was confirmed.
- Store confirmed mappings in a local JSON file and pass
  `signature_mapping_path` on later runs. Ambiguous mappings stop with
  `clarification_required` instead of selecting a class automatically.
- `inspect_drawing` reports `vector_clean`, `hybrid`, `vector_sparse`,
  `raster_scan`, or `unknown`, plus confidence, evidence, and a compatibility flag.
- `detect_symbol_candidates` remains available for one-symbol tuning and reuses
  the same in-memory context when possible.
- Candidate JSON retains the legacy `score` while adding `geometry_score`,
  `final_score`, `score_version`, and filtering provenance.
- Candidate Filtering v3 writes every automatically suppressed geometry match to
  `filtered_candidates.json`, including its source layers and filter reasons.
- `exclude_annotation_layers=false` disables layer-based suppression for unusual
  drawings; final counts still require review.
- `force_reprocess=true` bypasses the in-memory context cache.
- MCP responses use `response_detail=compact` by default. Complete coordinates
  and diagnostics remain in the returned JSON artifact paths; use
  `response_detail=full` only for debugging or integration.
- PDF vector paths are extracted once per shared sheet context and reused by the
  page profiler, layer inventory, and detector.
- The implementation remains Python, PyMuPDF, OpenCV, NumPy, and Pillow only;
  v0.1.4 adds no external OCR, Java, or third-party PDF pipeline.

## v0.1.4 scope and performance target

- Supported systems: **Power**, **Lighting**, **Fire Alarm**, **Data/Voice**, and **CCTV/Security**.
- Project-specific templates are required for classes without a bundled starter template.
- Routine target for one vector/hybrid sheet and one system: no more than three
  minutes and approximately 500k agent tokens or less.
- The time and token figures are workflow targets, not accuracy guarantees. Local
  geometry processing does not consume model tokens; contact-sheet review and
  clarification are the main token cost.
- A representative vector Fire Alarm sheet prepared the audit in 20.8 seconds
  locally. It returned 42 high-recall candidates for 11 visually confirmed
  symbols, so candidate review remains mandatory, especially for Manual Station.

## v0.1.4 review contract

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
