# Accuracy benchmark

The benchmark is deliberately separate from ordinary unit tests. It measures
detector output against fully reviewed symbol locations in PDF points.

Project drawings and ground-truth files are private test data. Keep them under
an ignored directory such as `test-runs/benchmark-data/`; never add them to the
public plugin archive.

## Ground truth requirements

- `schema_version` must be `"1"`.
- `review_complete` must be `true`.
- `clarification_required` must be `false`.
- `source_pdf_sha256` must match the exact PDF used by the benchmark runner.
- Every detection needs a stable ID, `symbol_id`, and PDF-point coordinates.

Copy `ground-truth.example.json` and replace the example values only after a
complete visual review. Provisional counts are rejected.

## Run a suite

Create a private manifest from `manifest.example.json`, then run:

```powershell
.\.venv\Scripts\python.exe scripts\run-accuracy-benchmark.py `
  test-runs\benchmark-data\manifest.json `
  --output-dir test-runs\accuracy-v0.2.0 `
  --fail-on-threshold
```

The summary reports shortlist precision, recall, F1, false-positive IDs,
false-negative IDs, and whether misses were caused by filtering or the
shortlist limit. Thresholds belong in the private manifest and should be raised
only from a reviewed baseline.
