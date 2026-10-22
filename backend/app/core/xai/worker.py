"""Background explanation worker: priority queue, result cache, files on disk (blueprint §7.1, §3.4)."""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from ..types import Box
from .cam import YoloCAM, overlay

log = logging.getLogger(__name__)
Method = Literal["gradcam", "eigencam"]
USER, AUTO = 0, 1  # lower runs first


@dataclass(slots=True)
class JobResult:
    id: str
    status: Literal["queued", "running", "done", "failed"]
    meta: dict | None = None
    overlay_path: str | None = None
    heatmap_path: str | None = None
    source_path: str | None = None
    error: str | None = None


@dataclass(order=True, slots=True)
class _Job:
    priority: int
    seq: int
    id: str = field(compare=False)
    frame: np.ndarray = field(compare=False, repr=False)
    box: Box | None = field(compare=False)
    cls: str | None = field(compare=False)
    method: Method = field(compare=False)
    key: str = field(compare=False)
    callback: Callable[[JobResult], None] | None = field(compare=False, default=None)


class XAIWorker:
    def __init__(self, cam: YoloCAM, out_dir: Path, cache_size: int = 256, timeout_s: float = 30.0) -> None:
        self.cam = cam
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self._q: queue.PriorityQueue[_Job] = queue.PriorityQueue()
        self._jobs: dict[str, JobResult] = {}
        self._done: dict[str, threading.Event] = {}
        self._cache: OrderedDict[str, JobResult] = OrderedDict()
        self._cache_size = cache_size
        self._seq = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="xai-worker", daemon=True)
        self._thread.start()

    @staticmethod
    def key(frame: np.ndarray, box: Box | None, cls: str | None, method: str) -> str:
        h = hashlib.blake2b(frame.tobytes(), digest_size=12)
        h.update(json.dumps([None if box is None else [round(v, 1) for v in box], cls, method]).encode())
        return h.hexdigest()

    def submit(self, frame: np.ndarray, box: Box | None, cls: str | None, method: Method = "gradcam",
               priority: int = USER, callback: Callable[[JobResult], None] | None = None) -> JobResult:  # fmt: skip
        if method == "gradcam" and (box is None or cls is None):
            raise ValueError("Grad-CAM needs a target box and class")
        k = self.key(frame, box, cls, method)
        with self._lock:
            if k in self._cache:
                self._cache.move_to_end(k)
                if callback is not None:
                    callback(self._cache[k])
                return self._cache[k]
            self._seq += 1
            job_id = "xai_" + uuid.uuid4().hex[:10]
            res = JobResult(job_id, "queued")
            self._jobs[job_id] = res
            self._done[job_id] = threading.Event()
            self._q.put(_Job(priority, self._seq, job_id, frame.copy(), box, cls, method, k, callback))
        return res

    def get(self, job_id: str) -> JobResult | None:
        return self._jobs.get(job_id)

    def wait(self, job_id: str, timeout: float | None = None) -> JobResult | None:
        ev = self._done.get(job_id)
        if ev is not None:
            ev.wait(timeout or self.timeout_s)
        return self._jobs.get(job_id)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            res = self._jobs[job.id]
            res.status = "running"
            try:
                if job.method == "gradcam":
                    assert job.box is not None and job.cls is not None
                    exp = self.cam.gradcam(job.frame, job.box, job.cls)
                else:
                    exp = self.cam.eigencam(job.frame, job.box, job.cls)
                ov = self.out_dir / f"{job.key}_overlay.jpg"
                hm = self.out_dir / f"{job.key}_heat.png"
                cv2.imwrite(
                    str(ov), overlay(job.frame, exp.heatmap, box=job.box), [cv2.IMWRITE_JPEG_QUALITY, 88]
                )
                cv2.imwrite(str(hm), (exp.heatmap * 255).astype(np.uint8))
                src = self.out_dir / f"{job.key}_src.jpg"
                cv2.imwrite(str(src), job.frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                res.meta, res.overlay_path, res.heatmap_path = exp.meta(), str(ov), str(hm)
                res.source_path = str(src)
                (self.out_dir / f"{job.key}.json").write_text(json.dumps(res.meta))
                res.status = "done"
                with self._lock:
                    self._cache[job.key] = res
                    while len(self._cache) > self._cache_size:
                        self._cache.popitem(last=False)
            except Exception as exc:  # an explanation must never take the service down
                log.exception("explanation failed")
                res.status, res.error = "failed", str(exc)
            finally:
                self._done[job.id].set()
                if job.callback is not None:
                    try:
                        job.callback(res)
                    except Exception:
                        log.exception("explanation callback failed")

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
