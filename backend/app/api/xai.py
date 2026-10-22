from pathlib import Path

import cv2
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..db.models import IncidentRow, Upload
from ..services.storage import decode_jpeg
from .deps import DB, ApiError, Svc, User
from .schemas import XaiIn, XaiOut

router = APIRouter(prefix="/xai", tags=["explainability"])


def _out(res) -> XaiOut:
    return XaiOut(id=res.id, status=res.status, meta=res.meta, error=res.error,
                  overlay_url=f"/api/v1/xai/{res.id}/overlay" if res.status == "done" else None)  # fmt: skip


@router.post("", response_model=XaiOut, status_code=202)
def request_explanation(body: XaiIn, svc: Svc, s: DB, user: User) -> XaiOut:
    if svc.xai is None:
        raise ApiError(503, "model_unavailable", "The detection model is not loaded.")
    if body.source == "live":
        rt = svc.cameras.get(body.camera_id or "") if svc.cameras else None
        hit = rt.frame_for(body.frame_idx) if rt is not None and body.frame_idx is not None else None
        if hit is None:
            raise ApiError(
                410, "frame_gone", "That frame is no longer in memory. Pause the view and try again."
            )
        frame = decode_jpeg(hit[0])
        # Live frames are downscaled for streaming; boxes from the UI are in original pixels.
        scale = frame.shape[1] / hit[1].width
    elif body.source == "incident":
        row = s.get(IncidentRow, body.incident_id or "")
        if row is None or not row.snapshot_path or not Path(row.snapshot_path).exists():
            raise ApiError(404, "not_found", "No evidence image for this incident.")
        frame = cv2.imread(row.snapshot_path)
        scale = 1.0
        body.box = body.box or (tuple(row.box) if row.box else None)  # type: ignore[assignment]
        body.cls = body.cls or "person"
    else:
        up = s.get(Upload, body.upload_id or "")
        if up is None:
            raise ApiError(404, "not_found", "No such upload.")
        frame = _upload_frame(up, body.frame_idx or 0)
        scale = 1.0
    if frame is None:
        raise ApiError(409, "frame_unreadable", "Could not read that frame.")
    box = tuple(v * scale for v in body.box) if body.box else None
    if body.method == "gradcam" and (box is None or not body.cls):
        raise ApiError(422, "target_required", "Pick a detection to explain.")
    res = svc.xai.submit(frame, box, body.cls, body.method)  # type: ignore[arg-type]
    return _out(res)


def _upload_frame(up: Upload, idx: int):
    if up.media == "image":
        return cv2.imread(up.path)
    cap = cv2.VideoCapture(up.path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, img = cap.read()
    cap.release()
    return img if ok else None


@router.get("/{job_id}", response_model=XaiOut)
def get_explanation(job_id: str, svc: Svc, user: User) -> XaiOut:
    res = svc.xai.get(job_id) if svc.xai else None
    if res is None:
        raise ApiError(404, "not_found", "Unknown explanation job.")
    return _out(res)


@router.get("/{job_id}/overlay", response_class=FileResponse)
def overlay(job_id: str, svc: Svc, user: User) -> FileResponse:
    res = svc.xai.get(job_id) if svc.xai else None
    if res is None or res.overlay_path is None:
        raise ApiError(404, "not_found", "Explanation not ready.")
    return FileResponse(res.overlay_path, media_type="image/jpeg")


@router.get("/{job_id}/heatmap", response_class=FileResponse)
def heatmap(job_id: str, svc: Svc, user: User) -> FileResponse:
    res = svc.xai.get(job_id) if svc.xai else None
    if res is None or res.heatmap_path is None:
        raise ApiError(404, "not_found", "Explanation not ready.")
    return FileResponse(res.heatmap_path, media_type="image/png")


@router.get("/{job_id}/source", response_class=FileResponse)
def source(job_id: str, svc: Svc, user: User) -> FileResponse:
    """The exact frame that was explained (so the UI can blend the heatmap at any opacity)."""
    res = svc.xai.get(job_id) if svc.xai else None
    if res is None or res.source_path is None:
        raise ApiError(404, "not_found", "Explanation not ready.")
    return FileResponse(res.source_path, media_type="image/jpeg")
