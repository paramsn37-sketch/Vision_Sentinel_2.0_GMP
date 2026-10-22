"""Offline analysis of uploaded images and videos with the same pipeline as live cameras (never a mock)."""

from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import threading
from pathlib import Path

import cv2
from sqlmodel import Session

from ..core.annotate import draw
from ..core.config import CoreConfig
from ..core.detection.detector import Detector
from ..core.incidents.manager import IncidentManager
from ..core.pipeline import Pipeline
from ..core.sources.base import FileSource, ImageSource
from ..core.zones.engine import ZoneEngine
from ..db.models import Upload
from ..db.session import engine
from .bus import EventBus
from .serialize import frame_payload

log = logging.getLogger(__name__)
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
MAX_KEYFRAMES = 120


class UploadWorker:
    def __init__(self, detector: Detector, cfg_factory, bus: EventBus, out_dir: Path) -> None:
        self.detector, self.cfg_factory, self.bus, self.out_dir = detector, cfg_factory, bus, out_dir
        self._q: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="uploads", daemon=True)
        self._thread.start()

    def submit(self, upload_id: str) -> None:
        self._q.put(upload_id)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                uid = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process(uid)
            except Exception as exc:
                log.exception("upload %s failed", uid)
                self._update(uid, status="failed", error=f"{type(exc).__name__}: {exc}")

    def _update(self, uid: str, **values) -> None:
        with Session(engine()) as s:
            row = s.get(Upload, uid)
            if row is None:
                return
            for k, v in values.items():
                setattr(row, k, v)
            s.add(row)
            s.commit()
        self.bus.publish(
            {
                "type": "upload",
                "id": uid,
                **{k: v for k, v in values.items() if k in ("status", "progress", "error")},
            }
        )

    def _process(self, uid: str) -> None:
        with Session(engine()) as s:
            up = s.get(Upload, uid)
            assert up is not None
            path, media = Path(up.path), up.media
        self._update(uid, status="running", progress=0.0)
        cfg: CoreConfig = self.cfg_factory()
        if media == "image":
            # A single image has no time axis: report per-frame observations directly.
            cfg.ppe.violation_min_s = 0.0
            cfg.tracking.min_hits, cfg.tracking.min_age_s, cfg.tracking.min_hit_ratio = 1, 0.0, 0.0
            src = ImageSource(path)
            fps, total = 1.0, 1
        else:
            src = FileSource(path)
            fps, total = src.fps, max(1, src.frame_count)
        zones = ZoneEngine([], cfg.zones)
        incidents = IncidentManager("upload", zones, cfg.incidents, cfg.ppe, cfg.site_required_ppe)
        pipe = Pipeline("upload", self.detector, cfg, fps, zones, incidents)
        out_path = self.out_dir / f"{uid}_annotated{'.jpg' if media == 'image' else '.mp4'}"
        writer = None
        keyframes: list[dict] = []
        step = max(1, total // MAX_KEYFRAMES)
        last = None
        n = 0
        for frame in src:
            r = pipe.process(frame)
            last, n = r, n + 1
            img = draw(frame.image, r)
            if media == "image":
                cv2.imwrite(str(out_path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            else:
                if writer is None:
                    h, w = img.shape[:2]
                    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                writer.write(img)
            if frame.idx % step == 0:
                keyframes.append(frame_payload(r, zones, incidents))
            if n % 15 == 0:
                self._update(uid, progress=round(min(0.99, n / total), 3))
        if writer is not None:
            writer.release()
            _to_h264(out_path)
        persons = last.persons if last else []
        ppe_summary: dict[str, dict[str, int]] = {}
        for tid, state in pipe.ppe.items():
            if not any(p.track_id == tid and p.confirmed for p in persons) and media == "image":
                continue
            for item, st in state.states().items():
                ppe_summary.setdefault(item, {"present": 0, "absent": 0, "unknown": 0})[st.value] += 1
        result = {
            "frames": n,
            "fps": fps,
            "duration_s": round(n / fps, 2) if media != "image" else 0,
            "unique_people": last.counts.unique_total if last else 0,
            "peak_people": max((k["counts"]["current"] for k in keyframes), default=0),
            "ppe_summary": ppe_summary,
            "incidents": [i.to_dict() for i in incidents.all()],
            "keyframes": keyframes,
            "model": self.detector.name,
        }
        self._update(uid, status="done", progress=1.0, result=result, output_path=str(out_path))

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)


def _to_h264(path: Path) -> None:
    """OpenCV writes MPEG-4 Part 2, which browsers won't play; re-encode to H.264 when ffmpeg is available."""
    if shutil.which("ffmpeg") is None:
        return
    tmp = path.with_suffix(".h264.mp4")
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)],
        check=False, timeout=600,
    )  # fmt: skip
    if res.returncode == 0 and tmp.exists():
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)
