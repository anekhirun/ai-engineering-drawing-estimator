from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

from server import SYSTEMS, get_symbol_rules, prepare_sheet_audit  # noqa: E402


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
        self.temp.cleanup()

    def test_v013_scope_contains_only_power_and_fire_alarm(self) -> None:
        self.assertEqual(set(SYSTEMS), {"POWER", "FIRE_ALARM"})
        power = get_symbol_rules({"system_id": "POWER"})
        self.assertEqual(
            power["symbol_ids"],
            ["DUPLEX_SOCKET_OUTLET", "SINGLE_SOCKET_OUTLET"],
        )
        self.assertNotIn("DATA_OUTLET", power["symbol_ids"])

    def test_fire_alarm_sheet_is_prepared_in_one_call(self) -> None:
        output = self.root / "audit"
        result = prepare_sheet_audit(
            {
                "pdf_path": str(self.pdf),
                "system_id": "FIRE_ALARM",
                "page": 1,
                "overview_dpi": 100,
                "output_dir": str(output),
            }
        )

        self.assertEqual(result["system_id"], "FIRE_ALARM")
        self.assertEqual(len(result["template_required"]), 8)
        self.assertTrue(result["clarification_required"])
        self.assertTrue(Path(result["overview"]["output_path"]).is_file())
        manifest = json.loads(
            Path(result["manifest_json"]).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["candidate_count"], 0)
        self.assertLess(result["elapsed_seconds"], 10)


if __name__ == "__main__":
    unittest.main()
