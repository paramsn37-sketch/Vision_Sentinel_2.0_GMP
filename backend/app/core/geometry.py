"""Small box helpers used across stages."""

from __future__ import annotations

from .types import Box


def area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def iou(a: Box, b: Box) -> float:
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def ioa(item: Box, region: Box) -> float:
    """Share of `item` that lies inside `region` (intersection over the item's area)."""
    a = area(item)
    return intersection(item, region) / a if a > 0 else 0.0


def center(b: Box) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def foot_point(b: Box, raise_frac: float = 0.05) -> tuple[float, float]:
    h = b[3] - b[1]
    return (b[0] + b[2]) / 2, b[3] - raise_frac * h
