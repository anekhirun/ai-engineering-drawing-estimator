from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp" / "engine"))

from detect_compound_symbol import (  # noqa: E402
    layer_filter_evidence,
    normalize_included_regions,
    text_overlap_ratio,
)
from vector_core import Primitive  # noqa: E402


def primitive(layer: str) -> Primitive:
    points = np.asarray([[2.0, 2.0], [8.0, 8.0]], dtype=np.float32)
    return Primitive(points, (2.0, 2.0, 8.0, 8.0), 8.5, layer, 0.25)


class CandidateFilteringTests(unittest.TestCase):
    def test_annotation_only_geometry_is_suppressed(self) -> None:
        evidence = layer_filter_evidence(
            [
                primitive("SWT-E-TEXT"),
                primitive("SWT-S-DIM"),
                primitive("acm-CT-ANNO-TTB_2"),
            ],
            [0, 0, 10, 10],
        )

        self.assertTrue(evidence["suppress"])
        self.assertEqual(evidence["annotation_fraction"], 1.0)

    def test_symbol_layer_prevents_annotation_suppression(self) -> None:
        evidence = layer_filter_evidence(
            [
                primitive("SWT-E-TEXT"),
                primitive("SWT-S-DIM"),
                primitive("SWT-E-OUTLET"),
            ],
            [0, 0, 10, 10],
        )

        self.assertFalse(evidence["suppress"])
        self.assertEqual(evidence["symbol_primitive_count"], 1)

    def test_project_specific_layer_tokens_are_supported(self) -> None:
        evidence = layer_filter_evidence(
            [primitive("SWT-E-OUTLET"), primitive("SWT-E-TEXT")],
            [0, 0, 10, 10],
            symbol_tokens=["OUTLET"],
        )

        self.assertEqual(evidence["symbol_primitive_count"], 1)

    def test_pdf_text_coverage_uses_whole_candidate_roi(self) -> None:
        ratio = text_overlap_ratio([0, 0, 10, 10], [(4, 0, 10, 10)], padding=0)

        self.assertAlmostEqual(ratio, 0.6)

    def test_included_regions_use_existing_rectangle_validation(self) -> None:
        self.assertEqual(
            normalize_included_regions([[1, 2, 30, 40]]),
            [[1.0, 2.0, 30.0, 40.0]],
        )
        with self.assertRaises(ValueError):
            normalize_included_regions([[10, 10, 5, 20]])


if __name__ == "__main__":
    unittest.main()
