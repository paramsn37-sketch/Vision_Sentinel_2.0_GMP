# Build Log

Each phase appends an entry here using the template in `BUILD_PROMPTS.md` §A.5. Newest at the bottom.
An executive summary is added at the top when the build finishes (Phase 12).

---

## Planning — Blueprint and build prompts
- **Status:** done
- **Dates:** 2026-10-22 (UTC)
- **What was built:** `docs/BLUEPRINT.md`, `BUILD_PROMPTS.md`, `CLAUDE.md`, `README.md`, this log, `docs/build_state.json`.
- **Decisions:** stack (FastAPI + SQLite + React/Vite), YOLO26 with YOLO11 fallback, ByteTrack with confirmation and
  lost-track merge for unique counting, foot-point zone membership with hysteresis, Grad-CAM on the raw head output
  plus EigenCAM fallback, ISA-101 style control-room UI. Rationale in the blueprint.
- **v1 audit findings:** per-frame person counting; stock COCO weights labelled as PPE classes; mock RNG in the
  upload endpoint; static zone page with pixel coordinates and box-centre test; Grad-CAM on post-NMS output.
- **Next phase:** 0 — Bootstrap, tooling, skills, environment probe
