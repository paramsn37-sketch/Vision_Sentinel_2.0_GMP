"""Request/response models for the REST API (the frontend's types are generated from these)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PPEItem = Literal["helmet", "vest", "gloves", "boots", "goggles"]


class LoginIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    user: str
    csrf_token: str


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    uri: str = Field(min_length=1, max_length=500)
    kind: Literal["file", "webcam", "stream"] = "file"
    enabled: bool = True
    loop: bool = True
    stride: int = Field(1, ge=1, le=10)
    point_mode: Literal["foot", "center"] = "foot"
    notes: str = ""


class CameraPatch(BaseModel):
    name: str | None = None
    uri: str | None = None
    enabled: bool | None = None
    loop: bool | None = None
    stride: int | None = Field(None, ge=1, le=10)
    point_mode: Literal["foot", "center"] | None = None
    notes: str | None = None


class CameraOut(BaseModel):
    id: str
    name: str
    uri: str
    kind: str
    enabled: bool
    loop: bool
    stride: int
    point_mode: str
    notes: str
    status: str
    error: str | None = None
    fps: float = 0
    people_now: int = 0
    unique_people: int = 0
    alert_level: str = "green"


class ZoneRulesIO(BaseModel):
    no_entry: bool = False
    required_ppe: list[PPEItem] = []
    max_occupancy: int | None = Field(None, ge=0)
    max_dwell_s: float | None = Field(None, gt=0)
    active_hours: str | None = None


class ZoneIn(BaseModel):
    camera_id: str
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["restricted", "ppe_required", "hazard"] = "hazard"
    polygon: list[tuple[float, float]]
    rules: ZoneRulesIO = ZoneRulesIO()
    severity: Literal["high", "medium", "low"] = "medium"
    enabled: bool = True


class ZoneOut(ZoneIn):
    id: str
    updated_at: datetime


class ValidationOut(BaseModel):
    valid: bool
    errors: list[str]


class IncidentOut(BaseModel):
    id: str
    camera_id: str
    camera_name: str | None = None
    track_id: int | None
    rule: str
    zone_id: str | None
    zone_name: str | None
    severity: str
    status: str
    active: bool
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None
    duration_s: float
    peak_conf: float
    box: list[float] | None
    reopen_count: int
    has_snapshot: bool
    has_xai: bool
    xai_meta: dict | None
    notes: list[dict]
    feedback: str | None


class IncidentPage(BaseModel):
    items: list[IncidentOut]
    next_cursor: str | None
    total: int


class IncidentPatch(BaseModel):
    status: Literal["open", "acknowledged", "resolved"] | None = None
    note: str | None = Field(None, max_length=1000)
    feedback: Literal["false_alarm", "correct"] | None = None


class XaiIn(BaseModel):
    source: Literal["live", "incident", "upload"]
    camera_id: str | None = None
    frame_idx: int | None = None
    incident_id: str | None = None
    upload_id: str | None = None
    box: tuple[float, float, float, float] | None = None
    cls: str | None = None
    method: Literal["gradcam", "eigencam"] = "gradcam"


class XaiOut(BaseModel):
    id: str
    status: str
    meta: dict | None = None
    error: str | None = None
    overlay_url: str | None = None


class UploadOut(BaseModel):
    id: str
    filename: str
    media: str
    status: str
    progress: float
    result: dict | None
    error: str | None
    created_at: datetime
    has_output: bool


class ThresholdsIO(BaseModel):
    tracking: dict[str, float | int] = {}
    ppe: dict[str, float | int] = {}
    zones: dict[str, float | int | str] = {}
    incidents: dict[str, float | int] = {}
    site: dict[str, list[PPEItem]] = {}


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=128)
