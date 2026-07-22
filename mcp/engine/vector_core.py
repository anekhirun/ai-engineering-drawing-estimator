from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import cv2
import fitz
import numpy as np


@dataclass
class Primitive:
    points: np.ndarray
    bbox: tuple[float, float, float, float]
    length: float
    layer: str = ""
    stroke_width: float = 0.0


def _sample_cubic(p0, p1, p2, p3, count=12):
    values = []
    for t in np.linspace(0.0, 1.0, count):
        point = (
            (1 - t) ** 3 * np.array([p0.x, p0.y])
            + 3 * (1 - t) ** 2 * t * np.array([p1.x, p1.y])
            + 3 * (1 - t) * t ** 2 * np.array([p2.x, p2.y])
            + t ** 3 * np.array([p3.x, p3.y])
        )
        values.append(point)
    return np.asarray(values, dtype=np.float32)


def _primitive(points, *, layer="", stroke_width=0.0):
    points = np.asarray(points, dtype=np.float32)
    if len(points) < 2:
        return None
    x1, y1 = points.min(axis=0)
    x2, y2 = points.max(axis=0)
    length = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
    return Primitive(
        points,
        (float(x1), float(y1), float(x2), float(y2)),
        length,
        str(layer or ""),
        float(stroke_width or 0.0),
    )


def extract_primitives_from_drawings(drawings) -> list[Primitive]:
    result = []
    for drawing in drawings:
        metadata = {
            "layer": drawing.get("layer", ""),
            "stroke_width": drawing.get("width", 0.0),
        }
        for item in drawing.get("items", []):
            kind = item[0]

            if kind == "l":
                p1, p2 = item[1], item[2]
                primitive = _primitive(
                    [[p1.x, p1.y], [p2.x, p2.y]], **metadata
                )
                if primitive:
                    result.append(primitive)

            elif kind == "c":
                p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
                primitive = _primitive(
                    _sample_cubic(p0, p1, p2, p3), **metadata
                )
                if primitive:
                    result.append(primitive)

            elif kind == "re":
                rect = item[1]
                points = [
                    [rect.x0, rect.y0], [rect.x1, rect.y0],
                    [rect.x1, rect.y1], [rect.x0, rect.y1],
                    [rect.x0, rect.y0],
                ]
                primitive = _primitive(points, **metadata)
                if primitive:
                    result.append(primitive)

            elif kind == "qu":
                quad = item[1]
                points = [
                    [quad.ul.x, quad.ul.y],
                    [quad.ur.x, quad.ur.y],
                    [quad.lr.x, quad.lr.y],
                    [quad.ll.x, quad.ll.y],
                    [quad.ul.x, quad.ul.y],
                ]
                primitive = _primitive(points, **metadata)
                if primitive:
                    result.append(primitive)

    return result


def extract_primitives(page: fitz.Page) -> list[Primitive]:
    return extract_primitives_from_drawings(page.get_drawings())


def bbox_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def intersects(bbox, roi):
    ax1, ay1, ax2, ay2 = bbox
    bx1, by1, bx2, by2 = roi
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)


def center_inside(bbox, roi):
    cx, cy = bbox_center(bbox)
    x1, y1, x2, y2 = roi
    return x1 <= cx <= x2 and y1 <= cy <= y2


def select_primitives(
    primitives,
    roi,
    max_length_factor=2.2,
    require_center_inside=False,
    require_bbox_inside=False,
):
    width = roi[2] - roi[0]
    height = roi[3] - roi[1]
    maximum_length = math.hypot(width, height) * max_length_factor
    selected = []
    for primitive in primitives:
        if not intersects(primitive.bbox, roi):
            continue
        if require_center_inside and not center_inside(primitive.bbox, roi):
            continue
        if require_bbox_inside:
            x1, y1, x2, y2 = primitive.bbox
            if not (roi[0] <= x1 and x2 <= roi[2] and roi[1] <= y1 and y2 <= roi[3]):
                continue
        if primitive.length <= maximum_length:
            selected.append(primitive)
    return selected


def primitive_points_in_roi(primitives, roi):
    x1, y1, x2, y2 = roi
    collected = []
    for primitive in primitives:
        points = primitive.points
        mask = (
            (points[:, 0] >= x1) & (points[:, 0] <= x2)
            & (points[:, 1] >= y1) & (points[:, 1] <= y2)
        )
        selected = points[mask]
        if len(selected):
            collected.append(selected)
    if not collected:
        return np.empty((0, 2), dtype=np.float32)
    return np.vstack(collected)


def points_to_mask(points, roi, grid_size=72, padding=4):
    mask = np.zeros((grid_size, grid_size), dtype=np.uint8)
    if len(points) == 0:
        return mask

    x1, y1, x2, y2 = roi
    width = max(x2 - x1, 1e-6)
    height = max(y2 - y1, 1e-6)

    normalized = np.empty_like(points, dtype=np.float32)
    normalized[:, 0] = (
        padding + (points[:, 0] - x1) / width * (grid_size - 1 - 2 * padding)
    )
    normalized[:, 1] = (
        padding + (points[:, 1] - y1) / height * (grid_size - 1 - 2 * padding)
    )
    normalized = np.round(normalized).astype(np.int32)

    for point in normalized:
        x, y = int(point[0]), int(point[1])
        if 0 <= x < grid_size and 0 <= y < grid_size:
            cv2.circle(mask, (x, y), 1, 255, -1)

    return mask


def rotate_mask(mask, angle):
    if angle == 0:
        return mask
    if angle == 90:
        return cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(mask, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(mask, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(angle)


def chamfer_score(mask_a, mask_b):
    binary_a = mask_a > 0
    binary_b = mask_b > 0
    if binary_a.sum() < 3 or binary_b.sum() < 3:
        return 1.0

    distance_to_b = cv2.distanceTransform(
        (~binary_b).astype(np.uint8), cv2.DIST_L2, 3
    )
    distance_to_a = cv2.distanceTransform(
        (~binary_a).astype(np.uint8), cv2.DIST_L2, 3
    )

    forward = float(distance_to_b[binary_a].mean())
    backward = float(distance_to_a[binary_b].mean())
    diagonal = math.hypot(mask_a.shape[0], mask_a.shape[1])
    return (forward + backward) / (2.0 * diagonal)


def best_rotation_score(template_mask, candidate_mask):
    best_score = 1.0
    best_rotation = 0
    for angle in (0, 90, 180, 270):
        rotated = rotate_mask(candidate_mask, angle)
        score = chamfer_score(template_mask, rotated)
        if score < best_score:
            best_score = score
            best_rotation = angle
    return best_score, best_rotation
