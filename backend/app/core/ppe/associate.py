"""Assign PPE and bare-body-part detections to tracked people (blueprint §5.4, step 2)."""

from __future__ import annotations

from ..geometry import ioa
from ..types import Box, Detection
from .regions import REGION_OF_CLASS, region


def associate(
    persons: list[tuple[int, Box]], items: list[Detection], ioa_min: float = 0.5
) -> tuple[dict[int, list[Detection]], list[Detection]]:
    """Greedy one-to-one assignment by IoA(item, body region) × confidence.

    Returns (items per person id, unassigned items). An item goes to at most one person, the best-scoring one;
    ties between overlapping people are broken by the higher overlap.
    """
    candidates: list[tuple[float, int, int]] = []
    for ii, item in enumerate(items):
        reg_name = REGION_OF_CLASS.get(item.cls)
        if reg_name is None:
            continue
        for pid, pbox in persons:
            overlap = ioa(item.xyxy, region(pbox, reg_name))
            if overlap >= ioa_min:
                candidates.append((overlap * item.conf, ii, pid))
    candidates.sort(reverse=True)
    taken: set[int] = set()
    out: dict[int, list[Detection]] = {pid: [] for pid, _ in persons}
    for _, ii, pid in candidates:
        if ii in taken:
            continue
        taken.add(ii)
        out[pid].append(items[ii])
    loose = [it for i, it in enumerate(items) if i not in taken]
    return out, loose
