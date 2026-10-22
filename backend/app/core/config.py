"""Tunable thresholds for the vision core. Defaults follow the blueprint (§5, §6); evals tune them (ADR-0009)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TrackingConfig:
    # Defaults tuned on MOT17-02/04 (docs/eval/counting_report.md, ADR-0009).
    track_high_thresh: float = 0.2
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.25
    match_thresh: float = 0.8
    track_buffer_s: float = 1.5
    # A track counts as a person only after this many hits *and* this much time (kills flicker IDs).
    min_hits: int = 2
    min_age_s: float = 0.2
    # ...and only if it was actually detected in at least this share of the frames since it first appeared,
    # so a false positive that recurs at one spot (a jacket on a hook) never becomes a person.
    min_hit_ratio: float = 0.5
    # Lost-track merge: a new tracker ID that appears near a recently lost confirmed track, with a similar size
    # and torso colour, inherits the old ID instead of becoming a new person.
    reid_window_s: float = 0.0  # merge off by default: it undercounted on MOT17 (ADR-0009)
    reid_max_center_dist: float = 0.75  # in units of the lost track's box height
    reid_size_ratio: tuple[float, float] = (0.6, 1.6)
    reid_max_hist_dist: float = 0.35  # Bhattacharyya distance of HSV torso histograms


@dataclass(slots=True)
class PPEConfig:
    ioa_min: float = 0.5
    evidence_tau_s: float = 0.6  # time constant of the exponential evidence filter
    absent_below: float = 0.3
    present_above: float = 0.7
    violation_min_s: float = 2.0
    min_person_height_px: float = 60.0  # below this every item is unknown
    vest_min_torso_px: float = 48.0
    vest_min_aspect: float = 1.6  # h / w; a roughly full-body box is needed to call a vest absent
    occlusion_ioa: float = 0.4
    # Items whose absence may be inferred without a bare-part detection (only the vest by default).
    infer_absence: tuple[str, ...] = ("vest",)


@dataclass(slots=True)
class ZoneConfig:
    enter_frames: int = 3
    exit_frames: int = 5
    foot_raise: float = 0.05  # foot point = bottom-centre raised by this fraction of box height
    point_mode: str = "foot"  # "foot" or "center" (top-down cameras)
    lost_grace_s: float = 1.0  # a lost track keeps its zone membership this long


@dataclass(slots=True)
class IncidentConfig:
    clear_s: float = 3.0
    cooldown_s: float = 30.0
    overcrowding_min_s: float = 2.0
    evidence_window_s: float = 1.0


@dataclass(slots=True)
class CoreConfig:
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    ppe: PPEConfig = field(default_factory=PPEConfig)
    zones: ZoneConfig = field(default_factory=ZoneConfig)
    incidents: IncidentConfig = field(default_factory=IncidentConfig)
    site_required_ppe: tuple[str, ...] = ()
