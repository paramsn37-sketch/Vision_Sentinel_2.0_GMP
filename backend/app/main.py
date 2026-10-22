"""FastAPI application: lifespan wiring, routers, error shape, security headers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import analytics, auth, cameras, incidents, model, reports, system, uploads, ws, xai, zones
from .logging import setup_logging
from .services.runtime import retention_cleanup
from .services.seed import seed_demo
from .services.state import AppServices
from .services.uploads import UploadWorker
from .settings import get_settings

log = logging.getLogger(__name__)


async def _retention_loop(svc: AppServices, every_s: float = 3600) -> None:
    """Hourly: delete snapshots and explanations older than storage.retention_days."""
    while True:
        try:
            n = await asyncio.to_thread(retention_cleanup, svc.paths, svc.settings.storage.retention_days)
            if n:
                log.info(
                    "retention: removed %d files older than %d days", n, svc.settings.storage.retention_days
                )
        except Exception:
            log.exception("retention cleanup failed")
        await asyncio.sleep(every_s)


def create_app(services: AppServices | None = None, *, start_cameras: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = services or AppServices.create(get_settings())
        if svc.settings.demo.seed:
            seed_demo()
        if svc.detector is not None and svc.uploads is None:
            svc.uploads = UploadWorker(svc.detector, svc.core_config, svc.bus, svc.paths.exports)
        if start_cameras:
            svc.start_cameras()
        app.state.vs = svc
        janitor = asyncio.create_task(_retention_loop(svc))
        yield
        janitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await janitor
        svc.shutdown()

    settings = get_settings()
    setup_logging(settings.data_dir)
    app = FastAPI(title="Vision Sentinel", version="2.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")  # fmt: skip
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.server.cors_origins, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )  # fmt: skip

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errs = exc.errors()
        first = errs[0] if errs else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        msg = (
            f"{field}: {first.get('msg', 'invalid value')}" if field else first.get("msg", "Invalid request.")
        )
        return JSONResponse(
            {"error": {"code": "validation", "message": msg, "details": errs}}, status_code=422
        )

    for r in (auth, cameras, zones, incidents, xai, uploads, analytics, model, reports, system):
        app.include_router(r.router, prefix="/api/v1")
    app.include_router(ws.router)
    return app


app = create_app()
