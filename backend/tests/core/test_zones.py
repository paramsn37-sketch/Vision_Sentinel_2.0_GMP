"""Zone geometry, validation and membership hysteresis (blueprint §6)."""

import time

import cv2
import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import ZoneConfig
from app.core.zones.engine import ZoneEngine
from app.core.zones.model import Zone, ZoneRules, dump_zones_yaml, load_zones_yaml, validate

from .helpers import ps

SQUARE = [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]
CONCAVE = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.5, 0.4], [0.1, 0.9]]  # an arrowhead with a notch


def box_with_foot(x: float, y: float, h: float = 200) -> tuple[float, float, float, float]:
    """A person box (1000×1000 frame) whose foot point sits at (x, y) in pixels."""
    top = y - 0.95 * h
    return (x - 30, top, x + 30, top + h)


@settings(max_examples=300)
@given(st.floats(0, 1), st.floats(0, 1))
def test_point_in_concave_polygon_matches_opencv(x: float, y: float) -> None:
    eng = ZoneEngine([Zone("c", CONCAVE, id="c")])
    pz = eng._zones["c"]
    poly = (np.array(CONCAVE) * 10_000).astype(np.int32)
    d = cv2.pointPolygonTest(poly, (x * 10_000, y * 10_000), True)
    if abs(d) > 2:  # skip points on the boundary, where integer rounding decides
        assert pz.contains(x, y) == (d > 0)


@given(
    st.floats(1, 4000),
    st.floats(1, 4000),
    st.lists(st.tuples(st.floats(0, 1), st.floats(0, 1)), min_size=3, max_size=8),
)
def test_normalised_round_trip(w: float, h: float, pts: list) -> None:
    px = np.array(pts) * [w, h]
    back = px / [w, h]
    assert np.allclose(back, np.array(pts), atol=1e-9)


def test_validation_messages() -> None:
    assert validate(Zone("ok", SQUARE)) == []
    assert any("3 points" in e for e in validate(Zone("x", [[0, 0], [1, 1]])))
    bowtie = [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]
    assert any("crosses itself" in e for e in validate(Zone("x", bowtie)))
    assert any("too small" in e for e in validate(Zone("x", [[0.5, 0.5], [0.51, 0.5], [0.51, 0.51]])))
    assert any("inside the camera frame" in e for e in validate(Zone("x", [[0, 0], [1.2, 0], [1, 1]])))
    assert any("06:00-22:00" in e for e in validate(Zone("x", SQUARE, rules=ZoneRules(active_hours="6am"))))
    assert any(
        "Unknown PPE" in e for e in validate(Zone("x", SQUARE, rules=ZoneRules(required_ppe=["cape"])))
    )


def test_active_hours_wrap_midnight() -> None:
    from datetime import time as t

    r = ZoneRules(active_hours="22:00-06:00")
    assert r.active_at(t(23, 0)) and r.active_at(t(5, 59)) and not r.active_at(t(12, 0))


def test_yaml_round_trip(tmp_path) -> None:
    zones = [Zone("A", SQUARE, kind="restricted", rules=ZoneRules(no_entry=True), severity="high")]
    p = tmp_path / "z.yaml"
    p.write_text(dump_zones_yaml(zones))
    back = load_zones_yaml(p)
    assert back[0].name == "A" and back[0].rules.no_entry and back[0].polygon == SQUARE


def test_entry_needs_consecutive_frames_and_jitter_does_not_flap() -> None:
    eng = ZoneEngine([Zone("A", SQUARE, id="A")], ZoneConfig(enter_frames=3, exit_frames=5))
    events = []
    # standing on the boundary at x = 0.2: alternate in/out every frame for 3 s
    for i in range(90):
        x = 205 if i % 2 == 0 else 195
        events += eng.update([ps(1, box_with_foot(x, 400))], i / 30, 1000, 1000)
    assert events == []
    for i in range(90, 95):
        events += eng.update([ps(1, box_with_foot(400, 400))], i / 30, 1000, 1000)
    assert [e.kind for e in events] == ["entered"]


def test_foot_point_not_centre_decides() -> None:
    """Head inside the zone, feet outside: not inside a floor zone."""
    eng = ZoneEngine([Zone("A", SQUARE, id="A")])
    box = (370.0, 450.0, 430.0, 750.0)  # centre y=600 (edge), feet at ~735 (outside)
    for i in range(10):
        eng.update([ps(1, box)], i / 30, 1000, 1000)
    assert eng.occupancy("A") == 0
    centre = ZoneEngine([Zone("A", SQUARE, id="A")], ZoneConfig(point_mode="center"))
    box2 = (370.0, 400.0, 430.0, 700.0)  # centre y=550, inside
    for i in range(10):
        centre.update([ps(1, box2)], i / 30, 1000, 1000)
    assert centre.occupancy("A") == 1


def test_counts_dwell_and_exit() -> None:
    eng = ZoneEngine([Zone("A", SQUARE, id="A")])
    for i in range(60):
        eng.update([ps(1, box_with_foot(400, 400)), ps(2, box_with_foot(900, 900))], i / 30, 1000, 1000)
    c = eng.counts()["A"]
    assert c.current == 1 and c.unique == 1
    assert 1.8 < eng.dwell("A", 1) < 2.0
    ev = []
    for i in range(60, 70):
        ev += eng.update([ps(1, box_with_foot(900, 900))], i / 30, 1000, 1000)
    assert [e.kind for e in ev] == ["exited"]
    assert eng.counts()["A"].current == 0 and eng.counts()["A"].unique == 1


def test_brief_loss_keeps_membership() -> None:
    eng = ZoneEngine([Zone("A", SQUARE, id="A")])
    ev = []
    for i in range(30):
        ev += eng.update([ps(1, box_with_foot(400, 400))], i / 30, 1000, 1000)
    for i in range(30, 45):  # tracker loses the person for 0.5 s
        ev += eng.update([], i / 30, 1000, 1000)
    for i in range(45, 60):
        ev += eng.update([ps(1, box_with_foot(400, 400))], i / 30, 1000, 1000)
    assert [e.kind for e in ev] == ["entered"]


def test_hot_reload_keeps_state_for_unchanged_zone() -> None:
    a = Zone("A", SQUARE, id="A")
    eng = ZoneEngine([a])
    for i in range(10):
        eng.update([ps(1, box_with_foot(400, 400))], i / 30, 1000, 1000)
    eng.set_zones([a, Zone("B", CONCAVE, id="B")])
    assert eng.occupancy("A") == 1
    eng.set_zones([Zone("A", CONCAVE, id="A")])  # outline changed → state resets
    assert eng.occupancy("A") == 0


def test_performance_10_zones_30_people() -> None:
    rng = np.random.default_rng(0)
    zones = [
        Zone(f"z{i}", (rng.random((6, 2)) * 0.3 + rng.random(2) * 0.6).tolist(), id=f"z{i}")
        for i in range(10)
    ]
    zones = [z for z in zones if not validate(z)] or [Zone("A", SQUARE, id="A")]
    zones = (zones * 10)[:10]
    for i, z in enumerate(zones):
        z.id = f"z{i}"
    eng = ZoneEngine(zones)
    people = [ps(t, box_with_foot(*(rng.random(2) * 1000))) for t in range(30)]
    eng.update(people, 0.0, 1000, 1000)
    n = 200
    t0 = time.perf_counter()
    for k in range(n):
        for p in people:
            p.zones.clear()
        eng.update(people, k / 30, 1000, 1000)
    mean_ms = (time.perf_counter() - t0) / n * 1000
    assert mean_ms < 1.0, f"{mean_ms:.3f} ms per frame"
