# Vision Sentinel 2.0 — Master Blueprint

> Real-time industrial safety monitoring: PPE compliance, polygon-zone intrusion detection and explainable AI.
> This document is the single source of truth for *what* we are building and *why*. The companion file
> [`BUILD_PROMPTS.md`](../BUILD_PROMPTS.md) says *how*, phase by phase.

Version 1.0 · 2026-10-22 · Owner: Param S N

---

## 0. How to read this document

| Section | Read it when |
|---|---|
| 1. Why 2.0 exists | You want to know what was wrong with v1 and what "fixed" means |
| 2. Product definition | You need the scope, users and the acceptance bar |
| 3. Architecture | You are writing code |
| 4–8. Subsystem specs | You are building that subsystem |
| 9. UI/UX direction | You are touching the frontend |
| 10. Quality, testing, records | You are about to call a phase done |
| 11. Repo layout | You are creating files |
| 12. Risks and fallbacks | Something is not working as planned |
| 13. Definition of done | You think the project is finished |

Words like **MUST**, **SHOULD**, **MAY** are used deliberately. A MUST is an acceptance gate.

---

## 1. Why 2.0 exists (audit of v1)

v1 (`paramsn37-sketch/VISION-SENTINAL-FINAL`) was read for context only. Nothing is carried over. The audit
found these root causes behind the five problems you described:

| # | Your complaint | Root cause found in v1 | What 2.0 does instead |
|---|---|---|---|
| 1 | "Every second it sees a person it counts 1" | `web/app.py` sums people **per frame** (`workers = len(all_dets)` across sampled frames); `vision_sentinel.py` increments `total_violations` every frame a violation is visible. No notion of identity over time. | Multi-object tracking gives every person a stable **track ID**. "People" = distinct *confirmed* tracks. Violations become **incidents** with a start and an end, deduplicated per person, per rule, per zone. Counting accuracy is measured against ground truth (MOT17). |
| 2 | Generic "AI slop" UI | Template dashboard (glow cards, gradients, uppercase micro-labels, decorative icons), no design system. | An industrial control-room design language built with the impeccable, Emil Kowalski and Taste skills, refined with Playwright screenshots. Documented in `DESIGN.md`. |
| 3 | YOLO11 "barely worked" | `config.yaml` loads the **stock COCO `yolo11m.pt`** but labels its outputs with PPE class names. A COCO model has no helmet/vest classes, so PPE detection could never work. The upload page uses a **random mock** (`random.Random(seed)` in `web/app.py`), not the model. | A detector **trained by us** on merged PPE datasets, with a fixed class taxonomy, full training logs, per-class metrics and a model card. Every inference path calls the real model. |
| 4 | Grad-CAM and intrusion "look like a drawing page" | The zone page is static JSX with dead tool buttons; zones are in absolute pixels for one resolution; intrusion uses the box **centre** (wrong for floor zones). Grad-CAM backpropagates through post-NMS outputs, which does not produce a valid class-discriminative map. | A real polygon editor (draw, drag vertices, insert/delete points, snap-close, undo) on the live camera frame with **normalised coordinates**; intrusion tests the person's **foot point** with entry/exit hysteresis. Grad-CAM is computed on the raw head output for the exact anchor behind a detection, and its quality is measured (pointing game). |
| 5 | No logs, tests, records or docs | No training runs, one smoke test, no CI. | Every phase writes to `docs/BUILD_LOG.md`; training writes a run registry, metrics, curves and a model card; pytest + Vitest + Playwright in CI; decision records; user and developer docs. |

**Interpretation note.** "Intrusion detection using p2p" is read as **point-in-polygon** (the geometric test that
decides whether a person is inside a zone). If something else was meant, it is a contained change in §6.

---

## 2. Product definition

### 2.1 One-line pitch
A lightweight, self-hosted safety console that watches one to four cameras, knows **who** is on site (as anonymous
tracks, not faces), **what PPE** each person wears, **where** they are relative to hazard zones, and can **show why**
the AI raised every alert.

### 2.2 Users
- **Safety officer (primary).** Watches live feeds, acknowledges and resolves incidents, exports shift reports.
- **Site admin.** Adds cameras, draws zones, sets rules and thresholds, reviews model performance.
- **Evaluator (college review panel).** Needs the metrics, logs, tests and explanations to be inspectable.

### 2.3 In scope (v2.0)
1. Sources: webcam, video file, RTSP/HTTP stream, image upload. Up to 4 concurrent streams on a laptop GPU, 1 on CPU.
2. Detection of person + PPE (taxonomy in §4.2) with a model we trained.
3. Tracking and **unique person counting**; current occupancy; per-zone occupancy and dwell time.
4. Per-person PPE state with temporal smoothing (present / absent / unknown).
5. Polygon zones with rules: *no entry*, *PPE required*, *max occupancy*, *max dwell*. Entry/exit events.
6. Incidents: lifecycle `open → acknowledged → resolved` with evidence snapshot, track ID, zone, rule, duration.
7. Explainability: Grad-CAM (and EigenCAM fallback) per detection, on demand and auto-attached to incidents.
8. Analytics: unique people over time, compliance rate, incidents by type/zone/hour.
9. Model page: training runs, metrics, curves, confusion matrix, dataset card, live inference speed.
10. Shift report export (PDF + CSV).
11. Single-admin authentication (local), audit log of admin actions.
12. Docs, tests, CI, Docker compose.

### 2.4 Out of scope (explicitly)
Face recognition or any biometric identity; cross-camera re-identification; mobile app; cloud multi-tenant; IoT sensors;
SMS/email delivery (a webhook hook point is provided instead). These are listed in `docs/ROADMAP.md`.

### 2.5 Non-functional targets
| Area | Target (MUST unless marked SHOULD) |
|---|---|
| Throughput | ≥ 25 FPS on one 720p stream on an RTX 3050-class GPU; ≥ 8 FPS on a modern 8-core CPU with the nano model at 640 px (SHOULD) |
| Latency | Detection → incident visible in UI < 1.0 s |
| Counting | Unique-count absolute error ≤ 10% on the evaluation sequences (§5.6); IDF1 reported |
| Detector | mAP50 ≥ 0.80 for `person`, ≥ 0.70 for `helmet`/`head`/`vest` on our held-out test split (SHOULD; actual numbers are recorded whatever they are) |
| Grad-CAM | < 300 ms per explanation on GPU; pointing-game hit rate reported |
| Footprint | Backend image < 2.5 GB (CPU torch); frontend JS < 250 KB gzipped for the initial route |
| Install | `docker compose up` or two commands without Docker |
| Privacy | No faces stored by default; snapshots blurred above the shoulders is a setting (SHOULD); retention setting |
| Accessibility | WCAG 2.2 AA contrast, keyboard operable, reduced-motion respected |

---

## 3. Architecture

### 3.1 Shape
One Python process (FastAPI) owns the vision pipeline and the API; one static React app talks to it over REST +
WebSocket. SQLite stores everything durable. No message broker, no Redis, no Postgres: that is what "lightweight"
means here. Each heavy part sits behind an interface so it can be swapped later.

```
            ┌──────────── Browser (React + Vite, static) ───────────────┐
            │ Live · Incidents · Zones · Analytics · Model · Settings    │
            │  canvas overlays drawn client-side from metadata           │
            └──────▲─────────────────────────▲───────────────────────────┘
          REST/JSON│                WebSocket│ (frames as JPEG + per-frame JSON)
┌─────────────────┴──────────────────────────┴──────────────────────────────┐
│ FastAPI app (uvicorn, single worker)                                     │
│  api/ routers ── services/ ── db (SQLModel + SQLite, WAL)                │
│                     │                                                    │
│  ┌──────────────────▼──────────────── Pipeline per camera (thread) ────┐ │
│  │ Source → Detector → Tracker → PPE Associator → Zone Engine →        │ │
│  │   Incident Manager → EventBus ──► WS broadcaster, DB writer          │ │
│  │                         └────► XAI worker (Grad-CAM, async queue)   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Technology choices (with reasons)
| Concern | Choice | Why | Fallback |
|---|---|---|---|
| Language/runtime | Python 3.11, `uv` for env/locks | fast, reproducible | pip + requirements.txt export |
| Detector | Ultralytics **YOLO26** (n or s), fine-tuned | NMS-free head, built for edge/CPU, same training API | YOLO11n/s if YOLO26 is not available in the installed `ultralytics` |
| Tracker | **ByteTrack** via Ultralytics tracker config (BoT-SORT optional) | strong IDF1 with low cost; no ReID model needed | `supervision.ByteTrack` |
| Geometry | `shapely` 2.x (prepared polygons) | robust, fast, tested | `cv2.pointPolygonTest` |
| XAI | Own Grad-CAM on raw head output; EigenCAM via `pytorch-grad-cam` | class-discriminative per detection; EigenCAM is gradient-free and robust | EigenCAM only |
| API | FastAPI + Pydantic v2 + uvicorn | typed, OpenAPI for free, WebSockets | — |
| DB | SQLite (WAL) via SQLModel; Alembic migrations | zero-ops, file-based | — |
| Frontend | React 19 + TypeScript + Vite, TanStack Query, Zustand (tiny), React Router | standard, small | — |
| Styling | Tailwind CSS v4 with CSS variables from `DESIGN.md` tokens; Radix primitives for a11y | design tokens enforce consistency | plain CSS modules |
| Motion | CSS transitions + `motion` (only where springs are needed), Sonner for toasts | Emil Kowalski motion principles | CSS only |
| Charts | uPlot (time series) + small hand-rolled SVG bars | 40 KB vs 400 KB | Recharts if needed |
| Reports | WeasyPrint (HTML → PDF) | reuse UI templates | ReportLab |
| Tests | pytest, hypothesis, httpx; Vitest + Testing Library; Playwright (e2e + screenshots + axe) | — | — |
| Lint/type | ruff, mypy (strict on `core/`), ESLint, `tsc --noEmit` | — | — |
| Packaging | Docker compose (backend CPU image, optional CUDA image; nginx serving the built frontend) | one-command run | `make dev` |

**Licence note.** Ultralytics is AGPL-3.0. Fine for an academic/open project; if this ever ships commercially it
needs an Ultralytics enterprise licence or a switch to an Apache-licensed detector (e.g. RT-DETR via HF). Recorded in
`docs/DECISIONS.md`.

### 3.3 Data contracts (the backbone everything shares)
Defined once in `backend/app/core/types.py` (Pydantic) and mirrored to TypeScript by generating types from OpenAPI
(`openapi-typescript`). No hand-copied types.

```python
class Detection:      # one box from the detector, one frame
    cls: str; conf: float; xyxy: tuple[float,float,float,float]   # pixels
class PersonState:    # one tracked person, updated each frame
    track_id: int; xyxy; foot_point: tuple[float,float]
    first_seen: float; last_seen: float; age_frames: int; confirmed: bool
    ppe: dict[str, Literal["present","absent","unknown"]]
    ppe_conf: dict[str, float]; zones: list[str]
class FrameResult:    # what the pipeline emits per processed frame
    camera_id: str; frame_idx: int; ts: float; width: int; height: int
    persons: list[PersonState]; objects: list[Detection]   # non-person detections
    counts: Counts    # current, unique_total, per_zone
    fps: float; latency_ms: float
class ZoneEvent:      # entered / exited
class Incident:       # id, camera_id, track_id, zone_id|None, rule, severity,
                      # status, started_at, last_seen_at, ended_at, peak_conf,
                      # snapshot_path, xai_path|None, notes
```

### 3.4 Runtime model
- One **pipeline thread per camera**. A bounded queue of size 1 between capture and inference: we always process the
  newest frame and drop stale ones (live monitoring prefers freshness over completeness). For **video files** the
  pipeline processes every frame (or every Nth, configured) so counts are reproducible.
- An `EventBus` (in-process, `asyncio` queues) fans out `FrameResult`, `ZoneEvent` and `Incident` changes to the WS
  broadcaster and a batched DB writer (flush every 500 ms).
- The XAI worker is a single background thread with a priority queue (user-requested > incident auto-attach).
- Model weights are loaded once and shared; inference uses `torch.inference_mode()` and FP16 on CUDA.

---

## 4. Detection model

### 4.1 Principles
- **Person-centric.** We detect people and the PPE items or bare body parts that prove presence or absence. A
  violation is a property of a *tracked person over time*, never of a single box in a single frame.
- **Positive evidence for absence.** "No helmet" is learned as a visible bare `head`. Missing vest/gloves/boots is
  inferred only when the relevant body region is visible enough (see §5.4), otherwise the state is `unknown`. This is
  what stops the false-alarm flood.

### 4.2 Class taxonomy (v2.0, 9 classes — revised in Phase 1, see ADR-0006)
| id | class | meaning | mapped from |
|---|---|---|---|
| 0 | person | full or partial human | Construction-PPE `Person`, Open Images `Person` |
| 1 | head | bare head (no hard hat) | Construction-PPE `no_helmet`, Open Images `Human head` |
| 2 | helmet | hard hat on a head | Construction-PPE `helmet` |
| 3 | vest | high-visibility vest | Construction-PPE `vest` |
| 4 | gloves | gloves on hands | Construction-PPE `gloves`, Open Images `Glove` |
| 5 | hand | bare hand | Construction-PPE `no_gloves`, Open Images `Human hand` |
| 6 | boots | safety boots / footwear | Construction-PPE `boots`, Open Images `Boot` |
| 7 | goggles | eye protection | Construction-PPE `goggles`, Open Images `Goggles` |
| 8 | no_goggles | visible eyes without protection | Construction-PPE `no_goggle` |

The original plan had a `mask` class; no reachable source had mask boxes, so it moved to the roadmap.
`no_boots`, `NO-Safety Vest` and other negative labels from source sets are **dropped** (they are inconsistent
across datasets); absence for those items is inferred by the associator. The mapping lives in
`training/configs/class_map.yaml` and is unit-tested (every source class is either mapped or explicitly dropped).

### 4.3 Data sources and plan
| Source | Access | Use |
|---|---|---|
| Ultralytics **Construction-PPE** (1,416 imgs, 11 classes, AGPL-3.0) | auto-download, no key | core PPE set; always available |
| **Hard Hat Workers** (Roboflow Universe / public mirror, ~7k imgs, head/helmet/person) | Roboflow key or public export | head vs helmet, crowded scenes |
| **SH17** (Kaggle, 8,099 imgs, 17 classes, CC BY-NC-SA 4.0) | Kaggle key | gloves/hands/boots/goggles/mask diversity, manufacturing scenes |
| **Construction Site Safety** (Roboflow/Kaggle) | key | extra helmet/vest/person |
| **Open Images V7** (via FiftyOne zoo) | public | `Person`, `Helmet`, `Glove`, `Goggles` in non-construction places for robustness; capped per class |
| Our own hard negatives | generated | frames with no people (warehouses, empty sites) to suppress false persons |

Rules:
- Credentials come from env vars (`KAGGLE_USERNAME`, `KAGGLE_KEY`, `ROBOFLOW_API_KEY`). Missing keys ⇒ that source is
  skipped and the skip is logged. The pipeline MUST still produce a trained model from public sources alone.
- Merge pipeline: download → convert to YOLO format → remap classes → drop images with zero kept labels (except
  curated negatives ≤ 10%) → perceptual-hash dedup across sources (pHash, Hamming ≤ 6) → **leak-free split** by source
  group (70/15/15), test split frozen and hashed (`data/manifests/test_manifest.sha256`).
- `data/DATASET_CARD.md` records per-source counts, per-class instance counts, image size stats, licences, and
  known biases (e.g. few night scenes). Datasets themselves are never committed (`.gitignore`), only manifests.
- Licence compatibility: SH17 is NC. The trained weights are therefore for non-commercial/academic use; recorded.

### 4.4 Training plan
- Baselines recorded first on our test split: (a) the v1 setup (stock COCO `yolo11m.pt`, person only) to quantify
  the improvement, (b) stock YOLO26n person-only.
- Main runs: YOLO26n @640 and YOLO26s @640, COCO-pretrained init; 100–150 epochs with early stopping (patience 25),
  cosine LR, mosaic off for the last 10 epochs, `close_mosaic=10`, AMP, seed fixed. Class-imbalance handled by
  per-source sampling caps rather than loss hacks.
- Small objects (gloves, goggles) SHOULD get a 960 px fine-tune run if GPU budget allows; recorded either way.
- **Compute adaptivity.** The build probes hardware. With a CUDA GPU: full plan. Without one: train YOLO26n at
  416–512 px on a stratified subset for a fixed wall-clock budget (default 3 h), mark the model card
  `trained_on: cpu-budget`, and ship `training/notebooks/train_colab.ipynb` + `training/scripts/train.py` so the full
  run can be repeated on Colab/Kaggle GPUs with the same configs. The app works with either weight file.
- Selection: best `mAP50-95` on val, ties broken by CPU latency. Final numbers are reported **on test only once**.

### 4.5 Training records (MUST exist after the training phase)
```
training/
  runs/<run_id>/            # Ultralytics output: results.csv, args.yaml, weights/best.pt, *.png curves
  registry.json             # one entry per run: id, git sha, data manifest hash, model, imgsz, epochs,
                            # hardware, wall time, best epoch, val + test metrics per class
  reports/
    MODEL_CARD.md           # intended use, data, metrics table, limits, licence
    training_report.md      # narrative: what was tried, what won, plots embedded, error analysis
    figures/                # loss curves, PR curves, confusion matrix, per-class AP bars, speed table
    error_analysis/         # 50 worst false positives/negatives with thumbnails + notes
  benchmarks/latency.json   # ms/frame per device, imgsz, model, format (PyTorch, ONNX)
```
The app's **Model** page reads `registry.json` and the figures, so the evaluator can see training history in the UI.

Exports: `best.pt` (committed via Git LFS if > 50 MB, otherwise directly; nano/small are ~6–20 MB) and `best.onnx`.

---

## 5. Tracking, counting and PPE state (fixes complaint #1)

### 5.1 Tracker
ByteTrack with tuned config in `backend/app/core/tracking/bytetrack.yaml`: `track_high_thresh 0.5`,
`track_low_thresh 0.1`, `new_track_thresh 0.6`, `track_buffer` = 2 s × fps, `match_thresh 0.8`. Only `person`
boxes feed the tracker; PPE boxes are associated, not tracked.

### 5.2 Track confirmation
A track becomes **confirmed** after it is seen in ≥ `min_hits` frames (default 5) *and* ≥ `min_age_s` (default
0.5 s). Unconfirmed tracks never count and never raise incidents. This kills flicker IDs.

### 5.3 Counts
| Metric | Definition |
|---|---|
| `current` | confirmed tracks visible in this frame |
| `unique_total` | number of distinct confirmed track IDs since the session/shift started |
| `per_zone.current` | confirmed tracks whose foot point is inside the zone now |
| `per_zone.unique` | distinct confirmed tracks that ever entered the zone |
| `dwell_s` | per track, per zone, accumulated time inside |
| `line_in / line_out` (SHOULD) | optional counting line: direction-aware crossings, for gates |

**ID-switch mitigation.** A lost track that reappears within `reid_window_s` (default 1.5 s) with IoU ≥ 0.3 to its
predicted box and a matching colour histogram (HSV, torso crop, Bhattacharyya < 0.35) is **merged** back into the old
ID instead of counting a new person. Cheap, no ReID network. Documented as a heuristic with measured effect.

### 5.4 PPE association and temporal state
1. For each confirmed person box, derive regions: head (top 25%), torso (25–60%), hands (whole box, side bands),
   feet (bottom 15%).
2. Assign each PPE/body-part detection to at most one person: highest score of `IoA(item, region) × conf`, with
   IoA ≥ 0.5. Unassigned items are reported as loose objects.
3. Per frame, per item, an *observation*: `present` (item found), `absent` (matching bare-part found: `head`,
   `hand`, `no_goggles`; or for the vest, torso region visible ≥ 60% and ≥ 48 px tall with no vest), `unknown`
   (region too small, occluded by another person box, or out of frame).
4. Per track, per item, an exponential evidence score `s ← λ·s + (1−λ)·obs` over present/absent (unknown leaves `s`
   unchanged), λ = 0.85. State switches with **hysteresis**: absent when `s ≤ 0.3`, present when `s ≥ 0.7`.
5. A PPE violation fires only when the state has been `absent` for ≥ `violation_min_s` (default 2 s) for an item the
   person's current zone (or the site default) requires.

### 5.5 Incidents (dedup by construction)
- Key: `(camera_id, track_id, rule, zone_id)`. While an incident with that key is open, new frames only update
  `last_seen_at` and `peak_conf`. The incident closes after the condition is false for `clear_s` (default 3 s) or the
  track is lost. If the same condition re-occurs within `cooldown_s` (default 30 s) the incident is reopened, not
  duplicated.
- On open: save one evidence JPEG (best-confidence frame in the first second), enqueue Grad-CAM for the triggering
  detection.
- Severity = zone severity × rule weight. Alert level for the UI: green (no open incidents), amber (open low/medium),
  red (any open high).

### 5.6 Measuring it (MUST)
`backend/eval/counting_eval.py`:
- Runs the pipeline (person class) on MOT17 training sequences (`MOT17-02`, `-04`, `-09` FRCNN, downloaded by script)
  and computes **IDF1, MOTA, ID switches** (via `motmetrics`) and **unique-count error** = |pred unique − GT unique|
  / GT unique.
- Also runs on 2–3 short public-licence industrial clips with hand-labelled unique counts in
  `data/eval/clips.yaml`.
- Writes `docs/eval/counting_report.md` with a before/after table: naive per-frame sum (v1 behaviour) vs tracker vs
  tracker + confirmation + merge. This table is the proof that complaint #1 is fixed.

---

## 6. Zones and intrusion detection (fixes complaint #4, part 1)

### 6.1 Zone model
```yaml
id: z_7f3a            # uuid
camera_id: cam_1
name: "Substation A"
kind: restricted | ppe_required | hazard
polygon: [[0.12,0.40],[0.48,0.38],[0.51,0.92],[0.10,0.95]]   # normalised 0..1, clockwise
rules:
  no_entry: true
  required_ppe: [helmet, vest]
  max_occupancy: 3
  max_dwell_s: 120
  active_hours: "06:00-22:00"   # optional
severity: high | medium | low
color: token name, not hex     # e.g. "zone-high"
```
Normalised coordinates make zones resolution-independent. Polygons are validated (≥ 3 points, non-self-intersecting via
`shapely.is_valid`, area > 0.1% of frame). Stored in SQLite; YAML import/export for backups.

### 6.2 Point-in-polygon test
- The test point is the **foot point** = bottom-centre of the person box, slightly raised (`y2 − 0.05·h`). For
  ceiling-mounted top-down cameras the camera setting switches to box centre.
- Prepared shapely polygons per zone; for > 20 zones a simple bbox pre-filter. Target < 1 ms for 10 zones × 30 people.
- **Entry/exit hysteresis:** a track is *inside* after `enter_frames` (default 3) consecutive inside results, and
  *outside* after `exit_frames` (default 5). Optional inward buffer of 2% of frame width to stop boundary jitter.

### 6.3 Rules → events → incidents
| Rule | Fires when | Incident type |
|---|---|---|
| no_entry | confirmed track is inside | `intrusion` |
| required_ppe | inside and item state `absent` ≥ `violation_min_s` | `ppe_missing:<item>` |
| max_occupancy | `per_zone.current > max` for ≥ 2 s | `overcrowding` (track_id = null) |
| max_dwell_s | dwell of a track > limit | `dwell_exceeded` |
| site default | outside all zones, site-level required PPE missing | `ppe_missing:<item>` (zone = null) |

### 6.4 Zone editor (UI contract, details in §9.5)
Draw on a frozen frame from the selected camera; click to add points, click first point or press Enter to close,
drag vertices, click an edge to insert a vertex, Delete/Backspace removes the selected vertex, Esc cancels, ⌘Z/⌘⇧Z
undo/redo, shift-drag to move the whole polygon, arrow keys nudge 1 px (shift = 10 px). Live preview shows which
current tracks would be inside. Validation errors are inline. Saved zones take effect without restarting the pipeline.

---

## 7. Explainability (fixes complaint #4, part 2)

### 7.1 Method
- **Grad-CAM for a specific detection.** Run the model with gradients enabled on the letterboxed input, take the
  **raw head output before any NMS/top-k** (`[1, 4+nc, N_anchors]` for YOLO11; for YOLO26's one-to-one head, the
  pre-selection logits). Find the anchor whose decoded box has the highest IoU with the chosen detection and the same
  class. Backpropagate that anchor's class logit. Hook the three neck outputs feeding the head (P3/P4/P5), compute
  Grad-CAM on each (`ReLU(Σ_k α_k A_k)` with α = spatially averaged gradients), upsample to input size, combine as a
  weighted sum (weights = gradient energy), remove letterbox padding, map back to the original frame.
- **EigenCAM** (first principal component of the activations) as a fast, gradient-free fallback and for a whole-frame
  "what is the model attending to" view.
- Output: heatmap (uint8, same size as frame), overlay JPEG, and a JSON with `target_class`, `target_box`, `layers`,
  `method`, `energy_in_box` (share of positive heat inside the box), `ms`.

### 7.2 Sanity and quality checks (MUST)
- **Pointing game**: share of explanations whose maximum lies inside the target box, on 300 test-set detections.
- **Deletion check**: masking the top-20% heat region must lower the target confidence more than masking a random
  20% region (averaged over 100 samples).
- **Model randomisation check** (Adebayo et al.): maps from randomised weights must differ (SSIM < 0.5) from maps of
  the trained model.
- Results in `docs/eval/xai_report.md` with example grids (correct helmet, bare head, vest, a false positive).

### 7.3 UX
In Incidents and Live (paused frame): click a person or item → side panel shows original, heatmap overlay with an
opacity slider, the method toggle (Grad-CAM / EigenCAM), the energy-in-box number in plain language ("82% of the
model's attention for *head* was inside this box"), and a "this alert was wrong" button that stores feedback for
the next training round (`data/feedback/`).

---

## 8. Backend API

### 8.1 Endpoints (prefix `/api/v1`)
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login`, `/auth/logout` | session cookie (httpOnly, SameSite=Lax), argon2 password hash |
| GET/POST/PATCH/DELETE | `/cameras` | sources; `POST /cameras/{id}/start|stop`; `GET /cameras/{id}/snapshot` |
| GET/POST/PATCH/DELETE | `/zones` (`?camera_id=`) | CRUD + `POST /zones/validate` + `GET /zones/export` + `POST /zones/import` |
| GET | `/incidents` | filter by status, type, zone, camera, time; cursor pagination |
| PATCH | `/incidents/{id}` | acknowledge / resolve / note |
| GET | `/incidents/{id}/evidence`, `/incidents/{id}/xai` | images |
| POST | `/xai` | `{camera_id|upload_id, frame_ref, box, class, method}` → job; `GET /xai/{job_id}` |
| POST | `/uploads` | image/video for offline analysis; `GET /uploads/{id}/result` (real model, never mock) |
| GET | `/analytics/summary`, `/analytics/timeseries` | counts, compliance, incidents |
| GET | `/model/runs`, `/model/active`, `/model/figures/{name}` | from `training/registry.json` |
| GET | `/reports/shift?from=&to=&format=pdf|csv` | export |
| GET | `/health`, `/metrics` | liveness; Prometheus text format (fps, latency, queue depth) |
| WS | `/ws/live?camera_id=` | binary JPEG frames + JSON `FrameResult`; client can request lower fps/quality |
| WS | `/ws/events` | incident and zone events for toasts and counters |

### 8.2 Persistence (SQLite tables)
`users, cameras, zones, tracks (summary per track: first/last seen, zones visited, ppe summary), zone_events,
incidents, xai_results, uploads, settings, audit_log`. Per-frame data is **not** stored (only aggregates per minute in
`counts_minutely`) to keep the DB small. Retention job deletes snapshots older than `retention_days` (default 30).

### 8.3 Config
`config/default.yaml` + env overrides (`VS_*`) via `pydantic-settings`. All thresholds from §5–§6 are config, with
the defaults above, and editable in Settings (validated server-side).

---

## 9. UI/UX direction (fixes complaint #2)

### 9.1 Skills and how they are used
| Skill | Role in the build |
|---|---|
| **impeccable** (pbakaus) | Sets the design direction, writes `DESIGN.md` + tokens, critiques and audits each screen, polishes, removes slop. |
| **Emil Kowalski design engineering** (emilkowalski/skill) | Motion and interaction craft: durations, easing, enter/exit, toasts (Sonner), press feedback, no gratuitous animation. |
| **Taste** (Leonxlnx/taste-skill) | Anti-generic guardrails: typography, spacing rhythm, colour restraint, layout variance; used as a checklist in review passes. |
| **Playwright** | Screenshots at 1440/1024/768/390 px in light and dark, interaction scripts for the zone editor and incident flow, axe accessibility scans, visual-regression baselines. |

If a skill cannot be installed in the build environment, the build records that in `docs/BUILD_LOG.md` and applies
the principles summarised in §9.2–§9.4 directly.

### 9.2 Visual language: "modern control room"
- **Mood:** calm, dense, legible from two metres. Think SCADA/HMI done with care (ISA-101 high-performance HMI
  principle: greyscale by default, colour only means state).
- **Colour:** neutral greys carry the UI. Safety colours follow ISO 3864 semantics and are reserved for state:
  red = danger/open high incident, amber = warning, green = compliant/ok, blue = information/selection.
  No gradients, no glows, no glassmorphism, no purple.
- **Theme:** dark default (control rooms), light theme fully supported. Contrast AA minimum, AAA for numbers on the
  live wall.
- **Type:** one grotesk for UI (e.g. *Inter Tight* or *IBM Plex Sans*), one mono for numbers, IDs and timestamps
  (*JetBrains Mono* / *IBM Plex Mono*), tabular figures everywhere numbers change. Sentence case labels, no
  all-caps micro-labels with wide tracking.
- **Layout:** 8 px grid, 4 px half-steps; dense tables (36 px rows); left rail navigation collapsible to icons;
  a persistent status strip (site alert level, cameras online, current people, open incidents, model, fps).
- **Iconography:** one set (Lucide), 16/20 px, only where it speeds recognition.

### 9.3 Motion (Emil Kowalski principles)
- Purposeful only: state changes, spatial continuity, feedback. 120–200 ms for UI, 250–300 ms for panels; ease-out
  for enter, ease-in for exit; never animate layout of the live video.
- New incident: row slides in 8 px + fades (180 ms), the status strip pulses once (not looping). Red never blinks
  forever.
- Buttons have a 0.97 press scale; drawers use spring with no overshoot; `prefers-reduced-motion` disables
  non-essential motion.

### 9.4 Anti-slop rules (checked in every UI review)
No emoji in UI; no "AI-powered" badges; no stat cards with giant numbers and trend arrows unless the trend is real;
no lorem; no placeholder charts; every empty state says what to do next; every number has a unit; every timestamp is
relative + absolute on hover; every destructive action is undoable or confirmed.

### 9.5 Screens
| Screen | Content |
|---|---|
| **Live** | 1/2/2×2 camera wall; each tile: video, client-drawn boxes (person outline, PPE chips: helmet ✓ vest ✗), zone polygons at 20% fill, track ID labels, fps. Right panel: people now, unique today, open incidents list. Click a person → track card (time on site, zones visited, PPE state timeline, explain button). |
| **Incidents** | Dense table with filters, keyboard navigation (j/k, a = acknowledge, r = resolve). Detail drawer: evidence image, Grad-CAM panel, timeline, notes, audit. |
| **Zones** | Camera picker → frozen frame canvas editor (§6.4) + zone list + rule form. Live "would trigger" preview. |
| **Analytics** | Unique people per hour, compliance % per zone, incidents by type, peak occupancy; date range; export. |
| **Model** | Active model card, metrics table per class, curves, confusion matrix, run history, dataset card, latency. |
| **Uploads** | Drop an image/video, see the same overlays, counts and incidents as live, download annotated output. |
| **Settings** | Cameras, thresholds (with explanation of each), retention, privacy blur, account. |

### 9.6 Video transport
Server sends compressed JPEG (quality 70, max 1280 px wide) over WebSocket at up to 15 fps per tile plus the JSON
metadata of the *same* frame; the browser draws overlays on a canvas so they stay crisp and togglable. Inference can
run faster than display.

---

## 10. Quality, testing and records (fixes complaint #5)

### 10.1 Test pyramid
| Layer | What | Tooling |
|---|---|---|
| Unit | geometry, foot point, hysteresis, PPE evidence filter, incident state machine, class map, config validation | pytest + hypothesis (property tests for polygon logic) |
| Component | tracker + counter on synthetic trajectories (crossing paths, occlusion, re-entry), associator on fixture boxes | pytest |
| Model | smoke test that weights load and detect a person in fixture images; class names match taxonomy | pytest (marked `model`) |
| Integration | API with test DB; upload a fixture video → expected unique count ± tolerance; WS stream yields frames | pytest + httpx |
| Eval (slow) | counting eval, XAI sanity checks, detector test metrics | `make eval` (not in default CI) |
| Frontend unit | stores, hooks, geometry helpers in the editor | Vitest |
| E2E | login, start camera from fixture video, draw zone, see intrusion incident, open Grad-CAM, acknowledge, export report | Playwright (uses backend in `VS_FAKE_SOURCE` video-file mode, never mock detections) |
| Visual/a11y | screenshots at 4 widths × 2 themes, axe with zero serious/critical issues | Playwright |

Coverage target: ≥ 85% lines for `backend/app/core/`, ≥ 70% overall backend.

### 10.2 CI (GitHub Actions)
`lint → typecheck → unit/integration (CPU, nano weights) → frontend build + vitest → playwright e2e (chromium)`.
Artifacts: coverage, Playwright report and screenshots.

### 10.3 Records
- `docs/BUILD_LOG.md`: one entry per phase (template in `BUILD_PROMPTS.md`).
- `docs/build_state.json`: machine-readable phase status for resuming.
- `docs/DECISIONS.md`: short ADRs (context, decision, consequences) for every non-obvious choice.
- `training/registry.json` + reports (§4.5); `docs/eval/*.md` for counting and XAI.
- `CHANGELOG.md` (Keep a Changelog), semantic versions.
- Structured JSON logs at runtime (`structlog`), rotated, with camera_id and track_id fields.

---

## 11. Repository layout (target)

```
Vision_Sentinel_2.0_GMP/
├── BUILD_PROMPTS.md          # the phased, unattended build script for Claude Code
├── CLAUDE.md                 # standing rules for any Claude session in this repo
├── README.md
├── DESIGN.md                 # design system (written by the impeccable pass)
├── CHANGELOG.md
├── Makefile                  # dev, test, eval, train, lint, e2e, docker
├── docker-compose.yml
├── config/default.yaml
├── backend/
│   ├── pyproject.toml  uv.lock
│   ├── app/
│   │   ├── main.py
│   │   ├── api/              # routers: auth, cameras, zones, incidents, xai, uploads, analytics, model, reports, ws
│   │   ├── core/
│   │   │   ├── types.py
│   │   │   ├── sources/      # webcam, file, rtsp, image
│   │   │   ├── detection/    # detector wrapper, warmup, device selection
│   │   │   ├── tracking/     # bytetrack config, confirmation, id-merge, counters
│   │   │   ├── ppe/          # regions, association, evidence filter
│   │   │   ├── zones/        # geometry, hysteresis, rules engine
│   │   │   ├── incidents/    # state machine, dedup, evidence
│   │   │   ├── xai/          # gradcam, eigencam, worker, sanity checks
│   │   │   └── pipeline.py   # per-camera orchestration
│   │   ├── services/  db/  settings.py  logging.py
│   ├── eval/                 # counting_eval.py, xai_eval.py, detector_eval.py
│   └── tests/
├── frontend/
│   ├── package.json  vite.config.ts  index.html
│   ├── src/ (app/, routes/, components/, features/{live,incidents,zones,analytics,model,uploads,settings}, lib/, styles/)
│   └── e2e/                  # Playwright specs + screenshot baselines
├── training/
│   ├── configs/ (class_map.yaml, data.yaml, hyp_*.yaml)
│   ├── scripts/ (download_*.py, merge.py, dedup.py, split.py, train.py, evaluate.py, export.py, benchmark.py)
│   ├── notebooks/train_colab.ipynb
│   ├── runs/  registry.json  reports/  benchmarks/
├── models/                   # active weights: vs2-yolo26n.pt/.onnx + model.json
├── data/                     # gitignored except manifests/, eval/clips.yaml, DATASET_CARD.md, samples/
└── docs/
    ├── BLUEPRINT.md  BUILD_LOG.md  build_state.json  DECISIONS.md  ROADMAP.md
    ├── architecture.md  api.md  user-guide.md  operations.md  training.md
    └── eval/ (counting_report.md, xai_report.md, detector_report.md)
```

---

## 12. Risks and fallbacks

| Risk | Likelihood | Fallback (decided in advance so the unattended build never stalls) |
|---|---|---|
| No GPU in build environment | High | CPU-budget training (§4.4) + Colab notebook; model card says so |
| Kaggle/Roboflow keys absent | Medium | Train on Construction-PPE + Open Images V7 + public Hard Hat mirror; log skipped sources |
| YOLO26 missing in installed `ultralytics` | Low | YOLO11n/s; same code path |
| Grad-CAM on YOLO26 head is awkward | Medium | Grad-CAM on the one-to-many auxiliary branch if present, else EigenCAM + documented limitation |
| MOT17 download blocked | Low | Use bundled synthetic + hand-labelled clips; report says which data was used |
| Skill install fails | Medium | Apply §9 principles directly; log it |
| Webcam unavailable in CI/container | Certain | File source with fixture videos; webcam tested manually (documented) |
| Big files in git | Medium | `.gitignore` datasets/runs weights except `best.pt` of the shipped model; Git LFS if > 50 MB |
| Time/context limits of one session | High | Phase state file + "resume" protocol in `BUILD_PROMPTS.md`; each phase ends committed and pushed |

---

## 13. Definition of done (v2.0.0)

- [ ] `make test` green; `make e2e` green; CI green on the default branch.
- [ ] Trained model shipped in `models/` with model card, registry, figures, test metrics and latency table.
- [ ] Counting report shows the per-frame (v1) vs tracked comparison and unique-count error on eval data.
- [ ] XAI report with pointing game, deletion check and randomisation check results.
- [ ] Zone editor: draw/edit/delete with keyboard support; intrusion incidents fire from a fixture video in e2e.
- [ ] No mock detection code anywhere outside tests (`grep -ri "mock" backend/app` returns nothing relevant).
- [ ] UI passes the Playwright screenshot review at 4 widths × 2 themes, axe has no serious issues, and `DESIGN.md`
      matches what shipped.
- [ ] README quick start works from a fresh clone (verified in a clean container); docs in `docs/` complete.
- [ ] `docs/BUILD_LOG.md` has an entry for every phase; `docs/build_state.json` shows all phases `done`.
- [ ] Tag `v2.0.0` pushed with release notes.
