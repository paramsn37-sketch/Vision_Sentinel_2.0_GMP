"""Incident state machine: one incident per condition, reopen within cooldown, evidence (blueprint §5.5)."""

import numpy as np

from app.core.config import IncidentConfig, PPEConfig
from app.core.incidents.manager import IncidentManager
from app.core.ppe.evidence import PersonPPE
from app.core.types import Detection
from app.core.zones.engine import ZoneEngine
from app.core.zones.model import Zone, ZoneRules

from .helpers import frame_result, ps

SQUARE = [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]
IN = (370.0, 300.0, 430.0, 500.0)  # feet at ~(400, 490): inside
OUT = (870.0, 700.0, 930.0, 900.0)
FRAME = np.zeros((1000, 1000, 3), np.uint8)
FIXED_CLOCK = 1_700_000_000.0  # a fixed wall clock so active-hours checks are deterministic


def setup(zone: Zone, **cfg):
    eng = ZoneEngine([zone])
    events = []
    mgr = IncidentManager(
        "cam",
        eng,
        IncidentConfig(**cfg),
        on_event=lambda k, i, f: events.append((k, i.id)),
        clock=lambda: FIXED_CLOCK,
    )
    return eng, mgr, events


def step(eng, mgr, people, ts, ppe=None):
    for p in people:
        p.zones.clear()
    res = frame_result(people, ts)
    eng.update(people, ts, 1000, 1000)
    mgr.update(res, ppe or {}, FRAME)


def run(eng, mgr, box_at, seconds: float, start: float = 0.0, ppe=None, tid: int = 1):
    n = int(seconds * 30)
    for i in range(n):
        ts = start + i / 30
        b = box_at(ts)
        step(eng, mgr, [ps(tid, b)] if b else [], ts, ppe)
    return start + n / 30


def test_standing_in_no_entry_zone_for_60_s_is_one_incident() -> None:
    eng, mgr, events = setup(
        Zone("Substation", SQUARE, id="A", rules=ZoneRules(no_entry=True), severity="high")
    )
    run(eng, mgr, lambda t: IN, 60)
    assert len(mgr.all()) == 1
    inc = mgr.all()[0]
    assert inc.rule == "intrusion" and inc.zone_name == "Substation" and inc.active
    assert inc.duration_s > 59
    assert mgr.alert_level() == "red"
    assert [k for k, _ in events].count("opened") == 1
    assert ("evidence", inc.id) in events


def test_leave_and_return_within_cooldown_reopens_same_incident() -> None:
    eng, mgr, _events = setup(
        Zone("A", SQUARE, id="A", rules=ZoneRules(no_entry=True)), clear_s=3.0, cooldown_s=30.0
    )
    t = run(eng, mgr, lambda t: IN, 5)
    t = run(eng, mgr, lambda t: OUT, 10, t)
    assert not mgr.all()[0].active
    run(eng, mgr, lambda t: IN, 5, t)
    assert len(mgr.all()) == 1
    assert mgr.all()[0].reopen_count == 1 and mgr.all()[0].active


def test_return_after_cooldown_is_a_new_incident() -> None:
    eng, mgr, _ = setup(Zone("A", SQUARE, id="A", rules=ZoneRules(no_entry=True)), cooldown_s=5.0)
    t = run(eng, mgr, lambda t: IN, 3)
    t = run(eng, mgr, lambda t: OUT, 12, t)
    run(eng, mgr, lambda t: IN, 3, t)
    assert len(mgr.all()) == 2


def test_resolved_incident_reopens_as_open() -> None:
    eng, mgr, _ = setup(Zone("A", SQUARE, id="A", rules=ZoneRules(no_entry=True)))
    t = run(eng, mgr, lambda t: IN, 3)
    t = run(eng, mgr, lambda t: OUT, 5, t)
    mgr.set_status(mgr.all()[0].id, "resolved")
    run(eng, mgr, lambda t: IN, 3, t)
    assert mgr.all()[0].status == "open"


def test_ppe_missing_needs_sustained_absence() -> None:
    eng, mgr, _ = setup(Zone("Yard", SQUARE, id="A", rules=ZoneRules(required_ppe=["helmet"])))
    ppe = {1: PersonPPE()}
    cfg = PPEConfig()

    def tick(ts, cls):
        ppe[1].update([Detection(cls, 0.9, IN)], IN, [], 1000, ts, cfg)
        step(eng, mgr, [ps(1, IN)], ts, ppe)

    for i in range(45):  # 1.5 s bare head: not yet a violation
        tick(i / 30, "head")
    assert mgr.all() == []
    for i in range(45, 120):
        tick(i / 30, "head")
    assert [i.rule for i in mgr.all()] == ["ppe_missing:helmet"]
    for i in range(120, 300):  # puts the helmet on
        tick(i / 30, "helmet")
    assert not mgr.all()[0].active


def test_overcrowding() -> None:
    eng, mgr, _ = setup(Zone("Lift", SQUARE, id="A", rules=ZoneRules(max_occupancy=2)))
    boxes = [(330.0 + 30 * k, 300.0, 390.0 + 30 * k, 500.0) for k in range(4)]
    for i in range(30 * 4):
        step(eng, mgr, [ps(k + 1, b) for k, b in enumerate(boxes)], i / 30)
    crowd = [i for i in mgr.all() if i.rule == "overcrowding"]
    assert len(crowd) == 1 and crowd[0].track_id is None


def test_dwell_exceeded() -> None:
    eng, mgr, _ = setup(Zone("Hot work", SQUARE, id="A", rules=ZoneRules(max_dwell_s=5)))
    run(eng, mgr, lambda t: IN, 8)
    assert [i.rule for i in mgr.all()] == ["dwell_exceeded"]


def test_inactive_hours_suppress_rules() -> None:
    eng = ZoneEngine([Zone("A", SQUARE, id="A", rules=ZoneRules(no_entry=True, active_hours="00:00-00:01"))])
    mgr = IncidentManager("cam", eng, clock=lambda: FIXED_CLOCK)
    run(eng, mgr, lambda t: IN, 3)
    assert mgr.all() == []
