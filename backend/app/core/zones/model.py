"""Zone definitions, validation and YAML import/export (blueprint §6.1).

Polygons are stored in normalised coordinates (0..1 of frame width/height) so they survive resolution changes.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import time as dtime
from pathlib import Path
from typing import Literal

import yaml
from shapely.geometry import Polygon

ZoneKind = Literal["restricted", "ppe_required", "hazard"]
Severity = Literal["high", "medium", "low"]
VALID_PPE = ("helmet", "vest", "gloves", "boots", "goggles")
MIN_AREA = 0.001  # 0.1% of the frame
_HOURS = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(slots=True)
class ZoneRules:
    no_entry: bool = False
    required_ppe: list[str] = field(default_factory=list)
    max_occupancy: int | None = None
    max_dwell_s: float | None = None
    active_hours: str | None = None  # "HH:MM-HH:MM", may wrap midnight

    def active_at(self, t: dtime) -> bool:
        if not self.active_hours:
            return True
        m = _HOURS.match(self.active_hours)
        if m is None:
            return True
        start = dtime(int(m[1]), int(m[2]))
        end = dtime(int(m[3]), int(m[4]))
        return start <= t < end if start <= end else t >= start or t < end


@dataclass(slots=True)
class Zone:
    name: str
    polygon: list[list[float]]
    camera_id: str = "default"
    kind: ZoneKind = "hazard"
    rules: ZoneRules = field(default_factory=ZoneRules)
    severity: Severity = "medium"
    enabled: bool = True
    id: str = field(default_factory=lambda: "z_" + uuid.uuid4().hex[:8])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Zone:
        d = dict(d)
        rules = ZoneRules(**(d.pop("rules", None) or {}))
        return cls(rules=rules, **d)


def validate(zone: Zone) -> list[str]:
    """Human-readable problems; an empty list means the zone is valid."""
    errors: list[str] = []
    pts = zone.polygon
    if not zone.name.strip():
        errors.append("Give the zone a name.")
    if len(pts) < 3:
        errors.append("A zone needs at least 3 points.")
        return errors
    if any(len(p) != 2 or not (0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0) for p in pts):
        errors.append("Every point must lie inside the camera frame.")
    poly = Polygon(pts)
    if not poly.is_valid:
        errors.append("The outline crosses itself. Move a point so the edges don't intersect.")
    elif poly.area < MIN_AREA:
        errors.append("The zone is too small (under 0.1% of the frame).")
    bad = [p for p in zone.rules.required_ppe if p not in VALID_PPE]
    if bad:
        errors.append(f"Unknown PPE item(s): {', '.join(bad)}.")
    if zone.rules.max_occupancy is not None and zone.rules.max_occupancy < 0:
        errors.append("Maximum occupancy can't be negative.")
    if zone.rules.max_dwell_s is not None and zone.rules.max_dwell_s <= 0:
        errors.append("Maximum dwell time must be more than 0 seconds.")
    if zone.rules.active_hours and not _HOURS.match(zone.rules.active_hours):
        errors.append("Active hours must look like 06:00-22:00.")
    return errors


def load_zones_yaml(path: Path) -> list[Zone]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [Zone.from_dict(z) for z in raw.get("zones", [])]


def dump_zones_yaml(zones: list[Zone]) -> str:
    return yaml.safe_dump({"zones": [z.to_dict() for z in zones]}, sort_keys=False)
