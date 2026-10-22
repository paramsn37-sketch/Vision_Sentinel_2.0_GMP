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

## Phase 0 — Bootstrap, tooling, skills, environment probe
- **Status:** done
- **Dates:** 2026-10-22T13:42Z → 2026-10-22T13:58Z (UTC)
- **What was built:**
  - Layout from blueprint §11; `backend/` managed by uv (Python 3.12) with dependency groups `dev`, `eval`, `train`.
  - `frontend/`: Vite 8 + React 19 + TypeScript (strict), Tailwind v4, TanStack Query, Zustand, Radix, Sonner,
    uPlot, Vitest, Playwright 1.56 (preinstalled Chromium), axe.
  - `Makefile` (setup, dev, lint, typecheck, test, e2e, eval, train, api-types, docker), `.github/workflows/ci.yml`.
  - Skills vendored into `.claude/skills/`: impeccable, emil-design-eng (+ review/improve-animations, ask-sonner,
    animation-performance), taste-skill.
  - `docs/environment.md`, `docs/DECISIONS.md` (ADR-0001…0005), `docs/ROADMAP.md`, `scripts/phase_state.py`.
- **Decisions:** ADR-0001 stack, ADR-0002 AGPL-3.0, ADR-0003 oxlint, ADR-0004 training environment, ADR-0005 skills.
- **Measurements:** 4 vCPU but ~1 effective core (matmul 2.5 s on 1 thread vs 9.1 s on 4); no GPU; 15 GB RAM.
- **Gate results:** `make lint` pass · `make test` pass (backend 1, frontend 1) · `npm run build` pass ·
  core imports pass · environment.md states training mode `cpu-budget` · skills installed.
- **Fallbacks used / deviations from blueprint:** training mode `cpu-budget`; Kaggle/Roboflow/HF/MOT site blocked by
  network policy (ADR-0004). Playwright MCP not configured (the CLI test runner covers the use).
- **Known issues / follow-ups:** `openapi-typescript` peer-requires TypeScript 5; run it through `npx` (Makefile).
- **Next phase:** 1 — Datasets
