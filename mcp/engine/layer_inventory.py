from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import time
from typing import Any


ANNOTATION_TOKENS = ("TEXT", "DIM", "ANNO", "NOTE", "TITLE", "GRID")


def _matches_layer(layer: str, tokens: list[str]) -> bool:
    value = layer.upper()
    return not tokens or any(token.upper() in value for token in tokens)


def _quantize(value: float, step: float) -> float:
    return round(round(value / step) * step, 3)


def _family(short_extent: float, long_extent: float) -> str:
    if short_extent <= 0.1:
        return "line"
    if long_extent / max(short_extent, 0.1) >= 4.0:
        return "elongated"
    return "compact"


def _mapping_match(group: dict[str, Any], mapping: dict[str, Any]) -> bool:
    layer_contains = str(mapping.get("layer_contains", "")).upper()
    if layer_contains and layer_contains not in group["layer"].upper():
        return False
    if mapping.get("shape_family") and mapping["shape_family"] != group["shape_family"]:
        return False
    tolerance = float(mapping.get("tolerance_pt", 1.0))
    for key in ("short_extent_pt", "long_extent_pt"):
        if key in mapping and abs(float(mapping[key]) - float(group[key])) > tolerance:
            return False
    return True


def analyze_layer_signatures(
    context,
    *,
    layer_tokens: list[str] | None = None,
    exclude_annotation_layers: bool = True,
    min_long_extent_pt: float = 3.0,
    max_long_extent_pt: float = 250.0,
    quantization_pt: float = 0.5,
    signature_mappings: list[dict[str, Any]] | None = None,
    output_dir: str | Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    tokens = [str(token) for token in (layer_tokens or []) if str(token).strip()]
    step = max(float(quantization_pt), 0.1)
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    matching_layers: dict[str, int] = defaultdict(int)
    filtered_paths = 0

    for drawing in context.drawings:
        layer = str(drawing.get("layer", "") or "")
        if not _matches_layer(layer, tokens):
            continue
        if exclude_annotation_layers and any(token in layer.upper() for token in ANNOTATION_TOKENS):
            continue
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = max(0.0, float(rect.x1 - rect.x0))
        height = max(0.0, float(rect.y1 - rect.y0))
        short_extent = min(width, height)
        long_extent = max(width, height)
        if long_extent < float(min_long_extent_pt) or long_extent > float(max_long_extent_pt):
            continue
        short_q = _quantize(short_extent, step)
        long_q = _quantize(long_extent, step)
        family = _family(short_q, long_q)
        filled = drawing.get("fill") is not None
        key = (layer, family, short_q, long_q, filled)
        if key not in groups:
            groups[key] = {
                "signature_id": "",
                "layer": layer,
                "shape_family": family,
                "short_extent_pt": short_q,
                "long_extent_pt": long_q,
                "filled": filled,
                "count": 0,
                "instances": [],
            }
        group = groups[key]
        group["count"] += 1
        group["instances"].append({
            "center_x_pt": round(float((rect.x0 + rect.x1) / 2), 3),
            "center_y_pt": round(float((rect.y0 + rect.y1) / 2), 3),
            "bbox_pdf_points": [round(float(value), 3) for value in rect],
        })
        matching_layers[layer] += 1
        filtered_paths += 1

    ordered = sorted(
        groups.values(),
        key=lambda item: (-item["count"], item["layer"], item["short_extent_pt"], item["long_extent_pt"]),
    )
    for index, group in enumerate(ordered, 1):
        group["signature_id"] = f"SIG-{index:03d}"

    mappings = signature_mappings or []
    mapped: list[dict[str, Any]] = []
    mapped_counts: dict[str, int] = defaultdict(int)
    ambiguous_signature_ids: list[str] = []
    for group in ordered:
        matches = [mapping for mapping in mappings if _mapping_match(group, mapping)]
        if len(matches) > 1:
            ambiguous_signature_ids.append(group["signature_id"])
            continue
        if not matches:
            continue
        symbol_id = str(matches[0]["symbol_id"])
        item = {
            "symbol_id": symbol_id,
            "signature_id": group["signature_id"],
            "count": group["count"],
            "layer": group["layer"],
            "shape_family": group["shape_family"],
            "short_extent_pt": group["short_extent_pt"],
            "long_extent_pt": group["long_extent_pt"],
            "instances": group["instances"],
            "mapping_source": matches[0].get("mapping_source", "caller_confirmed_project_mapping"),
        }
        mapped.append(item)
        mapped_counts[symbol_id] += group["count"]

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    details_path = output / "layer_signature_inventory.json"
    mapped_path = output / "mapped_layer_candidates.json"
    payload = {
        "version": "1",
        "pdf_path": str(context.pdf_path),
        "page": context.page_number,
        "context_id": context.context_id,
        "layer_tokens": tokens,
        "matching_layers": dict(sorted(matching_layers.items())),
        "filtered_drawing_paths": filtered_paths,
        "signatures": ordered,
    }
    details_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    mapped_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = round(time.perf_counter() - started, 4)
    return {
        "matching_layers": dict(sorted(matching_layers.items())),
        "filtered_drawing_paths": filtered_paths,
        "signature_count": len(ordered),
        "signatures": ordered,
        "mapped": mapped,
        "mapped_counts": dict(sorted(mapped_counts.items())),
        "ambiguous_signature_ids": ambiguous_signature_ids,
        "clarification_required": bool(ambiguous_signature_ids),
        "inventory_json": str(details_path),
        "mapped_candidates_json": str(mapped_path),
        "elapsed_seconds": elapsed,
        "warning": "Layer signatures are deterministic candidates, not final quantities; confirm the project legend mapping and review every mapped location.",
    }
