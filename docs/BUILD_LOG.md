# Build Log

Each phase appends an entry here using the template in `BUILD_PROMPTS.md` §A.5. Newest at the bottom.

## Executive summary (v2.0.0, 2026-10-22)

**What was built.** Vision Sentinel 2.0, from scratch in one day of unattended phases: a FastAPI vision service
(detection, tracking, PPE state, zones, incidents, explanations, analytics, reports, auth) and a React control-room
UI (Live, Incidents, Zones editor, Analytics, Uploads, Model, Settings), a trained person + PPE detector with full
records, evaluation scripts for detection, counting and explanations, Docker Compose, CI, and documentation.

**Headline numbers (all measured).**
- Detector (frozen test split, 559 images): helmet 0.867, vest 0.849, person 0.683, head 0.579 mAP50; mean 0.524.
  Stock COCO models detect no PPE at all.
- Unique-person counting (MOT17, 5 held-out sequences): 20.0 % mean error, against 107.9 % for v1's method.
- Explanations: pointing game 100 %, deletion check 95 %; randomisation check fails (SSIM 0.669).
- One camera on a 4-core CPU: 9.6 FPS (21.3 FPS with the trained model alone). 60-minute soak: memory +3.0 %.
- Tests: 70 backend + 6 model, 25 frontend unit, 20 Playwright e2e; `app/core` coverage 86 %; axe 0 serious issues.

**What remains** ([FINAL_AUDIT.md](FINAL_AUDIT.md)). Counting error is twice the 10 % target. The detector was
trained on CPU and stopped after 26 epochs by a machine restart; a GPU run (Colab notebook provided) is the first
improvement. One explanation sanity check fails. GPU speed was never measured.

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

## Phase 1 — Datasets: acquire, remap, dedup, split, dataset card
- **Status:** done-with-fallbacks
- **Dates:** 2026-10-22T13:58Z → 2026-10-22T14:12Z (UTC)
- **What was built:**
  - `training/configs/class_map.yaml` + `training/vs_data/classmap.py` (every source class mapped or dropped).
  - `download_openimages.py` (capped, PPE-relevant Open Images V7 subset, 2,450 images, 0 failed downloads).
  - `merge.py` (remap, clip, drop < 4 px boxes), `split.py` (exhaustive pHash dedup, stratified 70/15/15),
    frozen manifests + test checksum in `data/manifests/`.
  - `dataset_card.py` → `data/DATASET_CARD.md`, `data/figures/` (class distribution, box sizes, 9 QA grids).
  - `backend/eval/make_clips.py` → three MOT17 sample clips in `data/samples/` with ground-truth counts in
    `data/eval/clips.yaml`; 40 fixture images in `backend/tests/fixtures/images/`.
- **Decisions:** ADR-0006 (taxonomy, Open Images selection), ADR-0008 (exhaustive dedup).
- **Measurements:** 3,708 images after dedup → train 2,595 / val 554 / test 559 (the card's tables have
  per-class counts). 157 near-duplicates removed. Sample clips: 22 / 53 / 69 unique pedestrians (MOT GT).
- **Gate results:** `pytest tests/training` 8 passed (class map coverage, disjoint manifests, no cross-split
  near-duplicates) · DATASET_CARD.md has real numbers, train ≥ 2,000 · data.yaml accepted by Ultralytics
  (training scan: 2,595 images, 0 corrupt).
- **Fallbacks used / deviations from blueprint:** Kaggle SH17 and Roboflow sets unreachable (network policy, no
  credentials) → public sources only; no `mask` class; no hard negatives; sample clips are street scenes (MOT17),
  not industrial footage, because no permissively licensed worker video was reachable.
- **Known issues / follow-ups:** QA grid for `head` shows at least one Construction-PPE `no_helmet` box on a person
  wearing a hard hat (source label noise; kept, noted in the training report).
- **Next phase:** 2 — Detector training (running in the background), then 3 — Vision core

## Phase 3 — Vision core: sources, detector, tracking, unique counting, PPE state
- **Status:** done-with-fallbacks
- **Dates:** 2026-10-22 (UTC)
- **What was built:** `app/core/config.py` (typed config, `config/default.yaml`), `sources/base.py` (video file,
  image, webcam and RTSP/HTTP sources), `detection/detector.py` (Ultralytics wrapper with model info and
  fallback to COCO person-only), `tracking/tracker.py` (ByteTrack + confirmation: min hits, min age, hit ratio,
  optional appearance re-link), `ppe/` (box association, head/torso regions, per-person evidence with hysteresis;
  only PPE items the loaded model can detect are checked), `pipeline.py`, `cli.py`, `eval/counting_eval.py`.
- **Decisions:** ADR-0009 (counting thresholds).
- **Measurements:** `docs/eval/counting_report.md` on 5 held-out MOT17 sequences: mean unique-count error
  naive per-frame counting (v1 method) 107.9 %, ByteTrack defaults 25.2 %, ours 19.7 % (20.0 % with the shipped
  `min_hit_ratio` 0.5). Measured with the COCO fallback detector, not the trained model.
- **Gate results:** `pytest tests/core` pass (flicker, occlusion, re-entry, PPE hysteresis, person-only model).
- **Fallbacks used / deviations from blueprint:** the 10 % count-error target is **not met** (~20 %); reasons in
  ADR-0009. Appearance re-link hurt counting on MOT17, so it ships disabled.
- **Next phase:** 4

## Phase 4 — Zones, intrusion rules and incident engine
- **Status:** done
- **What was built:** `zones/model.py` (polygon validation: ≥3 points, no self-intersection, normalised coords),
  `zones/engine.py` (point-in-polygon on the foot point with dwell and exit grace; rules: no entry, required PPE,
  max occupancy, max dwell, active hours), `incidents/manager.py` (open/update/close with de-duplication per person, zone and rule; evidence
  frame selection), sample zone YAML for the three seeded cameras.
- **Gate results:** `pytest tests/core/test_zones.py tests/core/test_incidents.py` pass.
- **Next phase:** 5

## Phase 5 — Explainability: Grad-CAM, EigenCAM, sanity evaluations
- **Status:** partial (evaluation pending the trained model)
- **What was built:** `xai/cam.py` (Grad-CAM, HiResCAM, EigenCAM on the detection head branch that produced the
  box), `xai/worker.py` (background job queue, saves heatmap + source frame), `eval/xai_eval.py`.
- **Decisions:** ADR-0010 (target branch selection, HiResCAM default).
- **Measurements:** not measured yet. `xai_eval` (deletion/insertion and randomisation sanity checks) will run
  against the trained detector at the end of Phase 2.
- **Gate results:** `pytest tests/core/test_xai.py` pass.
- **Next phase:** 6

## Phase 6 — Backend API, persistence, streaming, auth, reports
- **Status:** done
- **What was built:** FastAPI app (`app/main.py`, `app/api/*`): auth (argon2, session cookie + CSRF), cameras,
  zones (+ server-side validate, YAML import/export), incidents (cursor paging, patch, notes), analytics, uploads,
  XAI jobs (+ `/xai/{id}/source`), model info, reports (PDF via fpdf2), health; WebSockets for events and live
  frames (JSON meta followed by a JPEG). SQLite with a single batched writer thread (failed batches are retried
  one job at a time), seeded demo cameras and zones, structured logging.
- **Decisions:** ADR-0011 (create_all + `user_version` instead of Alembic; fpdf2 instead of WeasyPrint).
- **Gate results:** `make lint` pass · backend `pytest -m "not slow and not model"` 62 passed · `/health` shows
  the 3 seeded cameras running with fps > 0.
- **Next phase:** 7

## Phase 7 — Design direction and design system
- **Status:** done
- **What was built:** `PRODUCT.md`, `DESIGN.md` (direction "data terminal", tokens, contrast table, type, motion,
  components, do/don't), `frontend/src/styles/tokens.css` (dark default + light), self-hosted Public Sans and IBM
  Plex Mono, `scripts/check-tokens.mjs`, UI primitives in `src/components/ui/`, `/_design` reference page (dev only).
- **Gate results:** `check-tokens` 61/61 tokens present, every contrast pair passes in both themes ·
  `e2e/design.spec.ts` 2 passed with screenshots in `e2e/__screenshots__/design/`.
- **Fallbacks used / deviations from blueprint:** 4 px rectangular control corners instead of the dealt sheet's
  rounder value (recorded in DESIGN.md).
- **Next phase:** 8

## Phase 8 — Frontend app: shell and screens
- **Status:** done
- **What was built:** app shell (icon rail, status strip, ⌘K command palette, `g <n>` navigation, grouped event
  toasts), Live (video tiles with canvas overlays, track cards, shift strip), Incidents (filters, j/k/Enter/a/r
  keys, drawer with evidence, explanation, timeline, notes), Zones (SVG polygon editor with undo/redo, zoom/pan,
  full keyboard editing), Analytics (hand-written SVG charts with screen-reader tables), Uploads, Model, Settings.
- **Measurements:** initial JS 173.7 KB gzip (budget 250 KB). Vitest 25 passed. Smoke e2e 2 passed (Live shows
  frames within 10 s; every route renders without page errors), screenshots in `e2e/__screenshots__/screens/`.
- **Fixes found by running it:** person-only model reported "No vest" (now only checkable PPE is evaluated); rail
  badge mispositioned (Radix Slot className merge); shift strip caption now shows the real peak.
- **Known issues / follow-ups:** two tolerated `set-state-in-effect` lint warnings; uPlot dependency removed
  (charts are hand-written SVG).
- **Next phase:** 9

## Phase 9 — Flagship interactions: zone editor and explainability panel
- **Status:** done
- **What was built:** the zone editor and XAI panel from Phase 8 were verified end to end and hardened:
  `e2e/zones-xai.spec.ts` (draw a no-entry zone on a live camera ⇒ intrusion incident ⇒ evidence ⇒ Grad-CAM
  heatmap and reading ⇒ acknowledge ⇒ resolve; drag a vertex and undo it; keyboard-only zone creation and save).
- **Fixes found by the tests:** the login throttle counted successful sign-ins, so repeated logins from one IP were
  blocked; it now counts only failed attempts (new API test). Zone validation fired a request per keystroke; it is
  now debounced (300 ms).
- **Gate results:** Vitest 25 passed three runs in a row · `zones-xai.spec.ts` 3/3 passed three runs in a row (after
  making the incident-row click retry when live rows re-render) · keyboard-only zone creation passes · smoke and
  design specs pass · backend auth tests 6 passed.
- **Known issues / follow-ups:** Grad-CAM was exercised with the COCO fallback detector; repeat with the trained model.
- **Next phase:** 10

## Phase 10 — Playwright refinement loop
- **Status:** done-with-fallbacks
- **What was built:** `e2e/visual.spec.ts` (7 routes × 1440/1024/768/390 px × dark/light, plus drawer, explanation
  and editor-mid-draw states; asserts no sideways scroll), `e2e/a11y.spec.ts` (axe WCAG 2.1 AA on every route in
  both themes; reduced-motion check), `e2e/routes.ts`, review `docs/ui-review/round-1.md`, curated
  `docs/screenshots/`, DESIGN.md updated from what shipped (responsive rules, contrast table regenerated).
- **Fixes:** 14 findings (5 high, 6 medium, 3 low), see round-1. Notable: every route scrolled sideways below
  1280 px; Live and Zones broke on phones; charts drew hours without data as zero (misleading); light-theme hint
  text below 4.5:1; editor foot markers looked like vertex handles. The slow upload test's bound now matches the
  measured MOT17-09 error (it had never run against the tuned thresholds).
- **Gate results:** `npx playwright test` 20 passed · axe 0 serious/critical in both themes · round-1 has no open
  high/medium findings · screenshots of Live, Incidents, Zones editor, XAI panel, Analytics, Model in both themes.
- **Fallbacks used / deviations from blueprint:** no `toHaveScreenshot` baselines: live video, counts and times
  change every frame, so pixel baselines would only measure the clock; the review set is regenerated instead and
  kept out of git (13 MB). Canvas draw time and long-task measurement moved to Phase 11's performance pass.
- **Next phase:** 11

## Phase 2 — Detector training, evaluation and records
- **Status:** done-with-fallbacks
- **What was built:** `training/scripts/{train,evaluate,export,benchmark,error_analysis}.py`, run registry
  (`training/registry.json`), baselines (v1 YOLO11m and stock YOLO26n on the frozen test split), the trained model
  `models/vs2-y26n.{pt,onnx}` with `models/model.json` (classes, per-class thresholds chosen on val, test metrics,
  sha256), `MODEL_CARD.md`, `training/reports/training_report.md`, error-analysis grids, latency table, Colab
  notebook for the full GPU plan.
- **Headline numbers (test split, 559 images):** mean mAP50 0.524; person 0.683 (stock YOLO26n 0.720, v1 YOLO11m
  0.745); helmet 0.867; vest 0.849; boots 0.683; head 0.579; hand 0.150 and no_goggles 0.016 unusable. CPU latency
  29.9 ms p50 (PyTorch, 480 px), 27.6 ms (ONNX).
- **Gate results:** `pytest -m model` 5 passed (class list matches the taxonomy; a person is found in ≥ 90 % of
  fixture images) · person mAP50 within 5 points of the stock model (3.7) · registry, curves, PR/F1/confusion plots
  and error analysis committed.
- **Fallbacks used / deviations from blueprint:** CPU-only training of the nano model at 480 px (ADR-0007); the run
  was interrupted after 26 of ~55 planned epochs by a machine restart and shipped as is (ADR-0012). Person and head
  miss their SHOULD targets (0.80 / 0.70).
- **Next phase:** re-run counting and XAI evaluations with this model (Phase 5 completion), then 11–12.

## Phase 5 (completion) — Explainability and counting with the trained model
- **Status:** done-with-fallbacks
- **What changed:** `eval.xai_eval` and `eval.counting_eval` re-run with `vs2-y26n`. The trained model's own person
  class made counting much worse (41.3 % at 480 px, 32.9 % at 640 px), so people now come from the COCO model and
  PPE from the trained model (ADR-0013); counting is back to 20.0 %. The Model screen crashed once real results
  existed; the API now normalises every results file and a test pins the shapes. mypy on `app/core` is clean.
- **Gate results:** pointing game 100 % (214 detections, 8 classes) · deletion check: hottest 20 % beats a random
  20 % in 95 % of cases (score drop 0.509 vs 0.109) · randomisation check **fails** (SSIM 0.669, needs < 0.5),
  explained in `docs/eval/xai_report.md` · explanation latency 142 ms p50 on CPU · counting 20.0 % mean error
  (target 10 %, not met, ADR-0009).
- **Fallbacks used / deviations from blueprint:** two networks per frame instead of one (ADR-0013).
- **Next phase:** 11

## Phase 11 — Integration, performance, hardening, Docker, CI
- **Status:** done-with-fallbacks
- **What was built:** disk-full guard with a UI notification; hourly retention job (it was never scheduled before);
  security tests (every API route and both WebSockets reject anonymous callers, path traversal, headers); failure
  tests (corrupt upload, low disk, retention); Docker images and compose (named volume, non-root, health check,
  nginx proxy for API and WebSockets); CI jobs for Playwright e2e and the Docker build with a smoke run and an image
  size budget; `eval/perf.py`, `scripts/soak.py`; docs: architecture, API (generated), operations, user guide,
  training.
- **Measurements:** one camera 9.6 FPS (default, two networks) or 21.3 FPS (trained model only) on 4 vCPU; detection
  is 97 % of frame time ([performance.md](eval/performance.md)). 60-minute soak with three cameras: memory +3.0 %
  after warm-up, open files and threads flat ([soak.md](eval/soak.md)).
- **Fixes found here:** the backend image was 6.14 GB because CUDA wheels from the lock file were installed into the
  CPU image; excluded (now 1.82 GB), and CI enforces the 2.5 GB budget. The benchmark script overwrote the promoted ONNX file
  (and so its checksum); it now exports from a temporary copy. Docker: bind-mounted data was not writable by the
  non-root user (named volume); OpenCV needed `libxcb1`/`libgl1`.
- **Fallbacks used / deviations from blueprint:** Docker is not available inside the build container, so images are
  built and smoke-tested in CI only. GPU throughput is not measured (no GPU). End-to-end UI latency is not
  instrumented separately from the pipeline.
- **Next phase:** 12

## Phase 12 — Docs, final audit, release v2.0.0
- **Status:** done-with-fallbacks
- **What was built:** README rewrite (quick start, honest feature status, results), `docs/report-appendix.md`,
  `docs/FINAL_AUDIT.md`, `MODEL_CARD.md`, `training/reports/training_report.md`, `docs/eval/performance.md`,
  per-class mAP figure, AGPL-3.0 licence text (the file was missing), CHANGELOG 2.0.0, this summary, tag `v2.0.0`.
- **Fixes found in the final pass:** the Model screen crashed with real results; a scrollable panel was not keyboard
  reachable; `make lint` called a bare `ruff`; mypy on `app/core` had 13 errors (now 0); the Docker image carried
  CUDA wheels.
- **Gate results:** FINAL_AUDIT covers every §13 item and every MUST · `make lint` clean (2 oxlint warnings) ·
  `make typecheck` clean · `make test` green (backend 70, Vitest 25) · `pytest -m model` 6 passed · `make e2e` 20
  passed · coverage `app/core` 86 % · all phases `done` or `done-with-fallbacks`.
- **Fallbacks used / deviations from blueprint:** see FINAL_AUDIT "Partial" and "Fail" rows.
