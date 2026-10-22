"""Data contracts shared by every pipeline stage (blueprint §3.3).

Plain slotted dataclasses on the per-frame hot path; the API layer converts them to Pydantic schemas.
Boxes are (x1, y1, x2, y2) in original-frame pixels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

Box = tuple[float, float, float, float]
Point = tuple[float, float]

PPE_ITEMS: tuple[str, ...] = ("helmet", "vest", "gloves", "boots", "goggles")


class PPEStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class Detection:
    cls: str
    conf: float
    xyxy: Box


@dataclass(slots=True)
class PersonState:
    track_id: int
    xyxy: Box
    conf: float
    foot_point: Point
    first_seen: float
    last_seen: float
    age_frames: int
    confirmed: bool
    ppe: dict[str, PPEStatus] = field(default_factory=dict)
    ppe_score: dict[str, float] = field(default_factory=dict)
    items: list[Detection] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ZoneCount:
    current: int = 0
    unique: int = 0


@dataclass(slots=True)
class Counts:
    current: int = 0
    unique_total: int = 0
    per_zone: dict[str, ZoneCount] = field(default_factory=dict)


@dataclass(slots=True)
class ZoneEvent:
    kind: Literal["entered", "exited"]
    camera_id: str
    zone_id: str
    track_id: int
    ts: float


@dataclass(slots=True)
class FrameResult:
    camera_id: str
    frame_idx: int
    ts: float
    width: int
    height: int
    persons: list[PersonState]
    objects: list[Detection]
    counts: Counts
    events: list[ZoneEvent] = field(default_factory=list)
    fps: float = 0.0
    latency_ms: dict[str, float] = field(default_factory=dict)

    @property
    def confirmed_persons(self) -> list[PersonState]:
        return [p for p in self.persons if p.confirmed]
