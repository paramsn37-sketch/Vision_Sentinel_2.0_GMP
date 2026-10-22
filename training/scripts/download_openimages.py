"""Download a capped, PPE-relevant subset of Open Images V7 in YOLO format.

Selection (see training/configs/class_map.yaml and docs/DECISIONS.md ADR-0006):
- an image qualifies when it has at least one non-group, non-depiction `Person` box and one `Human head` box
  (so heads are labelled wherever people are), or a `Glove` / `Goggles` / `Boot` box next to a `Person`;
- images labelled with any helmet class are excluded;
- caps keep the CPU training budget realistic.

Output: data/raw/oiv7/yolo/{images,labels}/<split>_<id>.jpg|txt and SOURCE.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.classmap import load_class_map
from vs_data.paths import RAW

META = RAW / "oiv7" / "meta"
OUT = RAW / "oiv7" / "yolo"
CSVS = {
    "train": META / "oidv6-train-annotations-bbox.csv",
    "validation": META / "validation-annotations-bbox.csv",
    "test": META / "test-annotations-bbox.csv",
}
IMG_URL = "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"
MAX_SIDE = 960


def label_ids() -> dict[str, str]:
    df = pd.read_csv(META / "oidv7-class-descriptions-boxable.csv", header=None, names=["mid", "name"])
    return dict(zip(df["name"], df["mid"], strict=True))


def load_boxes(split: str, mids: set[str]) -> pd.DataFrame:
    cols = ["ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax", "IsGroupOf", "IsDepiction", "IsOccluded"]
    chunks = []
    for chunk in pd.read_csv(CSVS[split], usecols=cols, chunksize=2_000_000):
        chunks.append(chunk[chunk["LabelName"].isin(mids)])
    df = pd.concat(chunks)
    df["split"] = split
    return df


def select_images(df: pd.DataFrame, names: dict[str, str], caps: dict[str, int], seed: int) -> list[str]:
    by_mid = {v: k for k, v in names.items()}
    df = df.assign(cls=df["LabelName"].map(by_mid))
    excluded = set(df[df["cls"].isin({"Helmet", "Bicycle helmet", "Football helmet"})]["ImageID"])
    bad = set(df[(df["IsDepiction"] == 1) | ((df["cls"] == "Person") & (df["IsGroupOf"] == 1))]["ImageID"])
    usable = df[~df["ImageID"].isin(excluded | bad)]
    present = usable.groupby("ImageID")["cls"].agg(set)
    rng = np.random.default_rng(seed)
    chosen: list[str] = []
    taken: set[str] = set()

    def take(pool: list[str], cap: int) -> None:
        pool = [i for i in pool if i not in taken]
        rng.shuffle(pool)
        for image_id in pool[:cap]:
            taken.add(image_id)
            chosen.append(image_id)

    # Rare PPE first so caps on people do not crowd them out.
    for cls in ("Goggles", "Glove", "Boot"):
        take([i for i, s in present.items() if cls in s and "Person" in s], caps[cls])
    take([i for i, s in present.items() if {"Person", "Human head"} <= s], caps["Person"])
    return chosen


def fetch(image_id: str, split: str, session: requests.Session) -> tuple[int, int] | None:
    dst = OUT / "images" / f"{split}_{image_id}.jpg"
    if dst.exists():
        img = cv2.imread(str(dst))
        return (img.shape[1], img.shape[0]) if img is not None else None
    try:
        r = session.get(IMG_URL.format(split=split, image_id=image_id), timeout=30)
        r.raise_for_status()
    except requests.RequestException:
        return None
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    scale = MAX_SIDE / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return img.shape[1], img.shape[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--person-cap", type=int, default=1800)
    ap.add_argument("--ppe-cap", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=24)
    args = ap.parse_args()

    cm = load_class_map()
    src = cm.sources["openimages_v7"]
    names = label_ids()
    wanted = set(src.mapping) | set(src.exclude_images_with)
    mids = {names[n] for n in wanted}
    df = pd.concat([load_boxes(s, mids) for s in CSVS])
    caps = {"Person": args.person_cap, "Glove": args.ppe_cap, "Goggles": args.ppe_cap, "Boot": args.ppe_cap}
    chosen = set(select_images(df, names, caps, args.seed))
    df = df[df["ImageID"].isin(chosen)]
    by_mid = {v: k for k, v in names.items()}

    (OUT / "images").mkdir(parents=True, exist_ok=True)
    (OUT / "labels").mkdir(parents=True, exist_ok=True)
    split_of = df.groupby("ImageID")["split"].first().to_dict()
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_maxsize=args.workers)
    session.mount("https://", adapter)
    with ThreadPoolExecutor(args.workers) as ex:
        sizes = dict(zip(chosen, ex.map(lambda i: fetch(i, split_of[i], session), chosen), strict=True))

    counts: dict[str, int] = defaultdict(int)
    written = 0
    for image_id, boxes in df.groupby("ImageID"):
        if sizes.get(image_id) is None:
            continue
        lines = []
        for b in boxes.itertuples():
            target = src.target(by_mid[b.LabelName])
            if target is None or b.IsGroupOf == 1:
                continue
            cx, cy = (b.XMin + b.XMax) / 2, (b.YMin + b.YMax) / 2
            w, h = b.XMax - b.XMin, b.YMax - b.YMin
            lines.append(f"{cm.index(target)} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            counts[target] += 1
        stem = f"{split_of[image_id]}_{image_id}"
        (OUT / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n")
        written += 1

    meta = {
        "source": "Open Images V7 (boxes from v5/v6 CSVs, images from the public S3 mirror)",
        "url": "https://storage.googleapis.com/openimages/web/index.html",
        "licence": "Annotations CC BY 4.0; images listed as CC BY 2.0 by Open Images",
        "downloaded_at": datetime.now(UTC).isoformat(),
        "selection": vars(args),
        "images": written,
        "instances": dict(counts),
        "failed_downloads": sum(1 for v in sizes.values() if v is None),
    }
    (RAW / "oiv7" / "SOURCE.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
