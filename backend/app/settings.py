"""Settings: config/default.yaml, then VS_* environment variables (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .core.config import CoreConfig, IncidentConfig, PPEConfig, TrackingConfig, ZoneConfig

REPO = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO / "config" / "default.yaml"


class ServerCfg(BaseModel):
    cors_origins: list[str] = ["http://localhost:5173"]
    session_hours: int = 12
    stream_fps: float = 12
    stream_max_width: int = 1280
    jpeg_quality: int = 70


class StorageCfg(BaseModel):
    data_dir: Path = Path("data/runtime")
    retention_days: int = 30
    max_upload_mb: int = 200


class PrivacyCfg(BaseModel):
    blur_heads_in_snapshots: bool = False


class DemoCfg(BaseModel):
    seed: bool = True


class DetectionCfg(BaseModel):
    device: str = "auto"
    imgsz: int | None = None


class SiteCfg(BaseModel):
    required_ppe: list[str] = []


class _YamlSource(PydanticBaseSettingsSource):
    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:  # pragma: no cover
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return yaml.safe_load(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VS_", env_nested_delimiter="__", env_file=REPO / ".env", extra="ignore"
    )

    admin_password: str | None = None
    secret_key: str | None = None
    server: ServerCfg = ServerCfg()
    storage: StorageCfg = StorageCfg()
    privacy: PrivacyCfg = PrivacyCfg()
    demo: DemoCfg = DemoCfg()
    detection: DetectionCfg = DetectionCfg()
    tracking: dict[str, Any] = Field(default_factory=dict)
    ppe: dict[str, Any] = Field(default_factory=dict)
    zones: dict[str, Any] = Field(default_factory=dict)
    incidents: dict[str, Any] = Field(default_factory=dict)
    site: SiteCfg = SiteCfg()

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):  # type: ignore[override]
        return init_settings, env_settings, dotenv_settings, _YamlSource(settings_cls)

    @property
    def data_dir(self) -> Path:
        d = self.storage.data_dir
        return d if d.is_absolute() else REPO / d

    def core(self) -> CoreConfig:
        return CoreConfig(
            tracking=TrackingConfig(**self.tracking),
            ppe=PPEConfig(**self.ppe),
            zones=ZoneConfig(**self.zones),
            incidents=IncidentConfig(**self.incidents),
            site_required_ppe=tuple(self.site.required_ppe),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
