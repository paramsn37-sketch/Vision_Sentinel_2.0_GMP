# CLAUDE.md — standing rules for this repository

This repo is **Vision Sentinel 2.0**, built from scratch by Claude Code in unattended phases.

- Spec: `docs/BLUEPRINT.md` (source of truth). Build script: `BUILD_PROMPTS.md`.
- Progress: append to `docs/BUILD_LOG.md` after every phase; keep `docs/build_state.json` current.
- Decisions: short ADRs in `docs/DECISIONS.md`.
- Work unattended: never stop to ask; decide, record, continue (see `BUILD_PROMPTS.md` §A).
- Never fake results: no mock detections, no invented metrics. Unmeasured means "not measured".
- Never commit secrets, datasets, caches or files > 50 MB.
- Commit and push at the end of every phase with message `phase <n>: <title>`.
- The old v1 repo (`paramsn37-sketch/VISION-SENTINAL-FINAL`) is context only. Do not copy code from it.
