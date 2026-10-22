"""Performance pass (Phase 11): per-stage latency and end-to-end throughput for 1 and 4 file-source cameras.

uv run python -m eval.perf [--seconds 60] [--imgsz 640]
Each camera runs the full pipeline (detect → track → PPE → zones/incidents) plus the live JPEG encode on its own
thread, unpaced (as fast as the machine allows), sharing one detector the way the server does. Writes
docs/eval/performance.{json,md}. Results depend on the machine and on its load, which are recorded alongside.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import torch

from app.core.detection.detector import Detector
from app.core.incidents.manager import IncidentManager
from app.core.pipeline import Pipeline
from app.core.sources.base import FileSource
from app.core.zones.engine import ZoneEngine
from app.core.zones.model import load_zones_yaml
from app.services.storage import encode_jpeg
from app.settings import DetectionCfg

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "data" / "samples"
OUT = REPO / "docs" / "eval"
CLIPS = [("pedestrian_street_night", "pedestrian_street_night.mp4"), ("town_square", "town_square.mp4")]


def pct(v: list[float], q: float) -> float:
    v = sorted(v)
    return round(v[min(len(v) - 1, int(q * (len(v) - 1)))], 1) if v else 0.0


def run(n_cams: int, seconds: float, detector: Detector) -> dict:
    stats: list[dict] = [{"lat": {}, "frames": 0, "res": None} for _ in range(n_cams)]
    stop = time.monotonic() + seconds

    def worker(i: int) -> None:
        name, clip = CLIPS[i % len(CLIPS)]
        zones_file = SAMPLES / "zones" / f"{name}.yaml"
        zones = ZoneEngine(load_zones_yaml(zones_file)) if zones_file.exists() else None
        src = FileSource(SAMPLES / clip, loop=True)
        pipe = Pipeline(f"cam{i}", detector, fps=src.effective_fps, zones=zones,
                        incidents=IncidentManager(f"cam{i}", zones) if zones else None)  # fmt: skip
        st = stats[i]
        while time.monotonic() < stop:
            frame = src.read()
            if frame is None:
                break
            res = pipe.process(frame)
            t = time.perf_counter()
            encode_jpeg(frame.image, 70, 1280)
            res.latency_ms["jpeg"] = (time.perf_counter() - t) * 1000
            for k, v in res.latency_ms.items():
                st["lat"].setdefault(k, []).append(v)
            st["frames"] += 1
            st["res"] = (frame.image.shape[1], frame.image.shape[0])
        src.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_cams)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.monotonic() - t0
    merged: dict[str, list[float]] = {}
    for st in stats:
        for k, v in st["lat"].items():
            merged.setdefault(k, []).extend(v)
    frames = sum(st["frames"] for st in stats)
    return {
        "cameras": n_cams,
        "seconds": round(wall, 1),
        "frames": frames,
        "fps_total": round(frames / wall, 2),
        "fps_per_camera": round(frames / wall / n_cams, 2),
        "resolutions": sorted({f"{st['res'][0]}x{st['res'][1]}" for st in stats if st["res"]}),
        "stage_ms": {
            k: {"p50": pct(v, 0.5), "p95": pct(v, 0.95), "mean": round(statistics.fmean(v), 1)}
            for k, v in merged.items()
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--cams", default="1,4")
    ap.add_argument("--label", default="default")
    ap.add_argument(
        "--person-model", default=None, help='override detection.person_model ("" = trained model only)'
    )
    args = ap.parse_args()

    det = DetectionCfg()
    person_model = det.person_model if args.person_model is None else args.person_model
    detector = Detector(imgsz=args.imgsz, person_model=person_model or None, person_imgsz=det.person_imgsz)
    runs = [run(int(n), args.seconds, detector) for n in args.cams.split(",")]
    machine = {
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "load_avg_1m_end": round(os.getloadavg()[0], 2),
    }
    out_json = OUT / "performance.json"
    data = json.loads(out_json.read_text()) if out_json.exists() else {}
    data[args.label] = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": detector.name,
        "imgsz": detector.imgsz,
        "device": detector.device,
        "machine": machine,
        "runs": runs,
    }
    out_json.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data[args.label], indent=1))


if __name__ == "__main__":
    main()
