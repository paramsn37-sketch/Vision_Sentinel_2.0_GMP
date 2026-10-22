# Decision records

Short ADRs. Format: context → decision → consequences. Newest at the bottom.

## ADR-0001 — Monorepo and stack
- **Context:** the blueprint asks for a lightweight but production-quality system that one person can run.
- **Decision:** one repo with `backend/` (FastAPI, SQLite, Ultralytics), `frontend/` (React + Vite), `training/`.
  Python 3.12 via `uv` (3.13 works but some wheels lag), Node 22.
- **Consequences:** one `Makefile` drives everything; no broker, no external database.

## ADR-0002 — Licence: AGPL-3.0
- **Context:** Ultralytics (detector, trainer) is AGPL-3.0; the Construction-PPE dataset is AGPL-3.0.
- **Decision:** license the project AGPL-3.0.
- **Consequences:** fine for academic/open use; a commercial closed deployment needs an Ultralytics licence.

## ADR-0003 — oxlint instead of ESLint
- **Context:** Vite 8's template ships oxlint; ESLint adds ~150 packages.
- **Decision:** keep oxlint + `tsc --noEmit` + Prettier.
- **Consequences:** fewer lint rules than ESLint's React plugins, much faster and lighter.

## ADR-0004 — Training environment and data sources
- **Context:** the build container has 4 CPU cores, 15 GB RAM, no GPU. Its network policy allows GitHub release
  assets (Ultralytics weights and datasets, boxmot's MOT17 subset), Open Images (Google Storage + S3) and PyPI/npm,
  but blocks Kaggle, Roboflow, Hugging Face and motchallenge.net. No Kaggle/Roboflow credentials are set.
- **Decision:** training mode `cpu-budget` (blueprint §4.4). Data: Ultralytics Construction-PPE + a capped Open
  Images V7 subset. Counting evaluation on the MOT17 half-length subset published as a boxmot release asset.
- **Consequences:** a smaller model trained for fewer epochs than the GPU plan; the Colab notebook reproduces the full
  plan with SH17/Roboflow data. All numbers in reports are from this setup and say so.

## ADR-0005 — Design skills
- **Context:** the UI must be built with impeccable, Emil Kowalski's design-engineering skills, Taste and Playwright.
- **Decision:** vendored into `.claude/skills/` (MIT / Apache-2.0 licences kept beside them):
  `impeccable` (direction, critique, audit, polish), `emil-design-eng`, `review-animations`, `improve-animations`,
  `ask-sonner`, `animation-performance` (motion and interaction craft), `taste-skill` (anti-generic constraints).
  Playwright via `@playwright/test` with the preinstalled Chromium.
- **How they are applied:** impeccable sets the direction and runs critique/audit passes on Playwright screenshots;
  Taste supplies the typography/spacing/colour checklist used in every review round; Emil's skills define motion
  tokens (durations, easings), toasts (Sonner) and review recorded interactions; Playwright captures screenshots at
  four widths and two themes, runs axe and holds visual baselines.

## ADR-0006 — Final taxonomy and Open Images selection
- **Context:** only Construction-PPE and Open Images V7 are reachable. Open Images `Helmet` covers bike/sport
  helmets, its labels are not exhaustive, and there is no mask class in either source.
- **Decision:** 9 classes (`person, head, helmet, vest, gloves, hand, boots, goggles, no_goggles`). From Open Images,
  take images with a non-group `Person` *and* a `Human head` box (so heads are labelled wherever people are) plus
  images with `Glove`/`Goggles`/`Boot` next to a person; exclude any image labelled with a helmet class; skip
  depictions and group boxes. Caps: 1,800 person images, 300 per PPE class.
- **Consequences:** heads and people from many places (street, office, home, sport) complement the construction
  images; `mask` moves to the roadmap; some unlabelled gloves/hands in Open Images are accepted label noise.
  No hard-negative set: "no Person box" in Open Images does not guarantee "no person", so it would add wrong labels.

## ADR-0007 — CPU training configuration
- **Context:** ~1 effective CPU core. Measured ≈0.35 s per training image at 480 px for YOLO26n.
- **Decision:** YOLO26n, 480 px, AdamW lr 0.002, cosine schedule, Ultralytics `time=8.0` h budget (it fits the LR
  schedule to the budget), patience 15, mosaic until the last 5 epochs. Training runs in the background while
  phases 3–10 proceed.
- **Consequences:** roughly 20–25 epochs. Small items (gloves, goggles) will be weaker than at 640 px. The GPU plan
  (`hyp_gpu_full.yaml`, notebook) remains the recommended retraining path.

## ADR-0008 — Exhaustive pHash deduplication
- **Context:** the first dedup bucketed hashes by exact 16-bit chunks; the leakage test found near-duplicates across
  splits because 6 differing bits can touch every chunk.
- **Decision:** exhaustive vectorised pairwise Hamming distance (3.7k images → ~7M comparisons, seconds).
- **Consequences:** 157 near-duplicates removed instead of 130; the leakage test passes; training was restarted on
  the corrected split before any results were used.

## ADR-0009 — Counting thresholds tuned on MOT17
- **Context:** blueprint §5 asks for thresholds tuned on MOT17-02/04 only and reported on held-out sequences.
  The first grid (confirmation knobs only) left the detector-limited tuning sequences badly undercounted.
- **Decision:** grid over 216 configurations including recall knobs (`track_high_thresh`, `new_track_thresh`).
  Chosen: high 0.2, new 0.25, min_hits 2, min_age 0.2 s, buffer 1.5 s, lost-track merge **off** (it merged
  different people on MOT17 and undercounted). `min_hit_ratio` is fixed at 0.5 as a product constraint (flicker
  must never count), costing 0.3 points.
- **Consequences:** mean unique-count error on MOT17-05/09/10/11/13 is 19.7–20.0 % with the stock YOLO26n person
  detector, against 107.9 % for v1's per-frame counting and 25.2 % for ByteTrack defaults. The 10 % target is not
  met; remaining error is mostly missed small/occluded people (detector recall at 640 px) and one crowded sequence
  (MOT17-09, +41 %). Follow-up: rerun with the trained weights and with 960 px input on a GPU.

## ADR-0010 — Grad-CAM target branch and variant
- **Context:** in eval mode the Ultralytics head returns `(y, preds)`. YOLO26 predicts with the one-to-one branch
  when `head.end2end` is true, otherwise with the one-to-many branch. Classic Grad-CAM (channel-mean weights)
  spread heat over the whole frame on these small models.
- **Decision:** backprop the matched anchor's class logit from the branch the predictor actually used
  (`one2one` if `end2end`, else `one2many`) into that branch's neck features. Default variant is HiResCAM
  (element-wise gradient × activation, ReLU, summed over channels and scales); classic Grad-CAM stays selectable;
  EigenCAM (first principal component, no gradients) is the fallback when no anchor matches.
- **Consequences:** on the fixture image ~0.79 of the heat energy lies inside the explained box and the peak is in
  the box. Sanity checks are in `docs/eval/xai_report.md`.

## ADR-0011 — Persistence and PDF without heavy native dependencies
- **Context:** the blueprint names Alembic and WeasyPrint. WeasyPrint needs Pango/Cairo system libraries; the schema
  is one version old.
- **Decision:** `SQLModel.metadata.create_all` with SQLite `PRAGMA user_version` (currently 1) as the schema version;
  a migration step is added when version 2 exists. PDF reports use `fpdf2` (pure Python).
- **Consequences:** no system packages beyond ffmpeg in the Docker image. Alembic is a follow-up if the schema starts
  changing between releases.
