---
name: count-engineering-drawing-symbols
description: Use TakeoffLens to count and audit supported building-system symbols in engineering DWG/DXF/PDF drawings by preferring CAD metadata, using vector geometry for vector PDFs, and using high-resolution vision only for raster PDFs. Electrical and ELV systems are the first active disciplines. Use when an agent must count equipment, compare floors or revisions, create candidate markups, evaluate detection accuracy, or produce a reviewable quantity report.
---

# TakeoffLens Drawing Audit

Use the `takeoff-lens` MCP tools. Treat every automatic detection as a candidate until it is visually confirmed.

## Workflow

1. Call `get_discipline_catalog` to distinguish active from planned disciplines. Then call `get_symbol_rules` with active `system_id=POWER`, `LIGHTING`, `FIRE_ALARM`, `DATA_VOICE`, or `CCTV_SECURITY` to lock the v0.2.0 scope. Never imply that a planned discipline is already supported.
2. Prefer DWG/DXF block, attribute, layer, and XREF extraction when CAD is available. For this v0.2.0 MCP, process vector/hybrid PDF directly.
3. On a clean vector sheet with meaningful equipment layers, call `analyze_vector_layers` first. Group by rotation-normalized dimensions, then apply only a user- or legend-confirmed project mapping. Save that mapping and reuse `signature_mapping_path`; never infer equipment class from a frequent shape alone.
4. Call `prepare_sheet_audit`. It builds one native shared sheet context, profiles the page, renders an overview, detects every symbol with a ready template, and creates one candidate contact sheet. Use the returned manifest instead of repeating separate inspection calls.
5. Read [references/symbol-rules.md](references/symbol-rules.md) before classification. Every class without a bundled starter requires either an unambiguous confirmed layer signature or a clean project-specific template from the current legend; build only templates listed in `template_required`, pass its exact `symbol_id` to `build_symbol_template`, then rerun `prepare_sheet_audit`.
6. Keep MCP responses at the default `response_detail=compact`. Read the detailed JSON artifact only when coordinates, diagnostics, or ambiguity review are needed. Use `response_detail=full` for debugging, not routine turns.
7. Use `detect_symbol_candidates` separately only for tuning or rerunning one symbol. Keep a high-recall shortlist.
8. Inspect every crop and markup. Also inspect `filtered_candidates.json` when Candidate Filtering v3 suppresses matches. Classify indoor and explicit WP variants from the crop and project legend; do not assume extracted PDF text contains a visible WP glyph. Independently sweep all wall faces, wall corners, both sides of doors, rotated symbols, and paired power/data symbols; do not treat a low candidate count as evidence of zero.
9. Reject candidates in legends, notes, details, title blocks, and unrelated systems.
10. Add visually verified misses as `manual_points`; do not silently change the final number.
11. Call `confirm_symbol_count` with every candidate classified in `accepted_ids`, `rejected_ids`, or `uncertain_ids`; pass the matching `detection_manifest_json`, include `floor_or_region`, and set `wall_door_sweep_completed` only after the independent sweep. A final result requires verified PDF, template, and candidate hashes.
12. If a symbol, legend mapping, boundary, or candidate decision is unknown or not sufficiently supported, keep it uncertain, record its page and coordinates, create a crop or markup, and ask the user a concise verification question. Group related uncertain points in one question when practical.
13. Continue reviewing independent clear items while waiting for clarification, but do not guess, silently exclude the item, or finalize any affected subtotal.
14. After the user answers, record the decision and rerun confirmation. Treat the result as final only when `review_complete` is true, `clarification_required` is false, and `provenance_verified` is true. Report count by page/floor and include final markup and CSV/JSON paths.
15. For detector tuning, call `evaluate_detection_accuracy` only with ground truth whose review is complete and whose PDF-point coordinates were visually verified. Compare shortlist recall with candidate-pool recall to identify filtering and shortlist-limit misses.

## Counting rules

- Never count from OCR output. Use OCR only for circuit numbers, tags, room names, mounting heights, notes, and legend descriptions.
- Treat wall proximity as strong evidence, not an absolute requirement; floor outlets can exist.
- Do not interpret nearby text as quantity. For example, `4` can be a circuit/circuit-breaker number and `C` can mean CCTV.
- Keep every supported symbol class separate even when symbols touch or share a conduit.
- Require coordinates for every counted item. A total without locations is incomplete.
- Ask the user when the project legend is missing, multiple symbols look alike, a region boundary changes the subtotal, or visual/vector evidence conflicts.
- In each question, state what is uncertain, where it is, the likely choices, and how each choice affects the count. Do not ask the user to inspect an unidentified location without a crop, markup ID, or coordinates.
- If `confirm_symbol_count` returns `review_warning`, the zero is provisional until the candidate set and wall sweep are explicitly reviewed.
- State uncertainty and detection method. Do not claim production-grade automatic accuracy in v0.2.0 without a reviewed benchmark report.

## Failure handling

- If a vector template returns too few candidates, loosen one parameter at a time and compare diagnostics.
- If it returns many false positives, build a clean project-specific template from the drawing legend with `build_symbol_template`. Letters, pole markers, and camera suffixes can occur in unrelated annotations or compound symbols, so never finalize from geometry matches alone.
- If the PDF is raster, render at 400-600 DPI, tile with overlap, and use vision/object detection; bundled vector templates are not sufficient.
- If a page contains multiple floors, review and group coordinates by visible floor region before reporting.

Read [references/output-schema.md](references/output-schema.md) when integrating results into another agent or BOQ workflow.
