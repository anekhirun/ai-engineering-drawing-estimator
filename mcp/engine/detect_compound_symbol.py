from __future__ import annotations

import argparse
import csv
import html
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import fitz
import numpy as np

from vector_core import (
    best_rotation_score,
    extract_primitives,
    primitive_points_in_roi,
    points_to_mask,
    select_primitives,
)


@dataclass
class Candidate:
    candidate_id: str
    center_x_pt: float
    center_y_pt: float
    constellation_error: float
    score: float
    rotation: int
    primitive_count: int
    detection_method: str = "pdf_vector_compound_match"
    crop_file: str = ""


class PrimitiveSpatialIndex:
    """Small uniform grid for fast local primitive lookup."""

    def __init__(self, descriptors, cell_size):
        self.cell_size = max(float(cell_size), 1.0)
        self.cells = defaultdict(list)
        for index, descriptor in enumerate(descriptors):
            key = (
                math.floor(descriptor["cx"] / self.cell_size),
                math.floor(descriptor["cy"] / self.cell_size),
            )
            self.cells[key].append(index)

    def query_contained(self, roi, primitives):
        x1, y1, x2, y2 = roi
        gx1 = math.floor(x1 / self.cell_size)
        gy1 = math.floor(y1 / self.cell_size)
        gx2 = math.floor(x2 / self.cell_size)
        gy2 = math.floor(y2 / self.cell_size)
        result = []
        for gx in range(gx1, gx2 + 1):
            for gy in range(gy1, gy2 + 1):
                for index in self.cells.get((gx, gy), ()):
                    px1, py1, px2, py2 = primitives[index].bbox
                    if x1 <= px1 and px2 <= x2 and y1 <= py1 and py2 <= y2:
                        result.append(index)
        return result


def render_page(page, dpi):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8)
    image = image.reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def primitive_abs_descriptor(p):
    x1, y1, x2, y2 = p.bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    dx = p.points[-1, 0] - p.points[0, 0]
    dy = p.points[-1, 1] - p.points[0, 1]
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    return {
        "cx": cx, "cy": cy,
        "width": x2 - x1,
        "height": y2 - y1,
        "length": p.length,
        "angle": angle,
    }


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


def text_boxes(page):
    """Return PDF text boxes used to suppress obvious text/grid false positives."""
    boxes = []
    for word in page.get_text("words"):
        if len(word) >= 4:
            x1, y1, x2, y2 = map(float, word[:4])
            boxes.append((x1, y1, x2, y2))
    return boxes


def center_overlaps_text(cx, cy, boxes, padding=0.8):
    return any(
        x1 - padding <= cx <= x2 + padding
        and y1 - padding <= cy <= y2 + padding
        for x1, y1, x2, y2 in boxes
    )


def save_outputs(image, candidates, template, output, dpi):
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
    <h1>AI Engineering Drawing Estimator v0.1.3 Candidate Review</h1>
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
    <h1>AI Engineering Drawing Estimator v0.1.3 Candidate Review</h1>
    <p>Shortlist: {len(candidates)} - review before reporting quantity.</p>
    <div class="toolbar"><b id="counts"></b>
    <button onclick="exportDecisions()">Export decisions.json</button></div>
    <main>{cards}</main><script>
    const storageKey = 'v33-decisions-' + location.pathname;
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
        help="Reject candidates whose center falls inside extracted PDF text.",
    )
    parser.add_argument(
        "--include-text", dest="exclude_text", action="store_false",
        help="Keep text-overlapping candidates for difficult project-specific symbols.",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    started = time.perf_counter()

    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    template_mask = np.asarray(template["mask"], dtype=np.uint8)
    grid_size = int(template["grid_size"])
    roi_w = template["width_pt"]
    roi_h = template["height_pt"]

    doc = fitz.open(args.pdf)
    page = doc[args.page - 1]
    primitives = extract_primitives(page)
    image = render_page(page, args.dpi)
    text_bboxes = text_boxes(page) if args.exclude_text else []
    abs_desc = [primitive_abs_descriptor(p) for p in primitives]
    spatial_index = PrimitiveSpatialIndex(abs_desc, max(roi_w, roi_h) * 1.5)
    extracted_at = time.perf_counter()

    # Predict symbol centers from the two longest template parts.  This avoids
    # treating every short text/arc primitive as a possible symbol center.
    anchor_parts = sorted(
        template["compound_parts"], key=lambda part: part["length"], reverse=True
    )[:2]
    seeds = {}
    for d in abs_desc:
        for target in anchor_parts:
            expected_length = target["length"] * math.hypot(roi_w, roi_h)
            if rel_error(d["length"], expected_length) > args.anchor_length_tolerance:
                continue
            for rotation in (0, 90, 180, 270):
                expected_angle = (target["angle"] + rotation) % 180
                if angle_diff(d["angle"], expected_angle) > args.anchor_angle_tolerance:
                    continue
                offset_x, offset_y = rotated_offset(target, roi_w, roi_h, rotation)
                center_x = d["cx"] - offset_x
                center_y = d["cy"] - offset_y
                if not (0 <= center_x <= page.rect.width * args.search_x_max):
                    continue
                if not (page.rect.height * 0.02 <= center_y <= page.rect.height * 0.96):
                    continue
                key = (
                    round(center_x / args.seed_step),
                    round(center_y / args.seed_step),
                )
                seeds[key] = (center_x, center_y)
    seeded_at = time.perf_counter()

    constellation_matches = []
    for cx, cy in seeds.values():
        roi = [cx - roi_w * 0.65, cy - roi_h * 0.65,
               cx + roi_w * 0.65, cy + roi_h * 0.65]
        local_indices = spatial_index.query_contained(roi, primitives)
        if len(local_indices) < 3 or len(local_indices) > 80:
            continue
        local_desc = [abs_desc[i] for i in local_indices]
        c_error, rotation = constellation_error(
            local_desc, template["compound_parts"], roi_w, roi_h, cx, cy
        )
        if c_error <= args.constellation_tolerance:
            constellation_matches.append((cx, cy, c_error, rotation, local_indices))
    constellation_at = time.perf_counter()

    candidates = []
    text_filtered_count = 0
    for cx, cy, c_error, rotation, local_indices in constellation_matches:
        if text_bboxes and center_overlaps_text(cx, cy, text_bboxes):
            text_filtered_count += 1
            continue
        roi = [cx - roi_w / 2, cy - roi_h / 2, cx + roi_w / 2, cy + roi_h / 2]
        selected = [primitives[i] for i in local_indices]
        points = primitive_points_in_roi(selected, roi)
        mask = points_to_mask(points, roi, grid_size=grid_size)
        score, mask_rotation = best_rotation_score(template_mask, mask)
        if score <= args.max_score:
            candidates.append(Candidate(
                candidate_id="",
                center_x_pt=float(cx),
                center_y_pt=float(cy),
                constellation_error=float(c_error),
                score=float(score),
                rotation=int(mask_rotation),
                primitive_count=len(selected),
            ))

    raw_candidates = nms(candidates, min(roi_w, roi_h) * 0.65)
    ranked = sorted(raw_candidates, key=lambda c: (c.score, c.constellation_error))
    if args.shortlist_limit > 0:
        candidates = ranked[:args.shortlist_limit]
    else:
        candidates = ranked
    output_path = Path(args.output)
    save_outputs(image, candidates, template, output_path, args.dpi)
    write_interactive_review(candidates, output_path)
    finished = time.perf_counter()

    diagnostics = {
        "primitive_count": len(primitives),
        "seed_count": len(seeds),
        "constellation_match_count": len(constellation_matches),
        "raw_candidate_count": len(raw_candidates),
        "shortlist_count": len(candidates),
        "parameters": {
            "constellation_tolerance": args.constellation_tolerance,
            "max_score": args.max_score,
            "shortlist_limit": args.shortlist_limit,
            "exclude_text": args.exclude_text,
            "text_filtered_count": text_filtered_count,
        },
        "timing_seconds": {
            "extract_and_render": round(extracted_at - started, 3),
            "seed_generation": round(seeded_at - extracted_at, 3),
            "constellation_search": round(constellation_at - seeded_at, 3),
            "mask_scoring_and_output": round(finished - constellation_at, 3),
            "total": round(finished - started, 3),
        },
    }
    (output_path / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Primitive count: {len(primitives)}")
    print(f"Seed count: {len(seeds)}")
    print(f"Constellation match count: {len(constellation_matches)}")
    print(f"Raw candidate count: {len(raw_candidates)}")
    print(f"Shortlist count: {len(candidates)}")
    print(f"Total time: {finished - started:.2f} seconds")
    print(f"Output: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
