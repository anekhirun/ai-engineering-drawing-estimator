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
  "geometry_score": 0.12
}
```

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
  "review_notes": "Checked wall faces, corners, and both sides of doors."
}
```

A count is final only when `review_complete` is `true`.
If `clarification_required` is `true`, ask the user about the affected markup
IDs or coordinates and rerun confirmation after recording the answer.
