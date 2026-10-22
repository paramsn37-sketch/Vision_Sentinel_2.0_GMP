"""WebSockets: `/ws/live` streams one camera (JSON metadata, then the JPEG of the same frame as binary);
`/ws/events` pushes incidents, zone events and upload progress."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.auth import SESSION_COOKIE

router = APIRouter()


def _authorised(ws: WebSocket) -> bool:
    token = ws.cookies.get(SESSION_COOKIE)
    return bool(token and ws.app.state.vs.signer.loads(token))


@router.websocket("/ws/live")
async def live(ws: WebSocket, camera_id: str, fps: float = 12.0) -> None:
    if not _authorised(ws):
        await ws.close(code=4401)
        return
    svc = ws.app.state.vs
    await ws.accept()
    max_fps = svc.settings.server.stream_fps
    interval = 1.0 / max(0.5, min(fps, max_fps))
    seen = 0

    async def control() -> None:
        nonlocal interval
        while True:
            msg = json.loads(await ws.receive_text())
            if "fps" in msg:
                interval = 1.0 / max(0.5, min(float(msg["fps"]), max_fps))

    ctl = asyncio.create_task(control())
    try:
        while not ctl.done():
            rt = svc.cameras.get(camera_id) if svc.cameras else None
            if rt is None:
                await ws.send_text(json.dumps({"type": "status", "status": "stopped"}))
                await asyncio.sleep(2)
                continue
            t0 = time.monotonic()
            n, jpeg, meta = await asyncio.to_thread(rt.wait_frame, seen, 2.0)
            if n == seen or jpeg is None:
                await ws.send_text(json.dumps({"type": "status", "status": rt.status, "error": rt.error}))
                continue
            seen = n
            await ws.send_text(json.dumps({"type": "frame", **(meta or {})}))
            await ws.send_bytes(jpeg)
            # Slow clients simply get fewer frames: we always send the newest one.
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - t0)))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ctl.cancel()
        with contextlib.suppress(Exception):
            await ws.close()


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    if not _authorised(ws):
        await ws.close(code=4401)
        return
    svc = ws.app.state.vs
    await ws.accept()
    try:
        async with svc.bus.subscribe() as q:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except TimeoutError:
                    ev = {"type": "ping"}
                await ws.send_text(json.dumps(ev, default=str))
    except (WebSocketDisconnect, RuntimeError):
        pass
