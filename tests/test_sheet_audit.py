from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

from server import (  # noqa: E402
    DISCIPLINES,
    SYSTEMS,
    build_symbol_template,
    detect_symbol_candidates,
    get_discipline_catalog,
    get_symbol_rules,
    inspect_drawing,
    prepare_sheet_audit,
)
from sheet_context import clear_context_cache  # noqa: E402


class SheetAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / "fire-alarm-sheet.pdf"
        document = fitz.open()
        page = document.new_page(width=400, height=300)
        for index in range(120):
            x = 10 + (index % 20) * 18
            y = 10 + (index // 20) * 18
            page.draw_line((x, y), (x + 8, y + 8))
        document.save(self.pdf)

    def tearDown(self) -> None:
        clear_context_cache()
        self.temp.cleanup()

    def test_v020_scope_contains_five_project_systems(self) -> None:
        self.assertEqual(
            set(SYSTEMS),
            {"POWER", "FIRE_ALARM", "DATA_VOICE", "CCTV_SECURITY", "LIGHTING"},
        )
        power = get_symbol_rules({"system_id": "POWER"})
        self.assertEqual(
            power["symbol_ids"],
            [
                "DUPLEX_SOCKET_OUTLET",
                "SINGLE_SOCKET_OUTLET",
                "POWER_RECEPTACLE_3P_N_E",
                "NON_FUSE_DISCONNECTING_SWITCH",
            ],
        )
        self.assertNotIn("DATA_OUTLET", power["symbol_ids"])
        self.assertIn(
            "DATA_OUTLET",
            get_symbol_rules({"system_id": "DATA_VOICE"})["symbol_ids"],
        )
        self.assertIn(
            "DUMMY_CCTV_CAMERA",
            get_symbol_rules({"system_id": "CCTV_SECURITY"})["symbol_ids"],
        )
        fire_alarm = get_symbol_rules(
            {"system_id": "FIRE_ALARM", "response_detail": "full"}
        )
        self.assertIn(
            "FIRE_ALARM_MANUAL_STATION_WP", fire_alarm["symbol_ids"]
        )
        self.assertIn(
            "SWT-E-FA",
            fire_alarm["symbols"]["FIRE_ALARM_MANUAL_STATION"]["layer_tokens"],
        )
        lighting = get_symbol_rules({"system_id": "LIGHTING"})["symbol_ids"]
        self.assertIn("ONE_WAY_LIGHTING_SWITCH", lighting)
        self.assertIn("LIGHTING_SWITCH_BANK", lighting)
        self.assertIn("SELF_CONTAINED_EMERGENCY_LIGHT_2X9W", lighting)
        self.assertIn("LED_RECESSED_DIFFUSER_2X10W_2X20W", lighting)
        self.assertIn("LED_SURFACE_WEATHERPROOF_IP65_10W_20W", lighting)

    def test_discipline_catalog_separates_active_scope_from_roadmap(self) -> None:
        catalog = get_discipline_catalog({})

        self.assertEqual(catalog["product"], "TakeoffLens")
        self.assertEqual(set(catalog["active_discipline_ids"]), {"ELECTRICAL", "ELV"})
        self.assertIn("MECHANICAL", catalog["planned_discipline_ids"])
        self.assertEqual(DISCIPLINES["PLUMBING"]["status"], "planned")
        self.assertEqual(
            get_discipline_catalog({"discipline_id": "ELECTRICAL"})["system_ids"],
            ["POWER", "LIGHTING"],
        )

    def test_symbol_rules_are_compact_by_default(self) -> None:
        compact = get_symbol_rules({"system_id": "LIGHTING"})
        full = get_symbol_rules({"system_id": "LIGHTING", "response_detail": "full"})
        compact_bytes = len(json.dumps(compact, ensure_ascii=False).encode("utf-8"))
        full_bytes = len(json.dumps(full, ensure_ascii=False).encode("utf-8"))

        self.assertLess(compact_bytes, full_bytes * 0.65)
        self.assertIn("template_ready", next(iter(compact["symbols"].values())))
        self.assertIn("visual_rule", next(iter(full["symbols"].values())))

    def test_page_profiler_v2_reports_evidence(self) -> None:
        inspection = inspect_drawing({"pdf_path": str(self.pdf)})
        profile = inspection["pages"][0]

        self.assertEqual(profile["profile_version"], "2")
        self.assertEqual(profile["classification"], "vector_clean")
        self.assertTrue(profile["automatic_matching_supported"])
        self.assertGreater(profile["classification_confidence"], 0.9)
        self.assertIn("classification_reason", profile)

    def test_simple_vector_symbol_can_build_a_warned_template(self) -> None:
        pdf = self.root / "simple-symbol.pdf"
        document = fitz.open()
        page = document.new_page(width=150, height=150)
        page.draw_line((50, 50), (50, 100))
        page.draw_line((45, 75), (55, 75))
        document.save(pdf)
        document.close()

        output = self.root / "simple-template.json"
        result = build_symbol_template(
            {
                "pdf_path": str(pdf),
                "page": 1,
                "roi_pdf_points": [40, 40, 60, 110],
                "symbol_id": "DUPLEX_SOCKET_OUTLET",
                "output_path": str(output),
            }
        )
        self.assertGreaterEqual(result["compound_part_count"], 1)
        self.assertLess(result["compound_part_count"], 3)
        self.assertTrue(output.is_file())
        template = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(template["template_schema_version"], "2")
        self.assertEqual(template["symbol_id"], "DUPLEX_SOCKET_OUTLET")

    def test_template_symbol_mismatch_stops_detection(self) -> None:
        template = self.root / "wrong-symbol.json"
        template.write_text(
            json.dumps({"symbol_id": "DATA_OUTLET"}), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "not DUPLEX_SOCKET_OUTLET"):
            detect_symbol_candidates(
                {
                    "pdf_path": str(self.pdf),
                    "symbol_id": "DUPLEX_SOCKET_OUTLET",
                    "template_path": str(template),
                    "output_dir": str(self.root / "mismatch"),
                }
            )

    def test_fire_alarm_sheet_is_prepared_in_one_call(self) -> None:
        output = self.root / "audit"
        result = prepare_sheet_audit(
            {
                "pdf_path": str(self.pdf),
                "system_id": "FIRE_ALARM",
                "page": 1,
                "overview_dpi": 100,
                "output_dir": str(output),
                "response_detail": "full",
            }
        )

        self.assertEqual(result["system_id"], "FIRE_ALARM")
        self.assertEqual(len(result["template_required"]), 11)
        self.assertTrue(result["clarification_required"])
        self.assertTrue(Path(result["overview"]["output_path"]).is_file())
        manifest = json.loads(
            Path(result["manifest_json"]).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["candidate_count"], 0)
        self.assertTrue(manifest["shared_context"])
        self.assertEqual(manifest["page_profile"]["profile_version"], "2")
        self.assertIn("timing_seconds", manifest)
        self.assertLess(result["elapsed_seconds"], 10)

    def test_power_audit_reuses_one_context_for_all_symbols_and_cache(self) -> None:
        first = prepare_sheet_audit(
            {
                "pdf_path": str(self.pdf),
                "system_id": "POWER",
                "page": 1,
                "dpi": 150,
                "overview_dpi": 100,
                "output_dir": str(self.root / "power-first"),
                "response_detail": "full",
            }
        )
        second = prepare_sheet_audit(
            {
                "pdf_path": str(self.pdf),
                "system_id": "POWER",
                "page": 1,
                "dpi": 150,
                "overview_dpi": 100,
                "output_dir": str(self.root / "power-second"),
                "response_detail": "full",
            }
        )

        self.assertEqual(len(first["runs"]), 2)
        self.assertFalse(first["context_cache_hit"])
        self.assertTrue(second["context_cache_hit"])
        self.assertEqual(first["context_id"], second["context_id"])
        for run in first["runs"]:
            self.assertEqual(run["diagnostics"]["context_id"], first["context_id"])
            self.assertEqual(run["diagnostics"]["pipeline_version"], "native_v3")
            self.assertEqual(run["diagnostics"]["candidate_filter_version"], "3")
            self.assertIn("template_validation", run["diagnostics"])
            self.assertTrue(Path(run["filtered_candidates_json"]).is_file())
            self.assertTrue(Path(run["candidate_pool_json"]).is_file())
            detection_manifest = json.loads(
                Path(run["detection_manifest_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual(detection_manifest["schema_version"], "1")
            self.assertEqual(detection_manifest["symbol_id"], run["symbol_id"])
            self.assertEqual(len(detection_manifest["pdf_sha256"]), 64)
            self.assertEqual(len(detection_manifest["candidates_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
