"""Evaluate a detector on the frozen test split and record the numbers (Phase 2, tasks 2 and 4).

Our model:  uv run python ../training/scripts/evaluate.py --weights ../training/runs/vs2-y26n-cpu480/weights/best.pt \
                --name vs2-y26n-cpu480 --imgsz 480 --thresholds
Baselines:  uv run python ../training/scripts/evaluate.py --weights yolo11m.pt --name baseline-v1-yolo11m --coco
            uv run python ../training/scripts/evaluate.py --weights yolo26n.pt --name baseline-yolo26n-coco --coco

`--coco` evaluates a stock COCO model: only its `person` predictions are kept (COCO person and our person are both
class 0); every PPE class scores 0 because COCO has none. That is the v1 setup.
Results go to docs/eval/detector_results.json (one entry per name) and the run registry; plots (PR, F1, confusion
matrix) to training/reports/eval/<name>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data import registry
from vs_data.dataset import resolved_data_yaml
from vs_data.paths import REPO

RESULTS = REPO / "docs" / "eval" / "detector_results.json"
REPORTS = REPO / "training" / "reports" / "eval"
WEIGHTS_CACHE = Path.home() / ".cache" / "vision-sentinel"


def taxonomy() -> list[str]:
    names = yaml.safe_load((REPO / "training" / "configs" / "data.yaml").read_text())["names"]
    return [names[i] for i in sorted(names)]


def per_class(box, classes: list[str], only: set[int] | None = None) -> dict[str, dict[str, float]]:
    """Per-class P, R, mAP50, mAP50-95 by taxonomy index (Ultralytics only reports classes present in GT)."""
    out = {c: {"precision": 0.0, "recall": 0.0, "mAP50": 0.0, "mAP50-95": 0.0} for c in classes}
    for k, ci in enumerate(box.ap_class_index):
        ci = int(ci)
        if ci >= len(classes) or (only is not None and ci not in only):
            continue
        out[classes[ci]] = {
            "precision": round(float(box.p[k]), 4),
            "recall": round(float(box.r[k]), 4),
            "mAP50": round(float(box.ap50[k]), 4),
            "mAP50-95": round(float(box.ap[k]), 4),
        }
    return out


def f1_thresholds(box, classes: list[str]) -> dict[str, float]:
    """Operating threshold per class = confidence that maximises F1 (computed on the split given)."""
    px = box.px
    th = {}
    for k, ci in enumerate(box.ap_class_index):
        ci = int(ci)
        if ci < len(classes):
            th[classes[ci]] = round(float(px[int(box.f1_curve[k].argmax())]), 3)
    return th


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--split", default="test")
    ap.add_argument("--coco", action="store_true", help="stock COCO model: keep person predictions only")
    ap.add_argument("--thresholds", action="store_true", help="also pick per-class F1 thresholds on val")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    import torch
    from ultralytics import YOLO

    local = WEIGHTS_CACHE / args.weights
    model = YOLO(str(local) if local.exists() else args.weights)
    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    classes = taxonomy()
    data = str(resolved_data_yaml())
    common = dict(data=data, imgsz=args.imgsz, device=device, batch=16, plots=True, verbose=False,
                  project=str(REPORTS), exist_ok=True)  # fmt: skip
    if args.coco:
        common["classes"] = [0]

    res = model.val(split=args.split, name=args.name, **common)
    only = {0} if args.coco else None
    pcs = per_class(res.box, classes, only)
    entry: dict = {
        "name": args.name,
        "weights": str(args.weights),
        "split": args.split,
        "imgsz": args.imgsz,
        "kind": "stock COCO, person only" if args.coco else "trained",
        "evaluated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "per_class": pcs,
        "mean": {
            "mAP50": round(sum(c["mAP50"] for c in pcs.values()) / len(pcs), 4),
            "mAP50-95": round(sum(c["mAP50-95"] for c in pcs.values()) / len(pcs), 4),
        },
        "speed_ms": {k: round(v, 2) for k, v in res.speed.items()},
        "plots": str((REPORTS / args.name).relative_to(REPO)),
    }
    if args.thresholds and not args.coco:
        val = model.val(split="val", name=f"{args.name}-val", **common)
        entry["thresholds_from_val"] = f1_thresholds(val.box, classes)

    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results[args.name] = entry
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2) + "\n")
    registry.upsert(args.name, **({"status": "baseline", "model": args.weights} if args.coco else {}),
                    test_metrics={"per_class": pcs, "mean": entry["mean"]})  # fmt: skip
    print(
        json.dumps({k: v["mAP50"] for k, v in pcs.items()} | {"mean_mAP50": entry["mean"]["mAP50"]}, indent=1)
    )


if __name__ == "__main__":
    main()
