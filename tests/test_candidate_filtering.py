from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp" / "engine"))

from detect_compound_symbol import (  # noqa: E402
    Candidate,
    has_wp_context,
    layer_filter_evidence,
    nms,
    normalize_included_regions,
    text_overlap_ratio,
)
from vector_core import Primitive  # noqa: E402


def primitive(layer: str) -> Primitive:
    points = np.asarray([[2.0, 2.0], [8.0, 8.0]], dtype=np.float32)
    return Primitive(points, (2.0, 2.0, 8.0, 8.0), 8.5, layer, 0.25)


class CandidateFilteringTests(unittest.TestCase):
    def test_wp_context_requires_a_complete_token(self) -> None:
        self.assertTrue(has_wp_context("B WP"))
        self.assertTrue(has_wp_context("wp / outdoor"))
        self.assertFalse(has_wp_context("SWITCH_POWER"))
        self.assertFalse(has_wp_context("WPS"))

    def test_filtered_candidate_cannot_hide_clean_overlapping_candidate(self) -> None:
        common = {
            "center_x_pt": 10.0,
            "center_y_pt": 10.0,
            "geometry_score": 0.1,
            "final_score": 0.1,
            "rotation": 0,
            "primitive_count": 4,
        }
        filtered = Candidate(
            candidate_id="filtered",
            constellation_error=0.01,
            score=0.01,
            filter_reasons=["pdf_text_overlaps_candidate_roi"],
            **common,
        )
        clean = Candidate(
            candidate_id="clean",
            constellation_error=0.1,
            score=0.1,
            filter_reasons=[],
            **common,
        )

        kept = nms([filtered, clean], distance=5)

        self.assertEqual([item.candidate_id for item in kept], ["clean"])

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
