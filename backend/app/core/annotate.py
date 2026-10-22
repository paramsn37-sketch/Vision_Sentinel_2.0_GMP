"""Server-side drawing for the CLI, exported videos and evidence snapshots (the UI draws its own overlays)."""

from __future__ import annotations

import cv2
import numpy as np

from .types import FrameResult, PPEStatus

GREEN, RED, AMBER, GREY, WHITE = (80, 175, 76), (54, 67, 244), (0, 170, 255), (160, 160, 160), (255, 255, 255)


def _label(img: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    y = max(th + 4, y)
    cv2.rectangle(img, (x, y - th - 4), (x + tw + 6, y), color, -1)
    cv2.putText(img, text, (x + 3, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1, cv2.LINE_AA)


def draw(
    img: np.ndarray, result: FrameResult, zones: list[tuple[str, np.ndarray]] | None = None
) -> np.ndarray:
    out = img.copy()
    for name, poly in zones or []:
        overlay = out.copy()
        cv2.fillPoly(overlay, [poly.astype(np.int32)], AMBER)
        out = cv2.addWeighted(overlay, 0.18, out, 0.82, 0)
        cv2.polylines(out, [poly.astype(np.int32)], True, AMBER, 2, cv2.LINE_AA)
        _label(out, name, int(poly[:, 0].min()), int(poly[:, 1].min()), AMBER)
    for p in result.persons:
        if not p.confirmed:
            continue
        missing = [k for k, v in p.ppe.items() if v is PPEStatus.ABSENT]
        color = RED if missing else GREEN if any(v is PPEStatus.PRESENT for v in p.ppe.values()) else GREY
        x1, y1, x2, y2 = (int(v) for v in p.xyxy)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        text = f"#{p.track_id}" + (" no " + ",".join(missing) if missing else "")
        _label(out, text, x1, y1, color)
    for it in result.objects:
        x1, y1, x2, y2 = (int(v) for v in it.xyxy)
        cv2.rectangle(out, (x1, y1), (x2, y2), GREY, 1)
    hud = f"people now {result.counts.current}   unique {result.counts.unique_total}   {result.fps:.1f} fps"
    _label(out, hud, 8, 24, (40, 40, 40))
    return out
