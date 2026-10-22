"""Cheap appearance cue for the lost-track merge: an HSV histogram of the torso crop."""

from __future__ import annotations

import cv2
import numpy as np

from ..types import Box

_BINS = [16, 8]
_RANGES = [0, 180, 0, 256]


def torso_histogram(frame: np.ndarray, box: Box) -> np.ndarray | None:
    h_img, w_img = frame.shape[:2]
    x1, y1, x2, y2 = box
    h = y2 - y1
    tx1, tx2 = int(max(0, x1)), int(min(w_img, x2))
    ty1, ty2 = int(max(0, y1 + 0.2 * h)), int(min(h_img, y1 + 0.6 * h))
    if tx2 - tx1 < 4 or ty2 - ty1 < 4:
        return None
    hsv = cv2.cvtColor(frame[ty1:ty2, tx1:tx2], cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, _BINS, _RANGES)
    cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)
    return hist


def histogram_distance(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Bhattacharyya distance in [0, 1]; 1.0 (no evidence of similarity) when either side is missing."""
    if a is None or b is None:
        return 1.0
    return float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))
