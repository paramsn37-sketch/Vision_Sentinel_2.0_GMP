"""Process-wide service container, created in the FastAPI lifespan and reached through `app.state.vs`."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from ..core.detection.detector import Detector, load_model_info
from ..core.xai.cam import YoloCAM
from ..core.xai.worker import XAIWorker
from ..db.models import Camera, SettingRow, User, ZoneRow
from ..db.session import engine, init_engine
from ..settings import Settings
from .auth import RateLimiter, Signer, hash_password
from .bus import EventBus
from .runtime import CameraManager, zone_from_row
from .storage import Paths
from .writer import DBWriter

log = logging.getLogger(__name__)


@dataclass
class AppServices:
    settings: Settings
    paths: Paths
    bus: EventBus
    writer: DBWriter
    signer: Signer
    detector: Detector | None = None
    xai: XAIWorker | None = None
    cameras: CameraManager | None = None
    login_limiter: RateLimiter = field(default_factory=RateLimiter)
    uploads: Any = None
    model_error: str | None = None

    @classmethod
    def create(
        cls, settings: Settings, *, load_model: bool = True, db_path: str | Path | None = None
    ) -> AppServices:
        paths = Paths(settings.data_dir).ensure()
        init_engine(db_path or paths.db)
        secret = settings.secret_key or _persistent_secret(paths)
        svc = cls(settings, paths, EventBus(), DBWriter(), Signer(secret))
        svc._ensure_admin()
        if load_model:
            svc.load_model()
        return svc

    def load_model(self) -> None:
        try:
            det = self.settings.detection
            self.detector = Detector(
                load_model_info(), device=det.device, imgsz=det.imgsz,
                person_model=det.person_model or None, person_imgsz=det.person_imgsz,
            )  # fmt: skip
            self.detector.warmup()
            self.xai = XAIWorker(
                YoloCAM(_cam_model(self.detector), self.detector.model.names, self.detector.imgsz),
                self.paths.xai,
            )
        except Exception as exc:  # the API still serves history, zones and settings without a model
            log.exception("model failed to load")
            self.model_error = f"{type(exc).__name__}: {exc}"
            return
        self.cameras = CameraManager(
            self.detector, self.core_config, self.bus, self.writer, self.xai, self.paths,
            jpeg_quality=self.settings.server.jpeg_quality, stream_max_width=self.settings.server.stream_max_width,
            blur=self.settings.privacy.blur_heads_in_snapshots,
        )  # fmt: skip

    def core_config(self):
        cfg = self.settings.core()
        overrides = self.runtime_overrides()
        for section, values in overrides.items():
            target = getattr(cfg, section, None)
            for k, v in (values or {}).items():
                if target is not None and hasattr(target, k):
                    setattr(target, k, v)
        if "site" in overrides:
            cfg.site_required_ppe = tuple(overrides["site"].get("required_ppe", cfg.site_required_ppe))
        return cfg

    def runtime_overrides(self) -> dict[str, dict]:
        with Session(engine()) as s:
            row = s.get(SettingRow, "thresholds")
            return dict(row.value) if row else {}

    def start_cameras(self) -> None:
        if self.cameras is None:
            return
        with Session(engine()) as s:
            cams = s.exec(select(Camera).where(Camera.enabled == True)).all()  # noqa: E712
            for cam in cams:
                zones = [
                    zone_from_row(z) for z in s.exec(select(ZoneRow).where(ZoneRow.camera_id == cam.id)).all()
                ]
                self.cameras.start(cam, zones)

    def _ensure_admin(self) -> None:
        with Session(engine()) as s:
            if s.exec(select(User)).first() is not None:
                return
            password = self.settings.admin_password
            generated = password is None
            password = password or secrets.token_urlsafe(9)
            s.add(User(username="admin", password_hash=hash_password(password)))
            s.commit()
        if generated:
            note = self.paths.root / "ADMIN_PASSWORD.txt"
            note.write_text(f"username: admin\npassword: {password}\n")
            log.warning(
                "created admin user; password written to %s (set VS_ADMIN_PASSWORD to choose one)", note
            )

    def shutdown(self) -> None:
        if self.cameras:
            self.cameras.stop_all()
        if self.xai:
            self.xai.close()
        if self.uploads:
            self.uploads.close()
        self.writer.drain()
        self.writer.close()


def _cam_model(detector: Detector):
    """A separate copy of the network for explanations, so Grad-CAM never races live inference."""
    from ultralytics import YOLO

    return YOLO(str(detector.info.weights)).model


def _persistent_secret(paths: Paths) -> str:
    f = paths.root / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(48))
        f.chmod(0o600)
    return f.read_text().strip()
