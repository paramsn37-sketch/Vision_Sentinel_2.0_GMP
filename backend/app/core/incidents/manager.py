"""Incident lifecycle: deduplicated by construction (blueprint §5.5, §6.3).

Every frame the rules produce a set of *conditions* keyed by (track, rule, zone). One incident exists per key
while the condition holds; it closes after the condition has been false for `clear_s`, and a recurrence within
`cooldown_s` reopens the same incident instead of creating a new one. Officers move incidents through
open → acknowledged → resolved; that workflow status is separate from whether the condition is still active.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

import numpy as np

from ..config import IncidentConfig, PPEConfig
from ..ppe.evidence import PersonPPE
from ..types import Box, FrameResult
from ..zones.engine import ZoneEngine

Status = Literal["open", "acknowledged", "resolved"]
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
Key = tuple[int | None, str, str | None]  # (track_id, rule, zone_id)


@dataclass(slots=True)
class Incident:
    camera_id: str
    track_id: int | None
    rule: str  # intrusion | ppe_missing:<item> | overcrowding | dwell_exceeded
    zone_id: str | None
    zone_name: str | None
    severity: str
    started_ts: float
    last_seen_ts: float
    started_at: str  # wall clock, ISO 8601
    id: str = field(default_factory=lambda: "inc_" + uuid.uuid4().hex[:10])
    status: Status = "open"
    active: bool = True
    ended_ts: float | None = None
    peak_conf: float = 0.0
    box: Box | None = None
    reopen_count: int = 0
    snapshot_path: str | None = None
    xai_path: str | None = None

    @property
    def key(self) -> Key:
        return (self.track_id, self.rule, self.zone_id)

    @property
    def duration_s(self) -> float:
        return round((self.ended_ts if self.ended_ts is not None else self.last_seen_ts) - self.started_ts, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = self.duration_s
        return d


@dataclass(slots=True)
class _Evidence:
    until_ts: float
    best_conf: float
    frame: np.ndarray
    box: Box | None


EventCallback = Callable[[str, Incident, np.ndarray | None], None]


class IncidentManager:
    def __init__(
        self,
        camera_id: str,
        zones: ZoneEngine | None = None,
        cfg: IncidentConfig | None = None,
        ppe_cfg: PPEConfig | None = None,
        site_required_ppe: tuple[str, ...] = (),
        on_event: EventCallback | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.camera_id = camera_id
        self.zones = zones
        self.cfg = cfg or IncidentConfig()
        self.ppe_cfg = ppe_cfg or PPEConfig()
        self.site_required_ppe = site_required_ppe
        self.on_event = on_event
        self.clock = clock
        self._by_key: dict[Key, Incident] = {}
        self._history: list[Incident] = []
        self._crowd_since: dict[str, float] = {}
        self._evidence: dict[str, _Evidence] = {}

    # -- queries -------------------------------------------------------------------------------------------
    def all(self) -> list[Incident]:
        return list(self._history)

    def active(self) -> list[Incident]:
        return [i for i in self._history if i.active]

    def get(self, incident_id: str) -> Incident | None:
        return next((i for i in self._history if i.id == incident_id), None)

    def alert_level(self) -> str:
        live = [i for i in self._history if i.active and i.status != "resolved"]
        if any(i.severity == "high" for i in live):
            return "red"
        return "amber" if live else "green"

    def set_status(self, incident_id: str, status: Status) -> Incident | None:
        inc = self.get(incident_id)
        if inc is not None:
            inc.status = status
            self._emit("status", inc, None)
        return inc

    # -- per frame -----------------------------------------------------------------------------------------
    def conditions(
        self, result: FrameResult, ppe: dict[int, PersonPPE]
    ) -> dict[Key, tuple[str, float, Box | None]]:
        """Currently true conditions → (severity, confidence, box)."""
        out: dict[Key, tuple[str, float, Box | None]] = {}
        now = datetime.fromtimestamp(self.clock()).time()
        min_s = self.ppe_cfg.violation_min_s
        for p in result.confirmed_persons:
            state = ppe.get(p.track_id)
            covered: set[str] = set()
            for zid in p.zones:
                zone = self.zones.zone(zid) if self.zones else None
                if zone is None or not zone.rules.active_at(now):
                    continue
                if zone.rules.no_entry:
                    out[(p.track_id, "intrusion", zid)] = (zone.severity, p.conf, p.xyxy)
                for item in zone.rules.required_ppe:
                    covered.add(item)
                    if state is not None and state.missing_for(item, result.ts) >= min_s:
                        out[(p.track_id, f"ppe_missing:{item}", zid)] = (zone.severity, p.conf, p.xyxy)
                if (
                    zone.rules.max_dwell_s
                    and self.zones
                    and self.zones.dwell(zid, p.track_id) > zone.rules.max_dwell_s
                ):
                    out[(p.track_id, "dwell_exceeded", zid)] = (zone.severity, p.conf, p.xyxy)
            for item in self.site_required_ppe:
                if item not in covered and state is not None and state.missing_for(item, result.ts) >= min_s:
                    out[(p.track_id, f"ppe_missing:{item}", None)] = ("medium", p.conf, p.xyxy)
        if self.zones:
            for zone in self.zones.zones:
                limit = zone.rules.max_occupancy
                if limit is None or not zone.rules.active_at(now):
                    continue
                if self.zones.occupancy(zone.id) > limit:
                    since = self._crowd_since.setdefault(zone.id, result.ts)
                    if result.ts - since >= self.cfg.overcrowding_min_s:
                        out[(None, "overcrowding", zone.id)] = (zone.severity, 1.0, None)
                else:
                    self._crowd_since.pop(zone.id, None)
        return out

    def update(self, result: FrameResult, ppe: dict[int, PersonPPE], frame: np.ndarray) -> None:
        ts = result.ts
        conds = self.conditions(result, ppe)
        for key, (severity, conf, box) in conds.items():
            inc = self._by_key.get(key)
            if inc is not None and inc.active:
                inc.last_seen_ts, inc.box = ts, box or inc.box
                inc.peak_conf = max(inc.peak_conf, conf)
                self._collect_evidence(inc, conf, box, frame, ts)
            elif inc is not None and inc.ended_ts is not None and ts - inc.ended_ts <= self.cfg.cooldown_s:
                inc.active, inc.ended_ts, inc.last_seen_ts = True, None, ts
                inc.reopen_count += 1
                if inc.status == "resolved":
                    inc.status = "open"
                self._emit("reopened", inc, None)
            else:
                zone = self.zones.zone(key[2]) if self.zones and key[2] else None
                inc = Incident(
                    camera_id=self.camera_id,
                    track_id=key[0],
                    rule=key[1],
                    zone_id=key[2],
                    zone_name=zone.name if zone else None,
                    severity=severity,
                    started_ts=ts,
                    last_seen_ts=ts,
                    started_at=datetime.fromtimestamp(self.clock())
                    .astimezone()
                    .isoformat(timespec="seconds"),
                    peak_conf=conf,
                    box=box,
                )
                self._by_key[key] = inc
                self._history.append(inc)
                self._evidence[inc.id] = _Evidence(ts + self.cfg.evidence_window_s, conf, frame.copy(), box)
                self._emit("opened", inc, None)
        for key, inc in self._by_key.items():
            if inc.active and key not in conds and ts - inc.last_seen_ts >= self.cfg.clear_s:
                inc.active, inc.ended_ts = False, inc.last_seen_ts
                self._emit("closed", inc, None)
        self._flush_evidence(ts)

    def _collect_evidence(
        self, inc: Incident, conf: float, box: Box | None, frame: np.ndarray, ts: float
    ) -> None:
        ev = self._evidence.get(inc.id)
        if ev is not None and ts <= ev.until_ts and conf > ev.best_conf:
            ev.best_conf, ev.frame, ev.box = conf, frame.copy(), box

    def _flush_evidence(self, ts: float) -> None:
        for iid, ev in list(self._evidence.items()):
            if ts > ev.until_ts:
                inc = self.get(iid)
                del self._evidence[iid]
                if inc is not None:
                    inc.box = ev.box or inc.box
                    self._emit("evidence", inc, ev.frame)

    def flush(self) -> None:
        """Emit pending evidence immediately (end of a video)."""
        self._flush_evidence(float("inf"))

    def _emit(self, kind: str, inc: Incident, frame: np.ndarray | None) -> None:
        if self.on_event is not None:
            self.on_event(kind, inc, frame)
