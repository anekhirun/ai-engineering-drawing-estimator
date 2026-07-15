from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import fitz
import numpy as np

from vector_core import (
    extract_primitives,
    primitive_points_in_roi,
    points_to_mask,
    select_primitives,
)


def render_page(page, dpi):
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8)
    image = image.reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def primitive_descriptor(primitive, roi):
    x1, y1, x2, y2 = primitive.bbox
    rx1, ry1, rx2, ry2 = roi
    rw = max(rx2 - rx1, 1e-6)
    rh = max(ry2 - ry1, 1e-6)

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    width = x2 - x1
    height = y2 - y1
    dx = primitive.points[-1, 0] - primitive.points[0, 0]
    dy = primitive.points[-1, 1] - primitive.points[0, 1]
    angle = math.degrees(math.atan2(dy, dx)) % 180.0

    return {
        "cx": (cx - rx1) / rw,
        "cy": (cy - ry1) / rh,
        "width": width / rw,
        "height": height / rh,
        "length": primitive.length / max(math.hypot(rw, rh), 1e-6),
        "angle": angle,
        "closedness": float(
            np.linalg.norm(primitive.points[0] - primitive.points[-1])
            / max(math.hypot(width, height), 1e-6)
        ),
    }


def descriptor_quality(d):
    size = max(d["width"], d["height"], d["length"])
    compact = min(d["width"] + 1e-6, d["height"] + 1e-6) / max(
        d["width"] + 1e-6, d["height"] + 1e-6
    )
    center_bonus = 1.0 - min(1.0, math.hypot(d["cx"] - 0.5, d["cy"] - 0.5))
    return 0.55 * size + 0.20 * compact + 0.25 * center_bonus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=400)
    parser.add_argument("--grid-size", type=int, default=96)
    parser.add_argument("--max-parts", type=int, default=8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    page = doc[args.page - 1]
    image = render_page(page, args.dpi)

    display_scale = min(1.0, 1800 / image.shape[1])
    display = cv2.resize(image, None, fx=display_scale, fy=display_scale)

    x, y, w, h = cv2.selectROI(
        "Select Duplex Socket only, then press ENTER",
        display,
        showCrosshair=True,
        fromCenter=False,
    )
    cv2.destroyAllWindows()
    if w <= 0 or h <= 0:
        raise RuntimeError("No ROI selected")

    to_pdf = 72.0 / args.dpi / display_scale
    roi = [x * to_pdf, y * to_pdf, (x + w) * to_pdf, (y + h) * to_pdf]

    primitives = extract_primitives(page)
    # A symbol ROI may touch conduit/wall lines outside the symbol.  Keep only
    # primitives whose own center is inside the ROI so those crossing lines do
    # not become part of the reusable template.
    selected = select_primitives(
        primitives,
        roi,
        max_length_factor=1.6,
        require_center_inside=True,
        require_bbox_inside=True,
    )
    descriptors = [primitive_descriptor(p, roi) for p in selected]
    ranked = sorted(descriptors, key=descriptor_quality, reverse=True)

    # Remove tiny fragments and retain a compound constellation.
    compound = [
        d for d in ranked
        if max(d["width"], d["height"], d["length"]) >= 0.08
    ][:args.max_parts]

    if len(compound) < 3:
        raise RuntimeError(
            "Template has fewer than 3 useful vector parts. "
            "Select the symbol again with a slightly larger clean ROI."
        )

    points = primitive_points_in_roi(selected, roi)
    mask = points_to_mask(points, roi, grid_size=args.grid_size)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    preview = output.with_name(output.stem + "_preview.png")
    cv2.imwrite(str(preview), mask)

    data = {
        "source_pdf": args.pdf,
        "source_page": args.page,
        "roi_pdf_points": roi,
        "width_pt": roi[2] - roi[0],
        "height_pt": roi[3] - roi[1],
        "grid_size": args.grid_size,
        "foreground_pixels": int((mask > 0).sum()),
        "primitive_count": len(selected),
        "compound_parts": compound,
        "mask": mask.tolist(),
    }
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved template: {output}")
    print(f"Preview: {preview}")
    print(f"ROI size: {data['width_pt']:.3f} x {data['height_pt']:.3f} pt")
    print(f"Primitive count: {len(selected)}")
    print(f"Compound part count: {len(compound)}")
    for i, d in enumerate(compound, 1):
        print(
            f"Part {i}: cx={d['cx']:.3f}, cy={d['cy']:.3f}, "
            f"w={d['width']:.3f}, h={d['height']:.3f}, "
            f"len={d['length']:.3f}, angle={d['angle']:.1f}"
        )


if __name__ == "__main__":
    main()
