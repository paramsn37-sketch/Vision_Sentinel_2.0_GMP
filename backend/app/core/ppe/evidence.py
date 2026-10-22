"""Per-person PPE state with temporal smoothing and hysteresis (blueprint §5.4, steps 3–5).

Each frame yields an *observation* per item: present, absent or unknown. An exponential filter accumulates
present (1) / absent (0) observations with a time constant; unknown leaves the score untouched. The state flips to
absent only below `absent_below` and back to present only above `present_above`, so flicker cannot toggle it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config import PPEConfig
from ..geometry import ioa
from ..types import PPE_ITEMS, Box, Detection, PPEStatus
from .regions import region

# item -> (class proving presence, class proving absence or None)
EVIDENCE: dict[str, tuple[str, str | None]] = {
    "helmet": ("helmet", "head"),
    "vest": ("vest", None),
    "gloves": ("gloves", "hand"),
    "boots": ("boots", None),
    "goggles": ("goggles", "no_goggles"),
}


def observe(
    item: str,
    assigned: list[Detection],
    person_box: Box,
    others: list[Box],
    frame_h: int,
    cfg: PPEConfig,
) -> PPEStatus:
    """One-frame observation for one item on one person."""
    x1, y1, x2, y2 = person_box
    h, w = y2 - y1, x2 - x1
    if h < cfg.min_person_height_px:
        return PPEStatus.UNKNOWN
    pos_cls, neg_cls = EVIDENCE[item]
    classes = {d.cls for d in assigned}
    if pos_cls in classes:
        return PPEStatus.PRESENT
    if neg_cls is not None and neg_cls in classes:
        return PPEStatus.ABSENT
    if item in cfg.infer_absence and item == "vest":
        torso = region(person_box, "torso")
        occluded = any(ioa(torso, o) > cfg.occlusion_ioa for o in others)
        truncated = y2 >= frame_h - 2 and h / max(w, 1) < cfg.vest_min_aspect
        big_enough = (torso[3] - torso[1]) >= cfg.vest_min_torso_px
        if big_enough and h / max(w, 1) >= cfg.vest_min_aspect and not occluded and not truncated:
            return PPEStatus.ABSENT
    return PPEStatus.UNKNOWN


@dataclass(slots=True)
class ItemFilter:
    score: float = 0.5
    state: PPEStatus = PPEStatus.UNKNOWN
    last_ts: float | None = None
    absent_since: float | None = None

    def update(self, obs: PPEStatus, ts: float, cfg: PPEConfig) -> None:
        if obs is not PPEStatus.UNKNOWN:
            dt = 0.0 if self.last_ts is None else max(0.0, ts - self.last_ts)
            if self.last_ts is None:
                # first real observation starts the score halfway towards it
                self.score = 0.75 if obs is PPEStatus.PRESENT else 0.25
            else:
                lam = math.exp(-dt / cfg.evidence_tau_s) if dt > 0 else 0.85
                target = 1.0 if obs is PPEStatus.PRESENT else 0.0
                self.score = lam * self.score + (1 - lam) * target
            self.last_ts = ts
        if self.score <= cfg.absent_below and self.state is not PPEStatus.ABSENT:
            self.state = PPEStatus.ABSENT
            self.absent_since = ts
        elif self.score >= cfg.present_above and self.state is not PPEStatus.PRESENT:
            self.state = PPEStatus.PRESENT
            self.absent_since = None

    def absent_for(self, ts: float) -> float:
        return (
            ts - self.absent_since
            if self.state is PPEStatus.ABSENT and self.absent_since is not None
            else 0.0
        )


@dataclass(slots=True)
class PersonPPE:
    items: dict[str, ItemFilter] = field(default_factory=lambda: {i: ItemFilter() for i in PPE_ITEMS})

    def update(
        self,
        assigned: list[Detection],
        person_box: Box,
        others: list[Box],
        frame_h: int,
        ts: float,
        cfg: PPEConfig,
    ) -> None:
        for name, f in self.items.items():
            f.update(observe(name, assigned, person_box, others, frame_h, cfg), ts, cfg)

    def states(self) -> dict[str, PPEStatus]:
        return {k: f.state for k, f in self.items.items()}

    def scores(self) -> dict[str, float]:
        return {k: round(f.score, 3) for k, f in self.items.items()}

    @classmethod
    def for_items(cls, items: tuple[str, ...] | list[str]) -> PersonPPE:
        return cls(items={i: ItemFilter() for i in items})

    def missing_for(self, item: str, ts: float) -> float:
        # Items the model cannot see are never "missing" (they are not tracked at all).
        f = self.items.get(item)
        return f.absent_for(ts) if f is not None else 0.0


def checkable_items(model_classes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """PPE items the active model can actually observe (its positive class exists). A person-only model checks none."""
    names = set(model_classes)
    return tuple(i for i in PPE_ITEMS if EVIDENCE[i][0] in names)
