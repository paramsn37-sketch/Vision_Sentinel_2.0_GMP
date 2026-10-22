# Vision Sentinel 2.0 — Unattended Build Prompts

This file drives the whole build. It is written for **Claude Code** running without a human watching.
Read §A (operating rules) once, then execute phases in order. The spec is [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md);
where this file and the blueprint disagree, the blueprint wins, and you record the conflict in `docs/DECISIONS.md`.

**Kickoff prompt** (what the person pastes into Claude Code):

> Read `CLAUDE.md`, `docs/BLUEPRINT.md` and `BUILD_PROMPTS.md`. Execute the build exactly as `BUILD_PROMPTS.md`
> describes, starting from the first phase that is not `done` in `docs/build_state.json`. Work unattended: do not
> ask me questions, make the best decision, record it, and keep going until every phase is done or a hard stop in
> §A.6 is reached.

---

## A. Operating rules (apply to every phase)

### A.1 Autonomy
- Nobody is monitoring. **Never stop to ask a question.** When a choice is open, pick the option that best serves
  the blueprint's goals in this order: *correctness → measurable evidence → simplicity/lightness → polish → speed of
  building*. Write a 3–6 line ADR in `docs/DECISIONS.md` for any choice a reviewer could reasonably question.
- Do not water down a MUST from the blueprint to make a gate pass. If a MUST is genuinely impossible in this
  environment (e.g. no GPU), apply the fallback the blueprint names in §12 and record it.
- Never fake results. No mock detections, no hard-coded metrics, no screenshots of placeholder data presented as
  real. If a number could not be measured, the report says "not measured" and why.

### A.2 Resume protocol (start of every session and every phase)
1. `git pull` (or fetch + rebase) the current branch.
2. Read `docs/build_state.json` and the last two entries of `docs/BUILD_LOG.md`.
3. Continue with the first phase whose status is not `done`. If a phase is `in_progress`, inspect what exists, finish
   the remaining tasks, do not redo completed work.
4. Set the phase to `in_progress` with `started_at` before working.

### A.3 End of every phase (all steps MUST happen)
1. Run the phase's **Gate** commands. Fix until they pass (max 5 fix rounds per failing gate; then see A.6).
2. Run the global checks that exist so far: `make lint`, `make test` (backend and frontend as applicable).
3. Append a log entry to `docs/BUILD_LOG.md` using the template in A.5.
4. Update `docs/build_state.json`: status `done`, `finished_at`, `commit`, `gate_results`, `notes`.
5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Commit with message `phase <n>: <title>` (conventional body listing main changes) and **push**. Retry push on
   network errors 4 times with 2/4/8/16 s backoff.

### A.4 Engineering standards
- Python 3.11, `uv`, ruff (format + lint), mypy (strict for `backend/app/core`), pytest. Type hints everywhere.
- TypeScript strict, ESLint, Prettier, Vitest, Playwright. Types for the API are **generated** from OpenAPI.
- Small modules with one job each. No file over ~400 lines without a reason. Comments explain *why*, not *what*.
- All thresholds are config with defaults from the blueprint; no magic numbers in logic.
- Lightweight: before adding a dependency, check if the standard library or an existing dependency covers it. Record
  each new runtime dependency and its size in the phase log.
- Secrets only from env vars (`KAGGLE_USERNAME`, `KAGGLE_KEY`, `ROBOFLOW_API_KEY`, `VS_ADMIN_PASSWORD`, …). Never
  commit them, never print them in logs. Ship `.env.example`.
- Never commit datasets, `training/runs/*/weights/last.pt`, caches, `node_modules`, or files > 50 MB (use Git LFS for
  the one shipped weight file only if needed).
- Long jobs (downloads, training, evals) run in the background with output to a log file under `logs/build/`; check
  on them between tasks instead of sleeping. Never block the session on a job that will take more than 10 minutes.

### A.5 Build log template (append to `docs/BUILD_LOG.md`)
```markdown
## Phase <n> — <title>
- **Status:** done | done-with-fallbacks | blocked
- **Dates:** <started_at> → <finished_at> (UTC)
- **Commit:** <sha>
- **What was built:** 3–8 bullets, concrete (files, features)
- **Decisions:** bullets linking ADR numbers in DECISIONS.md
- **Measurements:** tables/numbers produced in this phase (metrics, fps, sizes, coverage)
- **Gate results:** each gate command → pass/fail (+ short output)
- **Fallbacks used / deviations from blueprint:** or "none"
- **Known issues / follow-ups:** carried into later phases (also listed in build_state.json → `followups`)
- **Next phase:** <n+1> — <title>
```

### A.6 Hard stops and failure policy
- A gate still failing after 5 focused fix rounds: mark the phase `done-with-fallbacks` if the blueprint allows a
  fallback, otherwise `blocked`; write exactly what fails and why in the log; **continue with the next phase** if it
  does not depend on the blocked one. Return to blocked items in Phase 12.
- Stop the entire build only if: the repo cannot be pushed to, disk is full and cannot be freed, or a step would
  require spending money, publishing outside this repo, or using credentials that were not provided. Write the
  reason at the top of `docs/BUILD_LOG.md` under `## BUILD HALTED`.

### A.7 Skills
The UI phases use four skills: **impeccable**, **Emil Kowalski's design engineering skill**, **Taste (Leonxlnx)** and
**Playwright**. Phase 0 installs them. When a phase says "run impeccable <command>", invoke that skill through the
Skill tool if available; if a skill is not installed, follow the blueprint §9 principles directly and note it.

---

## Phase overview

| # | Title | Depends on | Typical length |
|---|---|---|---|
| 0 | Bootstrap, tooling, skills, environment probe | — | short |
| 1 | Datasets: acquire, remap, dedup, split, dataset card | 0 | medium (downloads) |
| 2 | Detector training, evaluation and records | 1 | long (runs in background) |
| 3 | Vision core: sources, detector wrapper, tracking, unique counting, PPE state | 0 (uses stock weights until 2 lands) | long |
| 4 | Zones, intrusion rules and incident engine | 3 | medium |
| 5 | Explainability: Grad-CAM, EigenCAM, sanity evals | 3 | medium |
| 6 | Backend API, persistence, streaming, auth, reports | 3, 4, 5 | long |
| 7 | Design direction and design system (impeccable + Taste + Emil) | 0 | medium |
| 8 | Frontend app: shell, Live, Incidents, Analytics, Model, Uploads, Settings | 6, 7 | long |
| 9 | Flagship interactions: zone editor and explainability panel | 8 | medium |
| 10 | Playwright refinement loop (visual, motion, a11y, taste audit) | 9 | medium |
| 11 | Integration, performance, hardening, Docker, CI | 2, 10 | medium |
| 12 | Docs, final audit against blueprint, release v2.0.0 | all | medium |

`docs/build_state.json` lists the same phases with `status: pending`.

---

## Phase 0 — Bootstrap, tooling, skills, environment probe

**Goal.** A clean monorepo skeleton where `make lint`, `make test` and `make dev` work on empty apps, the four skills
are installed, and the build knows what hardware and credentials it has.

**Tasks.**
1. Create the layout from blueprint §11 (empty packages with `__init__.py`, placeholder routes only where needed to
   make tooling run). Add `.gitignore` (Python, Node, datasets, runs, `.env`, `logs/`), `.editorconfig`,
   `.env.example`, `LICENSE` (choose AGPL-3.0 to match Ultralytics; ADR it), `CHANGELOG.md`.
2. Backend: `backend/pyproject.toml` managed by `uv` with groups `core`, `train`, `eval`, `dev`. Pin
   `torch` CPU wheels by default (index URL for CPU), allow CUDA via an extra. Install `ultralytics` (latest),
   `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlmodel`, `alembic`, `shapely`, `opencv-python-headless`,
   `structlog`, `argon2-cffi`; dev: `pytest`, `pytest-cov`, `hypothesis`, `httpx`, `ruff`, `mypy`.
   Minimal `app/main.py` with `/api/v1/health`.
3. Frontend: Vite + React 19 + TS strict, Tailwind v4, React Router, TanStack Query, Zustand, Vitest, Testing
   Library, ESLint, Prettier, Playwright (`@playwright/test`; use the preinstalled Chromium if
   `PLAYWRIGHT_BROWSERS_PATH` is set, do not download browsers when it is). One placeholder route.
4. `Makefile` targets: `setup`, `dev` (backend + frontend concurrently), `lint`, `typecheck`, `test`, `test-backend`,
   `test-frontend`, `e2e`, `eval`, `train`, `docker`, `clean`.
5. **Skills.** Install into the project's `.claude/skills/` (commit them so later sessions have them):
   - impeccable: `https://github.com/pbakaus/impeccable` (follow its README for Claude Code; plugin or skill folder).
   - Emil Kowalski: `https://github.com/emilkowalski/skill` (skill `emil-design-eng`).
   - Taste: `https://github.com/Leonxlnx/taste-skill`.
   - Playwright: use `@playwright/test` in the repo; also add the Playwright MCP to `.mcp.json`
     (`npx @playwright/mcp@latest`) if MCP servers are supported in the environment.
   Use `npx skills add <repo>` if available, else `git clone --depth 1` and copy the skill folders. Read each skill's
   SKILL.md once and write a 10-line summary of how it will be applied into `docs/DECISIONS.md` (ADR "Design
   skills").
6. **Environment probe** → `docs/environment.md` and `build_state.json.env`: OS, CPU cores, RAM, disk free, GPU
   (`nvidia-smi`, `torch.cuda.is_available()`), Python/Node versions, which credentials are present (names only, true/
   false), network reachability of: ultralytics assets, huggingface, kaggle, roboflow, storage.googleapis.com (Open
   Images), motchallenge.net. Decide the **training mode** (`gpu-full` or `cpu-budget`) here and record it.
7. Create `CLAUDE.md` additions if needed (it already exists: keep its rules), `docs/DECISIONS.md` (ADR-0001: monorepo
   and stack), `docs/ROADMAP.md` (out-of-scope items from blueprint §2.4).
8. GitHub Actions `ci.yml` skeleton running lint + tests on push (keep it green from day one).

**Gate.**
- `make setup && make lint && make test` exit 0.
- `cd frontend && npm run build` exits 0.
- `uv run python -c "import ultralytics, torch, shapely, fastapi"` exits 0.
- `docs/environment.md` exists and states the training mode.
- `.claude/skills/` contains the installed skills, or the log lists which failed and why.

---

## Phase 1 — Datasets: acquire, remap, dedup, split, dataset card

**Goal.** One merged, leak-free YOLO dataset with the 10-class taxonomy from blueprint §4.2, fully documented.

**Tasks.**
1. `training/configs/class_map.yaml`: for each source, map every source class to a target class or `drop`. Unit
   test: loading each source's own class list, every class is covered; unknown class ⇒ test fails.
2. Downloader scripts in `training/scripts/` (idempotent, resumable, checksum where possible, each writes
   `data/raw/<source>/SOURCE.json` with URL, licence, date, file count):
   - `download_construction_ppe.py` (Ultralytics `construction-ppe.yaml`; always available).
   - `download_openimages.py` via FiftyOne zoo `open-images-v7`, `label_types=["detections"]`, classes
     `Person, Helmet, Glove, Goggles` (plus `Human head` only as `head` when no `Helmet` overlaps it). Cap: 3,000
     images for Person, all available for the rest up to 3,000 each. Prefer images tagged in industrial, workshop,
     street and indoor contexts to cover "humans in different places".
   - `download_kaggle.py` (SH17 — find the exact dataset slug with `kaggle datasets list -s SH17` — and other PPE
     sets) — only if Kaggle credentials exist.
   - `download_roboflow.py` (Hard Hat Workers, Construction Site Safety, a PPE set with gloves/boots) — only if
     `ROBOFLOW_API_KEY` exists; otherwise try a public mirror of Hard Hat Workers (e.g. Kaggle/HF) if reachable.
   - Hard negatives: 300–600 people-free frames (Open Images classes such as `Warehouse`/`Factory`-like scenes, or
     empty frames from public videos). ≤ 10% of the train set.
   Skipped sources are logged with the reason.
3. `merge.py`: convert to YOLO txt, remap, clip boxes, drop boxes < 4 px, drop images with no kept labels (except
   negatives). `dedup.py`: pHash across all sources, Hamming ≤ 6 ⇒ keep one. `split.py`: 70/15/15 stratified by source
   and by presence of rare classes; same-source near-duplicates stay in one split. Freeze test:
   `data/manifests/{train,val,test}.txt` + `test_manifest.sha256`.
4. `training/configs/data.yaml` pointing at the merged set.
5. `data/DATASET_CARD.md`: table per source (images, instances per class, licence), per-class totals per split,
   box-size histogram, image-size stats, scene diversity notes, known biases, licence implications (SH17 is NC ⇒
   weights are for academic/non-commercial use). Figures in `data/figures/` (generated by a script, not by hand).
6. Visual QA: render a 6×6 grid of random labelled train images per class into `data/figures/qa_<class>.jpg` and
   inspect a few; fix mapping bugs you find (log them).
7. Small fixture subset (40 images, mixed classes, permissive licence only) into `backend/tests/fixtures/images/` for
   tests. Also fetch 2–3 short CC0/Pexels-licence clips of workers (≤ 20 s, ≤ 15 MB total) into `data/samples/` with
   `data/samples/LICENSES.md`; hand-count unique people in each and record in `data/eval/clips.yaml`.

**Gate.**
- `uv run pytest backend/tests/training -q` (class map + split leakage tests) passes. Leakage test: no pHash
  duplicate across splits.
- `data/DATASET_CARD.md` exists with real numbers; total train images ≥ 2,000 (≥ 1,000 allowed with a logged reason
  if only one public source is reachable).
- `training/configs/data.yaml` validates with `ultralytics` (`YOLO('yolo26n.pt').val(data=..., split='val',
  fraction=0.01)` runs, or the YOLO11 equivalent).

---

## Phase 2 — Detector training, evaluation and records

**Goal.** A trained person + PPE detector that clearly beats v1, with every number reproducible and visible.

**Tasks.**
1. `training/scripts/train.py`: wraps Ultralytics training from a hyperparameter YAML
   (`training/configs/hyp_<name>.yaml`), sets seeds, writes the run into `training/registry.json` (git sha, data
   manifest hash, env, args) at start and updates it at the end. Supports `--budget-hours` to stop gracefully.
2. **Baselines first** on the frozen test split (`evaluate.py`): v1 setup (stock COCO `yolo11m.pt`, evaluated on
   `person` only, other classes reported as 0 because COCO has none) and stock `yolo26n.pt` person-only. Log both.
3. **Main runs** according to the training mode from Phase 0:
   - `gpu-full`: YOLO26n@640 and YOLO26s@640, 150 epochs, patience 25, cosine LR, AMP, `close_mosaic=10`; if time
     allows, a 960 px fine-tune of the winner for small items.
   - `cpu-budget`: YOLO26n@512 on a stratified subset (≤ 4,000 images), `--budget-hours 3`, workers = cores − 1.
   Launch in the background (`nohup … > logs/build/train_<run>.log`), then **continue to Phase 3** while it runs.
   Mark Phase 2 `in_progress` with `notes: "training running: <run_id>"`. Come back to tasks 4–8 when the run ends
   (check at the start of each later phase; complete them no later than Phase 11).
   If YOLO26 is unavailable in the installed ultralytics, use YOLO11 n/s and ADR it.
4. `evaluate.py` on the test split, once per finalist: mAP50, mAP50-95, precision, recall per class, confusion
   matrix, PR curves, F1-confidence curve; pick the per-class operating threshold maximising F1 on **val**, store it in
   `models/model.json`.
5. `benchmark.py`: latency (ms/frame, p50/p95) and FPS for PyTorch and ONNX at 640 and 512 on the available devices
   → `training/benchmarks/latency.json`.
6. Error analysis: dump the 50 worst FPs and FNs (thumbnails with GT vs prediction) to
   `training/reports/error_analysis/`, write 5–10 observations.
7. Reports: `training/reports/figures/*` (generated), `MODEL_CARD.md`, `training_report.md` with a comparison table
   (v1 baseline vs stock vs ours), training curves, what was tried, what won and why, limitations.
8. Export the winner to `models/vs2-<arch>.pt` and `.onnx`; `models/model.json` with classes, thresholds, imgsz,
   metrics, sha256, training mode. Add `training/notebooks/train_colab.ipynb` that reproduces the full GPU run with
   the same configs (for the cpu-budget case and for future retraining).

**Gate.**
- `training/registry.json` has ≥ 3 entries (2 baselines + ≥ 1 trained run) with test metrics.
- `models/model.json` exists and `uv run pytest -m model` passes (weights load, class names equal the taxonomy, a
  person is detected in ≥ 90% of fixture images that contain one).
- Our model's test mAP50 on `person`, `helmet`, `head`, `vest` is reported; it must beat the v1 baseline on every PPE
  class (trivially true since v1 has none) and be within 5 points of stock on `person`.
- `MODEL_CARD.md` and `training_report.md` contain only measured numbers.

---

## Phase 3 — Vision core: sources, detector, tracking, unique counting, PPE state

**Goal.** A pure-Python pipeline (no web) that turns frames into `FrameResult`s with correct unique counts and
smoothed per-person PPE state. Use stock `yolo26n.pt` for persons until the Phase 2 weights exist; the detector
wrapper reads `models/model.json` when present.

**Tasks.**
1. `core/types.py` with the contracts from blueprint §3.3 (Pydantic v2, frozen where possible).
2. `core/sources/`: `FileSource` (deterministic, every frame or every Nth), `WebcamSource`, `RtspSource` (reconnect
   with backoff), `ImageSource`. Common interface, latest-frame queue of size 1 for live sources.
3. `core/detection/detector.py`: loads weights once, device auto-select, FP16 on CUDA, warmup, per-class thresholds
   from `model.json`, returns `Detection`s in original-frame pixels.
4. `core/tracking/`: ByteTrack config (§5.1), confirmation (§5.2), lost-track merge heuristic (§5.3), `Counter` for
   current / unique_total / per-zone counts / dwell. The tracker only sees `person` boxes.
5. `core/ppe/`: body regions, IoA association, observation rules and the evidence filter with hysteresis (§5.4).
6. `core/pipeline.py`: `Pipeline(source, detector, tracker, ppe, zones=None, incidents=None)` yields `FrameResult`;
   timing per stage recorded.
7. CLI `python -m app.core.cli run --source data/samples/x.mp4 --out out.mp4` that writes an annotated video and a
   JSON summary (useful for debugging and for the report).
8. `backend/eval/counting_eval.py` (§5.6): download MOT17 train sequences 02/04/09 if reachable (else use
   `data/eval/clips.yaml` clips only), run three variants (naive per-frame sum like v1, raw tracker, tracker +
   confirmation + merge), compute IDF1/MOTA/ID switches (`motmetrics`) and unique-count error, and write
   `docs/eval/counting_report.md`. Tune `min_hits`, `min_age_s`, `track_buffer` and merge thresholds on
   MOT17-02/04 only; report on MOT17-09 + clips (no tuning on the reporting set). Log the chosen values as ADR.
9. Tests: synthetic trajectories (two people crossing, occlusion for 1 s, leaving and re-entering after 10 s ⇒ new
   ID allowed and documented, flicker detections ⇒ never counted), evidence filter (alternating observations never
   flip state faster than hysteresis allows), association (two overlapping people, helmet assigned to the right one).
   Property tests with hypothesis for region maths.

**Gate.**
- `uv run pytest backend/tests/core -q` passes; coverage of `app/core/{tracking,ppe}` ≥ 90%.
- `docs/eval/counting_report.md` exists; on the reporting set the final variant's unique-count error ≤ 10% (if not,
  log the best achieved, the reason, and a follow-up; do not fake).
- CLI produces an annotated video for each sample clip; the JSON summary's `unique_total` equals the hand count ±1
  on at least 2 of 3 clips.

---

## Phase 4 — Zones, intrusion rules and incident engine

**Goal.** Zone geometry and rules that produce clean, deduplicated incidents.

**Tasks.**
1. `core/zones/geometry.py`: normalised ↔ pixel conversion, validation (≥ 3 points, valid, min area), prepared
   shapely polygons, bbox pre-filter, foot-point and centre modes, inward buffer.
2. `core/zones/membership.py`: per-track entry/exit hysteresis (§6.2) emitting `ZoneEvent`s; per-zone occupancy and
   dwell feed the `Counter`.
3. `core/zones/rules.py`: rule evaluators from §6.3 including `active_hours` and site-default PPE.
4. `core/incidents/manager.py`: state machine with key, `clear_s`, `cooldown_s`, reopen-not-duplicate, severity,
   alert level, evidence selection (best frame in the first second), hook to enqueue XAI.
5. YAML import/export for zones; default sample zones for each sample clip in `data/samples/zones/`.
6. Tests: hypothesis property tests (point inside convex/concave polygons vs shapely; normalisation round-trip);
   boundary jitter ⇒ no flapping events; a person standing in a no-entry zone for 60 s ⇒ exactly **one** incident;
   leave and return within cooldown ⇒ same incident reopened; occupancy rule with 4 synthetic tracks; performance
   test: 10 zones × 30 tracks < 1 ms mean.
7. Extend the CLI to draw zones and print the incident list for a clip; add zone-based expectations for the sample
   clips to `data/eval/clips.yaml` (e.g. number of intrusion incidents) and an integration test using them.

**Gate.**
- `uv run pytest backend/tests/core/zones backend/tests/core/incidents -q` passes, perf test included.
- The integration test on sample clips yields the expected incident counts (±1, documented).

---

## Phase 5 — Explainability: Grad-CAM, EigenCAM, sanity evaluations

**Goal.** Per-detection explanations that are correct, fast and proven sane.

**Tasks.**
1. `core/xai/gradcam.py` per blueprint §7.1: letterbox exactly like the detector, forward with gradients through the
   model's raw head, anchor matching by IoU + class, backprop the class logit, hooks on the three neck outputs,
   combine scales, unletterbox. Handle YOLO26 (one-to-one head) and YOLO11 heads; if the one-to-one head blocks
   gradients usefully, use the auxiliary one-to-many branch when present; ADR whatever is done. Release hooks and
   free memory after each call.
2. `core/xai/eigencam.py` via `pytorch-grad-cam` or a 30-line own implementation (prefer own if it avoids a
   dependency).
3. `core/xai/worker.py`: background thread, priority queue, result cache keyed by (frame hash, box, class, method),
   timeout, writes overlay JPEG + JSON to `data/xai/`.
4. `backend/eval/xai_eval.py`: pointing game on 300 test detections, deletion check on 100, model randomisation
   check on 30 (§7.2), per-class breakdown, latency p50/p95 → `docs/eval/xai_report.md` with example grids generated
   to `docs/eval/figures/`.
5. Tests: map shape equals frame shape; for a synthetic image with one person, max heat lies inside the box; cache
   hit returns same result; worker handles 20 concurrent requests without leaking hooks (assert hook count back to
   zero).

**Gate.**
- `uv run pytest backend/tests/core/xai -q` passes.
- `docs/eval/xai_report.md` exists with all three checks measured. Pointing game ≥ 0.6 for `person` and the deletion
  check better than random (else document why and keep EigenCAM as the default method in the UI).
- Grad-CAM p50 latency recorded (target < 300 ms GPU; on CPU just record it).

---

## Phase 6 — Backend API, persistence, streaming, auth, reports

**Goal.** A FastAPI service that exposes everything in blueprint §8, running real pipelines.

**Tasks.**
1. `settings.py` (pydantic-settings, `config/default.yaml` + `VS_*` env), structured logging (`structlog`, JSON,
   rotating file), request IDs.
2. `db/`: SQLModel models for the tables in §8.2, Alembic initial migration, WAL mode, batched writer, minutely
   aggregates, retention job.
3. `services/`: `CameraManager` (start/stop pipelines, health, auto-restart), `ZoneService`, `IncidentService`,
   `AnalyticsService`, `ModelService` (reads registry and model.json), `ReportService` (WeasyPrint PDF + CSV),
   `UploadService` (runs the same pipeline on an uploaded file in a worker, progress via `/ws/events`).
4. Routers for every endpoint in §8.1, with Pydantic response models, cursor pagination, consistent error shape
   `{error: {code, message, details}}`.
5. WebSockets: `/ws/live` sends binary JPEG + JSON metadata for the same frame, back-pressure aware (drop frames for
   slow clients, client can request fps/quality); `/ws/events` for incidents/zone events/upload progress.
6. Auth: single admin from `VS_ADMIN_PASSWORD` on first run (argon2), session cookie, CSRF token for mutating
   requests, rate-limited login. Audit log for admin actions.
7. `/metrics` Prometheus text; `/health` reports pipeline status per camera.
8. Generate `frontend/src/lib/api/schema.ts` from OpenAPI (`openapi-typescript`) via `make api-types`.
9. Seed script: creates two cameras from the sample clips (looping file sources) and their sample zones, so the app
   is alive on first run. This is real inference on real video, not mock data.
10. Tests: every router (auth required, validation errors, happy path), WS integration (receive ≥ 10 frames with
    metadata from a file source), upload of a sample clip ⇒ unique count within the clip's expected ±1, PDF report
    generates and contains the incident count.

**Gate.**
- `uv run pytest backend -q -m "not slow"` passes; overall backend coverage ≥ 70%.
- `make dev` then `curl /api/v1/health` reports both seeded cameras `running` with fps > 0.
- `grep -rni "mock\|random\.\(randint\|uniform\|choice\)" backend/app` finds nothing outside tests and seeding of
  IDs.

---

## Phase 7 — Design direction and design system

**Goal.** A considered, non-generic industrial design language, written down before screens are built.

**Tasks.**
1. Re-read blueprint §9. Run **impeccable** to shape the direction for this product (an industrial safety control
   room used by safety officers on large screens and laptops); use its process for context gathering, then answer
   its questions yourself from the blueprint (you are unattended).
2. Run **Taste** guidance as a constraint pass: typography pairing, spacing rhythm, colour restraint, layout variance.
3. Run **Emil Kowalski** guidance for the motion spec: durations, easing curves, enter/exit patterns, toasts,
   drawers, press states, reduced motion.
4. Produce `DESIGN.md` at the repo root: principles, colour tokens (neutral scale + ISO 3864 state colours + zone
   colours, light and dark, all contrast-checked with numbers), type scale (with tabular figures), spacing, radii,
   elevation (borders over shadows), iconography, motion tokens, data-density rules, component inventory, do/don't
   list with the anti-slop rules from §9.4.
5. Implement tokens in `frontend/src/styles/tokens.css` (CSS variables) and wire Tailwind v4 `@theme` to them. Build
   primitives (Button, IconButton, Input, Select, Switch, Tabs, Table, Badge/StatusPill, Drawer, Dialog, Tooltip,
   Toast via Sonner, Kbd, EmptyState, Skeleton, SegmentedControl) on Radix where it gives accessibility for free.
6. A `/_design` route (dev only) rendering every primitive in both themes; Playwright screenshot of it at 1440 px in
   both themes saved to `frontend/e2e/__screenshots__/design/`. Review the screenshots yourself (open the image
   files), run impeccable critique on them, fix, repeat until it has no material findings (max 3 rounds).

**Gate.**
- `DESIGN.md` exists and every token in it exists in `tokens.css` (script check).
- `npm run test` and `npm run build` pass; the design route screenshots exist for both themes.
- Contrast script: all text/background token pairs used by primitives ≥ 4.5:1 (≥ 3:1 for large text and UI
  boundaries).

---

## Phase 8 — Frontend app: shell and screens

**Goal.** Every screen from blueprint §9.5 working against the real backend.

**Tasks.**
1. App shell: left rail (collapsible), status strip (alert level, cameras online, people now, unique today, open
   incidents, model name, fps), command palette (⌘K) for navigation and actions, theme toggle, login page.
2. Data layer: generated API types, TanStack Query hooks per resource, a single WS client with reconnect/backoff and
   a Zustand store for live state; optimistic updates for incident acknowledge/resolve.
3. **Live**: camera wall (1, 2, 2×2), `<VideoTile>` decoding JPEG frames into a canvas with an overlay layer drawn
   from metadata (person boxes, PPE chips, track IDs, zone polygons, toggles per layer), click-to-select person ⇒
   track card. Right panel: counts and open incidents.
4. **Incidents**: dense table with filters, keyboard shortcuts (j/k/a/r, / to search), detail drawer with evidence,
   timeline and notes (XAI panel slot is filled in Phase 9).
5. **Analytics**: uPlot time series (unique people per hour, occupancy), compliance per zone (bars), incidents by
   type and hour (heat grid), date range picker, CSV/PDF export buttons. Follow the dataviz conventions in
   `DESIGN.md` (one accent per series, direct labels, units).
6. **Model**: active model card, per-class metrics table, curves and confusion matrix images from
   `/model/figures`, run history from the registry, dataset summary, measured latency.
7. **Uploads**: drag-and-drop, progress, the same overlay player for results, summary (unique people, incidents),
   download annotated video.
8. **Settings**: cameras CRUD (with test-connection), thresholds grouped with a one-line explanation each, retention,
   privacy blur, password change.
9. Every screen has loading (skeletons), empty and error states written in plain language.
10. Vitest for stores, hooks and overlay geometry; Playwright smoke test visiting every route logged in.

**Gate.**
- `npm run lint && npm run typecheck && npm run test && npm run build` pass; initial route JS ≤ 250 KB gzip (report
  the number).
- Playwright smoke test passes against `make dev` with the seeded cameras: Live shows frames and person boxes within
  10 s; Incidents lists at least one real incident after the sample clips loop once.

---

## Phase 9 — Flagship interactions: zone editor and explainability panel

**Goal.** The two features v1 failed at feel like professional tools.

**Tasks.**
1. **Zone editor** (`features/zones/editor/`), state machine (idle → drawing → editing) implemented as a reducer with
   undo/redo history. Everything from blueprint §6.4: add points, close by clicking the first point or Enter, drag
   vertices with a visible hit radius, insert on edge click, delete vertex, move polygon, nudge with arrows, Esc,
   ⌘Z/⌘⇧Z, snapping to the frame edges, self-intersection prevented live with an inline message, zoom (wheel) and pan
   (space-drag) on the frozen frame, coordinates stored normalised. Pointer events + keyboard; works with touch.
2. Rule form beside the canvas (kind, rules, severity) with validation from `/zones/validate`; live preview of which
   current tracks would be inside (uses latest metadata); save applies to the running pipeline without restart;
   import/export YAML.
3. **Explainability panel** (`features/xai/`): from Incidents drawer and from a paused Live frame or an upload frame,
   click a box ⇒ request `/xai` ⇒ skeleton ⇒ original vs overlay with opacity slider, method toggle (Grad-CAM /
   EigenCAM), class + confidence, "energy in box" sentence, timing, "this alert was wrong" feedback.
4. Tests: Vitest for the editor reducer (every transition, undo/redo, validation), geometry helpers; Playwright e2e:
   draw a no-entry zone over the area where people walk in a seeded clip ⇒ an `intrusion` incident appears ⇒ open it
   ⇒ request Grad-CAM ⇒ heatmap shown ⇒ acknowledge ⇒ resolve. Edit a vertex by dragging and undo it.

**Gate.**
- Vitest and the zone/XAI e2e specs pass three times in a row (flake check).
- Keyboard-only run of the editor (Playwright, no mouse) can create and save a zone.

---

## Phase 10 — Playwright refinement loop

**Goal.** Make it look and feel like a standard industrial product, verified by screenshots, not by assumption.

**Tasks.**
1. `frontend/e2e/visual.spec.ts`: for every route, capture full-page screenshots at 1440, 1024, 768 and 390 px in
   dark and light themes with real seeded data (wait for live frames). Also capture key states: empty incidents,
   error toast, drawer open, editor mid-draw, XAI panel.
2. Review loop (max 4 rounds): open every screenshot image and look at it; run **impeccable** critique/audit on the
   set, the **Taste** checklist, and the **Emil Kowalski** motion review on recorded traces/videos of: incident
   arrival, drawer open/close, zone vertex drag, theme switch. Write findings to
   `docs/ui-review/round-<n>.md` (finding, screen, severity, fix). Fix all high/medium findings, re-capture.
3. Accessibility: `@axe-core/playwright` on every route, zero serious/critical; focus order and visible focus rings;
   `prefers-reduced-motion` honoured (test with emulation).
4. Responsive: no horizontal scroll at 390 px; Live wall collapses to one column; tables become stacked rows on
   small screens.
5. Performance: Lighthouse-style check via Playwright tracing on Live (no long tasks > 100 ms while streaming two
   tiles at 15 fps; canvas draw < 4 ms per frame, measured).
6. Store final screenshots as Playwright baselines (`toHaveScreenshot`, with masks for live video areas) and copy a
   curated set to `docs/screenshots/` for the README.
7. Ask impeccable to update `DESIGN.md` from what actually shipped (documenter pass) so the doc matches reality.

**Gate.**
- `npx playwright test` (all specs, chromium) passes; axe: 0 serious/critical.
- The final `docs/ui-review/round-<n>.md` has no open high/medium findings.
- `docs/screenshots/` contains Live, Incidents, Zones editor, XAI panel, Analytics, Model in dark and light.

---

## Phase 11 — Integration, performance, hardening, Docker, CI

**Goal.** It runs reliably for hours, starts with one command, and CI proves it on every push.

**Tasks.**
1. **Finish Phase 2** if still open (collect training results, reports, export, swap the active model) and re-run
   the counting and XAI evals with the final weights; update their reports.
2. Performance pass: measure per-stage latency and end-to-end FPS for 1 and 4 file-source cameras on CPU (and GPU if
   present) → `docs/eval/performance.md`. Optimise the top two bottlenecks (e.g. frame resize before inference,
   ONNX Runtime on CPU if faster, JPEG encode with `cv2.IMWRITE_JPEG_QUALITY` and reuse buffers). Compare against
   blueprint §2.5 targets; state pass/fail honestly.
3. Soak test: 60-minute run with 2 looping cameras; record memory, fps, DB size, open file handles over time
   (sampled each minute) and show they are flat. Fix leaks.
4. Failure handling: camera disconnect/reconnect, corrupt upload, model file missing (clear error page, not a crash),
   DB locked, full disk on snapshots (stop saving, raise a system alert).
5. Security pass: run the security-review skill if available; check auth on every route, CSRF, upload size/type
   limits, path traversal on file endpoints, CORS locked to the frontend origin, secure headers.
6. Docker: `backend/Dockerfile` (multi-stage, CPU torch, non-root, healthcheck), optional `Dockerfile.cuda`,
   `frontend/Dockerfile` (build → nginx), `docker-compose.yml` with volumes for `data/` and `models/`. Verify
   `docker compose up` works if Docker is available; otherwise verify the images build with `docker build` or record
   that Docker is unavailable and test the non-Docker quick start in a clean venv instead.
7. CI: full `ci.yml` (lint, typecheck, backend tests with nano weights cached, frontend tests, build, Playwright e2e
   with the backend started in file-source mode, upload Playwright report). Push and make CI green (read the job logs
   through the GitHub tools when it fails).

**Gate.**
- `docs/eval/performance.md` and the soak test chart exist; no memory growth > 10% over the soak window.
- CI green on the latest push.
- Fresh-clone quick start (README steps) works in a clean directory.

---

## Phase 12 — Docs, final audit, release v2.0.0

**Goal.** Anyone (including a college panel) can install, use, evaluate and extend it.

**Tasks.**
1. `README.md`: what it is, screenshots, 2-minute quick start (Docker and non-Docker), feature list with honest
   status, key results table (detector metrics, counting error, XAI checks, fps), links to docs.
2. `docs/architecture.md` (diagrams as Mermaid: components, per-frame data flow, incident state machine, zone
   membership hysteresis), `docs/api.md` (generated from OpenAPI + WS message formats), `docs/user-guide.md`
   (officer and admin tasks with screenshots), `docs/operations.md` (config reference for every setting, backups,
   retention, upgrading the model, troubleshooting), `docs/training.md` (how to add data, retrain, evaluate and
   promote a model, including the Colab notebook).
3. A short `docs/report-appendix.md` the student team can lift into their college report: problem → method →
   results tables and figures, comparison with v1, limitations, future work. Only measured numbers.
4. **Final audit**: walk blueprint §13 item by item and every MUST in the blueprint; write `docs/FINAL_AUDIT.md` with
   pass/fail/evidence links for each. Fix what can be fixed now (including any `blocked` or `done-with-fallbacks`
   phases and `followups` in build_state.json). Anything still failing is listed honestly with the reason.
5. Run the full suite one last time: `make lint test e2e`, plus `make eval` if time allows.
6. `CHANGELOG.md` → `[2.0.0]`, tag `v2.0.0`, push the tag. Write the final BUILD_LOG entry with an executive summary
   at the top of `docs/BUILD_LOG.md` (what was built, headline numbers, what remains).

**Gate.**
- `docs/FINAL_AUDIT.md` exists and every blueprint §13 checkbox is either checked with evidence or explained.
- All phases in `docs/build_state.json` are `done` or `done-with-fallbacks` with reasons.
- Tag `v2.0.0` exists on the remote.
