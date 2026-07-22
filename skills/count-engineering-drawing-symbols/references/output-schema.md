# Output schema

Every final detection must contain:

```json
{
  "detection_id": "DS-01",
  "symbol_id": "DUPLEX_SOCKET_OUTLET",
  "page": 1,
  "floor_or_region": "GROUND FLOOR",
  "center_x_pt": 512.3,
  "center_y_pt": 284.1,
  "detection_method": "pdf_vector_compound_match",
  "review_status": "confirmed",
  "geometry_score": 0.12,
  "final_score": 0.11,
  "score_version": "native_v2"
}
```

TakeoffLens classifies product scope separately from detection results.
`get_discipline_catalog` reports `active` packs that may be processed and
`planned` packs that must not be presented as supported. Every active system
also declares its parent `discipline_id`.

Candidate diagnostics should also record the native `context_id`, Page Profiler
v2 result, template hash and validation, cache status, excluded regions, filter
counts, and per-stage timings. These fields improve reproducibility but never
replace visual review.

Routine MCP calls should return the compact summary and artifact paths. Full
candidate coordinates and diagnostics belong in those artifacts so they remain
auditable without repeatedly consuming the agent context.

Required report artifacts:

- Confirmed count grouped by symbol and floor/page.
- CSV and JSON with one row/object per confirmed detection.
- Markup image showing every confirmed location and ID.
- Explicit list of manual additions and uncertain/rejected candidates when relevant.

Required review evidence:

```json
{
  "review_complete": true,
  "clarification_required": false,
  "accepted_ids": ["C-0001"],
  "rejected_ids": ["C-0002"],
  "uncertain_ids": [],
  "unresolved_ids": [],
  "wall_door_sweep_completed": true,
  "provenance_verified": true,
  "review_notes": "Checked wall faces, corners, and both sides of doors."
}
```

A count is final only when `review_complete` and `provenance_verified` are `true`.
If `clarification_required` is `true`, ask the user about the affected markup
IDs or coordinates and rerun confirmation after recording the answer.

Every v0.2.0 detector run also writes `detection_manifest.json` and
`candidate_pool.json`. The manifest binds the PDF, page, template, candidate
files, parameters, and page profile. The pool preserves `shortlisted`,
`filtered`, and `ranked_out` records for benchmark miss attribution.
