import re
import uuid

from fastapi import APIRouter, Response
from sqlmodel import select

from ..core.sources.base import SourceError, open_source
from ..db.models import Camera, ZoneRow
from ..services.runtime import zone_from_row
from ..services.storage import encode_jpeg
from .deps import DB, ApiError, Svc, User, audit, require_cameras
from .schemas import CameraIn, CameraOut, CameraPatch

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _out(cam: Camera, svc) -> CameraOut:
    rt = svc.cameras.get(cam.id) if svc.cameras else None
    info = rt.info() if rt else {"status": "stopped" if cam.enabled else "disabled"}
    return CameraOut(
        **cam.model_dump(exclude={"created_at"}),
        **{k: v for k, v in info.items() if k in CameraOut.model_fields and k != "id"},
    )


def _get(s, camera_id: str) -> Camera:
    cam = s.get(Camera, camera_id)
    if cam is None:
        raise ApiError(404, "not_found", "No such camera.")
    return cam


def _zones(s, camera_id: str):
    return [zone_from_row(z) for z in s.exec(select(ZoneRow).where(ZoneRow.camera_id == camera_id)).all()]


@router.get("", response_model=list[CameraOut])
def list_cameras(svc: Svc, s: DB, user: User) -> list[CameraOut]:
    return [_out(c, svc) for c in s.exec(select(Camera).order_by(Camera.created_at)).all()]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(body: CameraIn, svc: Svc, s: DB, user: User) -> CameraOut:
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")[:24] or "camera"
    cam = Camera(id=f"{slug}-{uuid.uuid4().hex[:4]}", **body.model_dump())
    s.add(cam)
    audit(s, user, "camera.create", cam.id, body.model_dump())
    s.commit()
    if cam.enabled and svc.cameras:
        svc.cameras.start(cam, [])
    return _out(cam, svc)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, body: CameraPatch, svc: Svc, s: DB, user: User) -> CameraOut:
    cam = _get(s, camera_id)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(cam, k, v)
    s.add(cam)
    audit(s, user, "camera.update", cam.id, changes)
    s.commit()
    if svc.cameras:
        if cam.enabled:
            svc.cameras.start(cam, _zones(s, cam.id))
        else:
            svc.cameras.stop(cam.id)
    return _out(cam, svc)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: str, svc: Svc, s: DB, user: User) -> None:
    cam = _get(s, camera_id)
    if svc.cameras:
        svc.cameras.stop(camera_id)
    for z in s.exec(select(ZoneRow).where(ZoneRow.camera_id == camera_id)).all():
        s.delete(z)
    s.delete(cam)
    audit(s, user, "camera.delete", camera_id)
    s.commit()


@router.post("/{camera_id}/start", response_model=CameraOut)
def start_camera(camera_id: str, svc: Svc, s: DB, user: User) -> CameraOut:
    cam = _get(s, camera_id)
    require_cameras(svc).start(cam, _zones(s, cam.id))
    return _out(cam, svc)


@router.post("/{camera_id}/stop", response_model=CameraOut)
def stop_camera(camera_id: str, svc: Svc, s: DB, user: User) -> CameraOut:
    cam = _get(s, camera_id)
    require_cameras(svc).stop(camera_id)
    return _out(cam, svc)


@router.post("/test", response_model=dict)
def test_source(body: CameraIn, user: User) -> dict:
    """Try to open a source and read one frame (used by the 'Test connection' button)."""
    try:
        src = open_source(body.uri)
        frame = src.read() if not getattr(src, "live", False) else src.read(timeout=5.0)  # type: ignore[call-arg]
        src.close()
    except SourceError as exc:
        return {"ok": False, "message": str(exc)}
    if frame is None:
        return {"ok": False, "message": "Connected, but no frame arrived within 5 seconds."}
    h, w = frame.image.shape[:2]
    return {"ok": True, "message": f"Receiving {w}×{h} frames."}


@router.get("/{camera_id}/snapshot", responses={200: {"content": {"image/jpeg": {}}}})
def snapshot(camera_id: str, svc: Svc, s: DB, user: User) -> Response:
    """Latest frame of a running camera, or the first frame of its source (for the zone editor)."""
    cam = _get(s, camera_id)
    rt = svc.cameras.get(camera_id) if svc.cameras else None
    if rt is not None and rt.latest_jpeg is not None:
        return Response(rt.latest_jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    try:
        src = open_source(cam.uri)
        frame = src.read()
        src.close()
    except SourceError as exc:
        raise ApiError(409, "source_unavailable", str(exc)) from exc
    if frame is None:
        raise ApiError(409, "source_unavailable", "The camera returned no frame.")
    return Response(
        encode_jpeg(frame.image, 85), media_type="image/jpeg", headers={"Cache-Control": "no-store"}
    )
