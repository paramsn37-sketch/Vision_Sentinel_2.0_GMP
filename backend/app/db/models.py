"""SQLite tables (blueprint §8.2). Per-frame data is never stored; counts are aggregated per minute."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utcnow)


class Camera(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    uri: str  # file path, webcam index or stream URL
    kind: str = "file"  # file | webcam | stream
    enabled: bool = True
    loop: bool = True
    stride: int = 1
    point_mode: str = "foot"
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class ZoneRow(SQLModel, table=True):
    __tablename__ = "zones"
    id: str = Field(primary_key=True)
    camera_id: str = Field(index=True, foreign_key="camera.id")
    name: str
    kind: str = "hazard"
    polygon: list[list[float]] = Field(sa_column=Column(JSON))
    rules: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    severity: str = "medium"
    enabled: bool = True
    updated_at: datetime = Field(default_factory=utcnow)


class IncidentRow(SQLModel, table=True):
    __tablename__ = "incidents"
    id: str = Field(primary_key=True)
    camera_id: str = Field(index=True)
    track_id: int | None = None
    rule: str = Field(index=True)
    zone_id: str | None = Field(default=None, index=True)
    zone_name: str | None = None
    severity: str = "medium"
    status: str = Field(default="open", index=True)
    active: bool = True
    started_at: datetime = Field(default_factory=utcnow, index=True)
    last_seen_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None
    duration_s: float = 0.0
    peak_conf: float = 0.0
    box: list[float] | None = Field(default=None, sa_column=Column(JSON))
    reopen_count: int = 0
    snapshot_path: str | None = None
    xai_path: str | None = None
    xai_meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    notes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    feedback: str | None = None  # "false_alarm" when an officer marks it wrong


class ZoneEventRow(SQLModel, table=True):
    __tablename__ = "zone_events"
    id: int | None = Field(default=None, primary_key=True)
    camera_id: str = Field(index=True)
    zone_id: str = Field(index=True)
    track_id: int
    kind: str
    at: datetime = Field(default_factory=utcnow, index=True)


class TrackSummary(SQLModel, table=True):
    __tablename__ = "tracks"
    id: int | None = Field(default=None, primary_key=True)
    camera_id: str = Field(index=True)
    track_id: int = Field(index=True)
    session: str = Field(index=True)  # pipeline session id (each start of a camera)
    first_seen: datetime = Field(default_factory=utcnow)
    last_seen: datetime = Field(default_factory=utcnow)
    zones: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    ppe: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))


class CountsMinutely(SQLModel, table=True):
    __tablename__ = "counts_minutely"
    id: int | None = Field(default=None, primary_key=True)
    camera_id: str = Field(index=True)
    minute: datetime = Field(index=True)
    peak_current: int = 0
    new_people: int = 0  # people first confirmed in this minute
    compliant_people: int = 0
    noncompliant_people: int = 0
    zone_peaks: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON))


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"
    id: str = Field(primary_key=True)
    filename: str
    path: str
    media: str  # image | video
    status: str = "queued"  # queued | running | done | failed
    progress: float = 0.0
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    output_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class SettingRow(SQLModel, table=True):
    __tablename__ = "settings"
    key: str = Field(primary_key=True)
    value: dict[str, Any] = Field(sa_column=Column(JSON))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    user: str
    action: str
    target: str | None = None
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
