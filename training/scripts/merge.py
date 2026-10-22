"""Merge all downloaded sources into one YOLO dataset with the target taxonomy.

Reads data/raw/<source> (YOLO format with the source's own class ids), remaps through class_map.yaml, clips boxes,
drops boxes smaller than 4 px and images left without labels, then writes data/merged/all/{images,labels}.
Splitting happens afterwards in split.py so deduplication can see every image first.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.classmap import load_class_map
from vs_data.paths import MERGED, RAW

MIN_BOX_PX = 4
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def yolo_source(root: Path, names: dict[int, str], glob: str = "images/**/*"):
    """Yield (image_path, [(source_class_name, cx, cy, w, h)]) for a YOLO-format folder."""
    for img in sorted(root.glob(glob)):
        if img.suffix.lower() not in IMAGE_EXTS:
            continue
        lbl = Path(str(img).replace("/images/", "/labels/")).with_suffix(".txt")
        rows = []
        if lbl.exists():
            for line in lbl.read_text().split("\n"):
                parts = line.split()
                if len(parts) == 5:
                    rows.append((names[int(parts[0])], *map(float, parts[1:])))
        yield img, rows


def sources(cm):
    cppe = RAW / "cppe"
    if cppe.exists():
        names = yaml.safe_load((cppe / "data.yaml").read_text())["names"]
        yield "construction_ppe", yolo_source(cppe, names)
    oiv7 = RAW / "oiv7" / "yolo"
    if oiv7.exists():
        yield "openimages_v7", yolo_source(oiv7, dict(enumerate(cm.taxonomy)), "images/*.jpg")


def clip(cx: float, cy: float, w: float, h: float) -> tuple[float, float, float, float]:
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(1.0, cx + w / 2), min(1.0, cy + h / 2)
    return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def main() -> None:
    cm = load_class_map()
    out = MERGED / "all"
    shutil.rmtree(out, ignore_errors=True)
    (out / "images").mkdir(parents=True)
    (out / "labels").mkdir(parents=True)
    stats: dict[str, dict] = {}
    for source, items in sources(cm):
        src_map = cm.sources[source]
        kept_imgs, dropped_imgs, inst = 0, 0, Counter()
        for img_path, rows in items:
            img = cv2.imread(str(img_path))
            if img is None:
                dropped_imgs += 1
                continue
            h_px, w_px = img.shape[:2]
            lines = []
            for name, cx, cy, w, h in rows:
                # Open Images rows were already remapped by its downloader (names are taxonomy names).
                target = name if source == "openimages_v7" else src_map.target(name)
                if target is None:
                    continue
                cx, cy, w, h = clip(cx, cy, w, h)
                if w * w_px < MIN_BOX_PX or h * h_px < MIN_BOX_PX:
                    continue
                lines.append(f"{cm.index(target)} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                inst[target] += 1
            if not lines:
                dropped_imgs += 1
                continue
            stem = f"{source}__{img_path.stem}"
            cv2.imwrite(str(out / "images" / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            (out / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")
            kept_imgs += 1
        stats[source] = {"images": kept_imgs, "dropped_images": dropped_imgs, "instances": dict(inst)}
    (MERGED / "merge_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
