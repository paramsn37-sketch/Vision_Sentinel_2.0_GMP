"""Detector wrapper: loads weights once and returns `Detection`s in original-frame pixels.

The active model is described by `models/model.json` (classes, per-class thresholds, image size). Without it the
wrapper falls back to stock COCO weights and keeps only `person`, which is enough for tracking and zones but means
PPE states stay `unknown` (the UI says so).
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ..types import Detection

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[4]
MODELS_DIR = REPO / "models"
FALLBACK_WEIGHTS = "yolo26n.pt"
PERSON_FLOOR = 0.1  # ByteTrack's second association stage needs low-score person boxes
COCO_PERSON = 0


def _resolve_weights(name: str) -> str:
    cached = Path.home() / ".cache" / "vision-sentinel" / name
    return str(cached) if cached.exists() else name


@dataclass(slots=True)
class ModelInfo:
    name: str
    weights: Path | str
    classes: list[str]
    imgsz: int = 640
    thresholds: dict[str, float] = field(default_factory=dict)
    is_ppe_model: bool = True
    meta: dict = field(default_factory=dict)


def load_model_info(models_dir: Path = MODELS_DIR) -> ModelInfo:
    meta_path = models_dir / "model.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        return ModelInfo(
            name=meta["name"],
            weights=models_dir / meta["weights"],
            classes=list(meta["classes"]),
            imgsz=int(meta.get("imgsz", 640)),
            thresholds=dict(meta.get("thresholds", {})),
            is_ppe_model=True,
            meta=meta,
        )
    cached = Path.home() / ".cache" / "vision-sentinel" / FALLBACK_WEIGHTS
    return ModelInfo(
        name="yolo26n-coco (fallback, person only)",
        weights=cached if cached.exists() else FALLBACK_WEIGHTS,
        classes=["person"],
        imgsz=640,
        thresholds={"person": 0.25},
        is_ppe_model=False,
    )


class Detector:
    """One or two networks behind one `detect()`.

    With a PPE model active and `person_model` set, people come from that COCO model (better on small, distant
    pedestrians, which tracking and counting depend on) and every other class from the PPE model (ADR-0013).
    """

    def __init__(
        self,
        info: ModelInfo | None = None,
        device: str = "auto",
        imgsz: int | None = None,
        person_model: str | None = None,
        person_imgsz: int = 640,
    ) -> None:
        from ultralytics import YOLO

        self.info = info or load_model_info()
        self.device = ("cuda:0" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        self.imgsz = imgsz or self.info.imgsz
        self.model = YOLO(str(self.info.weights))
        names: dict[int, str] = self.model.names
        # Map the network's class ids onto our taxonomy names; ids outside it are ignored.
        self._keep = {i: n for i, n in names.items() if n in self.info.classes}
        self.person_model: Any = None
        self.person_model_name: str | None = None
        self.person_imgsz = person_imgsz
        if person_model and self.info.is_ppe_model:
            self.person_model = YOLO(_resolve_weights(person_model))
            self.person_model_name = Path(person_model).stem
            self._keep = {i: n for i, n in self._keep.items() if n != "person"}
        self._floor = (
            min([PERSON_FLOOR, *self.info.thresholds.values()]) if self.info.thresholds else PERSON_FLOOR
        )
        self._half = self.device.startswith("cuda")
        self._lock = threading.Lock()  # one forward at a time per model instance
        log.info("detector ready: %s on %s (imgsz=%d)", self.info.name, self.device, self.imgsz)

    @property
    def name(self) -> str:
        return (
            f"{self.info.name} + {self.person_model_name} (people)" if self.person_model else self.info.name
        )

    def warmup(self) -> None:
        self.detect(np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8))

    def threshold(self, cls: str) -> float:
        if cls == "person":
            return PERSON_FLOOR
        return self.info.thresholds.get(cls, 0.3)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        extra = {"half": True} if self._half else {}
        people = None
        with self._lock, torch.inference_mode():
            res: Any = self.model.predict(  # type: ignore[index]
                frame, imgsz=self.imgsz, conf=self._floor, device=self.device, classes=list(self._keep),
                verbose=False, **extra,
            )[0]  # fmt: skip
            if self.person_model is not None:
                people = self.person_model.predict(
                    frame, imgsz=self.person_imgsz, conf=PERSON_FLOOR, device=self.device, classes=[COCO_PERSON],
                    verbose=False, **extra,
                )[0]  # fmt: skip
        out = self._collect(res, self._keep)
        if people is not None:
            out = self._collect(people, {COCO_PERSON: "person"}) + out
        return out

    def _collect(self, res: Any, keep: dict[int, str]) -> list[Detection]:
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        out: list[Detection] = []
        for b, c, k in zip(xyxy, conf, cls, strict=True):
            name = keep.get(int(k))
            if name is None or c < self.threshold(name):
                continue
            out.append(Detection(name, float(c), (float(b[0]), float(b[1]), float(b[2]), float(b[3]))))
        return out
