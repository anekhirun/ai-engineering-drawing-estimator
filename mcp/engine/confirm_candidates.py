from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import cv2
import fitz
import numpy as np


def render_page(page: fitz.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if pix.n == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Confirm reviewed detector candidates and create auditable markup."
    )
    parser.add_argument("pdf")
    parser.add_argument("template")
    parser.add_argument("candidates_json")
    parser.add_argument("--accept", nargs="*", default=[])
    parser.add_argument(
        "--manual-point",
        nargs=2,
        action="append",
        default=[],
        metavar=("X_PT", "Y_PT"),
        help="Add a visually confirmed PDF-point coordinate missing from candidates.",
    )
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--symbol-id", default="DUPLEX_SOCKET_OUTLET")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    candidates = json.loads(Path(args.candidates_json).read_text(encoding="utf-8"))
    doc = fitz.open(args.pdf)
    if not 1 <= args.page <= len(doc):
        raise ValueError(f"page must be between 1 and {len(doc)}")
    page = doc[args.page - 1]
    accepted_ids = set(args.accept)
    accepted = [c for c in candidates if c["candidate_id"] in accepted_ids]
    missing = accepted_ids - {c["candidate_id"] for c in accepted}
    if missing:
        raise RuntimeError(f"Candidate IDs not found: {sorted(missing)}")
    for index, point in enumerate(args.manual_point, 1):
        x_pt, y_pt = map(float, point)
        if not (0 <= x_pt <= page.rect.width and 0 <= y_pt <= page.rect.height):
            raise ValueError(
                f"Manual point outside page bounds: ({x_pt}, {y_pt}) "
                f"for {page.rect.width} x {page.rect.height} pt"
            )
        accepted.append(
            {
                "candidate_id": f"MANUAL-{index:02d}",
                "center_x_pt": x_pt,
                "center_y_pt": y_pt,
                "constellation_error": None,
                "score": None,
                "detection_method": "manual_visual_confirmation",
                "review_status": "manual_visual_confirmation",
            }
        )

    image = render_page(page, args.dpi)
    scale = args.dpi / 72.0
    half_w = template["width_pt"] * 1.8
    half_h = template["height_pt"] * 1.8

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for index, candidate in enumerate(
        sorted(accepted, key=lambda c: (c["center_y_pt"], c["center_x_pt"])), 1
    ):
        x = float(candidate["center_x_pt"])
        y = float(candidate["center_y_pt"])
        x1 = max(0, round((x - half_w) * scale))
        y1 = max(0, round((y - half_h) * scale))
        x2 = min(image.shape[1], round((x + half_w) * scale))
        y2 = min(image.shape[0], round((y + half_h) * scale))
        detection_id = f"DS-{index:02d}"
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 180, 0), 4)
        cv2.putText(
            image,
            detection_id,
            (x1, max(26, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 150, 0),
            2,
        )
        records.append(
            {
                "detection_id": detection_id,
                "candidate_id": candidate["candidate_id"],
                "symbol_id": args.symbol_id,
                "page": args.page,
                "center_x_pt": x,
                "center_y_pt": y,
                "constellation_error": candidate["constellation_error"],
                "geometry_score": candidate["score"],
                "detection_method": candidate.get(
                    "detection_method", "pdf_vector_compound_match"
                ),
                "review_status": candidate.get("review_status", "confirmed"),
            }
        )

    symbol_slug = re.sub(r"[^a-z0-9]+", "_", args.symbol_id.lower()).strip("_")
    markup_name = f"confirmed_{symbol_slug}.png"
    cv2.imwrite(str(output / markup_name), image)
    accepted_detector_count = sum(
        1 for candidate in accepted
        if candidate.get("detection_method", "pdf_vector_compound_match")
        != "manual_visual_confirmation"
    )
    manual_count = len(accepted) - accepted_detector_count
    review_warning = None
    if candidates and not accepted:
        review_warning = (
            "No detector candidates or manual points were accepted. "
            "Treat confirmed_count=0 as pending review until every candidate "
            "and wall/door region has been checked."
        )
    report = {
        "source_pdf": str(Path(args.pdf)),
        "page": args.page,
        "symbol_id": args.symbol_id,
        "confirmed_count": len(records),
        "detector_candidate_count": len(candidates),
        "accepted_detector_count": accepted_detector_count,
        "manual_count": manual_count,
        "review_warning": review_warning,
        "detections": records,
    }
    (output / "quantity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "detection_id",
        "candidate_id",
        "symbol_id",
        "page",
        "center_x_pt",
        "center_y_pt",
        "constellation_error",
        "geometry_score",
        "detection_method",
        "review_status",
    ]
    with (output / "quantity_report.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    print(f"Confirmed count: {len(records)}")
    print(f"Markup: {(output / markup_name).resolve()}")
    print(f"Report: {(output / 'quantity_report.json').resolve()}")


if __name__ == "__main__":
    main()
