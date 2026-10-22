"""PPE association, observations and the evidence filter (blueprint §5.4)."""

from hypothesis import given
from hypothesis import strategies as st

from app.core.config import PPEConfig
from app.core.ppe.associate import associate
from app.core.ppe.evidence import ItemFilter, PersonPPE, observe
from app.core.ppe.regions import region
from app.core.types import Detection, PPEStatus

CFG = PPEConfig()
P1 = (100.0, 100.0, 180.0, 340.0)  # 80 x 240 person
P2 = (160.0, 110.0, 240.0, 350.0)  # overlapping neighbour


def det(cls: str, box, conf: float = 0.8) -> Detection:
    return Detection(cls, conf, box)


def test_helmet_goes_to_the_right_person() -> None:
    helmet = det("helmet", (175.0, 100.0, 225.0, 140.0))  # above P2's head, also touching P1's region
    out, loose = associate([(1, P1), (2, P2)], [helmet])
    assert out[2] == [helmet] and out[1] == [] and loose == []


def test_item_far_away_stays_loose() -> None:
    out, loose = associate([(1, P1)], [det("vest", (600.0, 600.0, 640.0, 650.0))])
    assert out[1] == [] and len(loose) == 1


def test_vest_must_be_on_torso() -> None:
    feet_vest = det("vest", (110.0, 300.0, 170.0, 340.0))
    torso_vest = det("vest", (105.0, 160.0, 175.0, 240.0))
    out, _ = associate([(1, P1)], [feet_vest, torso_vest])
    assert out[1] == [torso_vest]


def test_observations() -> None:
    assert observe("helmet", [det("helmet", P1)], P1, [], 720, CFG) is PPEStatus.PRESENT
    assert observe("helmet", [det("head", P1)], P1, [], 720, CFG) is PPEStatus.ABSENT
    assert observe("helmet", [], P1, [], 720, CFG) is PPEStatus.UNKNOWN
    assert observe("gloves", [det("hand", P1)], P1, [], 720, CFG) is PPEStatus.ABSENT
    assert observe("boots", [], P1, [], 720, CFG) is PPEStatus.UNKNOWN


def test_vest_absence_needs_a_clear_full_view() -> None:
    assert observe("vest", [], P1, [], 720, CFG) is PPEStatus.ABSENT
    assert observe("vest", [], P1, [P2], 720, CFG) is PPEStatus.ABSENT  # P2 covers < 40% of the torso
    blocker = (90.0, 150.0, 200.0, 260.0)
    assert observe("vest", [], P1, [blocker], 720, CFG) is PPEStatus.UNKNOWN
    tiny = (10.0, 10.0, 20.0, 50.0)
    assert observe("vest", [], tiny, [], 720, CFG) is PPEStatus.UNKNOWN
    squat = (100.0, 100.0, 300.0, 300.0)  # aspect 1.0: probably only the upper body is visible
    assert observe("vest", [], squat, [], 720, CFG) is PPEStatus.UNKNOWN


def test_filter_needs_sustained_evidence() -> None:
    f = ItemFilter()
    t = 0.0
    for _ in range(30):  # present for 1 s
        f.update(PPEStatus.PRESENT, t, CFG)
        t += 1 / 30
    assert f.state is PPEStatus.PRESENT
    f.update(PPEStatus.ABSENT, t, CFG)  # one bad frame
    assert f.state is PPEStatus.PRESENT
    for _ in range(60):
        t += 1 / 30
        f.update(PPEStatus.ABSENT, t, CFG)
    assert f.state is PPEStatus.ABSENT
    assert 1.0 < f.absent_for(t) < 2.0


def test_unknown_does_not_change_state() -> None:
    f = ItemFilter()
    for i in range(30):
        f.update(PPEStatus.ABSENT, i / 30, CFG)
    for i in range(30, 300):
        f.update(PPEStatus.UNKNOWN, i / 30, CFG)
    assert f.state is PPEStatus.ABSENT


@given(st.lists(st.booleans(), min_size=10, max_size=200))
def test_alternating_noise_never_flips_faster_than_hysteresis(obs: list[bool]) -> None:
    """Between two state flips the score must cross the whole hysteresis band, so flips are rare."""
    f = ItemFilter()
    flips, last = 0, f.state
    for i, o in enumerate(obs):
        f.update(PPEStatus.PRESENT if o else PPEStatus.ABSENT, i / 30, CFG)
        if f.state is not last and last is not PPEStatus.UNKNOWN:
            flips += 1
        last = f.state
    assert 0.0 <= f.score <= 1.0
    strict_alternation = [i % 2 == 0 for i in range(len(obs))]
    if obs == strict_alternation:
        assert flips == 0


@given(
    st.floats(0, 1000), st.floats(0, 1000), st.floats(10, 400), st.floats(10, 800),
    st.sampled_from(["head", "torso", "feet", "body"]),
)  # fmt: skip
def test_regions_are_well_formed(x: float, y: float, w: float, h: float, name: str) -> None:
    box = (x, y, x + w, y + h)
    r = region(box, name)
    assert r[0] < r[2] and r[1] < r[3]
    assert r[1] >= y - 0.08 * h - 1e-6 and r[3] <= y + h + 1e-6


def test_person_ppe_tracks_all_items() -> None:
    p = PersonPPE()
    for i in range(40):
        p.update([det("helmet", P1), det("vest", P1)], P1, [], 720, i / 30, CFG)
    s = p.states()
    assert s["helmet"] is PPEStatus.PRESENT and s["vest"] is PPEStatus.PRESENT
    assert s["boots"] is PPEStatus.UNKNOWN


def test_person_only_model_never_reports_missing_ppe() -> None:
    from app.core.ppe.evidence import checkable_items
    from app.core.types import PPE_ITEMS

    assert checkable_items(["person"]) == ()
    assert set(
        checkable_items(
            ["person", "head", "helmet", "vest", "gloves", "hand", "boots", "goggles", "no_goggles"]
        )
    ) == set(PPE_ITEMS)
    p = PersonPPE.for_items(())
    p.update([], (100, 100, 200, 400), [], 720, 0.0, PPEConfig())
    assert p.states() == {}
    assert p.missing_for("vest", 10.0) == 0.0
