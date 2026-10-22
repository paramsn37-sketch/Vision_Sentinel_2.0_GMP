"""In-process event fan-out from pipeline threads to asyncio WebSocket handlers."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    def __init__(self, maxsize: int = 256) -> None:
        self._subs: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def publish(self, event: dict[str, Any]) -> None:
        """Thread-safe. Slow subscribers drop their oldest events rather than blocking a camera."""
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            loop.call_soon_threadsafe(self._put, q, event)

    @staticmethod
    def _put(q: asyncio.Queue, event: dict) -> None:
        if q.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                q.get_nowait()
        q.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue]:
        q: asyncio.Queue = asyncio.Queue(self._maxsize)
        entry = (asyncio.get_running_loop(), q)
        with self._lock:
            self._subs.add(entry)
        try:
            yield q
        finally:
            with self._lock:
                self._subs.discard(entry)
