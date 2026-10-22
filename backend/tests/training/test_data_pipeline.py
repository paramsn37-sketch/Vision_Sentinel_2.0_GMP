"""Class map coverage and split leakage checks (Phase 1 gates)."""

import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "training"))

from vs_data.classmap import load_class_map  # noqa: E402
from vs_data.paths import MANIFESTS, MERGED, RAW  # noqa: E402

CPPE_NAMES = ["helmet", "gloves", "vest", "boots", "goggles", "none", "Person",
              "no_helmet", "no_goggle", "no_gloves", "no_boots"]  # fmt: skip
OIV7_NAMES = ["Person", "Human head", "Glove", "Human hand", "Boot", "Goggles"]


def test_taxonomy_matches_data_yaml() -> None:
    names = yaml.safe_load((REPO / "training" / "configs" / "data.yaml").read_text())["names"]
    assert list(names.values()) == load_class_map().taxonomy


@pytest.mark.parametrize(
    ("source", "classes"), [("construction_ppe", CPPE_NAMES), ("openimages_v7", OIV7_NAMES)]
)
def test_every_source_class_is_mapped_or_dropped(source: str, classes: list[str]) -> None:
    src = load_class_map().sources[source]
    for name in classes:
        target = src.target(name)  # raises on unknown
        assert target is None or target in load_class_map().taxonomy


def test_unknown_class_raises() -> None:
    with pytest.raises(KeyError):
        load_class_map().sources["construction_ppe"].target("hoodie")


def test_negative_labels_map_to_bare_parts() -> None:
    src = load_class_map().sources["construction_ppe"]
    assert src.target("no_helmet") == "head"
    assert src.target("no_gloves") == "hand"
    assert src.target("no_boots") is None


@pytest.mark.skipif(not (MANIFESTS / "test.txt").exists(), reason="dataset not built")
def test_manifests_are_disjoint() -> None:
    splits = {s: set((MANIFESTS / f"{s}.txt").read_text().split()) for s in ("train", "val", "test")}
    assert not splits["train"] & splits["val"]
    assert not splits["train"] & splits["test"]
    assert not splits["val"] & splits["test"]


@pytest.mark.skipif(not (MERGED / "test" / "images").exists(), reason="dataset not built")
def test_no_near_duplicates_across_splits() -> None:
    imagehash = pytest.importorskip("imagehash")
    from PIL import Image

    def hashes(split: str) -> list:
        return [
            imagehash.phash(Image.open(p).convert("L"))
            for p in sorted((MERGED / split / "images").glob("*.jpg"))
        ]

    test = hashes("test")
    for other in ("train", "val"):
        for h in hashes(other):
            assert min(h - t for t in test) > 6


def test_raw_sources_documented() -> None:
    if (RAW / "oiv7").exists():
        assert (RAW / "oiv7" / "SOURCE.json").exists()
