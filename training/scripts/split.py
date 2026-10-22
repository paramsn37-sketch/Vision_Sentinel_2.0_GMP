"""Deduplicate (perceptual hash) and split the merged dataset 70/15/15 without leakage.

Near-duplicates (pHash Hamming distance <= 6) are clustered; a cluster keeps one image and never spans splits.
Splitting is stratified by source and by whether an image contains a rare class, so every split sees them.
Writes data/merged/{train,val,test}/{images,labels} (symlinks), data/manifests/*.txt and a test-set checksum.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.classmap import load_class_map  # noqa: E402
from vs_data.paths import MANIFESTS, MERGED  # noqa: E402

HAMMING_MAX = 6
RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
RARE = {"goggles", "no_goggles", "boots", "gloves", "hand", "vest"}


def phash_all(images: list[Path]) -> dict[Path, imagehash.ImageHash]:
    return {p: imagehash.phash(Image.open(p).convert("L")) for p in images}


def dedup(hashes: dict[Path, imagehash.ImageHash]) -> tuple[list[Path], int]:
    """Greedy clustering on a 16-bit prefix bucket, then exact Hamming check. Returns kept images."""
    buckets: dict[int, list[tuple[Path, imagehash.ImageHash]]] = defaultdict(list)
    kept: list[Path] = []
    removed = 0
    for path, h in sorted(hashes.items()):
        bits = int(str(h), 16)
        keys = {(bits >> s) & 0xFFFF for s in (0, 16, 32, 48)}
        if any(h - other <= HAMMING_MAX for k in keys for _, other in buckets[k]):
            removed += 1
            continue
        for k in keys:
            buckets[k].append((path, h))
        kept.append(path)
    return kept, removed


def main() -> None:
    cm = load_class_map()
    rare_ids = {cm.index(c) for c in RARE}
    all_dir = MERGED / "all"
    images = sorted((all_dir / "images").glob("*.jpg"))
    kept, removed = dedup(phash_all(images))

    strata: dict[tuple[str, bool], list[Path]] = defaultdict(list)
    for img in kept:
        source = img.stem.split("__")[0]
        cls_ids = {int(line.split()[0]) for line in (all_dir / "labels" / f"{img.stem}.txt").read_text().split("\n") if line}
        strata[(source, bool(cls_ids & rare_ids))].append(img)

    rng = np.random.default_rng(42)
    split_of: dict[str, list[Path]] = {k: [] for k in RATIOS}
    for key in sorted(strata):
        group = strata[key]
        rng.shuffle(group)
        n_train, n_val = int(len(group) * RATIOS["train"]), int(len(group) * RATIOS["val"])
        split_of["train"] += group[:n_train]
        split_of["val"] += group[n_train : n_train + n_val]
        split_of["test"] += group[n_train + n_val :]

    MANIFESTS.mkdir(parents=True, exist_ok=True)
    summary = {"deduplicated_away": removed, "splits": {}}
    for split, imgs in split_of.items():
        for sub in ("images", "labels"):
            d = MERGED / split / sub
            d.mkdir(parents=True, exist_ok=True)
            for f in d.iterdir():
                f.unlink()
        for img in sorted(imgs):
            os.symlink(img, MERGED / split / "images" / img.name)
            os.symlink(all_dir / "labels" / f"{img.stem}.txt", MERGED / split / "labels" / f"{img.stem}.txt")
        names = sorted(p.name for p in imgs)
        (MANIFESTS / f"{split}.txt").write_text("\n".join(names) + "\n")
        summary["splits"][split] = len(names)
    digest = hashlib.sha256((MANIFESTS / "test.txt").read_bytes()).hexdigest()
    (MANIFESTS / "test_manifest.sha256").write_text(f"{digest}  test.txt\n")
    (MERGED / "split_stats.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
