import base64
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import col, select

from ..db.models import Camera, IncidentRow, utcnow
from .deps import DB, ApiError, Svc, User, audit
from .schemas import IncidentOut, IncidentPage, IncidentPatch

router = APIRouter(prefix="/incidents", tags=["incidents"])


def to_out(row: IncidentRow, names: dict[str, str]) -> IncidentOut:
    return IncidentOut(
        **row.model_dump(exclude={"snapshot_path", "xai_path"}),
        camera_name=names.get(row.camera_id),
        has_snapshot=bool(row.snapshot_path and Path(row.snapshot_path).exists()),
        has_xai=bool(row.xai_path and Path(row.xai_path).exists()),
    )


def camera_names(s) -> dict[str, str]:
    return {c.id: c.name for c in s.exec(select(Camera)).all()}


def _cursor(row: IncidentRow) -> str:
    return base64.urlsafe_b64encode(f"{row.started_at.isoformat()}|{row.id}".encode()).decode()


@router.get("", response_model=IncidentPage)
def list_incidents(
    s: DB, user: User, status: str | None = None, rule: str | None = None, camera_id: str | None = None,
    zone_id: str | None = None, severity: str | None = None, active: bool | None = None,
    since: datetime | None = None, until: datetime | None = None, q: str | None = None,
    cursor: str | None = None, limit: int = 50,
) -> IncidentPage:  # fmt: skip
    limit = max(1, min(limit, 200))
    query = select(IncidentRow)
    if status:
        query = query.where(col(IncidentRow.status).in_(status.split(",")))
    if rule:
        query = query.where(col(IncidentRow.rule).startswith(rule))
    if camera_id:
        query = query.where(IncidentRow.camera_id == camera_id)
    if zone_id:
        query = query.where(IncidentRow.zone_id == zone_id)
    if severity:
        query = query.where(col(IncidentRow.severity).in_(severity.split(",")))
    if active is not None:
        query = query.where(IncidentRow.active == active)
    if since:
        query = query.where(IncidentRow.started_at >= since)
    if until:
        query = query.where(IncidentRow.started_at < until)
    if q:
        like = f"%{q}%"
        query = query.where(
            col(IncidentRow.zone_name).like(like)
            | col(IncidentRow.rule).like(like)
            | col(IncidentRow.id).like(like)
        )
    total = s.exec(select(func.count()).select_from(query.subquery())).one()
    if cursor:
        started, last_id = base64.urlsafe_b64decode(cursor).decode().split("|")
        ts = datetime.fromisoformat(started)
        query = query.where(
            (IncidentRow.started_at < ts) | ((IncidentRow.started_at == ts) & (IncidentRow.id < last_id))
        )
    rows = s.exec(
        query.order_by(col(IncidentRow.started_at).desc(), col(IncidentRow.id).desc()).limit(limit + 1)
    ).all()
    names = camera_names(s)
    more = len(rows) > limit
    rows = rows[:limit]
    return IncidentPage(
        items=[to_out(r, names) for r in rows], next_cursor=_cursor(rows[-1]) if more else None, total=total
    )


def _get(s, incident_id: str) -> IncidentRow:
    row = s.get(IncidentRow, incident_id)
    if row is None:
        raise ApiError(404, "not_found", "No such incident.")
    return row


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, s: DB, user: User) -> IncidentOut:
    return to_out(_get(s, incident_id), camera_names(s))


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: str, body: IncidentPatch, svc: Svc, s: DB, user: User) -> IncidentOut:
    row = _get(s, incident_id)
    if body.status:
        row.status = body.status
        rt = svc.cameras.get(row.camera_id) if svc.cameras else None
        if rt is not None:
            rt.incidents.set_status(incident_id, body.status)
        row.notes = [
            *row.notes,
            {"at": utcnow().isoformat(), "user": user, "text": f"Marked {body.status}", "system": True},
        ]
    if body.note:
        row.notes = [*row.notes, {"at": utcnow().isoformat(), "user": user, "text": body.note}]
    if body.feedback:
        row.feedback = body.feedback
        if body.feedback == "false_alarm" and row.snapshot_path and Path(row.snapshot_path).exists():
            # Keep the frame for the next training round (data/feedback is never auto-deleted).
            dst = svc.paths.feedback / f"{row.id}.jpg"
            dst.write_bytes(Path(row.snapshot_path).read_bytes())
    s.add(row)
    audit(s, user, "incident.update", incident_id, body.model_dump(exclude_none=True))
    s.commit()
    s.refresh(row)
    svc.bus.publish({"type": "incident", "kind": "status", "incident": {"id": row.id, "status": row.status}})
    return to_out(row, camera_names(s))


@router.get("/{incident_id}/evidence", response_class=FileResponse)
def evidence(incident_id: str, s: DB, user: User) -> FileResponse:
    row = _get(s, incident_id)
    if not row.snapshot_path or not Path(row.snapshot_path).exists():
        raise ApiError(404, "not_found", "No evidence image for this incident yet.")
    return FileResponse(row.snapshot_path, media_type="image/jpeg")


@router.get("/{incident_id}/xai", response_class=FileResponse)
def xai_image(incident_id: str, s: DB, user: User) -> FileResponse:
    row = _get(s, incident_id)
    if not row.xai_path or not Path(row.xai_path).exists():
        raise ApiError(404, "not_found", "No explanation for this incident yet.")
    return FileResponse(row.xai_path, media_type="image/jpeg")
