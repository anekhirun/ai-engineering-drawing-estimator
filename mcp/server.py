from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

VERSION = "0.1.3"
ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
TEMPLATES = ROOT / "assets" / "templates"

SYMBOLS = {
    "DUPLEX_SOCKET_OUTLET": {
        "template": "duplex_socket_starter.json",
        "system_id": "POWER",
        "name_th": "เต้ารับคู่",
        "visual_rule": "วงกลมและเส้นขนานภายใน 2 เส้น หมุนได้ 0/90/180/270 องศา",
    },
    "SINGLE_SOCKET_OUTLET": {
        "template": "single_socket_starter.json",
        "system_id": "POWER",
        "name_th": "เต้ารับเดี่ยว",
        "visual_rule": "วงกลมและเส้นภายใน 1 เส้น; C ใกล้เคียงมักหมายถึง CCTV",
    },
    "DATA_OUTLET": {
        "template": "data_outlet_starter.json",
        "system_id": "COMMUNICATION",
        "release_scope": "deferred_to_v0.2.0",
        "name_th": "จุดต่อข้อมูล",
        "visual_rule": "รูป C หรือวงเปิดแบบเส้นประ มักวางคู่กับเต้ารับคู่",
    },
    "FIRE_ALARM_CONTROL_PANEL": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Fire Alarm Control Panel",
        "visual_rule": "Project legend FACP enclosure or label; require a project-specific template.",
    },
    "SMOKE_DETECTOR_PHOTOELECTRIC": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Smoke Detector Photoelectric",
        "visual_rule": "Commonly a circle containing S; verify against the project legend.",
    },
    "HEAT_DETECTOR_FIXED_135F": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Heat Detector Fixed Temperature 135 F",
        "visual_rule": "Commonly a circle containing F; distinguish the temperature suffix.",
    },
    "HEAT_DETECTOR_FIXED_200F": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Heat Detector Fixed Temperature 200 F",
        "visual_rule": "Commonly a circle containing F with a 200 suffix; verify the suffix.",
    },
    "FIRE_ALARM_BELL_WALL_MOUNTED": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Fire Alarm Bell Wall Mounted",
        "visual_rule": "Commonly a circle containing B; WP may indicate weatherproof.",
    },
    "FIRE_ALARM_MANUAL_STATION": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Fire Alarm Manual Station",
        "visual_rule": "Commonly a square containing F; verify against the legend.",
    },
    "FIRE_ALARM_STROBE_LIGHT": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Fire Alarm Strobe Light",
        "visual_rule": "Commonly a circle with diagonal rays; WP may indicate weatherproof.",
    },
    "FIRE_ALARM_END_OF_LINE": {
        "template": None,
        "system_id": "FIRE_ALARM",
        "name": "Fire Alarm End of Line",
        "visual_rule": "Circuit accessory, reported separately from primary equipment.",
    },
}

SYSTEMS = {
    "POWER": {
        "name": "Power System",
        "symbol_ids": ["DUPLEX_SOCKET_OUTLET", "SINGLE_SOCKET_OUTLET"],
    },
    "FIRE_ALARM": {
        "name": "Fire Alarm System",
        "symbol_ids": [
            "FIRE_ALARM_CONTROL_PANEL",
            "SMOKE_DETECTOR_PHOTOELECTRIC",
            "HEAT_DETECTOR_FIXED_135F",
            "HEAT_DETECTOR_FIXED_200F",
            "FIRE_ALARM_BELL_WALL_MOUNTED",
            "FIRE_ALARM_MANUAL_STATION",
            "FIRE_ALARM_STROBE_LIGHT",
            "FIRE_ALARM_END_OF_LINE",
        ],
    },
}


def _require_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def _output_dir(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _symbol_template(symbol_id: str, template_path: str | None = None) -> Path:
    if symbol_id not in SYMBOLS:
        raise ValueError(f"Unsupported symbol_id: {symbol_id}")
    if template_path:
        return _require_file(template_path, "template")
    starter = SYMBOLS[symbol_id].get("template")
    if not starter:
        raise ValueError(
            f"{symbol_id} requires a project-specific template built from "
            "the current drawing legend."
        )
    return _require_file(str(TEMPLATES / starter), "starter template")


def _run(script: str, arguments: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ENGINE / script), *arguments],
        cwd=ENGINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(
            f"{script} failed ({completed.returncode})\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return {"stdout": completed.stdout.strip()}


def inspect_drawing(args: dict[str, Any]) -> dict[str, Any]:
    import fitz

    pdf = _require_file(args["pdf_path"], "PDF")
    document = fitz.open(pdf)
    pages = []
    for index, page in enumerate(document):
        drawings = page.get_drawings()
        vector_items = sum(len(drawing.get("items", ())) for drawing in drawings)
        images = page.get_images(full=True)
        if vector_items > 100:
            classification = "vector_or_hybrid"
        elif images:
            classification = "likely_raster"
        else:
            classification = "unknown"
        pages.append({
            "page": index + 1,
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "drawing_paths": len(drawings),
            "vector_items": vector_items,
            "embedded_images": len(images),
            "text_characters": len(page.get_text("text")),
            "classification": classification,
        })
    return {"pdf_path": str(pdf), "page_count": len(document), "pages": pages}


def render_page(args: dict[str, Any]) -> dict[str, Any]:
    import fitz

    pdf = _require_file(args["pdf_path"], "PDF")
    page_number = int(args.get("page", 1))
    dpi = int(args.get("dpi", 300))
    output = Path(args["output_path"]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    if not 1 <= page_number <= len(document):
        raise ValueError(f"page must be between 1 and {len(document)}")
    pixmap = document[page_number - 1].get_pixmap(dpi=dpi, alpha=False)
    pixmap.save(output)
    return {"output_path": str(output), "page": page_number, "dpi": dpi,
            "width_px": pixmap.width, "height_px": pixmap.height}


def get_symbol_rules(args: dict[str, Any]) -> dict[str, Any]:
    system_id = args.get("system_id")
    if system_id:
        if system_id not in SYSTEMS:
            raise ValueError(f"Unsupported system_id: {system_id}")
        return {
            "system_id": system_id,
            **SYSTEMS[system_id],
            "symbols": {
                symbol_id: SYMBOLS[symbol_id]
                for symbol_id in SYSTEMS[system_id]["symbol_ids"]
            },
        }
    symbol_id = args.get("symbol_id")
    if symbol_id:
        if symbol_id not in SYMBOLS:
            raise ValueError(f"Unsupported symbol_id: {symbol_id}")
        return {symbol_id: SYMBOLS[symbol_id]}
    return SYMBOLS


def build_symbol_template(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    output = Path(args["output_path"]).expanduser().resolve()
    roi = args["roi_pdf_points"]
    if len(roi) != 4:
        raise ValueError("roi_pdf_points must contain [x1, y1, x2, y2]")
    result = _run("build_template_from_roi.py", [
        str(pdf), "--page", str(int(args.get("page", 1))),
        "--roi", *[str(float(value)) for value in roi],
        "--output", str(output),
    ])
    data = json.loads(output.read_text(encoding="utf-8"))
    return {"output_path": str(output),
            "preview_path": str(output.with_name(output.stem + "_preview.png")),
            "primitive_count": data["primitive_count"],
            "compound_part_count": len(data["compound_parts"]),
            "stdout": result["stdout"]}


def detect_symbol_candidates(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    symbol_id = args["symbol_id"]
    if symbol_id not in SYMBOLS:
        raise ValueError(f"Unsupported symbol_id: {symbol_id}")
    template = _symbol_template(symbol_id, args.get("template_path"))
    output = _output_dir(args["output_dir"])
    result = _run("detect_compound_symbol.py", [
        str(pdf), str(template),
        "--page", str(int(args.get("page", 1))),
        "--dpi", str(int(args.get("dpi", 300))),
        "--constellation-tolerance", str(float(args.get("constellation_tolerance", 0.16))),
        "--max-score", str(float(args.get("max_score", 0.16))),
        "--search-x-max", str(float(args.get("search_x_max", 0.80))),
        "--exclude-text" if args.get("exclude_text", True) else "--include-text",
        "--shortlist-limit", str(int(args.get("shortlist_limit", 40))),
        "--output", str(output),
    ])
    diagnostics = json.loads((output / "diagnostics.json").read_text(encoding="utf-8"))
    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))
    return {
        "symbol_id": symbol_id,
        "candidate_count": len(candidates),
        "candidates_json": str(output / "candidates.json"),
        "candidates_csv": str(output / "candidates.csv"),
        "markup_path": str(output / "marked_candidates.png"),
        "review_html": str(output / "review.html"),
        "diagnostics": diagnostics,
        "template_path": str(template),
        "warning": "Starter templates are high-recall candidates only. Text-overlap suppression and title-block bounds reduce false positives, but visual review remains mandatory.",
        "stdout": result["stdout"],
    }


def confirm_symbol_count(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    candidates = _require_file(args["candidates_json"], "candidates_json")
    symbol_id = args["symbol_id"]
    if symbol_id not in SYMBOLS:
        raise ValueError(f"Unsupported symbol_id: {symbol_id}")
    template = _symbol_template(symbol_id, args.get("template_path"))
    output = _output_dir(args["output_dir"])
    command_args = [
        str(pdf), str(template), str(candidates),
        "--page", str(int(args.get("page", 1))),
        "--dpi", str(int(args.get("dpi", 300))),
        "--symbol-id", symbol_id, "--output", str(output),
    ]
    accepted_ids = [str(value) for value in args.get("accepted_ids", [])]
    if accepted_ids:
        command_args.extend(["--accept", *accepted_ids])
    rejected_ids = [str(value) for value in args.get("rejected_ids", [])]
    if rejected_ids:
        command_args.extend(["--reject", *rejected_ids])
    uncertain_ids = [str(value) for value in args.get("uncertain_ids", [])]
    if uncertain_ids:
        command_args.extend(["--uncertain", *uncertain_ids])
    if args.get("wall_door_sweep_completed", False):
        command_args.append("--wall-door-sweep-completed")
    if args.get("floor_or_region"):
        command_args.extend(["--floor-or-region", str(args["floor_or_region"])])
    if args.get("review_notes"):
        command_args.extend(["--review-notes", str(args["review_notes"])])
    for point in args.get("manual_points", []):
        if len(point) != 2:
            raise ValueError("Each manual point must be [x_pt, y_pt]")
        command_args.extend(["--manual-point", str(float(point[0])), str(float(point[1]))])
    result = _run("confirm_candidates.py", command_args)
    report = json.loads((output / "quantity_report.json").read_text(encoding="utf-8"))
    return {
        "symbol_id": symbol_id,
        "confirmed_count": report["confirmed_count"],
        "rejected_count": report["rejected_count"],
        "uncertain_count": report["uncertain_count"],
        "unresolved_count": report["unresolved_count"],
        "review_complete": report["review_complete"],
        "clarification_required": report["clarification_required"],
        "unresolved_ids": report["unresolved_ids"],
        "uncertain_ids": report["uncertain_ids"],
        "wall_door_sweep_completed": report["wall_door_sweep_completed"],
        "report_json": str(output / "quantity_report.json"),
        "report_csv": str(output / "quantity_report.csv"),
        "markup_path": str(output / f"confirmed_{symbol_id.lower()}.png"),
        "review_warning": report.get("review_warning"),
        "stdout": result["stdout"],
    }


def _write_contact_sheet(runs: list[dict[str, Any]], output: Path) -> str | None:
    from PIL import Image, ImageDraw, ImageFont

    cards: list[tuple[str, Path]] = []
    for run in runs:
        candidate_dir = Path(run["candidates_json"]).parent
        candidates = json.loads(
            Path(run["candidates_json"]).read_text(encoding="utf-8")
        )
        for candidate in candidates:
            crop = candidate_dir / candidate["crop_file"]
            if crop.is_file():
                label = f"{run['symbol_id']} / {candidate['candidate_id']}"
                cards.append((label, crop))
    if not cards:
        return None

    columns = 4
    card_width, card_height = 320, 260
    rows = (len(cards) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * card_width, rows * card_height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, crop_path) in enumerate(cards):
        col, row = index % columns, index // columns
        x, y = col * card_width, row * card_height
        crop = Image.open(crop_path).convert("RGB")
        crop.thumbnail((card_width - 24, card_height - 54))
        px = x + (card_width - crop.width) // 2
        py = y + 10
        sheet.paste(crop, (px, py))
        draw.rectangle(
            (x + 4, y + 4, x + card_width - 4, y + card_height - 4),
            outline="#999999",
            width=2,
        )
        draw.text((x + 10, y + card_height - 34), label, fill="black", font=font)
    sheet.save(output)
    return str(output)


def prepare_sheet_audit(args: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    pdf = _require_file(args["pdf_path"], "PDF")
    system_id = str(args["system_id"])
    if system_id not in SYSTEMS:
        raise ValueError(
            f"v0.1.3 supports only {sorted(SYSTEMS)}; received {system_id}"
        )
    page = int(args.get("page", 1))
    dpi = int(args.get("dpi", 300))
    output = _output_dir(args["output_dir"])
    inspection = inspect_drawing({"pdf_path": str(pdf)})
    if not 1 <= page <= inspection["page_count"]:
        raise ValueError(f"page must be between 1 and {inspection['page_count']}")
    page_info = inspection["pages"][page - 1]

    overview = output / f"page_{page:03d}_overview.png"
    overview_result = render_page({
        "pdf_path": str(pdf),
        "page": page,
        "dpi": int(args.get("overview_dpi", 160)),
        "output_path": str(overview),
    })

    requested = args.get("symbol_ids") or SYSTEMS[system_id]["symbol_ids"]
    invalid = [
        symbol_id
        for symbol_id in requested
        if symbol_id not in SYSTEMS[system_id]["symbol_ids"]
    ]
    if invalid:
        raise ValueError(
            f"Symbols outside {system_id} v0.1.3 scope: {sorted(invalid)}"
        )

    template_paths = args.get("template_paths", {})
    runs = []
    template_required = []
    skipped = []
    if page_info["classification"] != "vector_or_hybrid":
        skipped.append({
            "page": page,
            "reason": "Automatic matching requires a vector_or_hybrid page.",
        })
    else:
        for symbol_id in requested:
            supplied = template_paths.get(symbol_id)
            starter = SYMBOLS[symbol_id].get("template")
            if not supplied and not starter:
                template_required.append({
                    "symbol_id": symbol_id,
                    "reason": "Build a project-specific template from the current legend.",
                })
                continue
            symbol_output = output / symbol_id.lower() / "candidates"
            runs.append(detect_symbol_candidates({
                "pdf_path": str(pdf),
                "page": page,
                "symbol_id": symbol_id,
                "template_path": supplied,
                "dpi": dpi,
                "output_dir": str(symbol_output),
                "constellation_tolerance": args.get("constellation_tolerance", 0.16),
                "max_score": args.get("max_score", 0.16),
                "search_x_max": args.get("search_x_max", 0.80),
                "exclude_text": args.get("exclude_text", True),
                "shortlist_limit": args.get("shortlist_limit", 40),
            }))

    contact_sheet = _write_contact_sheet(runs, output / "candidate_contact_sheet.png")
    manifest = {
        "version": VERSION,
        "system_id": system_id,
        "system_name": SYSTEMS[system_id]["name"],
        "pdf_path": str(pdf),
        "page": page,
        "classification": page_info["classification"],
        "overview": overview_result,
        "requested_symbol_ids": requested,
        "runs": runs,
        "candidate_count": sum(run["candidate_count"] for run in runs),
        "contact_sheet": contact_sheet,
        "template_required": template_required,
        "skipped": skipped,
        "clarification_required": bool(template_required or skipped),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "next_step": (
            "Review the overview and contact sheet in one pass. Build only the "
            "listed missing templates, ask the user about ambiguous symbols, "
            "then call confirm_symbol_count for each reviewed symbol."
        ),
    }
    manifest_path = output / "sheet_audit_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest["manifest_json"] = str(manifest_path)
    return manifest


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


TOOLS = [
    {"name": "inspect_drawing", "description": "Inspect a PDF and identify vector, hybrid, or raster pages before symbol counting.", "inputSchema": _schema({"pdf_path": {"type": "string"}}, ["pdf_path"])},
    {"name": "render_page", "description": "Render one PDF page for inspecting legends, floor regions, walls, doors, and candidates.", "inputSchema": _schema({"pdf_path": {"type": "string"}, "page": {"type": "integer", "minimum": 1}, "dpi": {"type": "integer", "minimum": 100, "maximum": 600}, "output_path": {"type": "string"}}, ["pdf_path", "output_path"])},
    {"name": "get_symbol_rules", "description": "Return v0.1.3 Power or Fire Alarm system scope and symbol rules.", "inputSchema": _schema({"system_id": {"type": "string", "enum": list(SYSTEMS)}, "symbol_id": {"type": "string", "enum": list(SYMBOLS)}}, [])},
    {"name": "build_symbol_template", "description": "Build a project-specific vector template from a clean legend ROI in PDF points.", "inputSchema": _schema({"pdf_path": {"type": "string"}, "page": {"type": "integer", "minimum": 1}, "roi_pdf_points": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, "output_path": {"type": "string"}}, ["pdf_path", "roi_pdf_points", "output_path"])},
        {"name": "detect_symbol_candidates", "description": "Create a high-recall candidate shortlist, crops, markup, diagnostics, and review HTML. Text-overlap suppression is enabled by default; results still require visual review.", "inputSchema": _schema({"pdf_path": {"type": "string"}, "symbol_id": {"type": "string", "enum": list(SYMBOLS)}, "template_path": {"type": "string", "description": "Optional project-specific template JSON"}, "page": {"type": "integer", "minimum": 1}, "dpi": {"type": "integer", "minimum": 150, "maximum": 600}, "output_dir": {"type": "string"}, "constellation_tolerance": {"type": "number", "minimum": 0.05, "maximum": 0.5}, "max_score": {"type": "number", "minimum": 0.05, "maximum": 0.5}, "search_x_max": {"type": "number", "minimum": 0.1, "maximum": 1.0}, "exclude_text": {"type": "boolean", "default": True}, "shortlist_limit": {"type": "integer", "minimum": 0, "maximum": 500}}, ["pdf_path", "symbol_id", "output_dir"])},
    {"name": "confirm_symbol_count", "description": "Record accepted, rejected, uncertain, and manual decisions; verify review completeness; and create auditable CSV, JSON, and markup. A report is final only when review_complete is true.", "inputSchema": _schema({"pdf_path": {"type": "string"}, "symbol_id": {"type": "string", "enum": list(SYMBOLS)}, "template_path": {"type": "string", "description": "Template used for candidate detection"}, "candidates_json": {"type": "string"}, "accepted_ids": {"type": "array", "items": {"type": "string"}}, "rejected_ids": {"type": "array", "items": {"type": "string"}}, "uncertain_ids": {"type": "array", "items": {"type": "string"}}, "manual_points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}}, "wall_door_sweep_completed": {"type": "boolean", "default": False}, "floor_or_region": {"type": "string", "description": "Visible floor or plan region for grouping the result"}, "review_notes": {"type": "string"}, "page": {"type": "integer", "minimum": 1}, "dpi": {"type": "integer", "minimum": 150, "maximum": 600}, "output_dir": {"type": "string"}}, ["pdf_path", "symbol_id", "candidates_json", "accepted_ids", "output_dir"])},
    {"name": "prepare_sheet_audit", "description": "Prepare one Power or Fire Alarm sheet in one MCP call: inspect, render an overview, run every ready vector template, create a candidate contact sheet, and return missing-template or clarification requirements.", "inputSchema": _schema({"pdf_path": {"type": "string"}, "system_id": {"type": "string", "enum": list(SYSTEMS)}, "page": {"type": "integer", "minimum": 1}, "dpi": {"type": "integer", "minimum": 150, "maximum": 600}, "overview_dpi": {"type": "integer", "minimum": 100, "maximum": 300}, "symbol_ids": {"type": "array", "items": {"type": "string"}}, "template_paths": {"type": "object", "additionalProperties": {"type": "string"}}, "output_dir": {"type": "string"}, "constellation_tolerance": {"type": "number", "minimum": 0.05, "maximum": 0.5}, "max_score": {"type": "number", "minimum": 0.05, "maximum": 0.5}, "search_x_max": {"type": "number", "minimum": 0.1, "maximum": 1.0}, "exclude_text": {"type": "boolean", "default": True}, "shortlist_limit": {"type": "integer", "minimum": 0, "maximum": 500}}, ["pdf_path", "system_id", "output_dir"])},
]

HANDLERS = {"inspect_drawing": inspect_drawing, "render_page": render_page,
            "get_symbol_rules": get_symbol_rules, "build_symbol_template": build_symbol_template,
            "detect_symbol_candidates": detect_symbol_candidates,
            "confirm_symbol_count": confirm_symbol_count,
            "prepare_sheet_audit": prepare_sheet_audit}


def _response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    message = {"jsonrpc": "2.0", "id": request_id}
    message["error" if error is not None else "result"] = error if error is not None else result
    return message


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        requested = message.get("params", {}).get("protocolVersion", "2025-06-18")
        return _response(request_id, {"protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "engineering-drawing-estimator", "version": VERSION}})
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        if name not in HANDLERS:
            return _response(request_id, error={"code": -32601, "message": f"Unknown tool: {name}"})
        try:
            data = HANDLERS[name](params.get("arguments", {}))
            return _response(request_id, {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}], "structuredContent": data, "isError": False})
        except Exception as exc:
            data = {"error": type(exc).__name__, "message": str(exc),
                    "traceback": traceback.format_exc(limit=8)}
            return _response(request_id, {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}], "structuredContent": data, "isError": True})
    if request_id is None:
        return None
    return _response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except Exception as exc:
            response = _response(None, error={"code": -32700, "message": str(exc)})
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
