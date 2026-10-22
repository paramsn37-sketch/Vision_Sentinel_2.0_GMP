"""Training run registry (training/registry.json): one entry per run, updated at start and end."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from typing import Any

from .paths import MANIFESTS, REPO

REGISTRY = REPO / "training" / "registry.json"


def _git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO)
    return out.stdout.strip() or "unknown"


def manifest_hash() -> str:
    h = hashlib.sha256()
    for split in ("train", "val", "test"):
        p = MANIFESTS / f"{split}.txt"
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def environment() -> dict[str, Any]:
    import torch
    import ultralytics

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "device": "cuda:" + torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "cpu": platform.processor() or platform.machine(),
    }


def load() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"runs": []}


def upsert(run_id: str, **fields: Any) -> dict[str, Any]:
    reg = load()
    entry = next((r for r in reg["runs"] if r["id"] == run_id), None)
    if entry is None:
        entry = {
            "id": run_id,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "data_manifest": manifest_hash(),
            "env": environment(),
        }
        reg["runs"].append(entry)
    entry.update(fields)
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n")
    return entry
