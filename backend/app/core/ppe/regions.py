"""Body regions of a person box (blueprint §5.4). Fractions are of the box height, from the top."""

from __future__ import annotations

from ..types import Box

HEAD = (0.0, 0.25)
TORSO = (0.2, 0.62)
FEET = (0.8, 1.0)

# Which region each item / bare-part class must fall into to belong to a person.
REGION_OF_CLASS: dict[str, str] = {
    "helmet": "head",
    "head": "head",
    "goggles": "head",
    "no_goggles": "head",
    "vest": "torso",
    "gloves": "body",
    "hand": "body",
    "boots": "feet",
}


def region(box: Box, name: str) -> Box:
    x1, y1, x2, y2 = box
    h = y2 - y1
    if name == "body":
        # hands reach a little outside the visible torso; widen by 15% each side
        w = x2 - x1
        return (x1 - 0.15 * w, y1, x2 + 0.15 * w, y2)
    top, bottom = {"head": HEAD, "torso": TORSO, "feet": FEET}[name]
    pad = 0.1 * (x2 - x1) if name == "head" else 0.0
    # Hard hats stick out above the box top when the person box is tight to the face.
    lift = 0.08 * h if name == "head" else 0.0
    return (x1 - pad, y1 + top * h - lift, x2 + pad, y1 + bottom * h)
