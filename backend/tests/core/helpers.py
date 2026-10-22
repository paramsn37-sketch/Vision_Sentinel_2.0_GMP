from app.core.geometry import foot_point
from app.core.types import Counts, FrameResult, PersonState


def ps(tid: int, box: tuple[float, float, float, float], ts: float = 0.0) -> PersonState:
    return PersonState(tid, box, 0.9, foot_point(box), 0.0, ts, 10, True)


def frame_result(persons: list[PersonState], ts: float, w: int = 1000, h: int = 1000) -> FrameResult:
    return FrameResult("cam", int(ts * 30), ts, w, h, persons, [], Counts())
