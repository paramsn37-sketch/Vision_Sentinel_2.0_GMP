"""Explainability sanity checks (blueprint §7.2) on detections from the frozen test split.

- Pointing game: does the heatmap's maximum fall inside the explained box?
- Deletion check: graying out the hottest 20% of pixels must lower the explained detection's score more than
  graying out a random 20%.
- Model randomisation (Adebayo et al. 2018): maps from a model with re-initialised weights must look different
  (SSIM < 0.5) from the trained model's maps; otherwise the method is just an edge detector.

    uv run python -m eval.xai_eval [--n 300] [--weights path]
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from skimage.metrics import structural_similarity

from app.core.detection.detector import load_model_info
from app.core.geometry import iou
from app.core.xai.cam import YoloCAM, letterbox, overlay

REPO = Path(__file__).resolve().parents[2]
TEST = REPO / "data" / "merged" / "test" / "images"
REPORT = REPO / "docs" / "eval" / "xai_report.md"
RESULTS = REPO / "docs" / "eval" / "xai_results.json"
FIG = REPO / "docs" / "eval" / "figures"


def anchor_score(cam: YoloCAM, img: np.ndarray, box, cls: str) -> float:
    """Best class score among anchors overlapping the box (IoU ≥ 0.5) — the detection's score after an edit."""
    lb = letterbox(img, cam.imgsz)
    with torch.no_grad():
        _, preds = cam.model(lb.tensor)
        branch = cam._branch(preds)
        probs = branch["scores"][0, cam.ids[cls]].sigmoid().cpu().numpy()
        boxes = cam._decoded_boxes(branch, lb)
    ious = np.array([iou(box, tuple(b)) for b in boxes])
    m = ious >= 0.5
    return float(probs[m].max()) if m.any() else 0.0


def gray_out(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = img.copy()
    out[mask] = (114, 114, 114)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--n-deletion", type=int, default=100)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--weights")
    ap.add_argument("--variant", default="hirescam")
    args = ap.parse_args()

    from ultralytics import YOLO

    info = load_model_info()
    weights = args.weights or str(info.weights)
    yolo = YOLO(weights)
    cam = YoloCAM(yolo.model, yolo.names, info.imgsz if not args.weights else 640)
    classes = set(info.classes)
    rng = random.Random(0)
    images = sorted(TEST.glob("*.jpg"))
    rng.shuffle(images)

    # Collect detections to explain, balanced across classes.
    samples: list[tuple[Path, tuple, str, float]] = []
    per_cls: dict[str, int] = defaultdict(int)
    cap = max(10, args.n // max(1, len(classes)))
    for p in images:
        if len(samples) >= args.n:
            break
        r = yolo.predict(str(p), imgsz=cam.imgsz, conf=0.35, verbose=False)[0]
        for b in r.boxes:
            name = r.names[int(b.cls)]
            if name in classes and per_cls[name] < cap:
                samples.append((p, tuple(b.xyxy[0].tolist()), name, float(b.conf)))
                per_cls[name] += 1
                break

    pointing: dict[str, list[bool]] = defaultdict(list)
    energy: dict[str, list[float]] = defaultdict(list)
    eig_point: list[bool] = []
    gc_classic_point: list[bool] = []
    times = []
    deletion = []
    FIG.mkdir(parents=True, exist_ok=True)
    grid = []
    for i, (p, box, cls, conf) in enumerate(samples):
        img = cv2.imread(str(p))
        e = cam.gradcam(img, box, cls, variant=args.variant)
        times.append(e.ms)
        pointing[cls].append(bool(e.peak_in_box))
        energy[cls].append(float(e.energy_in_box or 0))
        if i < 60:
            eig_point.append(bool(cam.eigencam(img, box, cls).peak_in_box))
            gc_classic_point.append(bool(cam.gradcam(img, box, cls, variant="gradcam").peak_in_box))
        if i < args.n_deletion:
            k = int(0.2 * e.heatmap.size)
            top = e.heatmap >= np.partition(e.heatmap.ravel(), -k)[-k]
            rand = np.zeros(e.heatmap.size, bool)
            rand[np.random.default_rng(i).choice(e.heatmap.size, k, replace=False)] = True
            rand = rand.reshape(e.heatmap.shape)
            base = anchor_score(cam, img, box, cls)
            deletion.append({
                "base": base,
                "top": anchor_score(cam, gray_out(img, top), box, cls),
                "random": anchor_score(cam, gray_out(img, rand), box, cls),
            })  # fmt: skip
        if len(grid) < 8:
            x1, y1, x2, y2 = (int(v) for v in box)
            pad = int(0.4 * max(x2 - x1, y2 - y1))
            crop = (slice(max(0, y1 - pad), y2 + pad), slice(max(0, x1 - pad), x2 + pad))
            tile = overlay(img, e.heatmap, box=box)[crop]
            tile = cv2.resize(tile, (200, 200))
            cv2.putText(
                tile,
                f"{cls} {conf:.2f}",
                (6, 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            grid.append(tile)
        print(f"{i + 1}/{len(samples)}", flush=True)
    if grid:
        while len(grid) % 4:
            grid.append(np.zeros_like(grid[0]))
        cv2.imwrite(
            str(FIG / "xai_examples.jpg"),
            np.vstack([np.hstack(grid[r : r + 4]) for r in range(0, len(grid), 4)]),
        )

    # Model randomisation check: re-initialise every conv weight.
    rand_model = copy.deepcopy(yolo.model)
    torch.manual_seed(0)
    for m in rand_model.modules():
        if isinstance(m, torch.nn.Conv2d):
            torch.nn.init.kaiming_normal_(m.weight)
    rcam = YoloCAM(rand_model, yolo.names, cam.imgsz)
    ssims = []
    for p, box, cls, _ in samples[: args.n_random]:
        img = cv2.imread(str(p))
        a = cam.gradcam(img, box, cls, variant=args.variant).heatmap
        b = rcam.gradcam(img, box, cls, variant=args.variant).heatmap
        ssims.append(float(structural_similarity(a, b, data_range=1.0)))

    all_point = [v for vs in pointing.values() for v in vs]
    d = np.array([[x["base"], x["top"], x["random"]] for x in deletion]) if deletion else np.zeros((0, 3))
    result = {
        "model": Path(weights).name,
        "variant": args.variant,
        "samples": len(samples),
        "pointing_game": float(np.mean(all_point)) if all_point else None,
        "pointing_by_class": {c: float(np.mean(v)) for c, v in pointing.items()},
        "energy_in_box_by_class": {c: float(np.mean(v)) for c, v in energy.items()},
        "n_by_class": {c: len(v) for c, v in pointing.items()},
        "pointing_eigencam_first60": float(np.mean(eig_point)) if eig_point else None,
        "pointing_classic_gradcam_first60": float(np.mean(gc_classic_point)) if gc_classic_point else None,
        "deletion": {
            "n": len(deletion),
            "mean_drop_top20": float((d[:, 0] - d[:, 1]).mean()) if len(d) else None,
            "mean_drop_random20": float((d[:, 0] - d[:, 2]).mean()) if len(d) else None,
            "share_top_beats_random": float(((d[:, 0] - d[:, 1]) > (d[:, 0] - d[:, 2])).mean())
            if len(d)
            else None,
        },
        "randomisation": {"n": len(ssims), "mean_ssim": float(np.mean(ssims)) if ssims else None},
        "latency_ms": {"p50": float(np.percentile(times, 50)), "p95": float(np.percentile(times, 95))}
        if times
        else None,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2))
    write_report(result)
    print(REPORT.read_text())


def write_report(r: dict) -> None:
    dl, rnd = r["deletion"], r["randomisation"]
    lines = [
        "# Explainability evaluation",
        "",
        f"Generated by `backend/eval/xai_eval.py`. Model: **{r['model']}**; method: **{r['variant']}** (per-detection,",
        f"see `backend/app/core/xai/cam.py`). {r['samples']} detections from the frozen test split, balanced by class.",
        "Hardware: the build container's CPU (no GPU).",
        "",
        "## Pointing game",
        "",
        f"Share of explanations whose hottest pixel lies inside the explained box: **{r['pointing_game']:.1%}**.",
        "",
        "| class | n | pointing game | heat inside box |",
        "|---|---|---|---|",
    ]
    for c, v in r["pointing_by_class"].items():
        lines.append(f"| {c} | {r['n_by_class'][c]} | {v:.1%} | {r['energy_in_box_by_class'][c]:.1%} |")
    lines += [
        "",
        "Method comparison on the first 60 detections (pointing game):",
        "",
        "| method | pointing game |",
        "|---|---|",
        f"| {r['variant']} (default) | {np.mean(list(r['pointing_by_class'].values())):.1%} (all classes, mean of class rates) |",
        f"| classic Grad-CAM (averaged gradients) | {r['pointing_classic_gradcam_first60']:.1%} |",
        f"| EigenCAM (gradient-free, not detection-specific) | {r['pointing_eigencam_first60']:.1%} |",
        "",
        "## Deletion check",
        "",
        f"Over {dl['n']} detections, graying out the hottest 20% of pixels lowered the detection score by",
        f"**{dl['mean_drop_top20']:.3f}** on average, versus **{dl['mean_drop_random20']:.3f}** for a random 20%.",
        f"The heatmap region mattered more than a random region in **{dl['share_top_beats_random']:.0%}** of cases.",
        "",
        "## Model randomisation check",
        "",
        f"Mean SSIM between maps of the trained model and a model with re-initialised conv weights: **{rnd['mean_ssim']:.3f}**",
        f"over {rnd['n']} detections (below 0.5 means the explanation depends on what the model learned).",
        "",
        "## Latency",
        "",
        f"p50 **{r['latency_ms']['p50']:.0f} ms**, p95 **{r['latency_ms']['p95']:.0f} ms** per explanation on the CPU",
        "(while training was running in parallel). The blueprint's 300 ms target assumes a GPU.",
        "",
        "## Examples",
        "",
        "![examples](figures/xai_examples.jpg)",
    ]
    REPORT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
