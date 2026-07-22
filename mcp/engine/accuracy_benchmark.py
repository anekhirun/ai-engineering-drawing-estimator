from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: str | Path, label: str) -> Any:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} not found: {resolved}")
    return json.loads(resolved.read_text(encoding="utf-8"))


def _coordinate(item: dict[str, Any], label: str) -> tuple[float, float]:
    try:
        return float(item["center_x_pt"]), float(item["center_y_pt"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain numeric center_x_pt and center_y_pt") from exc


def validate_ground_truth(
    payload: dict[str, Any], *, symbol_id: str | None = None
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Ground truth must be a JSON object")
    if str(payload.get("schema_version", "")) != SCHEMA_VERSION:
        raise ValueError(f"Ground truth schema_version must be {SCHEMA_VERSION}")
    if payload.get("review_complete") is not True:
        raise ValueError("Ground truth must have review_complete=true")
    if payload.get("clarification_required") is True:
        raise ValueError("Ground truth cannot require clarification")

    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise ValueError("Ground truth detections must be a list")

    selected = []
    seen_ids: set[str] = set()
    for index, item in enumerate(detections, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Ground truth detection {index} must be an object")
        item_symbol = str(item.get("symbol_id", payload.get("symbol_id", "")))
        if not item_symbol:
            raise ValueError(f"Ground truth detection {index} is missing symbol_id")
        if symbol_id and item_symbol != symbol_id:
            continue
        ground_truth_id = str(
            item.get("ground_truth_id") or item.get("detection_id") or f"GT-{index:04d}"
        )
        if ground_truth_id in seen_ids:
            raise ValueError(f"Duplicate ground truth id: {ground_truth_id}")
        seen_ids.add(ground_truth_id)
        x_pt, y_pt = _coordinate(item, f"Ground truth detection {index}")
        selected.append(
            {
                **item,
                "ground_truth_id": ground_truth_id,
                "symbol_id": item_symbol,
                "center_x_pt": x_pt,
                "center_y_pt": y_pt,
            }
        )
    return selected


def validate_candidates(payload: Any, label: str = "Candidates") -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(f"{label} JSON must contain a list")
    validated = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{label} item {index} must be an object")
        candidate_id = str(item.get("candidate_id") or f"ITEM-{index:04d}")
        if candidate_id in seen_ids:
            raise ValueError(f"Duplicate {label.lower()} id: {candidate_id}")
        seen_ids.add(candidate_id)
        x_pt, y_pt = _coordinate(item, f"{label} item {index}")
        validated.append(
            {
                **item,
                "candidate_id": candidate_id,
                "center_x_pt": x_pt,
                "center_y_pt": y_pt,
            }
        )
    return validated


def _distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.hypot(
        left["center_x_pt"] - right["center_x_pt"],
        left["center_y_pt"] - right["center_y_pt"],
    )


def match_detections(
    candidates: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    match_radius_pt: float,
) -> list[dict[str, Any]]:
    if match_radius_pt <= 0:
        raise ValueError("match_radius_pt must be positive")

    adjacency: list[list[int]] = []
    for candidate in candidates:
        choices = [
            (index, _distance(candidate, truth))
            for index, truth in enumerate(ground_truth)
            if _distance(candidate, truth) <= match_radius_pt
        ]
        adjacency.append([index for index, _ in sorted(choices, key=lambda value: value[1])])

    truth_to_candidate: dict[int, int] = {}

    def assign(candidate_index: int, visited: set[int]) -> bool:
        for truth_index in adjacency[candidate_index]:
            if truth_index in visited:
                continue
            visited.add(truth_index)
            previous = truth_to_candidate.get(truth_index)
            if previous is None or assign(previous, visited):
                truth_to_candidate[truth_index] = candidate_index
                return True
        return False

    candidate_order = sorted(
        range(len(candidates)),
        key=lambda index: (
            min(
                (_distance(candidates[index], ground_truth[item]) for item in adjacency[index]),
                default=float("inf"),
            ),
            candidates[index]["candidate_id"],
        ),
    )
    for candidate_index in candidate_order:
        assign(candidate_index, set())

    matches = []
    for truth_index, candidate_index in sorted(truth_to_candidate.items()):
        candidate = candidates[candidate_index]
        truth = ground_truth[truth_index]
        matches.append(
            {
                "candidate_id": candidate["candidate_id"],
                "ground_truth_id": truth["ground_truth_id"],
                "distance_pt": round(_distance(candidate, truth), 4),
            }
        )
    return matches


def evaluate_candidate_set(
    candidates: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    match_radius_pt: float,
) -> dict[str, Any]:
    matches = match_detections(candidates, ground_truth, match_radius_pt)
    matched_candidate_ids = {item["candidate_id"] for item in matches}
    matched_truth_ids = {item["ground_truth_id"] for item in matches}
    true_positives = len(matches)
    false_positives = len(candidates) - true_positives
    false_negatives = len(ground_truth) - true_positives
    precision = true_positives / len(candidates) if candidates else (1.0 if not ground_truth else 0.0)
    recall = true_positives / len(ground_truth) if ground_truth else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "candidate_count": len(candidates),
        "ground_truth_count": len(ground_truth),
        "true_positive_count": true_positives,
        "false_positive_count": false_positives,
        "false_negative_count": false_negatives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "matches": matches,
        "false_positive_ids": [
            item["candidate_id"]
            for item in candidates
            if item["candidate_id"] not in matched_candidate_ids
        ],
        "false_negative_ids": [
            item["ground_truth_id"]
            for item in ground_truth
            if item["ground_truth_id"] not in matched_truth_ids
        ],
    }


def evaluate_files(
    *,
    candidates_json: str | Path,
    ground_truth_json: str | Path,
    symbol_id: str,
    match_radius_pt: float = 8.0,
    candidate_pool_json: str | Path | None = None,
    detection_manifest_json: str | Path | None = None,
) -> dict[str, Any]:
    truth_payload = _load_json(ground_truth_json, "Ground truth")
    ground_truth = validate_ground_truth(truth_payload, symbol_id=symbol_id)
    candidates = validate_candidates(_load_json(candidates_json, "Candidates"))
    shortlist = evaluate_candidate_set(candidates, ground_truth, match_radius_pt)

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "symbol_id": symbol_id,
        "page": truth_payload.get("page"),
        "match_radius_pt": float(match_radius_pt),
        "ground_truth_review_complete": True,
        "source_identity_verified": False,
        "shortlist": shortlist,
    }

    if detection_manifest_json:
        detection_manifest = _load_json(
            detection_manifest_json, "Detection manifest"
        )
        checks = {
            "schema_version": SCHEMA_VERSION,
            "symbol_id": symbol_id,
            "candidates_sha256": _sha256_file(candidates_json),
        }
        if truth_payload.get("page") is not None:
            checks["page"] = truth_payload["page"]
        expected_pdf_hash = str(truth_payload.get("source_pdf_sha256", ""))
        if not expected_pdf_hash:
            raise ValueError("Ground truth is missing source_pdf_sha256")
        checks["pdf_sha256"] = expected_pdf_hash
        mismatches = [
            key
            for key, value in checks.items()
            if detection_manifest.get(key) != value
        ]
        if mismatches:
            raise ValueError(
                "Accuracy source identity mismatch for: " + ", ".join(mismatches)
            )
        result["source_identity_verified"] = True
        result["detection_manifest_json"] = str(
            Path(detection_manifest_json).resolve()
        )

    if candidate_pool_json:
        pool = validate_candidates(
            _load_json(candidate_pool_json, "Candidate pool"), "Candidate pool"
        )
        pool_metrics = evaluate_candidate_set(pool, ground_truth, match_radius_pt)
        shortlist_truth_ids = {
            item["ground_truth_id"] for item in shortlist["matches"]
        }
        stages: dict[str, list[str]] = {}
        for item in pool_metrics["matches"]:
            if item["ground_truth_id"] in shortlist_truth_ids:
                continue
            candidate = next(
                candidate
                for candidate in pool
                if candidate["candidate_id"] == item["candidate_id"]
            )
            stage = str(candidate.get("candidate_status", "candidate_pool_only"))
            stages.setdefault(stage, []).append(item["ground_truth_id"])
        result["candidate_pool"] = pool_metrics
        result["shortlist_misses_recovered_by_stage"] = stages
        result["filter_false_negative_count"] = len(stages.get("filtered", []))
        result["shortlist_limit_false_negative_count"] = len(
            stages.get("ranked_out", [])
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure detector candidates against reviewed PDF-point ground truth."
    )
    parser.add_argument("candidates_json")
    parser.add_argument("ground_truth_json")
    parser.add_argument("--symbol-id", required=True)
    parser.add_argument("--match-radius-pt", type=float, default=8.0)
    parser.add_argument("--candidate-pool-json")
    parser.add_argument("--detection-manifest-json")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = evaluate_files(
        candidates_json=args.candidates_json,
        ground_truth_json=args.ground_truth_json,
        symbol_id=args.symbol_id,
        match_radius_pt=args.match_radius_pt,
        candidate_pool_json=args.candidate_pool_json,
        detection_manifest_json=args.detection_manifest_json,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
