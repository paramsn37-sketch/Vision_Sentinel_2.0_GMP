"""Worst false positives and false negatives on the test split (Phase 2, task 6).

uv run python ../training/scripts/error_analysis.py --weights ../models/vs2-y26n.pt
Uses the per-class operating thresholds from models/model.json. A prediction is a true positive when it overlaps an
unmatched ground-truth box of the same class with IoU >= 0.5. Writes training/reports/error_analysis/:
fp_grid.jpg (50 most confident false positives), fn_grid.jpg (50 largest missed boxes) and errors.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.paths import MERGED, REPO

OUT = REPO / "training" / "reports" / "error_analysis"
TILE = 160


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def gt_boxes(label: Path, w: int, h: int) -> list[tuple[int, np.ndarray]]:
    out = []
    for line in label.read_text().splitlines() if label.exists() else []:
        c, cx, cy, bw, bh = line.split()[:5]
        cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
        out.append((int(c), np.array([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2])))
    return out


def tile(img: np.ndarray, box: np.ndarray, text: str, color: tuple[int, int, int]) -> np.ndarray:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    pad = 0.25 * max(x2 - x1, y2 - y1)
    xa, ya = int(max(0, x1 - pad)), int(max(0, y1 - pad))
    xb, yb = int(min(w, x2 + pad)), int(min(h, y2 + pad))
    crop = img[ya:yb, xa:xb].copy()
    cv2.rectangle(crop, (int(x1 - xa), int(y1 - ya)), (int(x2 - xa), int(y2 - ya)), color, 2)
    s = TILE / max(crop.shape[:2])
    crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))))
    canvas = np.full((TILE + 18, TILE, 3), 24, np.uint8)
    canvas[: crop.shape[0], : crop.shape[1]] = crop
    cv2.putText(
        canvas, text[:26], (3, TILE + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (235, 235, 235), 1, cv2.LINE_AA
    )
    return canvas


def grid(tiles: list[np.ndarray], cols: int = 10) -> np.ndarray:
    blank = np.full_like(tiles[0], 24) if tiles else np.full((TILE + 18, TILE, 3), 24, np.uint8)
    rows = [
        tiles[i : i + cols] + [blank] * (cols - len(tiles[i : i + cols])) for i in range(0, len(tiles), cols)
    ]
    return np.vstack([np.hstack(r) for r in rows]) if rows else blank


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True, type=Path)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    from ultralytics import YOLO

    meta = json.loads((REPO / "models" / "model.json").read_text())
    names, th, imgsz = meta["classes"], meta["thresholds"], meta["imgsz"]
    model = YOLO(str(args.weights))
    fps, fns = [], []
    images = sorted((MERGED / "test" / "images").glob("*"))
    for p in images:
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        gts = gt_boxes(MERGED / "test" / "labels" / f"{p.stem}.txt", w, h)
        r = model.predict(img, imgsz=imgsz, conf=min(th.values()), verbose=False)[0]
        preds = [
            (int(c), float(s), b.cpu().numpy())
            for c, s, b in zip(r.boxes.cls, r.boxes.conf, r.boxes.xyxy, strict=True)
            if float(s) >= th[names[int(c)]]
        ]
        used = set()
        for c, s, b in sorted(preds, key=lambda t: -t[1]):
            best, bi = 0.0, -1
            for i, (gc, gb) in enumerate(gts):
                if gc == c and i not in used and (v := iou(b, gb)) > best:
                    best, bi = v, i
            if best >= 0.5:
                used.add(bi)
            else:
                fps.append((s, p, names[c], b))
        for i, (gc, gb) in enumerate(gts):
            if i not in used:
                fns.append(((gb[2] - gb[0]) * (gb[3] - gb[1]), p, names[gc], gb))

    OUT.mkdir(parents=True, exist_ok=True)
    fps.sort(key=lambda t: -t[0])
    fns.sort(key=lambda t: -t[0])
    tiles_fp = [
        tile(cv2.imread(str(p)), b, f"FP {c} {s:.2f}", (60, 60, 240)) for s, p, c, b in fps[: args.top]
    ]
    tiles_fn = [tile(cv2.imread(str(p)), b, f"FN {c}", (60, 200, 240)) for _, p, c, b in fns[: args.top]]
    cv2.imwrite(str(OUT / "fp_grid.jpg"), grid(tiles_fp), [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(str(OUT / "fn_grid.jpg"), grid(tiles_fn), [cv2.IMWRITE_JPEG_QUALITY, 85])
    with (OUT / "errors.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["kind", "class", "score_or_area", "image", "x1", "y1", "x2", "y2"])
        for s, p, c, b in fps:
            wr.writerow(["fp", c, round(s, 3), p.name, *np.round(b, 1)])
        for a, p, c, b in fns:
            wr.writerow(["fn", c, round(float(a)), p.name, *np.round(b, 1)])
    by_class: dict[str, list[int]] = {}
    for _, _, c, _ in fps:
        by_class.setdefault(c, [0, 0])[0] += 1
    for _, _, c, _ in fns:
        by_class.setdefault(c, [0, 0])[1] += 1
    summary = {c: {"false_positives": v[0], "false_negatives": v[1]} for c, v in sorted(by_class.items())}
    (OUT / "summary.json").write_text(
        json.dumps({"images": len(images), "per_class": summary}, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
