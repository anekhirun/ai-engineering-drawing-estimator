from __future__ import annotations

import hashlib
import math
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np

from vector_core import extract_primitives_from_drawings


PROFILE_VERSION = "2"
CONTEXT_VERSION = "2"
CONTEXT_CACHE_SIZE = 2
MAX_CACHED_IMAGE_BYTES = 256 * 1024 * 1024


class PrimitiveSpatialIndex:
    """Uniform page index shared by every symbol detector on one sheet."""

    def __init__(self, descriptors: list[dict[str, float]], cell_size: float = 24.0):
        self.cell_size = max(float(cell_size), 1.0)
        self.cells: dict[tuple[int, int], list[int]] = defaultdict(list)
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


def render_page_image(page: fitz.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8)
    image = image.reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def primitive_abs_descriptor(primitive) -> dict[str, float]:
    x1, y1, x2, y2 = primitive.bbox
    dx = primitive.points[-1, 0] - primitive.points[0, 0]
    dy = primitive.points[-1, 1] - primitive.points[0, 1]
    return {
        "cx": (x1 + x2) / 2,
        "cy": (y1 + y2) / 2,
        "width": x2 - x1,
        "height": y2 - y1,
        "length": primitive.length,
        "angle": math.degrees(math.atan2(dy, dx)) % 180.0,
    }


def text_boxes(page: fitz.Page) -> list[tuple[float, float, float, float]]:
    boxes = []
    for word in page.get_text("words"):
        if len(word) >= 4:
            boxes.append(tuple(map(float, word[:4])))
    return boxes


def _image_area_ratio(page: fitz.Page) -> float:
    page_area = max(float(page.rect.width * page.rect.height), 1.0)
    area = 0.0
    try:
        image_info = page.get_image_info(xrefs=True)
    except TypeError:
        image_info = page.get_image_info()
    for item in image_info:
        bbox = item.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = map(float, bbox)
        area += max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return round(min(area / page_area, 1.0), 4)


def profile_page(
    page: fitz.Page,
    page_number: int,
    drawings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    drawings = page.get_drawings() if drawings is None else drawings
    vector_items = sum(len(drawing.get("items", ())) for drawing in drawings)
    embedded_images = len(page.get_images(full=True))
    text_characters = len(page.get_text("text"))
    image_area_ratio = _image_area_ratio(page)

    if vector_items > 100 and image_area_ratio < 0.25:
        classification = "vector_clean"
        confidence = 0.96
        reason = "Dense vector geometry with little embedded-image coverage."
    elif vector_items > 100:
        classification = "hybrid"
        confidence = 0.92
        reason = "Dense vector geometry and material embedded-image coverage."
    elif image_area_ratio >= 0.50 and vector_items < 100:
        classification = "raster_scan"
        confidence = 0.92
        reason = "A page-sized image dominates while vector geometry is sparse."
    elif vector_items > 0 and (embedded_images or text_characters):
        classification = "hybrid"
        confidence = 0.72
        reason = "Sparse vector geometry is mixed with text or images."
    elif vector_items > 0:
        classification = "vector_sparse"
        confidence = 0.68
        reason = "Vector geometry exists but is below the automatic-match threshold."
    else:
        classification = "unknown"
        confidence = 0.45
        reason = "No reliable vector or page-image signal was found."

    automatic_matching_supported = vector_items > 100
    legacy_classification = (
        "vector_or_hybrid"
        if automatic_matching_supported
        else "likely_raster" if embedded_images else "unknown"
    )
    return {
        "profile_version": PROFILE_VERSION,
        "page": page_number,
        "width_pt": float(page.rect.width),
        "height_pt": float(page.rect.height),
        "drawing_paths": len(drawings),
        "vector_items": vector_items,
        "embedded_images": embedded_images,
        "embedded_image_area_ratio_estimate": image_area_ratio,
        "text_characters": text_characters,
        "classification": classification,
        "classification_confidence": confidence,
        "classification_reason": reason,
        "legacy_classification": legacy_classification,
        "automatic_matching_supported": automatic_matching_supported,
    }


def inspect_pdf(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path).expanduser().resolve()
    # Reading from bytes avoids transient source-file locks on Windows.
    document = fitz.open(stream=path.read_bytes(), filetype="pdf")
    try:
        pages = [profile_page(page, index + 1) for index, page in enumerate(document)]
    finally:
        document.close()
    return {"pdf_path": str(path), "page_count": len(pages), "pages": pages}


def _context_key(path: Path, page_number: int, dpi: int) -> str:
    stat = path.stat()
    payload = (
        f"{path}|{stat.st_size}|{stat.st_mtime_ns}|{page_number}|{dpi}|"
        f"profile-{PROFILE_VERSION}|context-{CONTEXT_VERSION}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass
class SheetContext:
    pdf_path: Path
    page_number: int
    dpi: int
    context_id: str
    document: fitz.Document
    page: fitz.Page
    profile: dict[str, Any]
    drawings: list[dict[str, Any]]
    primitives: list[Any]
    descriptors: list[dict[str, float]]
    spatial_index: PrimitiveSpatialIndex
    text_bboxes: list[tuple[float, float, float, float]]
    image: np.ndarray
    preparation_seconds: float

    def close(self) -> None:
        if not self.document.is_closed:
            self.document.close()

    def release_oversized_image(self) -> None:
        """Keep geometry cached without retaining an unusually large render."""
        if self.image.nbytes > MAX_CACHED_IMAGE_BYTES:
            self.image = np.empty((0, 0, 3), dtype=np.uint8)


_CONTEXT_CACHE: OrderedDict[str, SheetContext] = OrderedDict()


def clear_context_cache() -> None:
    while _CONTEXT_CACHE:
        _, context = _CONTEXT_CACHE.popitem(last=False)
        context.close()


def get_sheet_context(
    pdf_path: str | Path,
    page_number: int,
    dpi: int,
    *,
    use_cache: bool = True,
    force_reprocess: bool = False,
    require_image: bool = True,
) -> tuple[SheetContext, bool]:
    path = Path(pdf_path).expanduser().resolve()
    key = _context_key(path, page_number, dpi)
    if use_cache and not force_reprocess and key in _CONTEXT_CACHE:
        context = _CONTEXT_CACHE.pop(key)
        _CONTEXT_CACHE[key] = context
        if require_image and context.image.size == 0:
            context.image = render_page_image(context.page, context.dpi)
        return context, True

    started = time.perf_counter()
    # Cached contexts must not hold a Windows file handle on the source PDF.
    document = fitz.open(stream=path.read_bytes(), filetype="pdf")
    if not 1 <= page_number <= len(document):
        document.close()
        raise ValueError(f"page must be between 1 and {len(document)}")
    page = document[page_number - 1]
    drawings = page.get_drawings()
    primitives = extract_primitives_from_drawings(drawings)
    descriptors = [primitive_abs_descriptor(item) for item in primitives]
    context = SheetContext(
        pdf_path=path,
        page_number=page_number,
        dpi=dpi,
        context_id=key,
        document=document,
        page=page,
        profile=profile_page(page, page_number, drawings),
        drawings=drawings,
        primitives=primitives,
        descriptors=descriptors,
        spatial_index=PrimitiveSpatialIndex(descriptors),
        text_bboxes=text_boxes(page),
        image=(
            render_page_image(page, dpi)
            if require_image
            else np.empty((0, 0, 3), dtype=np.uint8)
        ),
        preparation_seconds=round(time.perf_counter() - started, 3),
    )

    if use_cache:
        if key in _CONTEXT_CACHE:
            _CONTEXT_CACHE.pop(key).close()
        _CONTEXT_CACHE[key] = context
        while len(_CONTEXT_CACHE) > CONTEXT_CACHE_SIZE:
            _, evicted = _CONTEXT_CACHE.popitem(last=False)
            evicted.close()
    return context, False


def save_context_render(context: SheetContext, output: Path, dpi: int) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if dpi == context.dpi:
        image = context.image
    else:
        scale = dpi / context.dpi
        image = cv2.resize(
            context.image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
        )
    if not cv2.imwrite(str(output), image):
        raise OSError(f"Could not write rendered page: {output}")
    return {
        "output_path": str(output),
        "page": context.page_number,
        "dpi": dpi,
        "width_px": int(image.shape[1]),
        "height_px": int(image.shape[0]),
        "source": "shared_sheet_context",
    }
