"""Explainability on real weights (stock COCO person model is enough to test the mechanics)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.detection.detector import load_model_info

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images"
pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def cam():
    from ultralytics import YOLO

    from app.core.xai.cam import YoloCAM

    info = load_model_info()
    y = YOLO(str(info.weights))
    return YoloCAM(y.model, y.names, 320), y


def synthetic_person_frame() -> tuple[np.ndarray, tuple]:
    """Paste a real person crop from a fixture onto a plain background at a known spot."""
    for p in sorted(FIXTURES.glob("openimages*.jpg")):
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        for line in p.with_suffix(".txt").read_text().split("\n"):
            parts = line.split()
            if parts and parts[0] == "0" and float(parts[4]) > 0.4:
                cx, cy, bw, bh = (float(v) for v in parts[1:])
                x1, y1 = int((cx - bw / 2) * w), int((cy - bh / 2) * h)
                x2, y2 = int((cx + bw / 2) * w), int((cy + bh / 2) * h)
                crop = img[y1:y2, x1:x2]
                canvas = np.full((480, 640, 3), 128, np.uint8)
                ch, cw = min(400, crop.shape[0]), min(300, crop.shape[1])
                canvas[40 : 40 + ch, 300 : 300 + cw] = cv2.resize(crop, (cw, ch))
                return canvas, (300.0, 40.0, 300.0 + cw, 40.0 + ch)
    pytest.skip("no suitable person fixture")


def test_heatmap_matches_frame_and_peaks_on_person(cam) -> None:
    c, yolo = cam
    frame, _ = synthetic_person_frame()
    r = yolo.predict(frame, imgsz=320, verbose=False)[0]
    persons = [b for b in r.boxes if r.names[int(b.cls)] == "person"]
    assert persons, "detector should find the pasted person"
    box = tuple(persons[0].xyxy[0].tolist())
    e = c.gradcam(frame, box, "person")
    assert e.heatmap.shape == frame.shape[:2]
    assert e.heatmap.min() >= 0.0 and e.heatmap.max() <= 1.0
    assert e.peak_in_box
    assert e.energy_in_box is not None and e.energy_in_box > 0.5
    ec = c.eigencam(frame, box, "person")
    assert ec.heatmap.shape == frame.shape[:2]


def test_worker_cache_and_concurrency(cam, tmp_path) -> None:
    from app.core.xai.worker import XAIWorker

    c, _ = cam
    frame, box = synthetic_person_frame()
    w = XAIWorker(c, tmp_path)
    try:
        jobs = [w.submit(frame, (box[0] + i, box[1], box[2], box[3]), "person") for i in range(6)]
        jobs.append(w.submit(frame, None, None, method="eigencam"))
        results = [w.wait(j.id, timeout=120) for j in jobs]
        assert all(r is not None and r.status == "done" for r in results)
        again = w.submit(frame, (box[0], box[1], box[2], box[3]), "person")
        assert again.id == jobs[0].id  # cache hit returns the finished job
        assert Path(results[0].overlay_path).exists()
        # hooks/grad state must not accumulate: parameters never require grad
        assert not any(p.requires_grad for p in c.model.parameters())
    finally:
        w.close()


def test_gradcam_requires_target(cam, tmp_path) -> None:
    from app.core.xai.worker import XAIWorker

    w = XAIWorker(cam[0], tmp_path)
    try:
        with pytest.raises(ValueError):
            w.submit(np.zeros((10, 10, 3), np.uint8), None, None, method="gradcam")
    finally:
        w.close()
