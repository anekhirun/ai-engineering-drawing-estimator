---
name: count-engineering-drawing-symbols
description: Count and audit electrical and communication symbols in engineering DWG/DXF/PDF drawings by preferring CAD metadata, using vector geometry for vector PDFs, and using high-resolution vision only for raster PDFs. Use when an agent must count Duplex Socket Outlet, Single Socket Outlet, Data Outlet, or related engineering symbols; compare floors or revisions; create candidate markups; or produce a reviewable quantity report from drawings.
---

# Count Engineering Drawing Symbols

Use the `drawing-estimate-reader` MCP tools. Treat every automatic detection as a candidate until it is visually confirmed.

## Workflow

1. Call `inspect_drawing` before analysis.
2. Prefer DWG/DXF block, attribute, layer, and XREF extraction when CAD is available. For this v0.1.1 MCP, process vector/hybrid PDF directly.
3. Call `render_page` at 400-600 DPI for final review and identify page boundaries, floor-plan regions, legend, title block, details, demolition/existing areas, and schedules.
4. Read [references/symbol-rules.md](references/symbol-rules.md) before classifying socket or data symbols.
5. Call `detect_symbol_candidates` separately for each symbol and page. Keep a high-recall shortlist.
6. Inspect every crop and markup. Independently sweep all wall faces, wall corners, both sides of doors, rotated symbols, and paired power/data symbols; do not treat a low candidate count as evidence of zero.
7. Reject candidates in legends, notes, details, title blocks, and unrelated systems.
8. Add visually verified misses as `manual_points`; do not silently change the final number.
9. Call `confirm_symbol_count` only after review. Report count by page/floor and include final markup and CSV/JSON paths.

## Counting rules

- Never count from OCR output. Use OCR only for circuit numbers, tags, room names, mounting heights, notes, and legend descriptions.
- Treat wall proximity as strong evidence, not an absolute requirement; floor outlets can exist.
- Do not interpret nearby text as quantity. For example, `4` can be a circuit/circuit-breaker number and `C` can mean CCTV.
- Keep Duplex, Single, and Data separate even when symbols touch or share a conduit.
- Require coordinates for every counted item. A total without locations is incomplete.
- If `confirm_symbol_count` returns `review_warning`, the zero is provisional until the candidate set and wall sweep are explicitly reviewed.
- State uncertainty and detection method. Do not claim production-grade automatic accuracy in v0.1.1.

## Failure handling

- If a vector template returns too few candidates, loosen one parameter at a time and compare diagnostics.
- If it returns many false positives, build a clean project-specific template from the drawing legend with `build_symbol_template`.
- If the PDF is raster, render at 400-600 DPI, tile with overlap, and use vision/object detection; bundled vector templates are not sufficient.
- If a page contains multiple floors, review and group coordinates by visible floor region before reporting.

Read [references/output-schema.md](references/output-schema.md) when integrating results into another agent or BOQ workflow.
