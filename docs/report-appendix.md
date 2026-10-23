# Report appendix: Vision Sentinel 2.0

A self-contained summary for the college report. Every number is measured by a script in this repository; the
source file is named next to each table. "Not measured" means exactly that.

## A. Problem

Construction and factory sites must make sure that people wear protective equipment (hard hats, high-visibility
vests) and stay out of dangerous areas. Watching camera feeds by hand does not scale. The first version of this
project (v1) tried to automate it and had five problems: it counted the same person again in every frame, its user
interface was a generic template, its detector was a stock COCO model that cannot see PPE at all (and the upload page
used random numbers instead of the model), the zone and Grad-CAM pages were static mock-ups, and there were no tests
or records. Version 2.0 was rebuilt from scratch to fix each of these, with measurements to prove it.

## B. Method

**System.** One Python process (FastAPI) runs the vision pipeline and the API; a React web app shows live video,
incidents, zones, analytics and model information over REST and WebSockets; SQLite stores everything. Diagrams:
[architecture.md](architecture.md).

**Per-frame pipeline.**

1. *Detection.* Two YOLO26n networks: the stock COCO model finds people (640 px input), our fine-tuned model finds
   PPE items and bare heads/hands (480 px). ADR-0013 explains why two.
2. *Tracking.* ByteTrack assigns every person a track ID across frames. A track only counts as a person after it has
   been seen at least 2 times, for 0.2 s, in at least half of the frames since it appeared (track confirmation).
   Unique people = distinct confirmed tracks. Thresholds were tuned on two MOT17 sequences (216 combinations).
3. *PPE state.* Each PPE box is assigned to one person by the body region it falls in (head for helmets, torso for
   vests, feet for boots). Per person and item, an exponentially smoothed evidence value with hysteresis decides
   worn / missing / unknown, so one bad frame does not flip the state. A "missing" state must last 2 s before an
   incident opens.
4. *Zones.* Polygons in normalised coordinates, drawn on the camera image. A person is inside when their foot point
   (bottom-centre of the box) is inside, for 3 consecutive frames (5 to leave). Rules: no entry, PPE required, maximum
   occupancy, maximum dwell time, active hours.
5. *Incidents.* One incident per person, rule and zone, with start and end, evidence snapshot, and a 30 s window in
   which a recurrence reopens the same incident instead of creating a new one.
6. *Explanation.* For an incident's detection, HiResCAM (gradient × activation) is computed on the raw head output of
   the exact anchor that produced the box, at all three feature scales.

**Detector training.** 3,708 images from Ultralytics Construction-PPE and an Open Images V7 subset, remapped to 9
classes, near-duplicates removed by perceptual hash, split 70/15/15 with a frozen test split
([dataset card](../data/DATASET_CARD.md)). YOLO26n fine-tuned from COCO weights on CPU, 480 px, AdamW, mosaic
augmentation, in two stages: 26 epochs (3.8 h) until the machine restarted, then 24 more epochs (2.1 h) from those
weights with a lower, cosine-decayed learning rate and mosaic switched off for the last 8 epochs
([training report](../training/reports/training_report.md), [logs](../training/logs/README.md)).
Per-class operating thresholds chosen on validation, never on test.

## C. Results

### C.1 Detector (frozen test split, 559 images, 2,992 boxes; `training/scripts/evaluate.py`)

| class | precision | recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| person | 0.752 | 0.684 | 0.726 | 0.404 |
| head (bare) | 0.765 | 0.596 | 0.644 | 0.366 |
| helmet | 0.885 | 0.849 | 0.901 | 0.500 |
| vest | 0.858 | 0.832 | 0.888 | 0.548 |
| gloves | 0.752 | 0.495 | 0.555 | 0.261 |
| hand (bare) | 0.525 | 0.176 | 0.222 | 0.092 |
| boots | 0.734 | 0.617 | 0.696 | 0.369 |
| goggles | 0.747 | 0.392 | 0.450 | 0.173 |
| no_goggles | — | 0.000 | 0.034 | 0.008 |
| **mean** | 0.780 | 0.516 | **0.568** | 0.302 |

After the first stage alone the mean was 0.524 (person 0.683, helmet 0.867, vest 0.849); the second stage improved
every class.

Comparison on the same split, person class: v1's YOLO11m 0.745, stock YOLO26n 0.720, ours 0.726. Neither COCO model
detects any PPE class. Figures: `training/reports/eval/vs2-y26n-cpu480-ft/` (PR and F1 curves, confusion matrix),
`training/runs/vs2-y26n-cpu480{,-ft}/results.png` (learning curves of both stages), `training/reports/error_analysis/` (worst errors).

### C.2 Unique-person counting (MOT17, 5 sequences not used for tuning; `backend/eval/counting_eval.py`)

| sequence | true people | v1 method | ByteTrack defaults | ours |
|---|---|---|---|---|
| MOT17-05 | 71 | 171 (141 %) | 87 (23 %) | 74 (4 %) |
| MOT17-09 | 22 | 58 (164 %) | 36 (64 %) | 31 (41 %) |
| MOT17-10 | 36 | 65 (81 %) | 43 (19 %) | 35 (3 %) |
| MOT17-11 | 44 | 100 (127 %) | 50 (14 %) | 36 (18 %) |
| MOT17-13 | 44 | 32 (27 %) | 47 (7 %) | 29 (34 %) |
| **mean error** | | **107.9 %** | **25.2 %** | **20.0 %** |

"v1 method" reproduces v1's logic (people per frame, one frame per second, summed). Tracking quality (IDF1, MOTA, ID
switches) is in [counting_report.md](eval/counting_report.md). With our trained model's own person class instead of
the COCO person model, the error was 41.3 % (480 px) and 32.9 % (640 px).

### C.3 Explanations (256 test detections; `backend/eval/xai_eval.py`)

| check | result |
|---|---|
| Pointing game (hottest pixel inside the box) | 100 % (classic Grad-CAM: 65 %, EigenCAM: 23 %, on 60 detections) |
| Heat inside the box | 90–96 % by class |
| Deletion: hiding the hottest 20 % lowers the score more than hiding a random 20 % | 98 % of cases; mean drop 0.645 vs 0.146 |
| Model randomisation: maps from a randomly re-initialised network should differ (SSIM < 0.5) | **0.796, fails** |
| Time per explanation (CPU) | 161 ms p50, 248 ms p95 |

### C.4 System (`backend/eval/perf.py`, `scripts/soak.py`)

| measurement | result |
|---|---|
| One camera, 4 vCPU, no GPU | 9.6 FPS (both networks); 21.3 FPS (trained model only). Re-run a day later on a slower re-provisioned machine: 7.8 and 18.0 FPS |
| Four cameras | 9.7 FPS in total (2.4 each) |
| Share of frame time spent in detection | 97 % |
| 60-minute soak, three cameras | memory +3.0 % after warm-up; open files and threads constant |
| Frontend initial JavaScript | 173.7 KB gzip |
| Accessibility | axe: 0 serious or critical issues on every screen, both themes |
| Tests | backend 70 fast + 6 model tests, 25 frontend unit tests, 20 Playwright end-to-end tests |

## D. Comparison with v1

| | v1 | 2.0 |
|---|---|---|
| Counting | per-frame sums, 107.9 % error on MOT17 | tracked, confirmed people, 20.0 % |
| PPE detection | impossible (COCO model) | trained model: helmet 0.867, vest 0.849 mAP50 |
| Uploads | random numbers | the same pipeline as live cameras |
| Zones | static picture | polygon editor (keyboard operable, undo/redo), foot-point test with hysteresis |
| Grad-CAM | computed after NMS (not class-discriminative) | per-anchor HiResCAM with measured sanity checks |
| Records | one smoke test | CI with lint, unit, e2e and Docker jobs; build log, ADRs, model card, run registry |

## E. Limitations

1. **Counting error is 20 %, twice the 10 % target.** The worst sequences (MOT17-09, MOT17-13) are crowded or filmed
   from a moving camera; occlusions split and merge tracks.
2. **The detector is small and CPU-trained.** Nano model, 480 px, 50 epochs over two stages, now converged. Person
   mAP50 (0.726) and head (0.644) miss their targets (0.80 and 0.70). Bare hands and "no goggles" are effectively not detected, so glove and goggle
   violations are reported as "unknown" rather than raised.
3. **Domain gap.** PPE images are daylight construction sites, mostly frontal. Night, rain, top-down CCTV and other
   industries are under-represented.
4. **One explanation sanity check fails.** The randomisation check suggests the heatmap's shape depends partly on
   where the box is, not only on what the model learned. The deletion check still shows the hot region matters.
5. **GPU performance was not measured**, nor the end-to-end delay from detection to the browser.
6. **Two networks per frame** halve the frame rate on CPU to keep counting accurate.

## F. Future work

1. Train the full plan on a GPU (YOLO26s, 640 px, 150 epochs) with `training/notebooks/train_colab.ipynb`.
2. Add CCTV-style footage with complete person and PPE labels, then retire the separate COCO person model.
3. Re-identification by appearance to merge split tracks after long occlusions (the 10 % counting target).
4. A gradient-free or perturbation-based explanation (e.g. D-RISE) to pass the randomisation check.
5. Alert delivery (webhook to SMS or e-mail) and multi-camera site maps.
