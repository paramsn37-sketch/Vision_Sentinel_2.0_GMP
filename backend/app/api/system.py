import time

from fastapi import APIRouter, Response
from sqlmodel import col, select

from ..db.models import AuditLog, SettingRow
from .deps import DB, Svc, User, audit
from .schemas import ThresholdsIO

router = APIRouter(tags=["system"])
STARTED = time.time()


@router.get("/health")
def health(svc: Svc) -> dict:
    cams = {cid: rt.info() for cid, rt in (svc.cameras.runtimes.items() if svc.cameras else [])}
    return {
        "status": "ok" if svc.detector is not None else "degraded",
        "model": svc.detector.info.name if svc.detector else None,
        "model_error": svc.model_error,
        "uptime_s": round(time.time() - STARTED),
        "cameras": {
            cid: {k: info[k] for k in ("status", "fps", "people_now", "error")} for cid, info in cams.items()
        },
    }


@router.get("/metrics", response_class=Response)
def metrics(svc: Svc) -> Response:
    lines = [
        "# TYPE vs_camera_fps gauge",
        "# TYPE vs_camera_people gauge",
        "# TYPE vs_camera_frames_total counter",
    ]
    for cid, rt in svc.cameras.runtimes.items() if svc.cameras else []:
        info = rt.info()
        lines += [
            f'vs_camera_fps{{camera="{cid}"}} {info["fps"]}',
            f'vs_camera_people{{camera="{cid}"}} {info["people_now"]}',
            f'vs_camera_frames_total{{camera="{cid}"}} {info["frames"]}',
            f'vs_camera_up{{camera="{cid}"}} {int(info["status"] == "running")}',
        ]
        if rt.latest_result is not None:
            for stage, ms in rt.latest_result.latency_ms.items():
                lines.append(f'vs_stage_latency_ms{{camera="{cid}",stage="{stage}"}} {ms}')
    lines.append(f"vs_uptime_seconds {round(time.time() - STARTED)}")
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.get("/settings/thresholds", response_model=ThresholdsIO)
def get_thresholds(svc: Svc, user: User) -> ThresholdsIO:
    cfg = svc.core_config()
    return ThresholdsIO(
        tracking={k: getattr(cfg.tracking, k) for k in ("min_hits", "min_age_s", "min_hit_ratio", "new_track_thresh", "track_buffer_s", "reid_window_s")},
        ppe={k: getattr(cfg.ppe, k) for k in ("violation_min_s", "evidence_tau_s", "absent_below", "present_above", "min_person_height_px")},
        zones={k: getattr(cfg.zones, k) for k in ("enter_frames", "exit_frames", "lost_grace_s")},
        incidents={k: getattr(cfg.incidents, k) for k in ("clear_s", "cooldown_s", "overcrowding_min_s")},
        site={"required_ppe": list(cfg.site_required_ppe)},
    )  # fmt: skip


@router.put("/settings/thresholds", response_model=ThresholdsIO)
def put_thresholds(body: ThresholdsIO, svc: Svc, s: DB, user: User) -> ThresholdsIO:
    from .deps import ApiError

    current = svc.core_config()
    for section, values in body.model_dump().items():
        if section == "site":
            continue
        target = getattr(current, section)
        for k in values:
            if not hasattr(target, k):
                raise ApiError(422, "unknown_setting", f"Unknown setting {section}.{k}.")
    if body.ppe.get("absent_below", 0) >= body.ppe.get("present_above", 1):
        raise ApiError(
            422, "invalid_setting", "The 'absent below' threshold must be lower than 'present above'."
        )
    row = s.get(SettingRow, "thresholds") or SettingRow(key="thresholds", value={})
    row.value = body.model_dump()
    s.add(row)
    audit(s, user, "settings.thresholds", None, row.value)
    s.commit()
    if svc.cameras:  # restart pipelines so the new thresholds apply
        from ..db.models import Camera
        from .cameras import _zones

        for cid in list(svc.cameras.runtimes):
            cam = s.get(Camera, cid)
            if cam is not None:
                svc.cameras.start(cam, _zones(s, cid))
    return get_thresholds(svc, user)


@router.get("/audit")
def audit_log(s: DB, user: User, limit: int = 100) -> list[dict]:
    rows = s.exec(select(AuditLog).order_by(col(AuditLog.at).desc()).limit(min(limit, 500))).all()
    return [r.model_dump() for r in rows]
