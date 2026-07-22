from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp" / "engine"))

from accuracy_benchmark import (  # noqa: E402
    evaluate_candidate_set,
    evaluate_files,
    validate_ground_truth,
)


class AccuracyBenchmarkTests(unittest.TestCase):
    def ground_truth(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "review_complete": True,
            "clarification_required": False,
            "page": 1,
            "detections": [
                {
                    "ground_truth_id": "GT-001",
                    "symbol_id": "DUPLEX_SOCKET_OUTLET",
                    "center_x_pt": 10,
                    "center_y_pt": 10,
                },
                {
                    "ground_truth_id": "GT-002",
                    "symbol_id": "DUPLEX_SOCKET_OUTLET",
                    "center_x_pt": 50,
                    "center_y_pt": 50,
                },
            ],
        }

    def test_metrics_report_false_positive_and_false_negative_ids(self) -> None:
        truth = validate_ground_truth(
            self.ground_truth(), symbol_id="DUPLEX_SOCKET_OUTLET"
        )
        candidates = [
            {"candidate_id": "C001", "center_x_pt": 11, "center_y_pt": 11},
            {"candidate_id": "C002", "center_x_pt": 90, "center_y_pt": 90},
        ]

        result = evaluate_candidate_set(candidates, truth, match_radius_pt=4)

        self.assertEqual(result["true_positive_count"], 1)
        self.assertEqual(result["false_positive_ids"], ["C002"])
        self.assertEqual(result["false_negative_ids"], ["GT-002"])
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)

    def test_incomplete_or_uncertain_ground_truth_is_rejected(self) -> None:
        incomplete = self.ground_truth()
        incomplete["review_complete"] = False
        with self.assertRaisesRegex(ValueError, "review_complete=true"):
            validate_ground_truth(incomplete, symbol_id="DUPLEX_SOCKET_OUTLET")

        uncertain = self.ground_truth()
        uncertain["clarification_required"] = True
        with self.assertRaisesRegex(ValueError, "cannot require clarification"):
            validate_ground_truth(uncertain, symbol_id="DUPLEX_SOCKET_OUTLET")

    def test_candidate_pool_attributes_miss_to_filter_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth_path = root / "truth.json"
            candidates_path = root / "candidates.json"
            pool_path = root / "pool.json"
            truth_payload = self.ground_truth()
            truth_payload["source_pdf_sha256"] = "a" * 64
            truth_path.write_text(json.dumps(truth_payload), encoding="utf-8")
            candidates_path.write_text(
                json.dumps(
                    [
                        {
                            "candidate_id": "C001",
                            "center_x_pt": 10,
                            "center_y_pt": 10,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            pool_path.write_text(
                json.dumps(
                    [
                        {
                            "candidate_id": "C001",
                            "center_x_pt": 10,
                            "center_y_pt": 10,
                            "candidate_status": "shortlisted",
                        },
                        {
                            "candidate_id": "F001",
                            "center_x_pt": 50,
                            "center_y_pt": 50,
                            "candidate_status": "filtered",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            manifest_path = root / "detection_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "symbol_id": "DUPLEX_SOCKET_OUTLET",
                        "page": 1,
                        "pdf_sha256": "a" * 64,
                        "candidates_sha256": hashlib.sha256(
                            candidates_path.read_bytes()
                        ).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_files(
                candidates_json=candidates_path,
                candidate_pool_json=pool_path,
                detection_manifest_json=manifest_path,
                ground_truth_json=truth_path,
                symbol_id="DUPLEX_SOCKET_OUTLET",
                match_radius_pt=4,
            )

            self.assertEqual(result["shortlist"]["recall"], 0.5)
            self.assertTrue(result["source_identity_verified"])
            self.assertEqual(result["candidate_pool"]["recall"], 1.0)
            self.assertEqual(result["filter_false_negative_count"], 1)
            self.assertEqual(
                result["shortlist_misses_recovered_by_stage"],
                {"filtered": ["GT-002"]},
            )


if __name__ == "__main__":
    unittest.main()
