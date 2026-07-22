from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

VERSION = "0.1.4"
ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
TEMPLATES = ROOT / "assets" / "templates"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from detect_compound_symbol import detect_with_context  # noqa: E402
from layer_inventory import analyze_layer_signatures  # noqa: E402
from sheet_context import (  # noqa: E402
    get_sheet_context,
    inspect_pdf,
    save_context_render,
)

SYMBOLS = {
    "DUPLEX_SOCKET_OUTLET": {
        "template": "duplex_socket_starter.json",
        "layer_tokens": ["OUTLET", "SOCKET", "RECEPT"],
        "system_id": "POWER",
        "name_th": "เต้ารับคู่",
        "visual_rule": "วงกลมและเส้นขนานภายใน 2 เส้น หมุนได้ 0/90/180/270 องศา",
    },
    "SINGLE_SOCKET_OUTLET": {
        "template": "single_socket_starter.json",
        "layer_tokens": ["OUTLET", "SOCKET", "RECEPT"],
        "system_id": "POWER",
        "name_th": "เต้ารับเดี่ยว",
        "visual_rule": "วงกลมและเส้นภายใน 1 เส้น; C ใกล้เคียงมักหมายถึง CCTV",
    },
    "DATA_OUTLET": {
        "template": "data_outlet_starter.json",
        "layer_tokens": ["TEL", "DATA", "COMM"],
        "system_id": "DATA_VOICE",
        "name": "Data Outlet (RJ45)",
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

SYMBOLS.update({
    "POWER_RECEPTACLE_3P_N_E": {
        "template": None,
        "layer_tokens": ["OUTLET", "RECEPT"],
        "system_id": "POWER",
        "name": "Power Receptacle 3P+N+E",
        "visual_rule": "Circle with filled triangular pole marker; verify pole, ampere, and WP notes.",
    },
    "NON_FUSE_DISCONNECTING_SWITCH": {
        "template": None,
        "system_id": "POWER",
        "name": "Non-Fuse Disconnecting Switch",
        "visual_rule": "Project-legend disconnect enclosure; verify pole, ampere, and WP notes separately.",
    },
})

DATA_VOICE_SYMBOLS = {
    "PRIVATE_AUTOMATIC_BRANCH_EXCHANGE": "Private Automatic Branch Exchanger (PABX)",
    "MAIN_DISTRIBUTION_FRAME": "Main Distribution Frame (MDF)",
    "FIBER_OPTIC_PATCH_PANEL": "Fiber Optic Patch Panel",
    "UTP_PATCH_PANEL": "UTP Patch Panel",
    "TELEPHONE_TERMINAL_CABINET": "Telephone Terminal Cabinet",
    "TELEPHONE_OUTLET_RJ11": "Telephone Outlet (RJ11)",
    "TELEPHONE_FLOOR_OUTLET_RJ11": "Telephone Floor Outlet (RJ11)",
    "PUBLIC_TELEPHONE_OUTLET_RJ11": "Public Telephone Outlet (RJ11)",
    "DATA_FLOOR_OUTLET_RJ45": "Data Floor Outlet (RJ45)",
}
for symbol_id, name in DATA_VOICE_SYMBOLS.items():
    SYMBOLS[symbol_id] = {
        "template": None,
        "system_id": "DATA_VOICE",
        "name": name,
        "visual_rule": "Use the current project Telephone and Data legend; project-specific template required.",
    }

CCTV_SECURITY_SYMBOLS = {
    "SECURITY_KEY_SWITCH": "Security Key Switch",
    "PANIC_ALARM_PUSH_BUTTON": "Panic Alarm Push Button",
    "GLASS_BREAK_SENSOR": "Glass Break Sensor",
    "MAGNETIC_DOOR_MONITORING_CONTACT": "Magnetic Door Monitoring Contact",
    "SECURITY_DOOR_BELL": "Security Door Bell",
    "PASSIVE_INFRARED_DETECTOR": "Passive Infrared Detector",
    "CCTV_CAMERA_FIXED": "CCTV Camera Fixed Type",
    "CCTV_CAMERA_PAN_TILT": "CCTV Camera Pan-Tilt Type",
    "DUMMY_CCTV_CAMERA": "Dummy CCTV Camera",
    "SECURITY_MONITOR": "Security Monitor",
    "ACCESS_CONTROL_MAIN_TERMINAL": "Access Control Main Terminal",
    "DOOR_CONTROL_UNIT": "Door Control Unit",
    "SECURITY_CONTROL_UNIT": "Security Control Unit",
    "NETWORK_CONTROL_UNIT": "Network Control Unit",
    "SMART_CARD_READER": "Smart Card Reader",
    "ELECTROMAGNETIC_DOOR_LOCK": "Electrical Magnetic Door Lock",
    "EMERGENCY_DOOR_RELEASE_BREAK_GLASS": "Emergency Door Release Button with Break Glass",
    "DIGITAL_VIDEO_RECORDER": "Digital Video Recorder",
    "CHECK_POINT_GUARD_TOUR": "Check Point - Guard Tour",
    "SECURITY_JUNCTION_BOX": "Junction Box for Security System",
    "SECURITY_BUZZER": "Security Buzzer",
    "DOOR_RELEASE_BUTTON": "Door Release Button",
}
for symbol_id, name in CCTV_SECURITY_SYMBOLS.items():
    SYMBOLS[symbol_id] = {
        "template": None,
        "system_id": "CCTV_SECURITY",
        "name": name,
        "visual_rule": "Use the current project CCTV and Security legend; project-specific template required.",
    }

LIGHTING_SYMBOLS = {
    "ONE_WAY_LIGHTING_SWITCH": "One-Way Lighting Switch",
    "LIGHTING_SWITCH_BANK": "Lighting Switch Bank/Assembly",
    "TWO_WAY_LIGHTING_SWITCH": "Two-Way Lighting Switch",
    "INTERMEDIATE_LIGHTING_SWITCH": "Intermediate Lighting Switch",
    "FAN_SWITCH_WITH_INDICATING_LAMP": "Fan Switch with Indicating Lamp",
    "PHOTOCELL_SENSOR": "Photocell Sensor",
    "TIMER_SWITCH_MANUAL_BYPASS": "Timer Switch with Manual Bypass",
    "LIGHTING_CONTROL_PANEL": "Lighting Control Panel",
    "LIGHTING_JUNCTION_BOX": "Lighting Junction Box",
    "LIGHTING_JUNCTION_BOX_ABOVE_CEILING": "Lighting Junction Box above Ceiling",
    "CENTRAL_BATTERY_UNIT": "Central Battery Unit",
    "EMERGENCY_DOWNLIGHT_9W_2H": "Emergency Downlight 9W LED, 2 Hours",
    "FIRE_EXIT_SIGN_SINGLE_FRONT": "Fire Exit Sign 10W LED, Single Side/Front Exit",
    "FIRE_EXIT_SIGN_DOUBLE_SIDE": "Fire Exit Sign 10W LED, Double Side/Side Exit",
    "FIRE_EXIT_SIGN_SINGLE_SIDE": "Fire Exit Sign 10W LED, Single Side/Side Exit",
    "SELF_CONTAINED_EMERGENCY_LIGHT_2X9W": "Self-Contained Emergency Lighting Unit 2x9W LED, 2 Hours",
    "REMOTE_EMERGENCY_LAMP": "Remote Emergency Lamp",
    "LED_SURFACE_BATTEN_10W_20W": "LED 10W/20W Surface-Mounted Batten Luminaire",
    "LED_SURFACE_BATTEN_20W": "LED 20W Surface-Mounted Batten Luminaire",
    "LED_SURFACE_INDUSTRIAL_10W_20W": "LED 10W/20W Surface-Mounted Industrial Luminaire",
    "LED_SURFACE_INDUSTRIAL_20W": "LED 20W Surface-Mounted Industrial Luminaire",
    "LED_SURFACE_DIFFUSER": "LED Surface Diffuser Luminaire",
    "LED_SURFACE_WEATHERPROOF_IP65_10W_20W": "LED 10W 20W, SURFACE MOUNTED WEATHERPROOF IP65 LUMINAIRE C/W POLYCARBONATE BODY AND HIGH IMPACT RESISTANT ACRYLIC DIFFUSER, DRIVER.",
    "LED_RECESSED_DIFFUSER_2X10W_2X20W": "LED 2x10W 2x20W, RECESSED DIFFUSER LUMINAIRE C/W ALUMINIUM REFLECTOR, PRISMATIC DIFFUSER, C/W DRIVER.",
    "LED_RECESSED_LOUVER": "LED Recessed Louver Luminaire",
    "LED_RECESSED_LOUVER_SUPPLY_AIR": "LED Recessed Louver Luminaire with Supply Air Slot",
    "LED_DOUBLE_PARABOLIC_RECESSED_LOUVER": "LED Double-Parabolic Recessed Louver Luminaire",
    "LED_RECESSED_DOWNLIGHT_600LM": "LED Recessed Downlight 600 Lumen",
    "LED_RECESSED_DOWNLIGHT_1000LM": "LED Recessed Downlight 1000 Lumen",
    "LED_RECESSED_DOWNLIGHT_1500LM": "LED Recessed Downlight 1500 Lumen",
    "LED_MR16_DOWNLIGHT_6W": "LED MR16 Downlight 6W",
    "LED_HIGH_BAY_130W": "LED High-Bay Luminaire 130W",
    "LED_LOW_BAY_80W": "LED Low-Bay Luminaire 80W",
    "LED_FLOODLIGHT_380W": "LED Floodlight 380W IP65",
    "LED_FLOODLIGHT_900W": "LED Floodlight 900W IP65",
    "EXISTING_FLOODLIGHT": "Existing Floodlight",
    "LED_STREET_LIGHT_140W": "LED Street Light 140W",
}
for symbol_id, name in LIGHTING_SYMBOLS.items():
    SYMBOLS[symbol_id] = {
        "template": None,
        "layer_tokens": ["LIGHTING", "EQUIP", "OUTLET"],
        "system_id": "LIGHTING",
        "name": name,
        "visual_rule": "Use the current project Lighting, Emergency Lighting, and Luminaire legend; project-specific template required.",
    }

SYSTEMS = {
    "POWER": {
        "name": "Power System",
        "symbol_ids": [
            "DUPLEX_SOCKET_OUTLET",
            "SINGLE_SOCKET_OUTLET",
            "POWER_RECEPTACLE_3P_N_E",
            "NON_FUSE_DISCONNECTING_SWITCH",
        ],
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
    "DATA_VOICE": {
        "name": "Data and Voice System",
        "symbol_ids": ["DATA_OUTLET", *DATA_VOICE_SYMBOLS],
    },
    "CCTV_SECURITY": {
        "name": "CCTV and Security System",
        "symbol_ids": list(CCTV_SECURITY_SYMBOLS),
    },
    "LIGHTING": {
        "name": "Lighting System",
        "symbol_ids": list(LIGHTING_SYMBOLS),
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


def _full_response(args: dict[str, Any]) -> bool:
    return str(args.get("response_detail", "compact")).lower() == "full"


def inspect_drawing(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    return inspect_pdf(pdf)


def render_page(args: dict[str, Any]) -> dict[str, Any]:
    import fitz

    pdf = _require_file(args["pdf_path"], "PDF")
    page_number = int(args.get("page", 1))
    dpi = int(args.get("dpi", 300))
    output = Path(args["output_path"]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    try:
        if not 1 <= page_number <= len(document):
            raise ValueError(f"page must be between 1 and {len(document)}")
        pixmap = document[page_number - 1].get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(output)
        return {"output_path": str(output), "page": page_number, "dpi": dpi,
                "width_px": pixmap.width, "height_px": pixmap.height}
    finally:
        document.close()


def get_symbol_rules(args: dict[str, Any]) -> dict[str, Any]:
    system_id = args.get("system_id")
    if system_id:
        if system_id not in SYSTEMS:
            raise ValueError(f"Unsupported system_id: {system_id}")
        result = {
            "system_id": system_id,
            **SYSTEMS[system_id],
            "symbols": {
                symbol_id: SYMBOLS[symbol_id]
                for symbol_id in SYSTEMS[system_id]["symbol_ids"]
            },
        }
        if not _full_response(args):
            result["symbols"] = {
                symbol_id: {
                    "name": SYMBOLS[symbol_id].get("name", symbol_id),
                    "template_ready": bool(SYMBOLS[symbol_id].get("template")),
                }
                for symbol_id in result["symbol_ids"]
            }
        return result
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
    response = {"output_path": str(output),
            "preview_path": str(output.with_name(output.stem + "_preview.png")),
            "primitive_count": data["primitive_count"],
            "compound_part_count": len(data["compound_parts"])}
    if _full_response(args):
        response["stdout"] = result["stdout"]
    return response


def analyze_vector_layers(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    mappings = list(args.get("signature_mappings", []))
    mapping_path_value = args.get("signature_mapping_path")
    mapping_path = None
    if mapping_path_value:
        mapping_path = _require_file(mapping_path_value, "signature mapping")
        saved = json.loads(mapping_path.read_text(encoding="utf-8"))
        saved_mappings = saved.get("mappings", []) if isinstance(saved, dict) else saved
        if not isinstance(saved_mappings, list):
            raise ValueError("signature mapping file must contain a list or a mappings list")
        mappings.extend(saved_mappings)
    unknown_symbols = sorted({
        str(mapping.get("symbol_id", ""))
        for mapping in mappings
        if str(mapping.get("symbol_id", "")) not in SYMBOLS
    })
    if unknown_symbols:
        raise ValueError(f"Unsupported symbol_id in signature mappings: {unknown_symbols}")
    context, cache_hit = get_sheet_context(
        pdf,
        int(args.get("page", 1)),
        int(args.get("dpi", 150)),
        use_cache=True,
        force_reprocess=bool(args.get("force_reprocess", False)),
        require_image=False,
    )
    try:
        result = analyze_layer_signatures(
            context,
            layer_tokens=args.get("layer_tokens", []),
            exclude_annotation_layers=bool(args.get("exclude_annotation_layers", True)),
            min_long_extent_pt=float(args.get("min_long_extent_pt", 3.0)),
            max_long_extent_pt=float(args.get("max_long_extent_pt", 250.0)),
            quantization_pt=float(args.get("quantization_pt", 0.5)),
            signature_mappings=mappings,
            output_dir=args["output_dir"],
        )
        result["context_id"] = context.context_id
        result["context_cache_hit"] = cache_hit
        result["classification"] = context.profile["classification"]
        result["signature_mapping_path"] = str(mapping_path) if mapping_path else None
        if _full_response(args):
            return result
        limit = int(args.get("summary_limit", 12))
        return {
            "classification": result["classification"],
            "context_id": result["context_id"],
            "context_cache_hit": result["context_cache_hit"],
            "matching_layers": result["matching_layers"],
            "filtered_drawing_paths": result["filtered_drawing_paths"],
            "signature_count": result["signature_count"],
            "top_signatures": [
                {key: group[key] for key in (
                    "signature_id", "layer", "shape_family", "short_extent_pt",
                    "long_extent_pt", "filled", "count"
                )}
                for group in result["signatures"][:limit]
            ],
            "mapped_counts": result["mapped_counts"],
            "ambiguous_signature_ids": result["ambiguous_signature_ids"],
            "clarification_required": result["clarification_required"],
            "signature_mapping_path": result["signature_mapping_path"],
            "inventory_json": result["inventory_json"],
            "mapped_candidates_json": result["mapped_candidates_json"],
            "elapsed_seconds": result["elapsed_seconds"],
            "review_required": True,
        }
    finally:
        context.release_oversized_image()


def _detect_symbol_candidates_with_context(
    args: dict[str, Any], context, context_cache_hit: bool
) -> dict[str, Any]:
    symbol_id = args["symbol_id"]
    if symbol_id not in SYMBOLS:
        raise ValueError(f"Unsupported symbol_id: {symbol_id}")
    template = _symbol_template(symbol_id, args.get("template_path"))
    output = _output_dir(args["output_dir"])
    diagnostics = detect_with_context(
        context,
        template,
        output,
        constellation_tolerance=float(args.get("constellation_tolerance", 0.16)),
        max_score=float(args.get("max_score", 0.16)),
        search_x_max=float(args.get("search_x_max", 0.80)),
        shortlist_limit=int(args.get("shortlist_limit", 40)),
        exclude_text=bool(args.get("exclude_text", True)),
        exclude_annotation_layers=bool(args.get("exclude_annotation_layers", True)),
        text_overlap_threshold=float(args.get("text_overlap_threshold", 0.35)),
        excluded_regions=args.get("excluded_regions", []),
        included_regions=args.get("included_regions", []),
        preferred_layer_tokens=SYMBOLS[symbol_id].get("layer_tokens", []),
        context_cache_hit=context_cache_hit,
    )
    candidates = json.loads((output / "candidates.json").read_text(encoding="utf-8"))
    return {
        "symbol_id": symbol_id,
        "candidate_count": len(candidates),
        "candidates_json": str(output / "candidates.json"),
        "filtered_candidates_json": str(output / "filtered_candidates.json"),
        "filtered_candidates_markup": str(output / "filtered_candidates.png"),
        "candidates_csv": str(output / "candidates.csv"),
        "markup_path": str(output / "marked_candidates.png"),
        "review_html": str(output / "review.html"),
        "diagnostics": diagnostics,
        "template_path": str(template),
        "warning": "Candidate Filtering v2 suppresses strong text, annotation-layer, and region evidence while preserving an audit file. Visual review remains mandatory.",
        "stdout": (
            f"Context {context.context_id}; {len(candidates)} candidates; "
            f"detection {diagnostics['timing_seconds']['detection_total']:.3f}s"
        ),
    }


def detect_symbol_candidates(args: dict[str, Any]) -> dict[str, Any]:
    pdf = _require_file(args["pdf_path"], "PDF")
    context, cache_hit = get_sheet_context(
        pdf,
        int(args.get("page", 1)),
        int(args.get("dpi", 300)),
        use_cache=True,
        force_reprocess=bool(args.get("force_reprocess", False)),
    )
    try:
        result = _detect_symbol_candidates_with_context(args, context, cache_hit)
        if _full_response(args):
            return result
        return {
            "symbol_id": result["symbol_id"],
            "candidate_count": result["candidate_count"],
            "candidates_json": result["candidates_json"],
            "filtered_candidates_json": result["filtered_candidates_json"],
            "markup_path": result["markup_path"],
            "review_html": result["review_html"],
            "template_path": result["template_path"],
            "context_id": result["diagnostics"]["context_id"],
            "context_cache_hit": result["diagnostics"]["context_cache_hit"],
            "elapsed_seconds": result["diagnostics"]["timing_seconds"]["detection_total"],
            "review_required": True,
        }
    finally:
        context.release_oversized_image()


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
    response = {
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
    }
    if _full_response(args):
        response["stdout"] = result["stdout"]
    return response


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
        sheet = Image.new("RGB", (640, 180), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (24, 72),
            "No candidates after Candidate Filtering v2. Review filtered_candidates.json and sweep the plan before confirming zero.",
            fill="black",
            font=ImageFont.load_default(),
        )
        sheet.save(output)
        return str(output)

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
            f"v0.1.4 supports only {sorted(SYSTEMS)}; received {system_id}"
        )
    page = int(args.get("page", 1))
    dpi = int(args.get("dpi", 300))
    output = _output_dir(args["output_dir"])
    context, context_cache_hit = get_sheet_context(
        pdf,
        page,
        dpi,
        use_cache=True,
        force_reprocess=bool(args.get("force_reprocess", False)),
    )
    page_info = context.profile
    prepared_at = time.perf_counter()

    overview = output / f"page_{page:03d}_overview.png"
    overview_result = save_context_render(
        context, overview, int(args.get("overview_dpi", 160))
    )
    overview_at = time.perf_counter()

    requested = args.get("symbol_ids") or SYSTEMS[system_id]["symbol_ids"]
    invalid = [
        symbol_id
        for symbol_id in requested
        if symbol_id not in SYSTEMS[system_id]["symbol_ids"]
    ]
    if invalid:
        raise ValueError(
            f"Symbols outside {system_id} v0.1.4 scope: {sorted(invalid)}"
        )

    template_paths = args.get("template_paths", {})
    runs = []
    template_required = []
    skipped = []
    if not page_info["automatic_matching_supported"]:
        skipped.append({
            "page": page,
            "reason": (
                "Automatic matching requires dense vector geometry; "
                f"Page Profiler v2 classified this page as {page_info['classification']}."
            ),
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
            runs.append(_detect_symbol_candidates_with_context({
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
                "exclude_annotation_layers": args.get("exclude_annotation_layers", True),
                "text_overlap_threshold": args.get("text_overlap_threshold", 0.35),
                "excluded_regions": args.get("excluded_regions", []),
                "included_regions": args.get("included_regions", []),
                "shortlist_limit": args.get("shortlist_limit", 40),
            }, context, context_cache_hit))

    detected_at = time.perf_counter()
    contact_sheet = _write_contact_sheet(runs, output / "candidate_contact_sheet.png")
    finished = time.perf_counter()
    manifest = {
        "version": VERSION,
        "system_id": system_id,
        "system_name": SYSTEMS[system_id]["name"],
        "pdf_path": str(pdf),
        "page": page,
        "classification": page_info["classification"],
        "page_profile": page_info,
        "context_id": context.context_id,
        "context_cache_hit": context_cache_hit,
        "shared_context": True,
        "overview": overview_result,
        "requested_symbol_ids": requested,
        "runs": runs,
        "candidate_count": sum(run["candidate_count"] for run in runs),
        "contact_sheet": contact_sheet,
        "template_required": template_required,
        "skipped": skipped,
        "clarification_required": bool(template_required or skipped),
        "timing_seconds": {
            "context_preparation": round(prepared_at - started, 3),
            "overview_from_context": round(overview_at - prepared_at, 3),
            "all_symbol_detection": round(detected_at - overview_at, 3),
            "contact_sheet": round(finished - detected_at, 3),
            "total": round(finished - started, 3),
        },
        "elapsed_seconds": round(finished - started, 3),
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
    context.release_oversized_image()
    if _full_response(args):
        return manifest
    return {
        "version": VERSION,
        "system_id": system_id,
        "classification": page_info["classification"],
        "context_id": context.context_id,
        "context_cache_hit": context_cache_hit,
        "shared_context": True,
        "overview_path": overview_result["output_path"],
        "candidate_count": manifest["candidate_count"],
        "runs": [
            {
                "symbol_id": run["symbol_id"],
                "candidate_count": run["candidate_count"],
                "candidates_json": run["candidates_json"],
                "review_html": run["review_html"],
            }
            for run in runs
        ],
        "template_required": [item["symbol_id"] for item in template_required],
        "skipped": skipped,
        "clarification_required": manifest["clarification_required"],
        "contact_sheet": contact_sheet,
        "timing_seconds": manifest["timing_seconds"],
        "manifest_json": str(manifest_path),
        "next_step": "Review the overview/contact sheet, build only missing templates, then confirm every candidate.",
    }


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


RESPONSE_DETAIL = {
    "type": "string", "enum": ["compact", "full"], "default": "compact"
}
REGIONS = {
    "type": "array",
    "items": {
        "type": "array", "items": {"type": "number"},
        "minItems": 4, "maxItems": 4,
    },
}
DETECTION_OPTIONS = {
    "page": {"type": "integer", "minimum": 1},
    "dpi": {"type": "integer", "minimum": 150, "maximum": 600},
    "constellation_tolerance": {"type": "number", "minimum": 0.05, "maximum": 0.5},
    "max_score": {"type": "number", "minimum": 0.05, "maximum": 0.5},
    "search_x_max": {"type": "number", "minimum": 0.1, "maximum": 1.0},
    "exclude_text": {"type": "boolean", "default": True},
    "exclude_annotation_layers": {"type": "boolean", "default": True},
    "text_overlap_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.35},
    "excluded_regions": REGIONS,
    "included_regions": REGIONS,
    "force_reprocess": {"type": "boolean", "default": False},
    "shortlist_limit": {"type": "integer", "minimum": 0, "maximum": 500},
    "response_detail": RESPONSE_DETAIL,
}

TOOLS = [
    {
        "name": "inspect_drawing",
        "description": "Run native Page Profiler v2 before symbol counting.",
        "inputSchema": _schema({"pdf_path": {"type": "string"}}, ["pdf_path"]),
    },
    {
        "name": "render_page",
        "description": "Render one PDF page for visual review.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "dpi": {"type": "integer", "minimum": 100, "maximum": 600},
            "output_path": {"type": "string"},
        }, ["pdf_path", "output_path"]),
    },
    {
        "name": "get_symbol_rules",
        "description": "Return supported scope and rules; compact by default.",
        "inputSchema": _schema({
            "system_id": {"type": "string", "enum": list(SYSTEMS)},
            "symbol_id": {"type": "string", "enum": list(SYMBOLS)},
            "response_detail": RESPONSE_DETAIL,
        }, []),
    },
    {
        "name": "build_symbol_template",
        "description": "Build a project-specific vector template from a clean legend ROI.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "roi_pdf_points": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
            "output_path": {"type": "string"},
            "response_detail": RESPONSE_DETAIL,
        }, ["pdf_path", "roi_pdf_points", "output_path"]),
    },
    {
        "name": "analyze_vector_layers",
        "description": "Create compact rotation-normalized layer signatures and optional caller-confirmed mapped candidates; full coordinates stay in JSON.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "dpi": {"type": "integer", "minimum": 100, "maximum": 300, "default": 150},
            "layer_tokens": {"type": "array", "items": {"type": "string"}},
            "exclude_annotation_layers": {"type": "boolean", "default": True},
            "min_long_extent_pt": {"type": "number", "minimum": 0.1},
            "max_long_extent_pt": {"type": "number", "minimum": 1.0},
            "quantization_pt": {"type": "number", "minimum": 0.1, "maximum": 5.0},
            "signature_mappings": {"type": "array", "items": {"type": "object"}},
            "signature_mapping_path": {"type": "string"},
            "summary_limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
            "response_detail": RESPONSE_DETAIL,
            "force_reprocess": {"type": "boolean", "default": False},
            "output_dir": {"type": "string"},
        }, ["pdf_path", "output_dir"]),
    },
    {
        "name": "detect_symbol_candidates",
        "description": "Create reviewed candidate artifacts; compact response by default.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "symbol_id": {"type": "string", "enum": list(SYMBOLS)},
            "template_path": {"type": "string"},
            "output_dir": {"type": "string"},
            **DETECTION_OPTIONS,
        }, ["pdf_path", "symbol_id", "output_dir"]),
    },
    {
        "name": "confirm_symbol_count",
        "description": "Record final review decisions and create auditable CSV, JSON, and markup.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "symbol_id": {"type": "string", "enum": list(SYMBOLS)},
            "template_path": {"type": "string"},
            "candidates_json": {"type": "string"},
            "accepted_ids": {"type": "array", "items": {"type": "string"}},
            "rejected_ids": {"type": "array", "items": {"type": "string"}},
            "uncertain_ids": {"type": "array", "items": {"type": "string"}},
            "manual_points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}},
            "wall_door_sweep_completed": {"type": "boolean", "default": False},
            "floor_or_region": {"type": "string"},
            "review_notes": {"type": "string"},
            "page": {"type": "integer", "minimum": 1},
            "dpi": {"type": "integer", "minimum": 150, "maximum": 600},
            "output_dir": {"type": "string"},
            "response_detail": RESPONSE_DETAIL,
        }, ["pdf_path", "symbol_id", "candidates_json", "accepted_ids", "output_dir"]),
    },
    {
        "name": "prepare_sheet_audit",
        "description": "Prepare one system in one shared-context pass; compact response by default and full manifest on disk.",
        "inputSchema": _schema({
            "pdf_path": {"type": "string"},
            "system_id": {"type": "string", "enum": list(SYSTEMS)},
            "overview_dpi": {"type": "integer", "minimum": 100, "maximum": 300},
            "symbol_ids": {"type": "array", "items": {"type": "string"}},
            "template_paths": {"type": "object", "additionalProperties": {"type": "string"}},
            "output_dir": {"type": "string"},
            **DETECTION_OPTIONS,
        }, ["pdf_path", "system_id", "output_dir"]),
    },
]

HANDLERS = {"inspect_drawing": inspect_drawing, "render_page": render_page,
            "get_symbol_rules": get_symbol_rules, "build_symbol_template": build_symbol_template,
            "analyze_vector_layers": analyze_vector_layers,
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
