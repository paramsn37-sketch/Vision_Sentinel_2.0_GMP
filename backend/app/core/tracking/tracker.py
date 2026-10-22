"""Person tracking with confirmation and lost-track merging (blueprint §5.1–5.3).

ByteTrack (Ultralytics implementation) produces raw IDs. On top of it this module keeps *canonical* IDs:
- a raw ID becomes a counted person only once it is confirmed (enough hits over enough time);
- a new raw ID that appears close to a recently lost confirmed person with a similar size and torso colour is
  merged into that person instead of being counted twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker

from ..config import TrackingConfig
from ..geometry import center
from ..types import Box, Detection
from .appearance import histogram_distance, torso_histogram


class _DetArray:
    """Minimal numpy-backed stand-in for Ultralytics `Boxes`, which BYTETracker.update consumes."""

    def __init__(self, xyxy: np.ndarray, conf: np.ndarray) -> None:
        self.xyxy = xyxy.reshape(-1, 4).astype(np.float32)
        self.conf = conf.astype(np.float32)
        self.cls = np.zeros(len(conf), dtype=np.float32)
        wh = self.xyxy[:, 2:] - self.xyxy[:, :2]
        self.xywh = np.concatenate([self.xyxy[:, :2] + wh / 2, wh], axis=1)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, idx: np.ndarray) -> _DetArray:
        return _DetArray(self.xyxy[idx], self.conf[idx])


@dataclass(slots=True)
class Track:
    track_id: int  # canonical id
    xyxy: Box
    conf: float
    first_seen: float
    last_seen: float
    hits: int = 1
    confirmed: bool = False
    hist: np.ndarray | None = None
    raw_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class TrackUpdate:
    visible: list[Track]
    newly_confirmed: list[int]
    merged: list[tuple[int, int]]  # (raw id, canonical id)


class PersonTracker:
    def __init__(self, cfg: TrackingConfig | None = None, fps: float = 30.0) -> None:
        self.cfg = cfg or TrackingConfig()
        self.fps = fps
        self._byte = BYTETracker(
            SimpleNamespace(
                track_high_thresh=self.cfg.track_high_thresh,
                track_low_thresh=self.cfg.track_low_thresh,
                new_track_thresh=self.cfg.new_track_thresh,
                match_thresh=self.cfg.match_thresh,
                track_buffer=max(1, round(self.cfg.track_buffer_s * fps)),
                fuse_score=True,
            )
        )
        self.tracks: dict[int, Track] = {}
        self._alias: dict[int, int] = {}  # raw id -> canonical id
        self.raw_ids_seen: set[int] = set()

    def reset(self) -> None:
        self.__init__(self.cfg, self.fps)  # type: ignore[misc]

    @property
    def unique_confirmed(self) -> int:
        return sum(1 for t in self.tracks.values() if t.confirmed)

    def update(self, persons: list[Detection], frame: np.ndarray, ts: float) -> TrackUpdate:
        if persons:
            dets = _DetArray(np.array([d.xyxy for d in persons]), np.array([d.conf for d in persons]))
        else:
            dets = _DetArray(np.zeros((0, 4)), np.zeros(0))
        out = self._byte.update(dets, frame)
        visible: list[Track] = []
        newly_confirmed: list[int] = []
        merged: list[tuple[int, int]] = []
        busy = {self._alias[int(r[4])] for r in out if int(r[4]) in self._alias}
        for row in out:
            x1, y1, x2, y2, raw_id, score = (float(v) for v in row[:6])
            rid = int(raw_id)
            box = (x1, y1, x2, y2)
            self.raw_ids_seen.add(rid)
            cid = self._alias.get(rid)
            if cid is None:
                cid = self._match_lost(box, frame, ts, busy)
                if cid is not None:
                    merged.append((rid, cid))
                    busy.add(cid)
                else:
                    cid = rid if rid not in self.tracks else max(self.tracks) + 1
                self._alias[rid] = cid
            track = self.tracks.get(cid)
            if track is None:
                track = Track(cid, box, score, first_seen=ts, last_seen=ts, raw_ids={rid})
                self.tracks[cid] = track
            else:
                track.hits += 1
                track.xyxy, track.conf, track.last_seen = box, score, ts
                track.raw_ids.add(rid)
            if track.hits % 5 == 1 or track.hist is None:
                hist = torso_histogram(frame, box)
                if hist is not None:
                    track.hist = hist
            if not track.confirmed and self._ready(track, ts):
                track.confirmed = True
                newly_confirmed.append(cid)
            visible.append(track)
        return TrackUpdate(visible, newly_confirmed, merged)

    def _ready(self, track: Track, ts: float) -> bool:
        age = ts - track.first_seen
        frames_alive = age * self.fps + 1
        return (
            track.hits >= self.cfg.min_hits
            and age >= self.cfg.min_age_s
            and track.hits / frames_alive >= self.cfg.min_hit_ratio
        )

    def _match_lost(self, box: Box, frame: np.ndarray, ts: float, busy: set[int]) -> int | None:
        """Canonical id of a recently lost confirmed track that this new detection most likely is."""
        cfg = self.cfg
        h_new = box[3] - box[1]
        hist = None
        best, best_score = None, float("inf")
        for t in self.tracks.values():
            gap = ts - t.last_seen
            if not t.confirmed or t.track_id in busy or gap <= 0 or gap > cfg.reid_window_s:
                continue
            h_old = t.xyxy[3] - t.xyxy[1]
            if h_old <= 0 or not cfg.reid_size_ratio[0] <= h_new / h_old <= cfg.reid_size_ratio[1]:
                continue
            (cx, cy), (ox, oy) = center(box), center(t.xyxy)
            dist = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5 / h_old
            if dist > cfg.reid_max_center_dist:
                continue
            if hist is None:
                hist = torso_histogram(frame, box)
            hd = histogram_distance(hist, t.hist)
            if hd > cfg.reid_max_hist_dist:
                continue
            score = dist + hd
            if score < best_score:
                best, best_score = t.track_id, score
        return best
