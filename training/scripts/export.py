"""Promote a trained run to the app (Phase 2, task 8): copy the weights to models/, export ONNX, and write
models/model.json (classes, per-class thresholds from val, imgsz, test metrics, sha256, training mode).

uv run python ../training/scripts/export.py --run vs2-y26n-cpu480 --name vs2-y26n --imgsz 480
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data import registry
from vs_data.paths import REPO

MODELS = REPO / "models"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--imgsz", type=int, required=True)
    args = ap.parse_args()

    from ultralytics import YOLO

    results = json.loads((REPO / "docs" / "eval" / "detector_results.json").read_text())
    ev = results[args.run]
    run = next(r for r in registry.load()["runs"] if r["id"] == args.run)
    src = REPO / "training" / "runs" / args.run / "weights" / "best.pt"
    MODELS.mkdir(exist_ok=True)
    pt = MODELS / f"{args.name}.pt"
    shutil.copy2(src, pt)
    onnx = Path(YOLO(str(pt)).export(format="onnx", imgsz=args.imgsz, simplify=True))
    model = YOLO(str(pt))
    classes = [model.names[i] for i in sorted(model.names)]
    # A class the val split never contained has no F1 curve: fall back to a conservative 0.35.
    thresholds = {c: ev.get("thresholds_from_val", {}).get(c, 0.35) for c in classes}
    meta = {
        "name": args.name,
        "weights": pt.name,
        "onnx": onnx.name,
        "classes": classes,
        "imgsz": args.imgsz,
        "thresholds": thresholds,
        "metrics_test": ev["per_class"],
        "metrics_test_mean": ev["mean"],
        "trained_from": run.get("model"),
        "run": args.run,
        "training_mode": "cpu-budget" if run.get("device") == "cpu" else "gpu-full",
        "epochs_completed": run.get("epochs_completed"),
        "data_manifest": run.get("data_manifest"),
        "sha256": {pt.name: sha256(pt), onnx.name: sha256(onnx)},
        "licence_note": "AGPL-3.0. Trained on Ultralytics Construction-PPE (AGPL-3.0) and Open Images V7 (annotations CC BY 4.0, images CC BY 2.0); see data/DATASET_CARD.md.",
    }
    (MODELS / "model.json").write_text(json.dumps(meta, indent=2) + "\n")
    registry.upsert(args.run, status="promoted", promoted_as=args.name)
    print(json.dumps({k: meta[k] for k in ("name", "classes", "imgsz", "thresholds")}, indent=1))


if __name__ == "__main__":
    main()
