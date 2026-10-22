# Final audit (v2.0.0)

Every item of the blueprint's definition of done (§13) and every MUST, with the verdict and where the evidence is.
**Pass** = met and evidenced. **Partial** = met with a recorded deviation. **Fail** = not met; the reason is given.
Audited on 2026-10-22 against commit history up to the `v2.0.0` tag.

## §13 Definition of done

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | `make test` green; `make e2e` green; CI green on the default branch | **Pass** | Locally: backend 70 passed (fast suite) + 6 model tests, Vitest 25 passed, Playwright 20 passed. CI (lint, unit, e2e, Docker) is green on the tagged commit of `claude/project-thread-0fl5hs`, which is the repository's default branch. |
| 2 | Trained model in `models/` with model card, registry, figures, test metrics and latency table | **Partial** | `models/vs2-y26n.{pt,onnx}`, `models/model.json`, [MODEL_CARD.md](../MODEL_CARD.md), `training/registry.json`, [training report](../training/reports/training_report.md), figures in `training/reports/{figures,eval,error_analysis}` and `training/runs/vs2-y26n-cpu480/results.png`, `training/benchmarks/latency.json`. The run was interrupted after 26 epochs (ADR-0012). The model card is at the repository root instead of `training/reports/`. |
| 3 | Counting report with per-frame (v1) vs tracked comparison and unique-count error | **Pass** (target missed) | [counting_report.md](eval/counting_report.md): v1 method 107.9 %, ByteTrack defaults 25.2 %, ours 20.0 %; IDF1, MOTA, ID switches per sequence. The §2.5 target (≤ 10 %) is **not met**, see below. |
| 4 | XAI report with pointing game, deletion and randomisation checks | **Pass** (one check fails) | [xai_report.md](eval/xai_report.md): pointing game 100 %, deletion 95 %, randomisation SSIM 0.669 (fails, explained in the report). |
| 5 | Zone editor draw/edit/delete with keyboard; intrusion incidents fire from a fixture video in e2e | **Pass** | `frontend/e2e/zones-xai.spec.ts`: draw zone → intrusion incident → explanation → acknowledge → resolve; drag vertex + undo; keyboard-only creation. All pass locally and in CI. |
| 6 | No mock detection code outside tests | **Pass** | `grep -ri mock backend/app` finds only the docstring of `uploads.py` ("never a mock"). |
| 7 | Playwright screenshot review at 4 widths × 2 themes, axe no serious issues, DESIGN.md matches | **Pass** | `e2e/visual.spec.ts` (7 routes × 1440/1024/768/390 × dark/light), `e2e/a11y.spec.ts` (0 serious/critical; a Model-screen regression found and fixed in this phase), [ui-review/round-1.md](ui-review/round-1.md), `DESIGN.md` updated in Phase 10. |
| 8 | README quick start works from a fresh clone (clean container); docs complete | **Partial** | CI does exactly the quick start on a fresh runner: `uv sync` + `npm ci` + start backend and UI + 20 e2e tests, and `docker compose build` + `up` + health check. Docker could not run inside the build container itself. Docs: [README](../README.md), [user guide](user-guide.md), [operations](operations.md), [architecture](architecture.md), [API](api.md), [training](training.md), [report appendix](report-appendix.md). |
| 9 | BUILD_LOG entry for every phase; build_state all `done` | **Partial** | [BUILD_LOG.md](BUILD_LOG.md) has an entry for phases 0–12. `build_state.json`: 6 phases `done`, 7 `done-with-fallbacks`, each with its reason. |
| 10 | Tag `v2.0.0` pushed with release notes | **Pass** | Tag `v2.0.0`; release notes in [CHANGELOG.md](../CHANGELOG.md). |

## §2.5 Non-functional targets (MUST unless marked SHOULD)

| Area | Target | Verdict | Evidence |
|---|---|---|---|
| Throughput | ≥ 25 FPS, one 720p stream, RTX 3050-class GPU | **Not verified** | No GPU available to the build. |
| Throughput (SHOULD) | ≥ 8 FPS on an 8-core CPU, nano at 640 px | **Pass** | 9.6 FPS on 4 vCPU with both networks, 21.3 FPS trained model only ([performance.md](eval/performance.md)). |
| Latency | Detection → incident visible in UI < 1.0 s | **Partial** | Pipeline p95 126 ms (1 camera), 461 ms (4 cameras); the WebSocket hop is not instrumented separately. The e2e test sees the intrusion incident well inside its timeout. |
| Counting | Unique-count error ≤ 10 %; IDF1 reported | **Fail** | 20.0 % mean on 5 held-out MOT17 sequences (IDF1 reported). Worst on MOT17-09 (41 %, moving camera) and MOT17-13 (34 %). Appearance re-identification was tried and undercounted (ADR-0009). |
| Detector (SHOULD) | person ≥ 0.80, helmet/head/vest ≥ 0.70 mAP50 | **Partial** | helmet 0.867 and vest 0.849 met; person 0.683 and head 0.579 not met (under-trained CPU run, ADR-0012). |
| Grad-CAM | < 300 ms on GPU; pointing game reported | **Pass** (CPU) | 142 ms p50 / 224 ms p95 on CPU; pointing game 100 %. GPU not measured. |
| Footprint | Backend image < 2.5 GB; initial JS < 250 KB gzip | **Pass** | Backend image 1.82 GB (CI `docker` job; was 6.14 GB until CUDA wheels were excluded, and CI now fails the build over 2.5 GB); frontend image 49 MB; initial JS 173.7 KB. |
| Install | `docker compose up` or two commands without Docker | **Pass** | README quick start: `docker compose up --build`, or `make setup` + `make dev`. |
| Privacy | No faces stored by default; head blur setting (SHOULD); retention | **Pass** | No face or identity model; `privacy.blur_heads_in_snapshots`; `storage.retention_days` with an hourly job (`tests/api/test_failures.py`). |
| Accessibility | WCAG 2.2 AA contrast, keyboard operable, reduced motion | **Pass** | Contrast table in `DESIGN.md` (44 pairs pass), axe on every route in both themes, keyboard-only zone creation e2e, reduced-motion e2e check. |

## Other MUSTs

| Section | MUST | Verdict | Evidence |
|---|---|---|---|
| §4.3 | Produce a trained model from public sources alone | **Pass** | Construction-PPE + Open Images V7, no credentials used ([dataset card](../data/DATASET_CARD.md)). |
| §4.5 | Training records exist (runs, registry, reports, figures, error analysis, latency, exports) | **Partial** | All present (item 2 above). Locations differ slightly: model card at the root; learning curves in `training/runs/<run>/`, test curves in `training/reports/eval/<run>/`, per-class bars in `training/reports/figures/`. |
| §5.6 | Counting eval on MOT17 with IDF1, MOTA, ID switches and unique-count error; before/after table | **Partial** | Done on 5 held-out MOT17 sequences after tuning on 2. The "2–3 public-licence industrial clips with hand-labelled counts" were not available; `data/eval/clips.yaml` holds MOT17-derived clips with ground-truth counts instead (Phase 1). |
| §7.2 | Pointing game on 300 detections; deletion check over 100; randomisation check SSIM < 0.5; report with example grids | **Partial** | Pointing game on 214 detections (one per image, balanced by class; rare classes ran out before 300); deletion over 100; randomisation 0.669 **fails**; example grid `docs/eval/figures/xai_examples.jpg`. |
| §10.1 | Coverage ≥ 85 % for `app/core`, ≥ 70 % overall | **Pass** | `pytest --cov`: `app/core` 86 %, `app` 86 %. |

## Open items

1. Counting error 20 % vs 10 % target (ADR-0009). Next step: better person data and appearance re-identification.
2. Detector under-trained (ADR-0012). Next step: the GPU plan in `training/notebooks/train_colab.ipynb`.
3. Explanation randomisation check fails. Next step: a perturbation-based method (D-RISE) as a second opinion.
4. GPU throughput and end-to-end UI latency not measured.
