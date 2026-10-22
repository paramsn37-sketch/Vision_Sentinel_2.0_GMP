"""Fetch Ultralytics Construction-PPE (AGPL-3.0, ~180 MB) into data/raw/cppe in YOLO format.

uv run python ../training/scripts/download_construction_ppe.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vs_data.paths import RAW

URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip"
NAMES = ["helmet", "gloves", "vest", "boots", "goggles", "none", "Person", "no_helmet", "no_goggle", "no_gloves",
         "no_boots"]  # fmt: skip


def main() -> None:
    dst = RAW / "cppe"
    if (dst / "images").exists():
        print(f"already present: {dst}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "cppe.zip"
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, z)
        with zipfile.ZipFile(z) as f:
            f.extractall(tmp)
        root = next(p.parent for p in Path(tmp).rglob("images") if (p.parent / "labels").exists())
        dst.mkdir(parents=True, exist_ok=True)
        for part in ("images", "labels"):
            shutil.move(str(root / part), dst / part)
        for extra in ("LICENSE", "data.yaml"):
            if (root / extra).exists():
                shutil.copy2(root / extra, dst / extra)
    if not (dst / "data.yaml").exists():
        (dst / "data.yaml").write_text("names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(NAMES)))
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
