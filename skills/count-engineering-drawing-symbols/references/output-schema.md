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
