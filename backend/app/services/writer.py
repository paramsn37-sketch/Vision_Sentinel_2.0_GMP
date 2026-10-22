"""Single writer thread: pipeline threads enqueue small DB jobs; they are committed in batches every 500 ms."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

from sqlmodel import Session

from ..db.session import engine

log = logging.getLogger(__name__)
Job = Callable[[Session], None]


class DBWriter:
    def __init__(self, flush_s: float = 0.5) -> None:
        self._q: queue.Queue[Job] = queue.Queue()
        self._flush_s = flush_s
        self._stop = threading.Event()
        self._idle = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="db-writer", daemon=True)
        self._thread.start()

    def submit(self, job: Job) -> None:
        self._idle.clear()
        self._q.put(job)

    def _loop(self) -> None:
        while not self._stop.is_set() or not self._q.empty():
            try:
                first = self._q.get(timeout=self._flush_s)
            except queue.Empty:
                self._idle.set()
                continue
            batch = [first]
            while len(batch) < 500:
                try:
                    batch.append(self._q.get_nowait())
                except queue.Empty:
                    break
            try:
                with Session(engine()) as s:
                    for job in batch:
                        job(s)
                    s.commit()
            except Exception:
                log.warning("db batch failed (%d jobs), retrying one by one", len(batch), exc_info=True)
                self._run_singly(batch)
            if self._q.empty():
                self._idle.set()

    @staticmethod
    def _run_singly(batch: list[Job]) -> None:
        # One bad job (e.g. a row for a camera deleted meanwhile) must not drop the rest of the batch.
        for job in batch:
            try:
                with Session(engine()) as s:
                    job(s)
                    s.commit()
            except Exception:
                log.exception("db job failed: %r", job)

    def drain(self, timeout: float = 5.0) -> None:
        """Wait until everything submitted so far is committed (tests, shutdown)."""
        self._idle.wait(timeout)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
