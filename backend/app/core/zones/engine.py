"""Zone membership with entry/exit hysteresis, occupancy and dwell (blueprint §6.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from shapely import prepared
from shapely.geometry import Point, Polygon

from ..config import ZoneConfig
from ..geometry import center
from ..types import PersonState, ZoneCount, ZoneEvent
from .model import Zone


@dataclass(slots=True)
class _Membership:
    inside: bool = False
    in_streak: int = 0
    out_streak: int = 0
    entered_ts: float | None = None
    dwell_s: float = 0.0
    last_ts: float | None = None


@dataclass(slots=True)
class _PreparedZone:
    zone: Zone
    poly: Polygon
    prep: object
    bbox: tuple[float, float, float, float]
    members: dict[int, _Membership] = field(default_factory=dict)
    ever_inside: set[int] = field(default_factory=set)

    @classmethod
    def build(cls, zone: Zone) -> _PreparedZone:
        poly = Polygon(zone.polygon)
        return cls(zone, poly, prepared.prep(poly), poly.bounds)

    def contains(self, x: float, y: float) -> bool:
        b = self.bbox
        if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
            return False
        return bool(self.prep.contains(Point(x, y)))  # type: ignore[attr-defined]


class ZoneEngine:
    def __init__(
        self, zones: list[Zone] | None = None, cfg: ZoneConfig | None = None, camera_id: str = "default"
    ):
        self.cfg = cfg or ZoneConfig()
        self.camera_id = camera_id
        self._zones: dict[str, _PreparedZone] = {}
        self.set_zones(zones or [])

    @property
    def zones(self) -> list[Zone]:
        return [pz.zone for pz in self._zones.values()]

    def zone(self, zone_id: str) -> Zone | None:
        pz = self._zones.get(zone_id)
        return pz.zone if pz else None

    def set_zones(self, zones: list[Zone]) -> None:
        """Hot reload. Zones whose id and outline are unchanged keep their membership state."""
        new: dict[str, _PreparedZone] = {}
        for z in zones:
            if not z.enabled:
                continue
            old = self._zones.get(z.id)
            pz = _PreparedZone.build(z)
            if old is not None and old.zone.polygon == z.polygon:
                pz.members, pz.ever_inside = old.members, old.ever_inside
            new[z.id] = pz
        self._zones = new

    def test_point(self, person: PersonState, width: int, height: int) -> tuple[float, float]:
        x, y = person.foot_point if self.cfg.point_mode == "foot" else center(person.xyxy)
        return x / width, y / height

    def update(self, persons: list[PersonState], ts: float, width: int, height: int) -> list[ZoneEvent]:
        events: list[ZoneEvent] = []
        visible = {p.track_id for p in persons}
        for pz in self._zones.values():
            for p in persons:
                m = pz.members.setdefault(p.track_id, _Membership())
                hit = pz.contains(*self.test_point(p, width, height))
                if hit:
                    m.in_streak, m.out_streak = m.in_streak + 1, 0
                else:
                    m.out_streak, m.in_streak = m.out_streak + 1, 0
                if m.inside and m.last_ts is not None:
                    m.dwell_s += ts - m.last_ts
                m.last_ts = ts
                if not m.inside and m.in_streak >= self.cfg.enter_frames:
                    m.inside, m.entered_ts = True, ts
                    pz.ever_inside.add(p.track_id)
                    events.append(ZoneEvent("entered", self.camera_id, pz.zone.id, p.track_id, ts))
                elif m.inside and m.out_streak >= self.cfg.exit_frames:
                    m.inside = False
                    events.append(ZoneEvent("exited", self.camera_id, pz.zone.id, p.track_id, ts))
                if m.inside:
                    p.zones.append(pz.zone.id)
            # A person the tracker lost stays "inside" for a short grace period (brief occlusion), then leaves.
            for tid, m in list(pz.members.items()):
                if tid in visible or m.last_ts is None or ts - m.last_ts <= self.cfg.lost_grace_s:
                    continue
                if m.inside:
                    events.append(ZoneEvent("exited", self.camera_id, pz.zone.id, tid, ts))
                del pz.members[tid]
        return events

    def counts(self) -> dict[str, ZoneCount]:
        return {
            zid: ZoneCount(current=sum(m.inside for m in pz.members.values()), unique=len(pz.ever_inside))
            for zid, pz in self._zones.items()
        }

    def occupancy(self, zone_id: str) -> int:
        pz = self._zones.get(zone_id)
        return sum(m.inside for m in pz.members.values()) if pz else 0

    def dwell(self, zone_id: str, track_id: int) -> float:
        pz = self._zones.get(zone_id)
        m = pz.members.get(track_id) if pz else None
        return m.dwell_s if m and m.inside else 0.0

    def reset_counts(self) -> None:
        for pz in self._zones.values():
            pz.ever_inside.clear()

    def pixel_polygons(self, width: int, height: int) -> list[tuple[str, np.ndarray]]:
        return [(pz.zone.name, np.array(pz.zone.polygon) * [width, height]) for pz in self._zones.values()]
