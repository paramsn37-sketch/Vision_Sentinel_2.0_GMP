"""Counting and tracking evaluation on MOT17 (blueprint §5.6).

Detections are computed once per sequence and cached, then three counting strategies are compared:
  naive_1fps  — v1 behaviour: sum of people detected in one frame per second;
  bytetrack   — distinct raw ByteTrack IDs with Ultralytics' default tracker settings;
  ours        — PersonTracker (tuned ByteTrack + confirmation + lost-track merge), confirmed IDs only.
Thresholds are tuned on MOT17-02/04 only and reported on 05/09/10/11/13.

    uv run python -m eval.counting_eval [--weights path] [--imgsz 640] [--no-tune]
"""

from __future__ import annotations

import argparse
import configparser
import itertools
import json
from dataclasses import asdict, replace
from pathlib import Path

import cv2
import motmetrics as mm
import numpy as np

from app.core.config import TrackingConfig
from app.core.detection.detector import Detector, ModelInfo, load_model_info
from app.core.geometry import iou
from app.core.tracking.tracker import PersonTracker
from app.core.types import Detection
from app.settings import DetectionCfg

REPO = Path(__file__).resolve().parents[2]
MOT = REPO / "data" / "raw" / "mot17" / "MOT17-50" / "train"
CACHE = REPO / "data" / "eval" / "cache"
REPORT = REPO / "docs" / "eval" / "counting_report.md"
RESULTS = REPO / "docs" / "eval" / "counting_results.json"
TUNE = ["MOT17-02", "MOT17-04"]
REPORT_SEQS = ["MOT17-05", "MOT17-09", "MOT17-10", "MOT17-11", "MOT17-13"]
DISTRACTORS = {2, 7, 8, 12}
# Ultralytics' default bytetrack.yaml, i.e. what `model.track()` in v1 used.
DEFAULT_BYTETRACK = TrackingConfig(
    track_high_thresh=0.25, track_low_thresh=0.1, new_track_thresh=0.25, track_buffer_s=1.0,
    min_hits=1, min_age_s=0.0, min_hit_ratio=0.0, reid_window_s=0.0,
)  # fmt: skip


def seq_info(seq: Path) -> dict:
    cp = configparser.ConfigParser()
    cp.read(seq / "seqinfo.ini")
    s = cp["Sequence"]
    return {"fps": float(s["frameRate"]), "frames": len(list((seq / "img1").glob("*.jpg")))}


def load_gt(seq: Path) -> tuple[dict[int, list], dict[int, list], int]:
    targets: dict[int, list] = {}
    distract: dict[int, list] = {}
    ids = set()
    for line in (seq / "gt" / "gt.txt").read_text().split():
        f = line.split(",")
        fr, tid, x, y, w, h, consider, cls = int(f[0]), int(f[1]), *map(float, f[2:6]), int(f[6]), int(f[7])
        box = (x, y, x + w, y + h)
        if cls == 1 and consider == 1:
            targets.setdefault(fr, []).append((tid, box))
            ids.add(tid)
        elif cls in DISTRACTORS:
            distract.setdefault(fr, []).append(box)
    return targets, distract, len(ids)


def detections(seq: Path, detector: Detector, tag: str) -> dict[int, list[Detection]]:
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{seq.name}_{tag}.json"
    if cache.exists():
        raw = json.loads(cache.read_text())
        return {int(k): [Detection("person", c, tuple(b)) for c, b in v] for k, v in raw.items()}
    out: dict[int, list[Detection]] = {}
    for i, img_path in enumerate(sorted((seq / "img1").glob("*.jpg")), start=1):
        dets = [d for d in detector.detect(cv2.imread(str(img_path))) if d.cls == "person"]
        out[i] = dets
    cache.write_text(json.dumps({k: [(d.conf, d.xyxy) for d in v] for k, v in out.items()}))
    return out


def run_tracker(seq: Path, dets: dict[int, list[Detection]], cfg: TrackingConfig, fps: float):
    tracker = PersonTracker(cfg, fps=fps)
    per_frame: dict[int, list[tuple[int, tuple]]] = {}
    imgs = sorted((seq / "img1").glob("*.jpg"))
    for i, img_path in enumerate(imgs, start=1):
        # Appearance is only read for merge candidates; load the frame lazily (cheap enough at this scale).
        frame = cv2.imread(str(img_path)) if cfg.reid_window_s > 0 else np.zeros((8, 8, 3), np.uint8)
        upd = tracker.update(dets.get(i, []), frame, i / fps)
        per_frame[i] = [(t.track_id, t.xyxy) for t in upd.visible if t.confirmed or cfg.min_hits <= 1]
    return tracker, per_frame


def score(seq_name: str, per_frame, tracker: PersonTracker | None, gt, frames: int) -> dict:
    targets, distract, gt_unique = gt
    acc = mm.MOTAccumulator(auto_id=True)
    distractor_hits: dict[int, int] = {}
    frames_seen: dict[int, int] = {}
    for fr in range(1, frames + 1):
        preds = per_frame.get(fr, [])
        kept = []
        for tid, box in preds:
            frames_seen[tid] = frames_seen.get(tid, 0) + 1
            best_t = max((iou(box, b) for _, b in targets.get(fr, [])), default=0.0)
            best_d = max((iou(box, b) for b in distract.get(fr, [])), default=0.0)
            if best_d >= 0.5 and best_d > best_t:
                distractor_hits[tid] = distractor_hits.get(tid, 0) + 1
                continue
            kept.append((tid, box))
        gts = targets.get(fr, [])
        dist = (
            np.array([[1 - iou(g, p) for _, p in kept] for _, g in gts])
            if gts and kept
            else np.empty((len(gts), len(kept)))
        )
        dist[dist > 0.5] = np.nan
        acc.update([t for t, _ in gts], [t for t, _ in kept], dist)
    m = mm.metrics.create().compute(acc, metrics=["idf1", "mota", "num_switches"], name=seq_name)
    pred_ids = set(frames_seen)
    # A predicted person that spends most of its life on a distractor (cyclist, static person) is not counted.
    on_distractor = {t for t in pred_ids if distractor_hits.get(t, 0) > 0.5 * frames_seen[t]}
    pred_unique = len(pred_ids - on_distractor)
    return {
        "gt_unique": gt_unique,
        "pred_unique": pred_unique,
        "count_error": abs(pred_unique - gt_unique) / gt_unique,
        "idf1": float(m["idf1"].iloc[0]),
        "mota": float(m["mota"].iloc[0]),
        "id_switches": int(m["num_switches"].iloc[0]),
    }


def naive_1fps(dets: dict[int, list[Detection]], fps: float, gt_unique: int) -> dict:
    step = max(1, round(fps))
    total = sum(sum(1 for d in dets.get(f, []) if d.conf >= 0.5) for f in range(1, max(dets) + 1, step))
    return {"gt_unique": gt_unique, "pred_unique": total, "count_error": abs(total - gt_unique) / gt_unique}


def evaluate(seqs: list[str], cache: dict, cfg: TrackingConfig) -> dict[str, dict]:
    out = {}
    for name in seqs:
        seq, info, dets, gt = cache[name]
        tracker, per_frame = run_tracker(seq, dets, cfg, info["fps"])
        out[name] = score(name, per_frame, tracker, gt, info["frames"])
    return out


def objective(res: dict[str, dict]) -> float:
    return float(
        np.mean([r["count_error"] for r in res.values()])
        + 0.5 * np.mean([1 - r["idf1"] for r in res.values()])
    )


def tune(cache: dict) -> tuple[TrackingConfig, list[dict]]:
    base = TrackingConfig()
    grid = {
        # The tuning sequences are detector-limited (small, distant people), so recall knobs come first.
        "track_high_thresh": [0.2, 0.3, 0.5],
        "new_track_thresh": [0.25, 0.4, 0.6],
        "min_hits": [2, 3, 5],
        "min_age_s": [0.2, 0.5],
        "min_hit_ratio": [0.3],
        "track_buffer_s": [1.5, 3.0],
        "reid_window_s": [0.0, 2.0],
    }
    trials = []
    best_cfg, best = base, float("inf")
    for values in itertools.product(*grid.values()):
        cfg = replace(base, **dict(zip(grid, values, strict=True)))
        res = evaluate(TUNE, cache, cfg)
        obj = objective(res)
        trials.append({"params": dict(zip(grid, values, strict=True)), "objective": round(obj, 4)})
        if obj < best:
            best_cfg, best = cfg, obj
    return best_cfg, sorted(trials, key=lambda t: t["objective"])


def mean(rows: list[dict], key: str) -> float:
    return float(np.mean([r[key] for r in rows]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--weights", help="detector weights; default = active model (models/model.json) or fallback"
    )
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--no-tune", action="store_true")
    args = ap.parse_args()

    info = load_model_info()
    if args.weights:
        info = ModelInfo(
            name=Path(args.weights).stem, weights=args.weights, classes=["person"], thresholds={}
        )
    cfg_det = DetectionCfg()
    detector = Detector(info, imgsz=args.imgsz, person_model=cfg_det.person_model or None,
                        person_imgsz=cfg_det.person_imgsz)  # fmt: skip
    # Only person boxes matter here, so the cache key is whichever network produced them.
    tag = (
        f"{detector.person_model_name}_{detector.person_imgsz}"
        if detector.person_model
        else f"{Path(str(info.weights)).stem}_{detector.imgsz}"
    )

    cache = {}
    for name in TUNE + REPORT_SEQS:
        seq = MOT / name
        cache[name] = (seq, seq_info(seq), detections(seq, detector, tag), load_gt(seq))
        print("detections ready:", name, flush=True)

    trials: list[dict] = []
    cfg = TrackingConfig()
    if not args.no_tune:
        cfg, trials = tune(cache)
        # Product constraint (unit test "flicker detections never counted"): the steadiness ratio never goes
        # below 0.5, whatever the tuning prefers. Costs ~0.3 points of count error on MOT17 (ADR-0009).
        cfg = replace(cfg, min_hit_ratio=max(cfg.min_hit_ratio, 0.5))
    rows = []
    for name in REPORT_SEQS:
        seq, inf, dets, gt = cache[name]
        naive = naive_1fps(dets, inf["fps"], gt[2])
        bt = evaluate([name], cache, DEFAULT_BYTETRACK)[name]
        bt_tuned = evaluate(
            [name], cache, replace(cfg, min_hits=1, min_age_s=0.0, min_hit_ratio=0.0, reid_window_s=0.0)
        )[name]
        ours = evaluate([name], cache, cfg)[name]
        rows.append({"seq": name, "fps": inf["fps"], "frames": inf["frames"], "naive_1fps": naive,
                     "bytetrack_default": bt, "bytetrack_tuned": bt_tuned, "ours": ours})  # fmt: skip

    result = {"detector": detector.name, "imgsz": detector.person_imgsz if detector.person_model else detector.imgsz, "tuned_config": asdict(cfg),
              "top_trials": trials[:10], "trials": len(trials), "report": rows}  # fmt: skip
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2))
    write_report(result)
    print(REPORT.read_text())


def write_report(r: dict) -> None:
    rows = r["report"]
    variants = [("naive_1fps", "Naive: people per frame, 1 frame/s (v1)"), ("bytetrack_default", "ByteTrack, Ultralytics defaults"),
                ("bytetrack_tuned", "ByteTrack, tuned thresholds"), ("ours", "Ours: tuned + confirmation + merge")]  # fmt: skip
    lines = [
        "# Counting evaluation (MOT17)",
        "",
        "Generated by `backend/eval/counting_eval.py`. Data: the second half of each MOT17 training sequence (boxmot",
        "`MOT17-50` release). Ground truth = distinct pedestrian IDs (class 1, `consider` = 1). Predicted tracks that",
        "spend most of their life on distractors (static people, cyclists, reflections) are not counted.",
        f"Detector: **{r['detector']}** at {r['imgsz']} px. Thresholds tuned on MOT17-02/04 ({r['trials']} trials),",
        "reported on sequences never used for tuning.",
        "",
        "## Unique-person count error (lower is better)",
        "",
        "| sequence | GT people | " + " | ".join(v[1] for v in variants) + " |",
        "|---|---|" + "---|" * len(variants),
    ]
    for row in rows:
        cells = [f"{row[k]['pred_unique']} ({row[k]['count_error']:.0%})" for k, _ in variants]
        lines.append(f"| {row['seq']} | {row['ours']['gt_unique']} | " + " | ".join(cells) + " |")
    lines.append(
        "| **mean error** | | "
        + " | ".join(f"**{mean([x[k] for x in rows], 'count_error'):.1%}**" for k, _ in variants)
        + " |"
    )
    lines += [
        "",
        "## Tracking quality",
        "",
        "| sequence | IDF1 default | IDF1 ours | MOTA default | MOTA ours | ID switches default | ID switches ours |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        d, o = row["bytetrack_default"], row["ours"]
        lines.append(
            f"| {row['seq']} | {d['idf1']:.3f} | {o['idf1']:.3f} | {d['mota']:.3f} | {o['mota']:.3f} | {d['id_switches']} | {o['id_switches']} |"
        )
    lines += [
        "",
        "MOTA is bounded by the detector (missed and false boxes); it is listed to show the tracker does not",
        "trade detections for a better count.",
        "",
        "## Chosen thresholds",
        "",
        "```json",
        json.dumps(
            {
                k: r["tuned_config"][k]
                for k in (
                    "track_high_thresh",
                    "new_track_thresh",
                    "min_hits",
                    "min_age_s",
                    "min_hit_ratio",
                    "track_buffer_s",
                    "reid_window_s",
                )
            },
            indent=2,
        ),
        "```",
        "",
        "Top tuning trials (objective = mean count error + 0.5 × mean (1 − IDF1) on MOT17-02/04):",
        "",
        "| params | objective |",
        "|---|---|",
    ]
    lines += [f"| `{json.dumps(t['params'])}` | {t['objective']} |" for t in r["top_trials"][:5]]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
