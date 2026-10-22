import uuid

import yaml
from fastapi import APIRouter, Body, Response
from sqlmodel import select

from ..core.zones.model import Zone, ZoneRules, dump_zones_yaml, validate
from ..db.models import Camera, ZoneRow, utcnow
from ..services.runtime import zone_from_row
from .deps import DB, ApiError, Svc, User, audit
from .schemas import ValidationOut, ZoneIn, ZoneOut

router = APIRouter(prefix="/zones", tags=["zones"])


def _core(body: ZoneIn, zone_id: str = "new") -> Zone:
    return Zone(
        id=zone_id, camera_id=body.camera_id, name=body.name, kind=body.kind, polygon=[list(p) for p in body.polygon],
        rules=ZoneRules(**body.rules.model_dump()), severity=body.severity, enabled=body.enabled,
    )  # fmt: skip


def _out(row: ZoneRow) -> ZoneOut:
    return ZoneOut(**row.model_dump())


def _reload(svc, s, camera_id: str) -> None:
    rt = svc.cameras.get(camera_id) if svc.cameras else None
    if rt is not None:
        rt.set_zones(
            [zone_from_row(z) for z in s.exec(select(ZoneRow).where(ZoneRow.camera_id == camera_id)).all()]
        )


def _check(s, body: ZoneIn) -> None:
    if s.get(Camera, body.camera_id) is None:
        raise ApiError(404, "not_found", "No such camera.")
    errors = validate(_core(body))
    if errors:
        raise ApiError(422, "invalid_zone", errors[0], errors)


@router.get("", response_model=list[ZoneOut])
def list_zones(s: DB, user: User, camera_id: str | None = None) -> list[ZoneOut]:
    q = select(ZoneRow)
    if camera_id:
        q = q.where(ZoneRow.camera_id == camera_id)
    return [_out(z) for z in s.exec(q.order_by(ZoneRow.name)).all()]


@router.post("/validate", response_model=ValidationOut)
def validate_zone(body: ZoneIn, user: User) -> ValidationOut:
    errors = validate(_core(body))
    return ValidationOut(valid=not errors, errors=errors)


@router.post("", response_model=ZoneOut, status_code=201)
def create_zone(body: ZoneIn, svc: Svc, s: DB, user: User) -> ZoneOut:
    _check(s, body)
    row = ZoneRow(**_core(body, "z_" + uuid.uuid4().hex[:8]).to_dict())
    s.add(row)
    audit(s, user, "zone.create", row.id, {"name": row.name, "camera_id": row.camera_id})
    s.commit()
    _reload(svc, s, row.camera_id)
    return _out(row)


@router.put("/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: str, body: ZoneIn, svc: Svc, s: DB, user: User) -> ZoneOut:
    row = s.get(ZoneRow, zone_id)
    if row is None:
        raise ApiError(404, "not_found", "No such zone.")
    _check(s, body)
    for k, v in _core(body, zone_id).to_dict().items():
        setattr(row, k, v)
    row.updated_at = utcnow()
    s.add(row)
    audit(s, user, "zone.update", zone_id, {"name": row.name})
    s.commit()
    _reload(svc, s, row.camera_id)
    return _out(row)


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: str, svc: Svc, s: DB, user: User) -> None:
    row = s.get(ZoneRow, zone_id)
    if row is None:
        raise ApiError(404, "not_found", "No such zone.")
    cam = row.camera_id
    s.delete(row)
    audit(s, user, "zone.delete", zone_id)
    s.commit()
    _reload(svc, s, cam)


@router.get("/export", response_class=Response, responses={200: {"content": {"application/yaml": {}}}})
def export_zones(s: DB, user: User, camera_id: str | None = None) -> Response:
    rows = s.exec(
        select(ZoneRow).where(ZoneRow.camera_id == camera_id) if camera_id else select(ZoneRow)
    ).all()
    body = dump_zones_yaml([zone_from_row(r) for r in rows])
    return Response(
        body,
        media_type="application/yaml",
        headers={"Content-Disposition": "attachment; filename=zones.yaml"},
    )


@router.post("/import", response_model=list[ZoneOut])
def import_zones(
    svc: Svc, s: DB, user: User, camera_id: str, text: str = Body(..., media_type="application/yaml")
) -> list[ZoneOut]:
    try:
        raw = yaml.safe_load(text) or {}
        zones = [Zone.from_dict({**z, "camera_id": camera_id}) for z in raw.get("zones", [])]
    except (yaml.YAMLError, TypeError) as exc:
        raise ApiError(422, "invalid_yaml", f"Could not read the file: {exc}") from exc
    problems = {z.name: validate(z) for z in zones if validate(z)}
    if problems:
        raise ApiError(422, "invalid_zone", "Some zones are invalid.", problems)
    out = []
    for z in zones:
        row = ZoneRow(**{**z.to_dict(), "id": "z_" + uuid.uuid4().hex[:8]})
        s.add(row)
        out.append(row)
    audit(s, user, "zone.import", camera_id, {"count": len(zones)})
    s.commit()
    for r in out:
        s.refresh(r)
    _reload(svc, s, camera_id)
    return [_out(r) for r in out]
