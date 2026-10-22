import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..settings import REPO
from .deps import ApiError, Svc, User

router = APIRouter(prefix="/model", tags=["model"])
FIGURE_DIRS = {
    "summary": REPO / "training" / "reports" / "figures",
    "training": REPO / "training" / "runs" / "{run}",
    "test": REPO / "training" / "reports" / "eval" / "{run}",
    "errors": REPO / "training" / "reports" / "error_analysis",
    "dataset": REPO / "data" / "figures",
    "explanations": REPO / "docs" / "eval" / "figures",
}
# Only plots, not the per-batch sample mosaics Ultralytics also writes.
FIGURE_SKIP = ("train_batch", "val_batch")


def _figure_dir(group: str) -> Path | None:
    d = FIGURE_DIRS.get(group)
    if d is None:
        return None
    return Path(str(d).replace("{run}", _active_run() or "_none_"))


def _json(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


@router.get("/active")
def active(svc: Svc, user: User) -> dict:
    if svc.detector is None:
        return {"loaded": False, "error": svc.model_error}
    info = svc.detector.info
    return {
        "loaded": True,
        "name": info.name,
        "person_detector": svc.detector.person_model_name,
        "is_ppe_model": info.is_ppe_model,
        "classes": info.classes,
        "imgsz": svc.detector.imgsz,
        "device": svc.detector.device,
        "thresholds": info.thresholds,
        "meta": info.meta,
    }


def _active_run() -> str | None:
    meta = _json(REPO / "models" / "model.json") or {}
    return meta.get("run")


@router.get("/runs")
def runs(user: User) -> dict:
    """Training runs and baselines from training/registry.json, in one flat shape for the UI."""
    reg = _json(REPO / "training" / "registry.json") or {"runs": []}
    out = []
    for r in reg.get("runs", []):
        test_person = (r.get("test_metrics") or {}).get("per_class", {}).get("person", {})
        out.append(
            {
                "id": r.get("id"),
                "model": r.get("model"),
                "status": r.get("status"),
                "created_at": r.get("created_at"),
                "imgsz": (r.get("hyp") or {}).get("imgsz") or r.get("imgsz"),
                "epochs_completed": r.get("epochs_completed"),
                "val_map50": (r.get("val") or {}).get("mAP50"),
                "test_person_map50": test_person.get("mAP50"),
                "note": r.get("note"),
            }
        )
    return {"runs": out}


def _detector() -> dict | None:
    raw = _json(REPO / "docs" / "eval" / "detector_results.json")
    if not raw:
        return None
    models = []
    for name, r in raw.items():
        per_class = [
            {
                "class": c,
                "precision": v.get("precision"),
                "recall": v.get("recall"),
                "map50": v.get("mAP50"),
                "map50_95": v.get("mAP50-95"),
            }
            for c, v in (r.get("per_class") or {}).items()
        ]
        models.append(
            {"name": name, "kind": r.get("kind"), "imgsz": r.get("imgsz"), "per_class": per_class,
             "mean": {"map50": (r.get("mean") or {}).get("mAP50"), "map50_95": (r.get("mean") or {}).get("mAP50-95")}}
        )  # fmt: skip
    return {"active": _active_run(), "models": models}


def _latency() -> list[dict] | None:
    raw = _json(REPO / "training" / "benchmarks" / "latency.json")
    if not raw:
        return None
    return [
        {"model": name, "runtime": row["runtime"], "imgsz": row["imgsz"], "device": row.get("device"),
         "p50_ms": row["p50_ms"], "p95_ms": row["p95_ms"], "measured_at": entry.get("measured_at")}
        for name, entry in raw.items()
        for row in entry.get("results", [])
    ]  # fmt: skip


def _xai() -> dict | None:
    raw = _json(REPO / "docs" / "eval" / "xai_results.json")
    if not raw:
        return None
    dl, rnd, lat = raw.get("deletion") or {}, raw.get("randomisation") or {}, raw.get("latency_ms") or {}
    return {
        "model": raw.get("model"),
        "method": raw.get("variant"),
        "samples": raw.get("samples"),
        "pointing_game": raw.get("pointing_game"),
        "deletion_top_beats_random": dl.get("share_top_beats_random"),
        "deletion_drop_top20": dl.get("mean_drop_top20"),
        "deletion_drop_random20": dl.get("mean_drop_random20"),
        "randomisation_ssim": rnd.get("mean_ssim"),
        "latency_p50_ms": lat.get("p50"),
        "latency_p95_ms": lat.get("p95"),
    }


@router.get("/evaluations")
def evaluations(user: User) -> dict:
    return {
        "counting": _json(REPO / "docs" / "eval" / "counting_results.json"),
        "xai": _xai(),
        "detector": _detector(),
        "latency": _latency(),
    }


@router.get("/dataset")
def dataset(user: User) -> dict:
    card = REPO / "data" / "DATASET_CARD.md"
    return {
        "card": card.read_text() if card.exists() else None,
        "split": _json(REPO / "data" / "manifests" / "split_stats.json"),
    }


@router.get("/figures")
def figures(user: User) -> dict:
    out = {}
    for g in FIGURE_DIRS:
        d = _figure_dir(g)
        out[g] = (
            sorted(
                p.name
                for p in d.glob("*")
                if p.suffix in {".png", ".jpg"} and not p.name.startswith(FIGURE_SKIP)
            )
            if d and d.exists()
            else []
        )
    return out


@router.get("/figures/{group}/{name}", response_class=FileResponse)
def figure(group: str, name: str, user: User) -> FileResponse:
    d = _figure_dir(group)
    if d is None or "/" in name or "\\" in name or name.startswith("."):
        raise ApiError(404, "not_found", "No such figure.")
    p = (d / name).resolve()
    if p.parent != d.resolve() or not p.exists():
        raise ApiError(404, "not_found", "No such figure.")
    return FileResponse(p)
