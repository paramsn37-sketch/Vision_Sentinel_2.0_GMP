"""Train a detector from a hyperparameter YAML and record the run in training/registry.json.

uv run python ../training/scripts/train.py --hyp ../training/configs/hyp_cpu_budget.yaml --name vs2-y26n-cpu
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data import registry
from vs_data.dataset import resolved_data_yaml
from vs_data.paths import REPO

RUNS = REPO / "training" / "runs"
WEIGHTS_CACHE = Path.home() / ".cache" / "vision-sentinel"


def best_epoch(results_csv: Path) -> dict:
    rows = list(csv.DictReader(results_csv.open()))
    rows = [{k.strip(): v for k, v in r.items()} for r in rows]
    best = max(rows, key=lambda r: float(r.get("metrics/mAP50-95(B)", 0) or 0))
    return {
        "epochs_completed": len(rows),
        "best_epoch": int(float(best["epoch"])),
        "val": {
            "mAP50": float(best["metrics/mAP50(B)"]),
            "mAP50-95": float(best["metrics/mAP50-95(B)"]),
            "precision": float(best["metrics/precision(B)"]),
            "recall": float(best["metrics/recall(B)"]),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hyp", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--device", default=None)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument(
        "--resume", action="store_true", help="continue runs/<name>/weights/last.pt after an interruption"
    )
    args = ap.parse_args()

    import torch
    from ultralytics import YOLO

    if args.threads:
        torch.set_num_threads(args.threads)
    hyp = yaml.safe_load(args.hyp.read_text())
    model_name = hyp.pop("model")
    # A repo-relative path (e.g. models/vs2-y26n.pt) continues from our own weights; a bare name is a stock model.
    in_repo = REPO / model_name
    local = WEIGHTS_CACHE / model_name
    start = in_repo if in_repo.is_file() else local if local.exists() else model_name
    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    last = RUNS / args.name / "weights" / "last.pt"

    t0 = time.time()
    if args.resume:
        if not last.exists():
            raise SystemExit(f"nothing to resume: {last} does not exist")
        registry.upsert(
            args.name, status="running", resumed_at=datetime.now(UTC).isoformat(timespec="seconds")
        )
        model = YOLO(str(last))
        train_kwargs: dict = {"resume": True}
    else:
        registry.upsert(
            args.name, status="running", model=model_name, hyp=hyp, hyp_file=args.hyp.name, device=device
        )
        model = YOLO(str(start))
        train_kwargs = dict(
            data=str(resolved_data_yaml()), project=str(RUNS), name=args.name, exist_ok=True, device=device,
            plots=True, verbose=True, **hyp,
        )  # fmt: skip
    try:
        model.train(**train_kwargs)
    except Exception as exc:
        registry.upsert(
            args.name, status="failed", error=repr(exc), wall_time_h=round((time.time() - t0) / 3600, 2)
        )
        raise
    run_dir = RUNS / args.name
    registry.upsert(
        args.name,
        status="trained",
        finished_at=datetime.now(UTC).isoformat(timespec="seconds"),
        wall_time_h=round((time.time() - t0) / 3600, 2),
        run_dir=str(run_dir.relative_to(REPO)),
        **best_epoch(run_dir / "results.csv"),
    )


if __name__ == "__main__":
    main()
