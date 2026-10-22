"""Runtime file layout under settings.data_dir and image helpers for evidence snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..core.types import Box


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def db(self) -> Path:
        return self.root / "vision_sentinel.db"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @property
    def xai(self) -> Path:
        return self.root / "xai"

    @property
    def uploads(self) -> Path:
        return self.root / "uploads"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def feedback(self) -> Path:
        return self.root / "feedback"

    def ensure(self) -> Paths:
        for d in (self.root, self.snapshots, self.xai, self.uploads, self.exports, self.feedback):
            d.mkdir(parents=True, exist_ok=True)
        return self


def encode_jpeg(img: np.ndarray, quality: int = 80, max_width: int | None = None) -> bytes:
    if max_width and img.shape[1] > max_width:
        s = max_width / img.shape[1]
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("jpeg encoding failed")
    return buf.tobytes()


def decode_jpeg(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    return img


def blur_heads(img: np.ndarray, boxes: list[Box]) -> np.ndarray:
    """Privacy option: blur the top 22% of every person box (head and face)."""
    out = img.copy()
    for x1, y1, x2, y2 in boxes:
        hy2 = int(y1 + 0.22 * (y2 - y1))
        xa, ya, xb = max(0, int(x1)), max(0, int(y1)), min(out.shape[1], int(x2))
        if xb - xa > 2 and hy2 - ya > 2:
            roi = out[ya:hy2, xa:xb]
            k = max(3, (min(roi.shape[:2]) // 3) | 1)
            out[ya:hy2, xa:xb] = cv2.GaussianBlur(roi, (k, k), 0)
    return out
