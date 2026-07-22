from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import fitz

from select_compound_template import descriptor_quality, primitive_descriptor
from vector_core import extract_primitives, points_to_mask, primitive_points_in_roi, select_primitives


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a compound vector template from an exact PDF-point ROI."
    )
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--roi", type=float, nargs=4, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--grid-size", type=int, default=96)
    parser.add_argument("--max-parts", type=int, default=10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    roi = list(args.roi)
    if roi[2] <= roi[0] or roi[3] <= roi[1]:
        raise ValueError("ROI must have positive width and height")

    doc = fitz.open(args.pdf)
    page = doc[args.page - 1]
    primitives = extract_primitives(page)
    selected = select_primitives(
        primitives,
        roi,
        max_length_factor=1.8,
        require_center_inside=True,
        require_bbox_inside=True,
    )
    descriptors = [primitive_descriptor(primitive, roi) for primitive in selected]
    compound = [
        descriptor
        for descriptor in sorted(descriptors, key=descriptor_quality, reverse=True)
        if max(descriptor["width"], descriptor["height"], descriptor["length"]) >= 0.06
    ][: args.max_parts]
    if not compound:
        raise RuntimeError(
            "ROI contains no useful vector parts; adjust the ROI."
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
    print(f"ROI: {roi}")
    print(f"Primitive count: {len(selected)}")
    print(f"Compound part count: {len(compound)}")
    if len(compound) < 3:
        print(
            "Warning: simple template has fewer than three compound parts; "
            "use layer/context filtering and mandatory review."
        )
    for index, descriptor in enumerate(compound, 1):
        print(
            f"Part {index}: cx={descriptor['cx']:.3f}, cy={descriptor['cy']:.3f}, "
            f"w={descriptor['width']:.3f}, h={descriptor['height']:.3f}, "
            f"len={descriptor['length']:.3f}, angle={descriptor['angle']:.1f}"
        )


if __name__ == "__main__":
    main()
