import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..settings import REPO
from .deps import ApiError, Svc, User

router = APIRouter(prefix="/model", tags=["model"])
FIGURE_DIRS = {
    "training": REPO / "training" / "reports" / "figures",
    "dataset": REPO / "data" / "figures",
    "eval": REPO / "docs" / "eval" / "figures",
}


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
        "is_ppe_model": info.is_ppe_model,
        "classes": info.classes,
        "imgsz": svc.detector.imgsz,
        "device": svc.detector.device,
        "thresholds": info.thresholds,
        "meta": info.meta,
    }


@router.get("/runs")
def runs(user: User) -> dict:
    return _json(REPO / "training" / "registry.json") or {"runs": []}


@router.get("/evaluations")
def evaluations(user: User) -> dict:
    ev = REPO / "docs" / "eval"
    return {
        "counting": _json(ev / "counting_results.json"),
        "xai": _json(ev / "xai_results.json"),
        "detector": _json(ev / "detector_results.json"),
        "latency": _json(REPO / "training" / "benchmarks" / "latency.json"),
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
    return {
        g: sorted(p.name for p in d.glob("*") if p.suffix in {".png", ".jpg"}) if d.exists() else []
        for g, d in FIGURE_DIRS.items()
    }


@router.get("/figures/{group}/{name}", response_class=FileResponse)
def figure(group: str, name: str, user: User) -> FileResponse:
    d = FIGURE_DIRS.get(group)
    if d is None or "/" in name or "\\" in name or name.startswith("."):
        raise ApiError(404, "not_found", "No such figure.")
    p = (d / name).resolve()
    if p.parent != d.resolve() or not p.exists():
        raise ApiError(404, "not_found", "No such figure.")
    return FileResponse(p)
