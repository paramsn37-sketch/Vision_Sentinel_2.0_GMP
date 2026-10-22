"""Camera runtimes: one pipeline thread per camera, publishing frames and events (blueprint §3.4).

A runtime owns its source, pipeline, zone engine and incident manager. It
- paces file sources to real time (demo cameras) and processes every `stride`-th frame;
- keeps the newest JPEG + metadata for WebSocket viewers and a short ring of recent frames for explanations;
- persists incidents, zone events, track summaries and per-minute counts through the DB writer;
- asks the XAI worker to explain each new incident and stores the result on the incident.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlmodel import Session, select

from ..core.config import CoreConfig
from ..core.detection.detector import Detector
from ..core.incidents.manager import Incident, IncidentManager
from ..core.pipeline import Pipeline
from ..core.sources.base import FileSource, FrameSource, SourceError, open_source
from ..core.types import FrameResult, PPEStatus
from ..core.xai.worker import AUTO, JobResult, XAIWorker
from ..core.zones.engine import ZoneEngine
from ..core.zones.model import Zone, ZoneRules
from ..db.models import Camera, CountsMinutely, IncidentRow, TrackSummary, ZoneEventRow, ZoneRow
from .bus import EventBus
from .serialize import frame_payload, incident_payload
from .storage import Paths, blur_heads, encode_jpeg
from .writer import DBWriter

log = logging.getLogger(__name__)
RING = 120  # recent frames kept for "explain this" on a paused live view


def zone_from_row(row: ZoneRow) -> Zone:
    return Zone(
        id=row.id, camera_id=row.camera_id, name=row.name, kind=row.kind,  # type: ignore[arg-type]
        polygon=row.polygon, rules=ZoneRules(**(row.rules or {})), severity=row.severity,  # type: ignore[arg-type]
        enabled=row.enabled,
    )  # fmt: skip


def _dt(ts_wall: float) -> datetime:
    return datetime.fromtimestamp(ts_wall, UTC)


@dataclass
class _Minute:
    start: datetime
    peak_current: int = 0
    new_people: int = 0
    compliant: set[int] = field(default_factory=set)
    noncompliant: set[int] = field(default_factory=set)
    zone_peaks: dict[str, int] = field(default_factory=dict)


class CameraRuntime:
    def __init__(
        self,
        camera: Camera,
        detector: Detector,
        cfg: CoreConfig,
        zones: list[Zone],
        bus: EventBus,
        writer: DBWriter,
        xai: XAIWorker | None,
        paths: Paths,
        jpeg_quality: int = 70,
        stream_max_width: int = 1280,
        blur: bool = False,
    ) -> None:
        self.camera = camera
        self.detector = detector
        self.cfg = cfg
        self.cfg.zones.point_mode = camera.point_mode
        self.bus, self.writer, self.xai, self.paths = bus, writer, xai, paths
        self.jpeg_quality, self.stream_max_width, self.blur = jpeg_quality, stream_max_width, blur
        self.zone_engine = ZoneEngine(zones, self.cfg.zones, camera.id)
        self.incidents = IncidentManager(
            camera.id,
            self.zone_engine,
            self.cfg.incidents,
            self.cfg.ppe,
            cfg.site_required_ppe,
            self._on_incident,
        )
        self.session = uuid.uuid4().hex[:8]
        self.status = "stopped"
        self.error: str | None = None
        self.fps = 0.0
        self.frames = 0
        self.started_at: datetime | None = None
        self.latest_jpeg: bytes | None = None
        self.latest_meta: dict[str, Any] | None = None
        self.latest_result: FrameResult | None = None
        self._frame_cond = threading.Condition()
        self._ring: OrderedDict[int, tuple[bytes, FrameResult]] = OrderedDict()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: FrameSource | None = None
        self._minute: _Minute | None = None
        self._wall0 = 0.0
        self._ts0 = 0.0
        self._track_flush = 0.0
        self._known: set[int] = set()

    # -- lifecycle -------------------------------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.status, self.error = "starting", None
        self._thread = threading.Thread(target=self._run, name=f"camera-{self.camera.id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._source is not None:
            self._source.close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self.status = "stopped"
        self._flush_minute()

    def set_zones(self, zones: list[Zone]) -> None:
        self.zone_engine.set_zones(zones)

    def info(self) -> dict[str, Any]:
        r = self.latest_result
        return {
            "id": self.camera.id,
            "status": self.status,
            "error": self.error,
            "fps": round(self.fps, 1),
            "frames": self.frames,
            "people_now": r.counts.current if r else 0,
            "unique_people": r.counts.unique_total if r else 0,
            "session": self.session,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "alert_level": self.incidents.alert_level(),
        }

    def wait_frame(self, after: int, timeout: float = 2.0) -> tuple[int, bytes | None, dict | None]:
        with self._frame_cond:
            if self.frames <= after:
                self._frame_cond.wait(timeout)
            return self.frames, self.latest_jpeg, self.latest_meta

    def frame_for(self, frame_idx: int) -> tuple[bytes, FrameResult] | None:
        return self._ring.get(frame_idx)

    # -- loop ------------------------------------------------------------------------------------------------
    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self._source = open_source(self.camera.uri, loop=self.camera.loop, stride=self.camera.stride)
                fps = self._source.effective_fps if isinstance(self._source, FileSource) else self._source.fps
                pipe = Pipeline(
                    self.camera.id, self.detector, self.cfg, fps, self.zone_engine, self.incidents
                )
                self.status, self.started_at = "running", datetime.now(UTC)
                self._wall0, self._ts0 = time.time(), 0.0
                backoff = 1.0
                for frame in self._source:
                    if self._stop.is_set():
                        break
                    if isinstance(self._source, FileSource):
                        self._pace(frame.ts)
                    result = pipe.process(frame)
                    self._publish(frame.image, result)
                if not self._stop.is_set():
                    self.status = "ended"
                    return
            except SourceError as exc:
                self.status, self.error = "error", str(exc)
                log.warning("camera %s: %s", self.camera.id, exc)
            except Exception as exc:  # keep the service alive; retry with backoff
                self.status, self.error = "error", f"{type(exc).__name__}: {exc}"
                log.exception("camera %s crashed", self.camera.id)
            finally:
                if self._source is not None:
                    self._source.close()
            self._stop.wait(backoff)
            backoff = min(30.0, backoff * 2)

    def _pace(self, video_ts: float) -> None:
        """Play files at real speed. If processing is slower than real time the stride already drops frames."""
        ahead = (video_ts - self._ts0) - (time.time() - self._wall0)
        if ahead > 0:
            self._stop.wait(min(ahead, 1.0))
        elif ahead < -5:  # far behind (slow CPU): re-anchor instead of racing forever
            self._wall0, self._ts0 = time.time(), video_ts

    def _wall(self, ts: float) -> float:
        return self._wall0 + (ts - self._ts0)

    def _publish(self, img: np.ndarray, result: FrameResult) -> None:
        jpeg = encode_jpeg(img, self.jpeg_quality, self.stream_max_width)
        meta = frame_payload(result, self.zone_engine, self.incidents)
        with self._frame_cond:
            self.frames += 1
            self.fps = result.fps
            self.latest_jpeg, self.latest_meta, self.latest_result = jpeg, meta, result
            self._ring[result.frame_idx] = (jpeg, result)
            while len(self._ring) > RING:
                self._ring.popitem(last=False)
            self._frame_cond.notify_all()
        self._record(result)

    # -- persistence -----------------------------------------------------------------------------------------
    def _record(self, r: FrameResult) -> None:
        now = time.time()
        minute = _dt(now).replace(second=0, microsecond=0)
        if self._minute is None or self._minute.start != minute:
            self._flush_minute()
            self._minute = _Minute(minute)
        m = self._minute
        m.peak_current = max(m.peak_current, r.counts.current)
        for zid, zc in r.counts.per_zone.items():
            m.zone_peaks[zid] = max(m.zone_peaks.get(zid, 0), zc.current)
        for p in r.confirmed_persons:
            missing = any(v is PPEStatus.ABSENT for v in p.ppe.values())
            known = any(v is not PPEStatus.UNKNOWN for v in p.ppe.values())
            if missing:
                m.noncompliant.add(p.track_id)
            elif known:
                m.compliant.add(p.track_id)
        new_ids = [p for p in r.confirmed_persons if p.track_id not in self._known]
        for p in new_ids:
            self._known.add(p.track_id)
            m.new_people += 1
            cam, session, tid, seen = self.camera.id, self.session, p.track_id, _dt(now)
            self.writer.submit(
                lambda s, cam=cam, session=session, tid=tid, seen=seen: s.add(
                    TrackSummary(
                        camera_id=cam, track_id=tid, session=session, first_seen=seen, last_seen=seen
                    )
                )
            )
        for ev in r.events:
            row = ZoneEventRow(
                camera_id=ev.camera_id,
                zone_id=ev.zone_id,
                track_id=ev.track_id,
                kind=ev.kind,
                at=_dt(self._wall(ev.ts)),
            )
            self.writer.submit(lambda s, row=row: s.add(row))
            self.bus.publish(
                {
                    "type": "zone_event",
                    "camera_id": ev.camera_id,
                    "zone_id": ev.zone_id,
                    "track_id": ev.track_id,
                    "kind": ev.kind,
                }
            )
        if now - self._track_flush > 5:
            self._track_flush = now
            snapshot = [
                (p.track_id, list(p.zones), {k: v.value for k, v in p.ppe.items()})
                for p in r.confirmed_persons
            ]
            cam, session, seen = self.camera.id, self.session, _dt(now)

            def update_tracks(s: Session) -> None:
                for tid, zones, ppe in snapshot:
                    row = s.exec(select(TrackSummary).where(
                        TrackSummary.camera_id == cam, TrackSummary.session == session, TrackSummary.track_id == tid
                    )).first()  # fmt: skip
                    if row is not None:
                        row.last_seen = seen
                        row.zones = sorted(set(row.zones) | set(zones))
                        row.ppe = ppe
                        s.add(row)

            self.writer.submit(update_tracks)

    def _flush_minute(self) -> None:
        m, self._minute = self._minute, None
        if m is None:
            return
        row = CountsMinutely(
            camera_id=self.camera.id, minute=m.start, peak_current=m.peak_current, new_people=m.new_people,
            compliant_people=len(m.compliant), noncompliant_people=len(m.noncompliant), zone_peaks=m.zone_peaks,
        )  # fmt: skip
        self.writer.submit(lambda s: s.add(row))

    def _on_incident(self, kind: str, inc: Incident, frame: np.ndarray | None) -> None:
        started = _dt(self._wall(inc.started_ts))
        last = _dt(self._wall(inc.last_seen_ts))
        ended = _dt(self._wall(inc.ended_ts)) if inc.ended_ts is not None else None
        values = {
            "status": inc.status, "active": inc.active, "last_seen_at": last, "ended_at": ended,
            "duration_s": inc.duration_s, "peak_conf": round(inc.peak_conf, 3), "reopen_count": inc.reopen_count,
            "box": list(inc.box) if inc.box else None,
        }  # fmt: skip
        if kind == "opened":
            row = IncidentRow(
                id=inc.id, camera_id=inc.camera_id, track_id=inc.track_id, rule=inc.rule, zone_id=inc.zone_id,
                zone_name=inc.zone_name, severity=inc.severity, started_at=started, **values,
            )  # fmt: skip
            self.writer.submit(lambda s: s.add(row))
        elif kind == "evidence" and frame is not None:
            self._save_evidence(inc, frame)
        if kind != "opened":
            self.writer.submit(lambda s: _update_incident(s, inc.id, values))
        self.bus.publish(
            {"type": "incident", "kind": kind, "incident": incident_payload(inc, started, ended)}
        )

    def _save_evidence(self, inc: Incident, frame: np.ndarray) -> None:
        img = frame
        if self.blur and self.latest_result is not None:
            img = blur_heads(img, [p.xyxy for p in self.latest_result.confirmed_persons])
        path = self.paths.snapshots / f"{inc.id}.jpg"
        path.write_bytes(encode_jpeg(img, 88))
        rel = str(path)
        self.writer.submit(lambda s: _update_incident(s, inc.id, {"snapshot_path": rel}))
        if self.xai is None or inc.box is None:
            return
        target_cls, box = "person", inc.box
        if inc.rule.startswith("ppe_missing:") and self.latest_result is not None:
            # Explain the bare-part detection that proved the absence when there is one (e.g. the bare head).
            bare = {"helmet": "head", "gloves": "hand", "goggles": "no_goggles"}.get(
                inc.rule.split(":", 1)[1]
            )
            person = next((p for p in self.latest_result.persons if p.track_id == inc.track_id), None)
            item = next((d for d in (person.items if person else []) if d.cls == bare), None)
            if item is not None:
                target_cls, box = item.cls, item.xyxy
        iid = inc.id

        def done(res: JobResult) -> None:
            if res.status == "done":
                vals = {"xai_path": res.overlay_path, "xai_meta": res.meta}
                self.writer.submit(lambda s: _update_incident(s, iid, vals))
                self.bus.publish({"type": "incident_xai", "incident_id": iid, "meta": res.meta})

        self.xai.submit(frame, box, target_cls, "gradcam", AUTO, done)


def _update_incident(s: Session, incident_id: str, values: dict[str, Any]) -> None:
    row = s.get(IncidentRow, incident_id)
    if row is None:
        return
    for k, v in values.items():
        setattr(row, k, v)
    s.add(row)


class CameraManager:
    def __init__(self, detector: Detector, cfg_factory, bus: EventBus, writer: DBWriter, xai: XAIWorker | None,
                 paths: Paths, **runtime_kwargs: Any) -> None:  # fmt: skip
        self.detector, self.cfg_factory, self.bus, self.writer, self.xai, self.paths = (
            detector, cfg_factory, bus, writer, xai, paths,
        )  # fmt: skip
        self.kwargs = runtime_kwargs
        self.runtimes: dict[str, CameraRuntime] = {}
        self._lock = threading.Lock()

    def start(self, camera: Camera, zones: list[Zone]) -> CameraRuntime:
        with self._lock:
            old = self.runtimes.pop(camera.id, None)
        if old is not None:
            old.stop()
        rt = CameraRuntime(
            camera,
            self.detector,
            self.cfg_factory(),
            zones,
            self.bus,
            self.writer,
            self.xai,
            self.paths,
            **self.kwargs,
        )
        with self._lock:
            self.runtimes[camera.id] = rt
        rt.start()
        return rt

    def stop(self, camera_id: str) -> None:
        with self._lock:
            rt = self.runtimes.pop(camera_id, None)
        if rt is not None:
            rt.stop()

    def get(self, camera_id: str) -> CameraRuntime | None:
        return self.runtimes.get(camera_id)

    def stop_all(self) -> None:
        for cid in list(self.runtimes):
            self.stop(cid)

    def alert_level(self) -> str:
        levels = [rt.incidents.alert_level() for rt in self.runtimes.values()]
        return "red" if "red" in levels else "amber" if "amber" in levels else "green"


def retention_cleanup(paths: Paths, days: int) -> int:
    """Delete snapshots and explanations older than `days`. Returns the number of files removed."""
    cutoff = time.time() - days * 86400
    removed = 0
    for d in (paths.snapshots, paths.xai):
        for f in d.glob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
    return removed
