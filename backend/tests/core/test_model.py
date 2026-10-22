"""Gate for the promoted detector (Phase 2): `uv run pytest -m model`. Skipped until models/model.json exists."""

from pathlib import Path

import pytest
import yaml

from app.core.detection.detector import MODELS_DIR, load_model_info

REPO = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images"

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(not (MODELS_DIR / "model.json").exists(), reason="no promoted model in models/"),
]


def test_classes_match_taxonomy() -> None:
    names = yaml.safe_load((REPO / "training" / "configs" / "data.yaml").read_text())["names"]
    info = load_model_info()
    assert info.is_ppe_model
    assert info.classes == [names[i] for i in sorted(names)]
    assert set(info.thresholds) == set(info.classes)


def test_person_found_in_fixture_images() -> None:
    from ultralytics import YOLO

    info = load_model_info()
    model = YOLO(str(info.weights))
    with_person = [
        p for p in sorted(FIXTURES.glob("*.jpg"))
        if any(line.split()[0] == "0" for line in p.with_suffix(".txt").read_text().splitlines() if line.strip())
    ]  # fmt: skip
    assert len(with_person) >= 10
    found = 0
    for p in with_person:
        r = model.predict(str(p), imgsz=info.imgsz, conf=info.thresholds["person"], verbose=False)[0]
        found += any(int(c) == 0 for c in r.boxes.cls)
    assert found / len(with_person) >= 0.9, f"person found in {found}/{len(with_person)} fixture images"


def test_people_come_from_the_person_model_and_ppe_from_the_trained_model() -> None:
    import cv2

    from app.core.detection.detector import Detector

    det = Detector(load_model_info(), device="cpu", person_model="yolo26n.pt")
    assert det.person_model is not None and "person" not in det._keep.values()
    seen: set[str] = set()
    for p in sorted(FIXTURES.glob("*.jpg"))[:12]:
        seen |= {d.cls for d in det.detect(cv2.imread(str(p)))}
    assert "person" in seen and seen - {"person"}, f"classes seen: {seen}"
    solo = Detector(load_model_info(), device="cpu", person_model=None)
    assert solo.person_model is None and "person" in solo._keep.values()
