// One-line explanation for every editable threshold (Settings screen). Keys mirror config/default.yaml.
export const THRESHOLD_DOCS: Record<string, Record<string, { label: string; help: string; unit?: string }>> = {
  tracking: {
    track_high_thresh: { label: 'Detection confidence to track', help: 'Boxes above this score are matched to people first.' },
    track_low_thresh: { label: 'Low-confidence rescue', help: 'Weaker boxes can still continue an existing track (helps in crowds).' },
    new_track_thresh: { label: 'Confidence to start a new person', help: 'Higher means fewer false people, but late starts.' },
    match_thresh: { label: 'Matching tolerance', help: 'How loosely a box may match last frame’s position (IoU cost).' },
    track_buffer_s: { label: 'Keep a lost person for', help: 'An ID survives a short occlusion this long.', unit: 's' },
    min_hits: { label: 'Frames before counting', help: 'A person is counted only after this many detections.' },
    min_age_s: { label: 'Seconds before counting', help: 'And only after being seen for at least this long.', unit: 's' },
    min_hit_ratio: { label: 'Steadiness before counting', help: 'Share of frames the person must be detected in (0–1). Blocks flicker.' },
    reid_window_s: { label: 'Re-join window', help: 'A new ID close to a just-lost one, in similar clothes, is merged within this time. 0 = off.', unit: 's' },
  },
  ppe: {
    evidence_tau_s: { label: 'Evidence smoothing', help: 'Time constant of the PPE evidence filter.', unit: 's' },
    absent_below: { label: 'Missing below', help: 'Evidence level under which an item counts as missing (0–1).' },
    present_above: { label: 'Wearing above', help: 'Evidence level over which an item counts as worn (0–1).' },
    violation_min_s: { label: 'Missing for at least', help: 'An item must be missing this long before an incident opens.', unit: 's' },
    min_person_height_px: { label: 'Smallest person checked', help: 'People shorter than this are too small to judge PPE.', unit: 'px' },
  },
  zones: {
    enter_frames: { label: 'Frames to enter', help: 'Consecutive frames inside before a person counts as entered.' },
    exit_frames: { label: 'Frames to leave', help: 'Consecutive frames outside before a person counts as left.' },
    lost_grace_s: { label: 'Keep zone membership for', help: 'A person briefly lost by the tracker stays in the zone this long.', unit: 's' },
  },
  incidents: {
    clear_s: { label: 'Clear after', help: 'An incident ends when its condition has been false this long.', unit: 's' },
    cooldown_s: { label: 'Reopen window', help: 'If it happens again within this time, the same incident reopens instead of a new one.', unit: 's' },
    overcrowding_min_s: { label: 'Over capacity for at least', help: 'Occupancy must exceed the limit this long.', unit: 's' },
  },
}

export const SECTION_TITLES: Record<string, { title: string; help: string }> = {
  tracking: { title: 'Counting people', help: 'How detections become unique people. Defaults were tuned on MOT17 (see the counting report).' },
  ppe: { title: 'PPE checks', help: 'How detected items become “wearing” or “missing”, without flicker.' },
  zones: { title: 'Zones', help: 'When a person counts as inside a zone.' },
  incidents: { title: 'Incidents', help: 'When incidents open, close and reopen.' },
}
