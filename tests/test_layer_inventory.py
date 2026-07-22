from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import fitz


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp" / "engine"))

from layer_inventory import analyze_layer_signatures  # noqa: E402


class LayerInventoryTests(unittest.TestCase):
    def test_rotation_normalization_mapping_and_ambiguity_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            context = SimpleNamespace(
                pdf_path=root / "fixture.pdf",
                page_number=1,
                context_id="fixture-context",
                drawings=[
                    {"layer": "SWT-E-LIGHTING", "rect": fitz.Rect(10, 10, 10, 78), "fill": None},
                    {"layer": "SWT-E-LIGHTING", "rect": fitz.Rect(30, 30, 98, 30), "fill": None},
                    {"layer": "SWT-E-LIGHTING", "rect": fitz.Rect(110, 10, 121.5, 78), "fill": None},
                    {"layer": "SWT-E-TEXT", "rect": fitz.Rect(10, 100, 10, 168), "fill": None},
                ],
            )
            mappings = [
                {
                    "symbol_id": "SURFACE",
                    "layer_contains": "LIGHTING",
                    "shape_family": "line",
                    "short_extent_pt": 0,
                    "long_extent_pt": 68,
                    "tolerance_pt": 0.6,
                },
                {
                    "symbol_id": "RECESSED",
                    "layer_contains": "LIGHTING",
                    "shape_family": "elongated",
                    "short_extent_pt": 11.5,
                    "long_extent_pt": 68,
                    "tolerance_pt": 0.6,
                },
            ]
            result = analyze_layer_signatures(
                context,
                layer_tokens=["SWT-E"],
                signature_mappings=mappings,
                output_dir=root / "output",
            )

            self.assertEqual(result["mapped_counts"], {"RECESSED": 1, "SURFACE": 2})
            self.assertEqual(result["filtered_drawing_paths"], 3)
            self.assertFalse(result["clarification_required"])
            self.assertTrue(Path(result["inventory_json"]).is_file())
            mapped = json.loads(Path(result["mapped_candidates_json"]).read_text(encoding="utf-8"))
            self.assertEqual(sum(item["count"] for item in mapped), 3)

            ambiguous = analyze_layer_signatures(
                context,
                layer_tokens=["LIGHTING"],
                signature_mappings=[
                    mappings[0],
                    {**mappings[0], "symbol_id": "OTHER"},
                    mappings[1],
                ],
                output_dir=root / "ambiguous",
            )
            self.assertTrue(ambiguous["clarification_required"])
            self.assertEqual(ambiguous["mapped_counts"], {"RECESSED": 1})
            self.assertEqual(len(ambiguous["ambiguous_signature_ids"]), 1)


if __name__ == "__main__":
    unittest.main()
