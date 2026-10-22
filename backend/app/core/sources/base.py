"""Frame sources. File sources are deterministic (video time); live sources always hand out the newest frame."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(slots=True)
class Frame:
    image: np.ndarray
    idx: int
    ts: float  # seconds; video time for files, monotonic wall time for live sources


class SourceError(RuntimeError):
    pass


class FrameSource:
    fps: float = 30.0
    live: bool = False

    def read(self) -> Frame | None:  # None = end of stream
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __iter__(self):
        while (f := self.read()) is not None:
            yield f


class FileSource(FrameSource):
    """Video file. `stride` processes every Nth frame; `loop` restarts at the end (demo cameras)."""

    def __init__(self, path: str | Path, stride: int = 1, loop: bool = False) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise SourceError(f"video not found: {self.path}")
        self.cap = cv2.VideoCapture(str(self.path))
        if not self.cap.isOpened():
            raise SourceError(f"cannot open video: {self.path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.stride = max(1, stride)
        self.loop = loop
        self._idx = -1
        self._offset = 0.0  # added to timestamps after each loop so time keeps increasing

    @property
    def effective_fps(self) -> float:
        return self.fps / self.stride

    def read(self) -> Frame | None:
        while True:
            ok, img = self.cap.read()
            if not ok:
                if not self.loop or self._idx < 0:
                    return None
                self._offset += (self._idx + 1) / self.fps
                self._idx = -1
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            self._idx += 1
            if self._idx % self.stride == 0:
                return Frame(img, self._idx, self._offset + self._idx / self.fps)

    def close(self) -> None:
        self.cap.release()


class ImageSource(FrameSource):
    def __init__(self, path: str | Path) -> None:
        img = cv2.imread(str(path))
        if img is None:
            raise SourceError(f"cannot read image: {path}")
        self._img: np.ndarray | None = img

    def read(self) -> Frame | None:
        img, self._img = self._img, None
        return None if img is None else Frame(img, 0, 0.0)


class LiveSource(FrameSource):
    """Webcam or RTSP/HTTP stream read on a thread; `read()` returns the newest frame (stale ones are dropped).

    Reconnects with exponential backoff (1 s → 30 s) when the stream drops.
    """

    live = True

    def __init__(self, uri: str | int, max_backoff_s: float = 30.0) -> None:
        self.uri = uri
        self.max_backoff_s = max_backoff_s
        self._latest: Frame | None = None
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._idx = 0
        self.connected = False
        self.last_error: str | None = None
        self._cap = self._open()
        self.fps = (self._cap.get(cv2.CAP_PROP_FPS) if self._cap else 0) or 25.0
        self._thread = threading.Thread(target=self._loop, name=f"capture-{uri}", daemon=True)
        self._thread.start()

    def _open(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(self.uri)
        self.connected = cap.isOpened()
        if not self.connected:
            self.last_error = f"cannot open {self.uri}"
            return None
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            if self._cap is None:
                self._stop.wait(backoff)
                backoff = min(self.max_backoff_s, backoff * 2)
                self._cap = self._open()
                continue
            ok, img = self._cap.read()
            if not ok:
                self.connected = False
                self.last_error = "stream read failed"
                self._cap.release()
                self._cap = None
                continue
            backoff = 1.0
            self.connected = True
            with self._cond:
                self._latest = Frame(img, self._idx, time.monotonic())
                self._idx += 1
                self._cond.notify_all()

    def read(self, timeout: float = 5.0) -> Frame | None:
        """Block until a new frame arrives; None only once the source is closed."""
        while not self._stop.is_set():
            with self._cond:
                if self._latest is None:
                    self._cond.wait(timeout)
                frame, self._latest = self._latest, None
            if frame is not None:
                return frame
        return None

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._cap is not None:
            self._cap.release()


def open_source(uri: str, *, loop: bool = False, stride: int = 1) -> FrameSource:
    """`0`/`1` → webcam, `rtsp://`/`http(s)://` → stream, image extension → image, otherwise a video file."""
    if uri.isdigit():
        return LiveSource(int(uri))
    if uri.startswith(("rtsp://", "rtsps://", "http://", "https://")):
        return LiveSource(uri)
    if Path(uri).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return ImageSource(uri)
    return FileSource(uri, stride=stride, loop=loop)
