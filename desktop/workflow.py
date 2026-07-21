from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


VALID_DECISIONS = {"accept", "reject", "uncertain", "unreviewed"}


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()
    return slug or "drawing"


def detection_output_dir(
    project_root: Path, pdf_path: Path, page: int, symbol_id: str
) -> Path:
    return (
        project_root
        / "output"
        / safe_slug(pdf_path.stem)
        / f"page_{page:03d}"
        / safe_slug(symbol_id)
        / "candidates"
    )


def confirmation_output_dir(candidate_dir: Path) -> Path:
    return candidate_dir.parent / "confirmed"


def load_candidates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("candidates.json must contain a list")
    required = {"candidate_id", "center_x_pt", "center_y_pt", "score"}
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"Candidate {index} is missing required fields")
    return data


def decision_counts(decisions: dict[str, str], candidate_ids: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in ("accept", "reject", "uncertain", "unreviewed")}
    for candidate_id in candidate_ids:
        value = decisions.get(candidate_id, "unreviewed")
        if value not in VALID_DECISIONS:
            value = "unreviewed"
        counts[value] += 1
    return counts


def unresolved_candidate_ids(
    decisions: dict[str, str], candidate_ids: list[str]
) -> list[str]:
    return [
        candidate_id
        for candidate_id in candidate_ids
        if decisions.get(candidate_id, "unreviewed") in {"unreviewed", "uncertain"}
    ]
