from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))
sys.path.insert(0, str(ROOT / "mcp" / "engine"))

from accuracy_benchmark import evaluate_files, validate_ground_truth  # noqa: E402
from server import detect_symbol_candidates  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(base: Path, value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return normalized or "case"


def threshold_result(metrics: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for metric, default in (("recall", 0.0), ("precision", 0.0), ("f1", 0.0)):
        minimum = float(thresholds.get(f"min_{metric}", default))
        actual = float(metrics[metric])
        checks[f"min_{metric}"] = {
            "minimum": minimum,
            "actual": actual,
            "passed": actual >= minimum,
        }
    return {"passed": all(item["passed"] for item in checks.values()), "checks": checks}


def run_manifest(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if str(manifest.get("schema_version", "")) != "1":
        raise ValueError("Benchmark manifest schema_version must be 1")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Benchmark manifest cases must be a non-empty list")

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    base = manifest_path.parent
    global_thresholds = manifest.get("thresholds", {})
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            raise ValueError(f"Benchmark case {index} must be an object")
        case_id = str(case.get("case_id") or f"case-{index:03d}")
        pdf = resolve_path(base, str(case["pdf_path"]), f"{case_id} PDF")
        template = resolve_path(
            base, str(case["template_path"]), f"{case_id} template"
        )
        ground_truth = resolve_path(
            base, str(case["ground_truth_json"]), f"{case_id} ground truth"
        )
        truth_payload = json.loads(ground_truth.read_text(encoding="utf-8"))
        validate_ground_truth(truth_payload, symbol_id=str(case["symbol_id"]))
        expected_hash = str(truth_payload.get("source_pdf_sha256", ""))
        actual_hash = sha256_file(pdf)
        if not expected_hash:
            raise ValueError(f"{case_id} ground truth is missing source_pdf_sha256")
        if expected_hash != actual_hash:
            raise ValueError(f"{case_id} ground truth does not match the source PDF hash")

        case_output = output_dir / slug(case_id)
        detection_args = {
            "pdf_path": str(pdf),
            "page": int(case.get("page", truth_payload.get("page", 1))),
            "symbol_id": str(case["symbol_id"]),
            "template_path": str(template),
            "output_dir": str(case_output / "detection"),
            "response_detail": "full",
            **case.get("detection_options", {}),
        }
        detection = detect_symbol_candidates(detection_args)
        evaluation = evaluate_files(
            candidates_json=detection["candidates_json"],
            candidate_pool_json=detection["candidate_pool_json"],
            detection_manifest_json=detection["detection_manifest_json"],
            ground_truth_json=ground_truth,
            symbol_id=str(case["symbol_id"]),
            match_radius_pt=float(case.get("match_radius_pt", 8.0)),
        )
        metrics = evaluation["shortlist"]
        thresholds = {**global_thresholds, **case.get("thresholds", {})}
        gate = threshold_result(metrics, thresholds)
        case_result = {
            "case_id": case_id,
            "symbol_id": case["symbol_id"],
            "pdf_sha256": actual_hash,
            "detection_manifest_json": detection["detection_manifest_json"],
            "metrics": metrics,
            "candidate_pool_metrics": evaluation.get("candidate_pool"),
            "miss_attribution": evaluation.get(
                "shortlist_misses_recovered_by_stage", {}
            ),
            "quality_gate": gate,
        }
        case_report = case_output / "accuracy_report.json"
        case_report.parent.mkdir(parents=True, exist_ok=True)
        case_report.write_text(
            json.dumps(case_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        case_result["accuracy_report_json"] = str(case_report)
        results.append(case_result)
        totals["tp"] += metrics["true_positive_count"]
        totals["fp"] += metrics["false_positive_count"]
        totals["fn"] += metrics["false_negative_count"]

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 1.0
    recall = totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    summary = {
        "schema_version": "1",
        "case_count": len(results),
        "passed": all(item["quality_gate"]["passed"] for item in results),
        "micro_metrics": {
            "true_positive_count": totals["tp"],
            "false_positive_count": totals["fp"],
            "false_negative_count": totals["fn"],
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        },
        "cases": results,
    }
    (output_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run reviewed drawing cases through the detector and accuracy gates."
    )
    parser.add_argument("manifest")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fail-on-threshold", action="store_true")
    args = parser.parse_args()
    summary = run_manifest(Path(args.manifest).resolve(), Path(args.output_dir).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if args.fail_on_threshold and not summary["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
