"""Write an absolute-path copy of configs/data.yaml for Ultralytics (it resolves `path` against its own cwd)."""

from pathlib import Path

import yaml

from .paths import MERGED, REPO

DATA_YAML = REPO / "training" / "configs" / "data.yaml"


def resolved_data_yaml(out_dir: Path | None = None) -> Path:
    cfg = yaml.safe_load(DATA_YAML.read_text())
    cfg["path"] = str(MERGED.resolve())
    out = (out_dir or MERGED) / "data.resolved.yaml"
    out.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return out
