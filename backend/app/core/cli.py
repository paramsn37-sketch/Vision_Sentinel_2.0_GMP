"""Command-line runner for debugging and reports.

uv run python -m app.core.cli run --source ../data/samples/street_corner.mp4 --out /tmp/out.mp4 --json /tmp/s.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from .annotate import draw
from .detection.detector import Detector
from .pipeline import Pipeline
from .sources.base import FileSource, open_source


def run(args: argparse.Namespace) -> dict:
    source = open_source(args.source, stride=args.stride)
    fps = source.effective_fps if isinstance(source, FileSource) else source.fps
    detector = Detector(imgsz=args.imgsz)
    zone_engine = incidents = None
    zone_polys: list = []
    if args.zones:
        from .incidents.manager import IncidentManager
        from .zones.engine import ZoneEngine
        from .zones.model import load_zones_yaml

        zones = load_zones_yaml(Path(args.zones))
        zone_engine = ZoneEngine(zones)
        incidents = IncidentManager("cli", zone_engine)
    pipe = Pipeline("cli", detector, fps=fps, zones=zone_engine, incidents=incidents)
    writer = None
    t0, n, last = time.perf_counter(), 0, None
    for frame in source:
        res = pipe.process(frame)
        last, n = res, n + 1
        if args.out:
            if zone_engine is not None:
                zone_polys = zone_engine.pixel_polygons(res.width, res.height)
            img = draw(frame.image, res, zone_polys)
            if writer is None:
                h, w = img.shape[:2]
                writer = cv2.VideoWriter(args.out, cv2.VideoWriter.fourcc(*"mp4v"), fps, (w, h))
            writer.write(img)
    if writer is not None:
        writer.release()
    summary = {
        "source": args.source,
        "frames": n,
        "unique_total": last.counts.unique_total if last else 0,
        "raw_track_ids": len(pipe.tracker.raw_ids_seen),
        "wall_s": round(time.perf_counter() - t0, 1),
        "model": detector.name,
    }
    if incidents is not None:
        summary["incidents"] = [i.to_dict() for i in incidents.all()]
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "incidents"}, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(prog="vision-sentinel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="process a video/image/stream")
    r.add_argument("--source", required=True)
    r.add_argument("--out")
    r.add_argument("--json")
    r.add_argument("--zones", help="zones YAML for this source")
    r.add_argument("--stride", type=int, default=1)
    r.add_argument("--imgsz", type=int, default=None)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args)


if __name__ == "__main__":
    main()
