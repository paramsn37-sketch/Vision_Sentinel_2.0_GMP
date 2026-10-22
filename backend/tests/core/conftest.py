import numpy as np
import pytest

from app.core.types import Detection


@pytest.fixture
def frame() -> np.ndarray:
    """Plain grey 720p frame; people are painted in by helpers when appearance matters."""
    return np.full((720, 1280, 3), 90, dtype=np.uint8)


def person(x: float, y: float, w: float = 60, h: float = 160, conf: float = 0.9) -> Detection:
    return Detection("person", conf, (x, y, x + w, y + h))


def paint(frame: np.ndarray, d: Detection, color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = (int(v) for v in d.xyxy)
    frame[y1:y2, x1:x2] = color
