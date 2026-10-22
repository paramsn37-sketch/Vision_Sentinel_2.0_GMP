"""Latency benchmark (Phase 2, task 5): ms per frame (p50/p95) and FPS for PyTorch and ONNX Runtime at two input
sizes on the devices available, using real test-split images. Writes training/benchmarks/latency.json.

uv run python ../training/scripts/benchmark.py --weights ../models/vs2-y26n.pt --name vs2-y26n
Numbers depend on the machine and on what else runs on it; the JSON records both (cpu count, load average).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.paths import MERGED, REPO

OUT = REPO / "training" / "benchmarks" / "latency.json"


def measure(model, images: list, imgsz: int, device: str, warmup: int = 5) -> dict:
    for im in images[:warmup]:
        model.predict(im, imgsz=imgsz, device=device, verbose=False)
    times = []
    for im in images:
        t0 = time.perf_counter()
        model.predict(im, imgsz=imgsz, device=device, verbose=False)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p50 = statistics.median(times)
    return {
        "frames": len(times),
        "p50_ms": round(p50, 1),
        "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1),
        "fps_at_p50": round(1000 / p50, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--sizes", default="640,480")
    ap.add_argument("--frames", type=int, default=60)
    args = ap.parse_args()

    import cv2
    import torch
    from ultralytics import YOLO

    imgs = sorted((MERGED / "test" / "images").glob("*"))[: args.frames]
    images = [cv2.imread(str(p)) for p in imgs]
    devices = ["cpu"] + (["0"] if torch.cuda.is_available() else [])
    rows = []
    for imgsz in [int(s) for s in args.sizes.split(",")]:
        for device in devices:
            rows.append({"runtime": "pytorch", "imgsz": imgsz, "device": device,
                         **measure(YOLO(str(args.weights)), images, imgsz, device)})  # fmt: skip
        # Export from a temporary copy so the promoted models/*.onnx (and its sha256 in model.json) is untouched.
        tmp = Path(tempfile.mkdtemp()) / args.weights.name
        shutil.copy2(args.weights, tmp)
        onnx = YOLO(str(tmp)).export(format="onnx", imgsz=imgsz, dynamic=False, simplify=True)
        rows.append({"runtime": "onnxruntime", "imgsz": imgsz, "device": "cpu",
                     **measure(YOLO(onnx, task="detect"), images, imgsz, "cpu")})  # fmt: skip
        print(rows[-2:], flush=True)

    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    machine = {
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "load_avg_1m": round(os.getloadavg()[0], 2),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    out[args.name] = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "weights": str(args.weights),
        "machine": machine,
        "note": "single image per call, includes pre- and post-processing",
        "results": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
