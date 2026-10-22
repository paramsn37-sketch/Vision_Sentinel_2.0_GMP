"""Load and apply the class map in `training/configs/class_map.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CLASS_MAP_PATH = Path(__file__).resolve().parents[1] / "configs" / "class_map.yaml"


@dataclass(frozen=True)
class SourceMap:
    name: str
    mapping: dict[str, str]
    drop: frozenset[str]
    exclude_images_with: frozenset[str]

    def target(self, source_class: str) -> str | None:
        """Target class name, or None when the class is dropped. Unknown classes raise."""
        if source_class in self.mapping:
            return self.mapping[source_class]
        if source_class in self.drop:
            return None
        raise KeyError(f"{self.name}: class {source_class!r} is neither mapped nor dropped")


@dataclass(frozen=True)
class ClassMap:
    taxonomy: list[str]
    sources: dict[str, SourceMap]

    def index(self, name: str) -> int:
        return self.taxonomy.index(name)


def load_class_map(path: Path = CLASS_MAP_PATH) -> ClassMap:
    raw = yaml.safe_load(path.read_text())
    sources = {
        name: SourceMap(
            name=name,
            mapping=dict(cfg.get("map", {})),
            drop=frozenset(cfg.get("drop", [])),
            exclude_images_with=frozenset(cfg.get("exclude_images_with", [])),
        )
        for name, cfg in raw["sources"].items()
    }
    cm = ClassMap(taxonomy=list(raw["taxonomy"]), sources=sources)
    for src in sources.values():
        unknown = set(src.mapping.values()) - set(cm.taxonomy)
        if unknown:
            raise ValueError(f"{src.name} maps to classes outside the taxonomy: {sorted(unknown)}")
    return cm
