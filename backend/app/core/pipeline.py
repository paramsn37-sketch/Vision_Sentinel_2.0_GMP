"""Per-camera orchestration: detect → track → associate PPE → zones → incidents (blueprint §3.4)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Protocol

import numpy as np

from .config import CoreConfig
from .geometry import foot_point
from .ppe.associate import associate
from .ppe.evidence import PersonPPE, checkable_items
from .sources.base import Frame, FrameSource
from .tracking.tracker import PersonTracker
from .types import Counts, Detection, FrameResult, PersonState, ZoneEvent


class DetectorLike(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class ZoneStage(Protocol):
    def update(self, persons: list[PersonState], ts: float, width: int, height: int) -> list[ZoneEvent]: ...

    def counts(self) -> dict: ...


class IncidentStage(Protocol):
    def update(self, result: FrameResult, ppe: dict[int, PersonPPE], frame: np.ndarray) -> None: ...


class Pipeline:
    def __init__(
        self,
        camera_id: str,
        detector: DetectorLike,
        cfg: CoreConfig | None = None,
        fps: float = 30.0,
        zones: ZoneStage | None = None,
        incidents: IncidentStage | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.detector = detector
        self.cfg = cfg or CoreConfig()
        self.tracker = PersonTracker(self.cfg.tracking, fps=fps)
        self.zones = zones
        self.incidents = incidents
        self.ppe: dict[int, PersonPPE] = {}
        # Only items the model can detect are judged; with a person-only model PPE stays empty, never "missing".
        self.ppe_items = checkable_items(getattr(getattr(detector, "info", None), "classes", None) or ())
        self._fps_ema = 0.0
        self._last_wall: float | None = None

    def reset(self) -> None:
        self.tracker.reset()
        self.ppe.clear()

    def process(self, frame: Frame) -> FrameResult:
        img, ts = frame.image, frame.ts
        h, w = img.shape[:2]
        lat: dict[str, float] = {}
        t0 = time.perf_counter()
        dets = self.detector.detect(img)
        t1 = time.perf_counter()
        lat["detect"] = (t1 - t0) * 1000

        person_dets = [d for d in dets if d.cls == "person"]
        items = [d for d in dets if d.cls != "person"]
        upd = self.tracker.update(person_dets, img, ts)
        t2 = time.perf_counter()
        lat["track"] = (t2 - t1) * 1000

        boxes = [(t.track_id, t.xyxy) for t in upd.visible]
        assigned, loose = associate(boxes, items, self.cfg.ppe.ioa_min)
        persons: list[PersonState] = []
        for t in upd.visible:
            others = [b for tid, b in boxes if tid != t.track_id]
            state = self.ppe.get(t.track_id) or self.ppe.setdefault(
                t.track_id, PersonPPE.for_items(self.ppe_items)
            )
            state.update(assigned[t.track_id], t.xyxy, others, h, ts, self.cfg.ppe)
            persons.append(
                PersonState(
                    track_id=t.track_id,
                    xyxy=t.xyxy,
                    conf=t.conf,
                    foot_point=foot_point(t.xyxy, self.cfg.zones.foot_raise),
                    first_seen=t.first_seen,
                    last_seen=t.last_seen,
                    age_frames=t.hits,
                    confirmed=t.confirmed,
                    ppe=state.states(),
                    ppe_score=state.scores(),
                    items=assigned[t.track_id],
                )
            )
        t3 = time.perf_counter()
        lat["ppe"] = (t3 - t2) * 1000

        events: list[ZoneEvent] = []
        counts = Counts(current=sum(p.confirmed for p in persons), unique_total=self.tracker.unique_confirmed)
        if self.zones is not None:
            events = self.zones.update([p for p in persons if p.confirmed], ts, w, h)
            counts.per_zone = self.zones.counts()
        result = FrameResult(
            camera_id=self.camera_id,
            frame_idx=frame.idx,
            ts=ts,
            width=w,
            height=h,
            persons=persons,
            objects=loose,
            counts=counts,
            events=events,
        )
        if self.incidents is not None:
            self.incidents.update(result, self.ppe, img)
        t4 = time.perf_counter()
        lat["zones_incidents"] = (t4 - t3) * 1000
        lat["total"] = (t4 - t0) * 1000
        result.latency_ms = {k: round(v, 2) for k, v in lat.items()}
        if self._last_wall is not None:
            inst = 1.0 / max(1e-6, t4 - self._last_wall)
            self._fps_ema = inst if self._fps_ema == 0 else 0.9 * self._fps_ema + 0.1 * inst
        self._last_wall = t4
        result.fps = round(self._fps_ema, 1)
        return result

    def run(self, source: FrameSource) -> Iterator[FrameResult]:
        for frame in source:
            yield self.process(frame)
