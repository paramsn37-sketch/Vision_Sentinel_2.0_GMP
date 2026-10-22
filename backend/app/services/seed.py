"""Demo content for a first run: cameras looping the bundled sample clips, with zones that exercise every rule.
The clips are real footage processed by the real model (see data/samples/LICENSES.md)."""

from __future__ import annotations

from sqlmodel import Session, select

from ..db.models import Camera, ZoneRow
from ..db.session import engine
from ..settings import REPO

SAMPLES = REPO / "data" / "samples"

DEMO = [
    {
        "camera": {
            "id": "street-night",
            "name": "Pedestrian street (night)",
            "file": "pedestrian_street_night.mp4",
            "stride": 3,
            "notes": "Demo: MOT17-04, elevated view. Shows unique counting and intrusion on the vehicle lane.",
        },
        "zones": [
            {
                "name": "Vehicle lane",
                "kind": "restricted",
                "severity": "high",
                "polygon": [[0.43, 0.0], [0.70, 0.0], [0.80, 1.0], [0.44, 1.0]],
                "rules": {"no_entry": True},
            },
            {
                "name": "West walkway",
                "kind": "hazard",
                "severity": "low",
                "polygon": [[0.0, 0.0], [0.33, 0.0], [0.30, 1.0], [0.0, 1.0]],
                "rules": {"max_occupancy": 12},
            },
        ],
    },
    {
        "camera": {
            "id": "town-square",
            "name": "Town square",
            "file": "town_square.mp4",
            "stride": 3,
            "notes": "Demo: MOT17-02, eye-level view. Shows occupancy and dwell rules.",
        },
        "zones": [
            {
                "name": "Square centre",
                "kind": "hazard",
                "severity": "medium",
                "polygon": [[0.22, 0.62], [0.78, 0.60], [0.95, 1.0], [0.10, 1.0]],
                "rules": {"max_occupancy": 3, "max_dwell_s": 20},
            },
        ],
    },
    {
        "camera": {
            "id": "ppe-check",
            "name": "PPE check (still images)",
            "file": "ppe_slideshow.mp4",
            "stride": 2,
            "notes": "Demo: Construction-PPE test images shown for 4 s each. Not continuous video: people "
            "change between images, so counts here are per image.",
        },
        "zones": [
            {
                "name": "Site floor",
                "kind": "ppe_required",
                "severity": "high",
                "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
                "rules": {"required_ppe": ["helmet", "vest"]},
            },
        ],
    },
]


def seed_demo() -> list[str]:
    created = []
    with Session(engine()) as s:
        if s.exec(select(Camera)).first() is not None:
            return created
        for entry in DEMO:
            c = entry["camera"]
            path = SAMPLES / c["file"]
            if not path.exists():
                continue
            s.add(
                Camera(
                    id=c["id"],
                    name=c["name"],
                    uri=str(path),
                    kind="file",
                    loop=True,
                    stride=c["stride"],
                    notes=c["notes"],
                )
            )
            for i, z in enumerate(entry["zones"]):
                s.add(ZoneRow(id=f"z_{c['id']}_{i}", camera_id=c["id"], **z))
            created.append(c["id"])
        s.commit()
    return created
