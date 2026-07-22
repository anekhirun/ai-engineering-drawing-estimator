from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

from server import TOOLS, VERSION, confirm_symbol_count  # noqa: E402


class ReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / "drawing.pdf"
        document = fitz.open()
        document.new_page(width=300, height=200)
        document.save(self.pdf)

        self.template = self.root / "template.json"
        self.template.write_text(
            json.dumps({"width_pt": 10, "height_pt": 10}),
            encoding="utf-8",
        )
        self.candidates = self.root / "candidates.json"
        self.candidates.write_text(
            json.dumps(
                [
                    {
                        "candidate_id": "C-0001",
                        "center_x_pt": 50,
                        "center_y_pt": 60,
                        "constellation_error": 0.08,
                        "score": 0.09,
                    },
                    {
                        "candidate_id": "C-0002",
                        "center_x_pt": 150,
                        "center_y_pt": 120,
                        "constellation_error": 0.10,
                        "score": 0.11,
                    },
                ]
            ),
            encoding="utf-8",
        )
        self.detection_manifest = self.root / "detection_manifest.json"
        self.detection_manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "pdf_sha256": hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                    "template_sha256": hashlib.sha256(
                        self.template.read_bytes()
                    ).hexdigest(),
                    "candidates_sha256": hashlib.sha256(
                        self.candidates.read_bytes()
                    ).hexdigest(),
                    "page": 1,
                    "symbol_id": "DUPLEX_SOCKET_OUTLET",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def base_args(self, output_name: str) -> dict[str, object]:
        return {
            "pdf_path": str(self.pdf),
            "template_path": str(self.template),
            "candidates_json": str(self.candidates),
            "detection_manifest_json": str(self.detection_manifest),
            "symbol_id": "DUPLEX_SOCKET_OUTLET",
            "page": 1,
            "dpi": 150,
            "accepted_ids": ["C-0001"],
            "output_dir": str(self.root / output_name),
        }

    def test_complete_review_is_final_and_auditable(self) -> None:
        args = self.base_args("complete")
        args.update(
            {
                "rejected_ids": ["C-0002"],
                "uncertain_ids": [],
                "wall_door_sweep_completed": True,
                "floor_or_region": "GROUND FLOOR",
                "review_notes": "Checked walls, corners, and doors.",
            }
        )

        result = confirm_symbol_count(args)
        report = json.loads(Path(result["report_json"]).read_text(encoding="utf-8"))

        self.assertTrue(result["review_complete"])
        self.assertFalse(result["clarification_required"])
        self.assertEqual(result["unresolved_ids"], [])
        self.assertEqual(report["rejected_ids"], ["C-0002"])
        self.assertEqual(report["floor_or_region"], "GROUND FLOOR")
        self.assertEqual(report["detections"][0]["floor_or_region"], "GROUND FLOOR")
        self.assertTrue(report["provenance_verified"])

    def test_legacy_call_remains_valid_but_not_final(self) -> None:
        result = confirm_symbol_count(self.base_args("legacy"))

        self.assertFalse(result["review_complete"])
        self.assertTrue(result["clarification_required"])
        self.assertEqual(result["unresolved_ids"], ["C-0002"])
        self.assertFalse(result["wall_door_sweep_completed"])
        self.assertIn("unreviewed", result["review_warning"])

    def test_uncertain_candidate_requires_user_clarification(self) -> None:
        args = self.base_args("uncertain")
        args.update(
            {
                "uncertain_ids": ["C-0002"],
                "wall_door_sweep_completed": True,
            }
        )

        result = confirm_symbol_count(args)

        self.assertFalse(result["review_complete"])
        self.assertTrue(result["clarification_required"])
        self.assertEqual(result["uncertain_ids"], ["C-0002"])
        self.assertIn("uncertain", result["review_warning"])

    def test_tampered_candidates_are_rejected_by_provenance_check(self) -> None:
        self.candidates.write_text("[]", encoding="utf-8")
        args = self.base_args("tampered")
        args.update(
            {
                "accepted_ids": [],
                "wall_door_sweep_completed": True,
            }
        )

        with self.assertRaisesRegex(RuntimeError, "provenance mismatch"):
            confirm_symbol_count(args)

    def test_version_and_tool_surface(self) -> None:
        self.assertEqual(VERSION, "0.2.0")
        self.assertEqual(len(TOOLS), 10)
        confirm_tool = next(tool for tool in TOOLS if tool["name"] == "confirm_symbol_count")
        properties = confirm_tool["inputSchema"]["properties"]
        self.assertIn("rejected_ids", properties)
        self.assertIn("wall_door_sweep_completed", properties)
        self.assertIn("prepare_sheet_audit", {tool["name"] for tool in TOOLS})
        self.assertIn("get_discipline_catalog", {tool["name"] for tool in TOOLS})
        audit_tool = next(tool for tool in TOOLS if tool["name"] == "prepare_sheet_audit")
        audit_properties = audit_tool["inputSchema"]["properties"]
        self.assertIn("excluded_regions", audit_properties)
        self.assertIn("included_regions", audit_properties)
        self.assertIn("exclude_annotation_layers", audit_properties)
        self.assertIn("text_overlap_threshold", audit_properties)
        self.assertIn("force_reprocess", audit_properties)
        layer_tool = next(tool for tool in TOOLS if tool["name"] == "analyze_vector_layers")
        layer_properties = layer_tool["inputSchema"]["properties"]
        self.assertIn("signature_mapping_path", layer_properties)
        self.assertEqual(layer_properties["response_detail"]["default"], "compact")
        accuracy_tool = next(
            tool for tool in TOOLS if tool["name"] == "evaluate_detection_accuracy"
        )
        accuracy_properties = accuracy_tool["inputSchema"]["properties"]
        self.assertIn("ground_truth_json", accuracy_properties)
        self.assertIn("candidate_pool_json", accuracy_properties)


if __name__ == "__main__":
    unittest.main()
