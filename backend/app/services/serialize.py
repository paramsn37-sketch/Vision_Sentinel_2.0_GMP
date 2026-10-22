"""Pipeline objects → JSON payloads for the WebSocket stream and the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..core.incidents.manager import Incident, IncidentManager
from ..core.types import FrameResult
from ..core.zones.engine import ZoneEngine


def _r(v: float) -> float:
    return round(float(v), 1)


def frame_payload(r: FrameResult, zones: ZoneEngine, incidents: IncidentManager) -> dict[str, Any]:
    """Metadata of one frame. Boxes are in frame pixels; `width`/`height` let the client scale its overlay."""
    open_by_track: dict[int, list[str]] = {}
    for inc in incidents.active():
        if inc.track_id is not None:
            open_by_track.setdefault(inc.track_id, []).append(inc.rule)
    return {
        "camera_id": r.camera_id,
        "frame_idx": r.frame_idx,
        "ts": round(r.ts, 3),
        "width": r.width,
        "height": r.height,
        "fps": r.fps,
        "latency_ms": r.latency_ms,
        "counts": {
            "current": r.counts.current,
            "unique_total": r.counts.unique_total,
            "per_zone": {k: {"current": v.current, "unique": v.unique} for k, v in r.counts.per_zone.items()},
        },
        "persons": [
            {
                "track_id": p.track_id,
                "box": [_r(v) for v in p.xyxy],
                "conf": round(p.conf, 3),
                "confirmed": p.confirmed,
                "since_s": round(p.last_seen - p.first_seen, 1),
                "ppe": {k: v.value for k, v in p.ppe.items()},
                "items": [
                    {"cls": d.cls, "conf": round(d.conf, 3), "box": [_r(v) for v in d.xyxy]} for d in p.items
                ],
                "zones": p.zones,
                "violations": open_by_track.get(p.track_id, []),
            }
            for p in r.persons
            if p.confirmed
        ],
        "objects": [
            {"cls": d.cls, "conf": round(d.conf, 3), "box": [_r(v) for v in d.xyxy]} for d in r.objects
        ],
        "zones": [
            {"id": z.id, "name": z.name, "kind": z.kind, "severity": z.severity, "polygon": z.polygon}
            for z in zones.zones
        ],
        "alert_level": incidents.alert_level(),
    }


def incident_payload(inc: Incident, started: datetime, ended: datetime | None) -> dict[str, Any]:
    return {
        "id": inc.id,
        "camera_id": inc.camera_id,
        "track_id": inc.track_id,
        "rule": inc.rule,
        "zone_id": inc.zone_id,
        "zone_name": inc.zone_name,
        "severity": inc.severity,
        "status": inc.status,
        "active": inc.active,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat() if ended else None,
        "duration_s": inc.duration_s,
        "peak_conf": round(inc.peak_conf, 3),
        "reopen_count": inc.reopen_count,
    }
