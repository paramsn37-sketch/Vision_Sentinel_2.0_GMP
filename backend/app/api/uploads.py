import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import col, select

from ..db.models import Upload
from ..services.uploads import IMAGE_EXT, VIDEO_EXT
from .deps import DB, ApiError, Svc, User, audit
from .schemas import UploadOut

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _out(u: Upload) -> UploadOut:
    return UploadOut(
        **u.model_dump(exclude={"path", "output_path"}),
        has_output=bool(u.output_path and Path(u.output_path).exists()),
    )


@router.post("", response_model=UploadOut, status_code=202)
async def upload(file: UploadFile, svc: Svc, s: DB, user: User) -> UploadOut:
    if svc.uploads is None:
        raise ApiError(503, "model_unavailable", "The detection model is not loaded.")
    name = Path(file.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in IMAGE_EXT | VIDEO_EXT:
        raise ApiError(415, "unsupported_type", "Upload a JPG/PNG image or an MP4/MOV/AVI/MKV/WebM video.")
    uid = "up_" + uuid.uuid4().hex[:10]
    dst = svc.paths.uploads / f"{uid}{ext}"
    limit = svc.settings.storage.max_upload_mb * 1024 * 1024
    size = 0
    with dst.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dst.unlink(missing_ok=True)
                raise ApiError(
                    413, "too_large", f"Files up to {svc.settings.storage.max_upload_mb} MB are accepted."
                )
            out.write(chunk)
    row = Upload(id=uid, filename=name, path=str(dst), media="image" if ext in IMAGE_EXT else "video")
    s.add(row)
    audit(s, user, "upload.create", uid, {"filename": name, "bytes": size})
    s.commit()
    svc.uploads.submit(uid)
    return _out(row)


@router.get("", response_model=list[UploadOut])
def list_uploads(s: DB, user: User, limit: int = 20) -> list[UploadOut]:
    return [
        _out(u)
        for u in s.exec(select(Upload).order_by(col(Upload.created_at).desc()).limit(min(limit, 100))).all()
    ]


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: str, s: DB, user: User) -> UploadOut:
    u = s.get(Upload, upload_id)
    if u is None:
        raise ApiError(404, "not_found", "No such upload.")
    return _out(u)


@router.get("/{upload_id}/source", response_class=FileResponse)
def source(upload_id: str, s: DB, user: User) -> FileResponse:
    u = s.get(Upload, upload_id)
    if u is None or not Path(u.path).exists():
        raise ApiError(404, "not_found", "No such upload.")
    return FileResponse(u.path, filename=u.filename)


@router.get("/{upload_id}/annotated", response_class=FileResponse)
def annotated(upload_id: str, s: DB, user: User) -> FileResponse:
    u = s.get(Upload, upload_id)
    if u is None or not u.output_path or not Path(u.output_path).exists():
        raise ApiError(404, "not_found", "The annotated file is not ready.")
    return FileResponse(
        u.output_path, filename=f"annotated_{Path(u.filename).stem}{Path(u.output_path).suffix}"
    )


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: str, s: DB, user: User) -> None:
    u = s.get(Upload, upload_id)
    if u is None:
        raise ApiError(404, "not_found", "No such upload.")
    for p in (u.path, u.output_path):
        if p:
            Path(p).unlink(missing_ok=True)
    s.delete(u)
    audit(s, user, "upload.delete", upload_id)
    s.commit()
