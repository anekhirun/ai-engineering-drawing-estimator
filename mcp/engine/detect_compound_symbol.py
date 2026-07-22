from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

from sheet_context import SheetContext, get_sheet_context
from vector_core import (
    best_rotation_score,
    primitive_points_in_roi,
    points_to_mask,
)


@dataclass
class Candidate:
    candidate_id: str
    center_x_pt: float
    center_y_pt: float
    constellation_error: float
    score: float
    geometry_score: float
    final_score: float
    rotation: int
    primitive_count: int
    detection_method: str = "pdf_vector_compound_match"
    score_version: str = "native_v2"
    text_overlap_penalty: float = 0.0
    annotation_layer_penalty: float = 0.0
    excluded_region_penalty: float = 0.0
    source_layers: list[str] | None = None
    filter_reasons: list[str] | None = None
    crop_file: str = ""


ANNOTATION_LAYER_TOKENS = (
    "TEXT", "DIM", "ANNO", "TITLE", "TTLN", "NOTE", "SPEC", "GRID",
    "HATCH", "PHASING", "KEY  LOCATION", "KEY LOCATION",
)
SYMBOL_LAYER_TOKENS = (
    "OUTLET", "SOCKET", "RECEPT", "POWER", "POWR", "DEVICE", "SYMBOL",
)


def angle_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


def rel_error(a, b):
    return abs(a - b) / max(abs(b), 1e-6)


def rotated_offset(target, roi_w, roi_h, rotation):
    tx = target["cx"] - 0.5
    ty = target["cy"] - 0.5
    if rotation == 90:
        tx, ty = -ty, tx
    elif rotation == 180:
        tx, ty = -tx, -ty
    elif rotation == 270:
        tx, ty = ty, -tx
    return tx * roi_w, ty * roi_h


def compare_part(candidate, target, roi_w, roi_h, center_x, center_y, rotation):
    # Rotate target normalized position around center.
    offset_x, offset_y = rotated_offset(target, roi_w, roi_h, rotation)
    expected_x = center_x + offset_x
    expected_y = center_y + offset_y

    position_error = math.hypot(
        (candidate["cx"] - expected_x) / max(roi_w, 1e-6),
        (candidate["cy"] - expected_y) / max(roi_h, 1e-6),
    )

    expected_w = target["width"] * (roi_h if rotation in (90, 270) else roi_w)
    expected_h = target["height"] * (roi_w if rotation in (90, 270) else roi_h)
    expected_len = target["length"] * math.hypot(roi_w, roi_h)
    expected_angle = (target["angle"] + rotation) % 180

    shape_error = np.mean([
        rel_error(candidate["width"], expected_w),
        rel_error(candidate["height"], expected_h),
        rel_error(candidate["length"], expected_len),
        angle_diff(candidate["angle"], expected_angle) / 90.0,
    ])
    return 0.58 * position_error + 0.42 * shape_error


def constellation_error(local_desc, parts, roi_w, roi_h, cx, cy):
    best_rotation_error = 999.0
    best_rotation = 0

    for rotation in (0, 90, 180, 270):
        errors = []
        used = set()
        for target in parts:
            choices = []
            for idx, cand in enumerate(local_desc):
                if idx in used:
                    continue
                choices.append((
                    compare_part(cand, target, roi_w, roi_h, cx, cy, rotation),
                    idx,
                ))
            if not choices:
                errors.append(2.0)
                continue
            error, index = min(choices)
            used.add(index)
            errors.append(error)

        mean_error = float(np.mean(sorted(errors)[:max(3, len(parts) - 1)]))
        if mean_error < best_rotation_error:
            best_rotation_error = mean_error
            best_rotation = rotation

    return best_rotation_error, best_rotation


def nms(candidates, distance):
    kept = []
    for c in sorted(candidates, key=lambda x: (x.score, x.constellation_error)):
        if all(
            math.hypot(c.center_x_pt - k.center_x_pt, c.center_y_pt - k.center_y_pt)
            >= distance
            for k in kept
        ):
            kept.append(c)
    return kept


def center_overlaps_text(cx, cy, boxes, padding=0.8):
    return any(
        x1 - padding <= cx <= x2 + padding
        and y1 - padding <= cy <= y2 + padding
        for x1, y1, x2, y2 in boxes
    )


def save_outputs(image, candidates, template, output, dpi, suppressed=None):
    output.mkdir(parents=True, exist_ok=True)
    crops = output / "crops"
    crops.mkdir(exist_ok=True)
    scale = dpi / 72.0
    marked = image.copy()
    records = []

    for i, c in enumerate(candidates, 1):
        c.candidate_id = f"C{i:03d}"
        hw = template["width_pt"] * 1.8
        hh = template["height_pt"] * 1.8
        x1 = max(0, round((c.center_x_pt - hw) * scale))
        y1 = max(0, round((c.center_y_pt - hh) * scale))
        x2 = min(image.shape[1], round((c.center_x_pt + hw) * scale))
        y2 = min(image.shape[0], round((c.center_y_pt + hh) * scale))

        name = f"{c.candidate_id}.png"
        cv2.imwrite(str(crops / name), image[y1:y2, x1:x2])
        c.crop_file = f"crops/{name}"
        cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(
            marked, f"{c.candidate_id} {c.score:.3f}",
            (x1, max(22, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2
        )
        records.append(asdict(c))

    cv2.imwrite(str(output / "marked_candidates.png"), marked)
    (output / "candidates.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    suppressed_records = []
    filtered_crops = output / "filtered_crops"
    filtered_crops.mkdir(exist_ok=True)
    filtered_marked = image.copy()
    for i, candidate in enumerate(suppressed or [], 1):
        candidate.candidate_id = f"F{i:03d}"
        hw = template["width_pt"] * 1.8
        hh = template["height_pt"] * 1.8
        x1 = max(0, round((candidate.center_x_pt - hw) * scale))
        y1 = max(0, round((candidate.center_y_pt - hh) * scale))
        x2 = min(image.shape[1], round((candidate.center_x_pt + hw) * scale))
        y2 = min(image.shape[0], round((candidate.center_y_pt + hh) * scale))
        name = f"{candidate.candidate_id}.png"
        cv2.imwrite(str(filtered_crops / name), image[y1:y2, x1:x2])
        candidate.crop_file = f"filtered_crops/{name}"
        cv2.rectangle(filtered_marked, (x1, y1), (x2, y2), (0, 165, 255), 3)
        cv2.putText(
            filtered_marked,
            candidate.candidate_id,
            (x1, max(22, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 165, 255),
            2,
        )
        suppressed_records.append(asdict(candidate))
    cv2.imwrite(str(output / "filtered_candidates.png"), filtered_marked)
    (output / "filtered_candidates.json").write_text(
        json.dumps(suppressed_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fields = list(records[0].keys()) if records else [
        "candidate_id", "center_x_pt", "center_y_pt",
        "constellation_error", "score", "rotation",
        "primitive_count", "crop_file"
    ]
    with (output / "candidates.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    cards = "".join(
        f'<article><img src="{html.escape(c.crop_file)}"><div><b>{c.candidate_id}</b>'
        f'<p>Score {c.score:.4f}</p><p>Constellation {c.constellation_error:.4f}</p>'
        f'<p>Rotation {c.rotation}°</p></div></article>'
        for c in candidates
    )
    review = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    body{{font-family:Arial;margin:24px}}main{{display:grid;grid-template-columns:
    repeat(auto-fill,minmax(310px,1fr));gap:14px}}article{{display:flex;gap:12px;
    border:1px solid #aaa;padding:10px;border-radius:8px}}img{{width:160px;height:
    160px;object-fit:contain;border:1px solid #ddd}}</style></head><body>
    <h1>AI Engineering Drawing Estimator v0.1.5 Candidate Review</h1>
    <p>Shortlist: {len(candidates)} - review before reporting quantity.</p>
    <main>{cards}</main></body></html>"""
    (output / "review.html").write_text(review, encoding="utf-8")


def write_interactive_review(candidates, output):
    cards = "".join(
        f'<article id="card-{c.candidate_id}" data-id="{c.candidate_id}">'
        f'<img src="{html.escape(c.crop_file)}"><div><b>{c.candidate_id}</b>'
        f'<p>Score {c.score:.4f}</p><p>Constellation {c.constellation_error:.4f}</p>'
        f'<p>Rotation {c.rotation} deg</p><div class="buttons">'
        f'<button onclick="setDecision(\'{c.candidate_id}\',\'accept\')">Accept</button>'
        f'<button onclick="setDecision(\'{c.candidate_id}\',\'reject\')">Reject</button>'
        f'<button onclick="setDecision(\'{c.candidate_id}\',\'uncertain\')">Uncertain</button>'
        f'</div></div></article>'
        for c in candidates
    )
    review = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    body{{font-family:Arial;margin:24px}}main{{display:grid;grid-template-columns:
    repeat(auto-fill,minmax(310px,1fr));gap:14px}}article{{display:flex;gap:12px;
    border:2px solid #aaa;padding:10px;border-radius:8px}}img{{width:160px;height:
    160px;object-fit:contain;border:1px solid #ddd}}button{{margin:2px;padding:6px}}
    article.accept{{border-color:#159447;background:#effbf3}}
    article.reject{{border-color:#c9302c;background:#fff1f0}}
    article.uncertain{{border-color:#d28b00;background:#fff9e8}}
    .toolbar{{position:sticky;top:0;background:white;padding:10px 0;z-index:2}}
    </style></head><body>
    <h1>AI Engineering Drawing Estimator v0.1.5 Candidate Review</h1>
    <p>Shortlist: {len(candidates)} - review before reporting quantity.</p>
    <div class="toolbar"><b id="counts"></b>
    <button onclick="exportDecisions()">Export decisions.json</button></div>
    <main>{cards}</main><script>
    const storageKey = 'v014-decisions-' + location.pathname;
    const decisions = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
    function paint(id) {{
      const card = document.getElementById('card-' + id);
      card.classList.remove('accept','reject','uncertain');
      if (decisions[id]) card.classList.add(decisions[id]);
    }}
    function refreshCounts() {{
      const values = Object.values(decisions);
      const count = x => values.filter(v => v === x).length;
      document.getElementById('counts').textContent =
        `Accepted ${{count('accept')}} | Rejected ${{count('reject')}} | ` +
        `Uncertain ${{count('uncertain')}} | Unreviewed ${{{len(candidates)} - values.length}}`;
    }}
    function setDecision(id, value) {{
      decisions[id] = value;
      localStorage.setItem(storageKey, JSON.stringify(decisions));
      paint(id); refreshCounts();
    }}
    function exportDecisions() {{
      const payload = JSON.stringify({{decisions}}, null, 2);
      const link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([payload], {{type:'application/json'}}));
      link.download = 'decisions.json'; link.click(); URL.revokeObjectURL(link.href);
    }}
    Object.keys(decisions).forEach(paint); refreshCounts();
    </script></body></html>"""
    (output / "review.html").write_text(review, encoding="utf-8")


def validate_template(template: dict) -> dict:
    required = {"mask", "grid_size", "width_pt", "height_pt", "compound_parts"}
    missing = sorted(required - set(template))
    if missing:
        raise ValueError(f"Template is missing required fields: {missing}")
    if float(template["width_pt"]) <= 0 or float(template["height_pt"]) <= 0:
        raise ValueError("Template width_pt and height_pt must be positive")
    if int(template["grid_size"]) < 16:
        raise ValueError("Template grid_size must be at least 16")
    part_count = len(template["compound_parts"])
    warnings = []
    if part_count < 3:
        warnings.append("Template has fewer than three compound parts and may be ambiguous.")
    return {
        "valid": True,
        "compound_part_count": part_count,
        "warnings": warnings,
    }


def normalize_excluded_regions(regions) -> list[list[float]]:
    normalized = []
    for index, region in enumerate(regions or [], 1):
        if len(region) != 4:
            raise ValueError(
                f"excluded_regions item {index} must be [x1, y1, x2, y2]"
            )
        x1, y1, x2, y2 = map(float, region)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(
                f"excluded_regions item {index} must have x2>x1 and y2>y1"
            )
        normalized.append([x1, y1, x2, y2])
    return normalized


def normalize_included_regions(regions) -> list[list[float]]:
    return normalize_excluded_regions(regions)


def _center_in_regions(cx: float, cy: float, regions) -> bool:
    return any(
        len(region) == 4
        and float(region[0]) <= cx <= float(region[2])
        and float(region[1]) <= cy <= float(region[3])
        for region in regions
    )


def _intersection_area(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[3], b[3]) - max(a[1], b[1])
    )


def text_overlap_ratio(roi, boxes, padding=0.4) -> float:
    """Return bounded text coverage of a candidate ROI in PDF points."""
    x1, y1, x2, y2 = map(float, roi)
    area = max((x2 - x1) * (y2 - y1), 1e-6)
    overlap = 0.0
    for bx1, by1, bx2, by2 in boxes:
        expanded = (
            float(bx1) - padding,
            float(by1) - padding,
            float(bx2) + padding,
            float(by2) + padding,
        )
        overlap += _intersection_area((x1, y1, x2, y2), expanded)
    return min(overlap / area, 1.0)


def _layer_has_token(layer: str, tokens) -> bool:
    value = str(layer or "").upper()
    return any(token in value for token in tokens)


def layer_filter_evidence(primitives, roi, symbol_tokens=None) -> dict:
    """Classify only primitives that contribute points inside the scoring ROI."""
    layers = []
    annotation_count = 0
    symbol_count = 0
    attributed_count = 0
    x1, y1, x2, y2 = roi
    active_symbol_tokens = tuple(symbol_tokens or SYMBOL_LAYER_TOKENS)
    for primitive in primitives:
        points = primitive.points
        inside = (
            (points[:, 0] >= x1) & (points[:, 0] <= x2)
            & (points[:, 1] >= y1) & (points[:, 1] <= y2)
        )
        if not bool(inside.any()):
            continue
        layer = str(getattr(primitive, "layer", "") or "")
        if not layer or layer in {"0", "00"}:
            continue
        attributed_count += 1
        if layer not in layers:
            layers.append(layer)
        if _layer_has_token(layer, active_symbol_tokens):
            symbol_count += 1
        elif _layer_has_token(layer, ANNOTATION_LAYER_TOKENS):
            annotation_count += 1
    annotation_fraction = (
        annotation_count / attributed_count if attributed_count else 0.0
    )
    return {
        "source_layers": sorted(layers),
        "attributed_primitive_count": attributed_count,
        "annotation_primitive_count": annotation_count,
        "symbol_primitive_count": symbol_count,
        "annotation_fraction": annotation_fraction,
        "suppress": (
            attributed_count >= 3
            and symbol_count == 0
            and annotation_fraction >= 0.85
        ),
    }


def detect_with_context(
    context: SheetContext,
    template_path: str | Path,
    output: str | Path,
    *,
    constellation_tolerance: float = 0.24,
    max_score: float = 0.16,
    search_x_max: float = 0.74,
    seed_step: float = 1.5,
    anchor_length_tolerance: float = 0.18,
    anchor_angle_tolerance: float = 10.0,
    shortlist_limit: int = 20,
    exclude_text: bool = True,
    exclude_annotation_layers: bool = True,
    text_overlap_threshold: float = 0.35,
    excluded_regions=None,
    included_regions=None,
    preferred_layer_tokens=None,
    context_cache_hit: bool = False,
) -> dict:
    started = time.perf_counter()
    template_path = Path(template_path).resolve()
    template_bytes = template_path.read_bytes()
    template = json.loads(template_bytes.decode("utf-8"))
    template_validation = validate_template(template)
    template_hash = hashlib.sha256(template_bytes).hexdigest()[:16]
    template_mask = np.asarray(template["mask"], dtype=np.uint8)
    grid_size = int(template["grid_size"])
    roi_w = float(template["width_pt"])
    roi_h = float(template["height_pt"])
    excluded_regions = normalize_excluded_regions(excluded_regions)
    included_regions = normalize_included_regions(included_regions)
    if not 0.0 <= float(text_overlap_threshold) <= 1.0:
        raise ValueError("text_overlap_threshold must be between 0 and 1")

    page = context.page
    primitives = context.primitives
    abs_desc = context.descriptors
    spatial_index = context.spatial_index
    text_bboxes = context.text_bboxes if exclude_text else []
    preferred_layer_tokens = tuple(preferred_layer_tokens or ())
    page_has_preferred_layers = bool(preferred_layer_tokens) and any(
        _layer_has_token(getattr(item, "layer", ""), preferred_layer_tokens)
        for item in primitives
    )

    anchor_parts = sorted(
        template["compound_parts"], key=lambda part: part["length"], reverse=True
    )[:2]
    seeds = {}
    for descriptor in abs_desc:
        for target in anchor_parts:
            expected_length = target["length"] * math.hypot(roi_w, roi_h)
            if rel_error(descriptor["length"], expected_length) > anchor_length_tolerance:
                continue
            for rotation in (0, 90, 180, 270):
                expected_angle = (target["angle"] + rotation) % 180
                if angle_diff(descriptor["angle"], expected_angle) > anchor_angle_tolerance:
                    continue
                offset_x, offset_y = rotated_offset(target, roi_w, roi_h, rotation)
                center_x = descriptor["cx"] - offset_x
                center_y = descriptor["cy"] - offset_y
                if not (0 <= center_x <= page.rect.width * search_x_max):
                    continue
                if not (page.rect.height * 0.02 <= center_y <= page.rect.height * 0.96):
                    continue
                key = (round(center_x / seed_step), round(center_y / seed_step))
                seeds[key] = (center_x, center_y)
    seeded_at = time.perf_counter()

    constellation_matches = []
    for cx, cy in seeds.values():
        roi = [
            cx - roi_w * 0.65,
            cy - roi_h * 0.65,
            cx + roi_w * 0.65,
            cy + roi_h * 0.65,
        ]
        local_indices = spatial_index.query_contained(roi, primitives)
        if len(local_indices) < 3 or len(local_indices) > 80:
            continue
        local_desc = [abs_desc[index] for index in local_indices]
        c_error, rotation = constellation_error(
            local_desc, template["compound_parts"], roi_w, roi_h, cx, cy
        )
        if c_error <= constellation_tolerance:
            constellation_matches.append((cx, cy, c_error, rotation, local_indices))
    constellation_at = time.perf_counter()

    scored_candidates = []
    excluded_region_filtered_count = 0
    included_region_filtered_count = 0
    for cx, cy, c_error, rotation, local_indices in constellation_matches:
        if _center_in_regions(cx, cy, excluded_regions):
            excluded_region_filtered_count += 1
            continue
        if included_regions and not _center_in_regions(cx, cy, included_regions):
            included_region_filtered_count += 1
            continue
        roi = [cx - roi_w / 2, cy - roi_h / 2, cx + roi_w / 2, cy + roi_h / 2]
        selected = [primitives[index] for index in local_indices]
        overlap_ratio = text_overlap_ratio(roi, text_bboxes) if text_bboxes else 0.0
        layer_evidence = layer_filter_evidence(
            selected, roi, preferred_layer_tokens or None
        )
        points = primitive_points_in_roi(selected, roi)
        mask = points_to_mask(points, roi, grid_size=grid_size)
        geometry_score, mask_rotation = best_rotation_score(template_mask, mask)
        if geometry_score <= max_score:
            final_score = 0.65 * float(geometry_score) + 0.35 * float(c_error)
            filter_reasons = []
            if exclude_text and overlap_ratio >= text_overlap_threshold:
                filter_reasons.append("pdf_text_overlaps_candidate_roi")
            if exclude_annotation_layers and layer_evidence["suppress"]:
                filter_reasons.append("annotation_only_vector_layers")
            if (
                exclude_annotation_layers
                and page_has_preferred_layers
                and layer_evidence["symbol_primitive_count"] == 0
            ):
                filter_reasons.append("outside_preferred_symbol_layers")
            candidate = Candidate(
                candidate_id="",
                center_x_pt=float(cx),
                center_y_pt=float(cy),
                constellation_error=float(c_error),
                score=float(geometry_score),
                geometry_score=float(geometry_score),
                final_score=final_score,
                rotation=int(mask_rotation),
                primitive_count=len(selected),
                text_overlap_penalty=float(overlap_ratio),
                annotation_layer_penalty=float(
                    layer_evidence["annotation_fraction"]
                ),
                source_layers=layer_evidence["source_layers"],
                filter_reasons=filter_reasons,
            )
            scored_candidates.append(candidate)

    pre_filter_candidates = nms(
        scored_candidates, min(roi_w, roi_h) * 0.65
    )
    suppressed_candidates = [
        item for item in pre_filter_candidates if item.filter_reasons
    ]
    raw_candidates = [
        item for item in pre_filter_candidates if not item.filter_reasons
    ]
    text_filtered_count = sum(
        "pdf_text_overlaps_candidate_roi" in (item.filter_reasons or [])
        for item in suppressed_candidates
    )
    annotation_layer_filtered_count = sum(
        "annotation_only_vector_layers" in (item.filter_reasons or [])
        for item in suppressed_candidates
    )
    preferred_layer_filtered_count = sum(
        "outside_preferred_symbol_layers" in (item.filter_reasons or [])
        for item in suppressed_candidates
    )
    # Preserve the v0.1.3 shortlist order so optimization cannot silently hide a
    # previously visible high-recall candidate. final_score is diagnostic in
    # v0.1.5 until it has drawing-backed regression evidence.
    ranked = sorted(raw_candidates, key=lambda item: (item.score, item.constellation_error))
    candidates = ranked[:shortlist_limit] if shortlist_limit > 0 else ranked
    output_path = Path(output).resolve()
    save_outputs(
        context.image, candidates, template, output_path, context.dpi,
        suppressed_candidates,
    )
    write_interactive_review(candidates, output_path)
    finished = time.perf_counter()

    diagnostics = {
        "pipeline_version": "native_v2",
        "candidate_filter_version": "2",
        "page_has_preferred_layers": page_has_preferred_layers,
        "preferred_layer_tokens": list(preferred_layer_tokens),
        "context_id": context.context_id,
        "context_cache_hit": context_cache_hit,
        "page_profile": context.profile,
        "template_hash": template_hash,
        "template_validation": template_validation,
        "primitive_count": len(primitives),
        "seed_count": len(seeds),
        "constellation_match_count": len(constellation_matches),
        "pre_filter_candidate_count": len(pre_filter_candidates),
        "raw_candidate_count": len(raw_candidates),
        "shortlist_count": len(candidates),
        "parameters": {
            "constellation_tolerance": constellation_tolerance,
            "max_score": max_score,
            "search_x_max": search_x_max,
            "shortlist_limit": shortlist_limit,
            "exclude_text": exclude_text,
            "exclude_annotation_layers": exclude_annotation_layers,
            "text_overlap_threshold": text_overlap_threshold,
            "excluded_regions": excluded_regions,
            "included_regions": included_regions,
            "text_filtered_count": text_filtered_count,
            "annotation_layer_filtered_count": annotation_layer_filtered_count,
            "preferred_layer_filtered_count": preferred_layer_filtered_count,
            "excluded_region_filtered_count": excluded_region_filtered_count,
            "included_region_filtered_count": included_region_filtered_count,
            "suppressed_candidate_count": len(suppressed_candidates),
        },
        "timing_seconds": {
            "shared_context_preparation": context.preparation_seconds,
            "seed_generation": round(seeded_at - started, 3),
            "constellation_search": round(constellation_at - seeded_at, 3),
            "mask_scoring_and_output": round(finished - constellation_at, 3),
            "detection_total": round(finished - started, 3),
        },
    }
    (output_path / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("template")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--constellation-tolerance", type=float, default=0.24)
    parser.add_argument("--max-score", type=float, default=0.16)
    parser.add_argument("--search-x-max", type=float, default=0.74)
    parser.add_argument("--seed-step", type=float, default=1.5)
    parser.add_argument("--anchor-length-tolerance", type=float, default=0.18)
    parser.add_argument("--anchor-angle-tolerance", type=float, default=10.0)
    parser.add_argument("--shortlist-limit", type=int, default=20)
    parser.add_argument(
        "--exclude-text", dest="exclude_text", action="store_true", default=True,
        help="Reject candidates with substantial extracted-text coverage in the ROI.",
    )
    parser.add_argument(
        "--include-text", dest="exclude_text", action="store_false",
        help="Keep text-overlapping candidates for difficult project-specific symbols.",
    )
    parser.add_argument(
        "--include-annotation-layers",
        dest="exclude_annotation_layers",
        action="store_false",
        default=True,
        help="Keep candidates composed only from text/dimension/annotation layers.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    context, cache_hit = get_sheet_context(
        args.pdf, args.page, args.dpi, use_cache=False
    )
    try:
        diagnostics = detect_with_context(
            context,
            args.template,
            args.output,
            constellation_tolerance=args.constellation_tolerance,
            max_score=args.max_score,
            search_x_max=args.search_x_max,
            seed_step=args.seed_step,
            anchor_length_tolerance=args.anchor_length_tolerance,
            anchor_angle_tolerance=args.anchor_angle_tolerance,
            shortlist_limit=args.shortlist_limit,
            exclude_text=args.exclude_text,
            exclude_annotation_layers=args.exclude_annotation_layers,
            context_cache_hit=cache_hit,
        )
    finally:
        context.close()

    print(f"Primitive count: {diagnostics['primitive_count']}")
    print(f"Seed count: {diagnostics['seed_count']}")
    print(f"Constellation match count: {diagnostics['constellation_match_count']}")
    print(f"Raw candidate count: {diagnostics['raw_candidate_count']}")
    print(f"Shortlist count: {diagnostics['shortlist_count']}")
    print(f"Detection time: {diagnostics['timing_seconds']['detection_total']:.2f} seconds")
    print(f"Output: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
