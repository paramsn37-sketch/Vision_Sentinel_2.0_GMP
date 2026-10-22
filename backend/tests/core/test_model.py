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
