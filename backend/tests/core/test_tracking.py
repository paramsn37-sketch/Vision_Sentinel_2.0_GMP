"""Synthetic trajectories for the tracker, confirmation and lost-track merge (blueprint §5.2–5.3)."""

import numpy as np

from app.core.config import TrackingConfig
from app.core.tracking.tracker import PersonTracker

from .conftest import paint, person

FPS = 30.0


def run(frames: list[list], cfg: TrackingConfig | None = None, frame=None, colors=None) -> PersonTracker:
    tr = PersonTracker(cfg or TrackingConfig(), fps=FPS)
    for i, dets in enumerate(frames):
        img = frame.copy() if frame is not None else np.full((720, 1280, 3), 90, np.uint8)
        for j, d in enumerate(dets):
            if colors:
                paint(img, d, colors[j % len(colors)])
        tr.update(dets, img, i / FPS)
    return tr


def test_one_person_walking_counts_once() -> None:
    frames = [[person(100 + 4 * i, 300)] for i in range(90)]
    tr = run(frames)
    assert tr.unique_confirmed == 1


def test_not_counted_per_frame_or_per_second() -> None:
    """The v1 bug: 3 people visible for 10 s must be 3, not 30 or 900."""
    frames = [[person(100 + i, 100), person(500, 300 + i // 3), person(900 - i, 200)] for i in range(300)]
    assert run(frames).unique_confirmed == 3


def test_flicker_detections_never_counted() -> None:
    frames = [[person(100 + 3 * i, 300)] for i in range(60)]
    for i in range(0, 60, 10):  # a spurious box for 2 frames every third of a second
        frames[i].append(person(1000, 50, conf=0.95))
        frames[i + 1].append(person(1000, 50, conf=0.95))
    assert run(frames).unique_confirmed == 1


def test_short_occlusion_keeps_identity() -> None:
    frames = [[person(100 + 4 * i, 300)] for i in range(45)]
    frames += [[] for _ in range(20)]  # 0.66 s gone
    frames += [[person(100 + 4 * (i + 65), 300)] for i in range(45)]
    assert run(frames).unique_confirmed == 1


def test_two_people_crossing_stay_two() -> None:
    frames = [[person(100 + 8 * i, 300), person(900 - 8 * i, 310)] for i in range(100)]
    assert run(frames, colors=[(0, 0, 220), (220, 0, 0)]).unique_confirmed == 2


def test_merge_rejoins_jump_after_gap() -> None:
    """Reappearing 0.8 s later a bit off the predicted path: ByteTrack gives a new id, the merge restores it."""
    frames = [[person(300, 300)] for _ in range(40)]
    frames += [[] for _ in range(24)]
    frames += [[person(330, 300)] for _ in range(40)]
    cfg = TrackingConfig(track_buffer_s=0.3, reid_window_s=2.0)  # drop the track during the gap; merge on
    merged = run(frames, cfg, colors=[(30, 160, 30)])
    unmerged = run(frames, TrackingConfig(track_buffer_s=0.3, reid_window_s=0.0), colors=[(30, 160, 30)])
    assert unmerged.unique_confirmed == 2
    assert merged.unique_confirmed == 1


def test_merge_rejects_different_clothes() -> None:
    frames = [[person(300, 300)] for _ in range(40)] + [[] for _ in range(24)]
    tr = PersonTracker(TrackingConfig(track_buffer_s=0.3, reid_window_s=2.0), fps=FPS)
    for i, dets in enumerate(frames):
        img = np.full((720, 1280, 3), 90, np.uint8)
        for d in dets:
            paint(img, d, (30, 160, 30))
        tr.update(dets, img, i / FPS)
    for k in range(40):
        img = np.full((720, 1280, 3), 90, np.uint8)
        d = person(330, 300)
        paint(img, d, (200, 40, 200))  # someone else, different colour
        tr.update([d], img, (64 + k) / FPS)
    assert tr.unique_confirmed == 2


def test_leaving_and_returning_much_later_is_a_new_person() -> None:
    """Without re-identification a return after 10 s counts again; this is documented behaviour."""
    frames = (
        [[person(300, 300)] for _ in range(30)]
        + [[] for _ in range(300)]
        + [[person(300, 300)] for _ in range(30)]
    )
    assert run(frames).unique_confirmed == 2


def test_empty_frames() -> None:
    assert run([[] for _ in range(10)]).unique_confirmed == 0
