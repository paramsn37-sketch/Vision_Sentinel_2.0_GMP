# Changelog

All notable changes to this project are documented here (format: Keep a Changelog, versions: SemVer).

## [2.0.0] - 2026-10-22

A rebuild from scratch of the v1 prototype. Nothing was carried over from v1's code.

### Added
- Live monitoring of video files, webcams and RTSP/HTTP streams; photo and video uploads through the same pipeline.
- Person + PPE detector trained for this project (`models/vs2-y26n`: person, head, helmet, vest, gloves, hand,
  boots, goggles, no_goggles) with model card, run registry, test metrics, latency table and error analysis.
  People for tracking come from the stock COCO model (ADR-0013).
- Tracking (ByteTrack) with track confirmation: unique people are distinct confirmed tracks, not per-frame sums.
  MOT17 unique-count error 20.0 % (v1's method: 107.9 %).
- Per-person PPE state with temporal smoothing (worn / missing / unknown).
- Polygon zones (no entry, PPE required, max occupancy, max dwell, active hours) with foot-point test and
  entry/exit hysteresis; zone editor with keyboard support, undo/redo, import/export.
- Incidents with lifecycle (open, acknowledged, resolved), evidence frames, timeline, notes, feedback.
- Explanations: per-detection HiResCAM/Grad-CAM and EigenCAM, with measured sanity checks.
- Analytics, PDF and CSV shift reports; Model screen with training runs, metrics and figures.
- Single-admin sign-in, CSRF protection, login throttling, audit log, security headers, retention job,
  disk-full guard.
- Industrial control-room UI in dark and light themes (WCAG 2.2 AA contrast, keyboard operable, reduced motion).
- Docker Compose (CPU image, non-root, health check), CI (lint, unit, Playwright e2e, Docker build and smoke run).
- Docs: user guide, operations, architecture, API, training, report appendix, final audit, ADRs, build log.

### Known limitations
- Counting error 20 % (target 10 %); detector under-trained (CPU, 26 epochs); gloves, goggles and bare hands not
  reliable; explanation randomisation check fails; GPU performance not measured. See `docs/FINAL_AUDIT.md`.
