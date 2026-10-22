"""Filesystem layout for datasets. Override the root with VS_DATA_ROOT (e.g. a bigger disk)."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("VS_DATA_ROOT", REPO / "data"))
RAW = DATA / "raw"
MERGED = DATA / "merged"
MANIFESTS = REPO / "data" / "manifests"
FIGURES = REPO / "data" / "figures"
