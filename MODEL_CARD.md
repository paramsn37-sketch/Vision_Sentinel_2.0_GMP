# Model card: vs2-y26n

The detector shipped in `models/` (`vs2-y26n.pt`, `vs2-y26n.onnx`, metadata in `models/model.json`). Every number
below was produced by the scripts named next to it; nothing is estimated.

## Summary

| | |
|---|---|
| Architecture | YOLO26n (Ultralytics 8.4.183), 2.39 M parameters, fine-tuned from COCO weights (`yolo26n.pt`) in two stages; see ADR-0012 and ADR-0014 |
| Task | Detect people and PPE in one pass: `person, head, helmet, vest, gloves, hand, boots, goggles, no_goggles` |
| Input size | 480 px (letterboxed) |
| Training | CPU only. Stage 1 `vs2-y26n-cpu480`: 26 epochs (3.8 h, interrupted), AdamW lr 0.002. Stage 2 `vs2-y26n-cpu480-ft` (shipped): 24 more epochs (2.1 h), AdamW lr 0.0008 cosine-decayed, mosaic off for the last 8. See [training report](training/reports/training_report.md) and [logs](training/logs/README.md) |
| Data | 3,708 images: Ultralytics Construction-PPE + an Open Images V7 subset, 70/15/15 split, near-duplicates removed ([dataset card](data/DATASET_CARD.md)) |
| Licence | AGPL-3.0 (Ultralytics and Construction-PPE are AGPL-3.0; Open Images annotations CC BY 4.0, images CC BY 2.0) |
| sha256 | `.pt` `4b7d265b…a2ae9692`, `.onnx` `7f653d07…5ec1b5b6` (full hashes in `models/model.json`) |

## Intended use

Flag people on an industrial site who are missing a hard hat or high-visibility vest, or who are inside a restricted
zone, for a human safety officer to review. Each alert carries an evidence frame and a heatmap explanation so the
officer can judge it. It is a decision aid, not an automatic enforcement system.

**Not for:** identifying people (there is no face or identity model), judging whether PPE is certified or correctly
fastened, top-down or thermal cameras, or any use where a missed detection is the only safeguard.

## Test results (frozen test split, 559 images, never used for training or threshold choice)

`training/scripts/evaluate.py`, results in `docs/eval/detector_results.json`, plots in
`training/reports/eval/vs2-y26n-cpu480-ft/`. Precision and recall at Ultralytics' F1-optimal confidence.

| class | test instances | precision | recall | mAP50 | mAP50-95 | operating threshold |
|---|---|---|---|---|---|---|
| person | 976 | 0.752 | 0.684 | **0.726** | 0.404 | 0.287 |
| head | 681 | 0.765 | 0.596 | **0.644** | 0.366 | 0.186 |
| helmet | 205 | 0.885 | 0.849 | **0.901** | 0.500 | 0.317 |
| vest | 210 | 0.858 | 0.832 | **0.888** | 0.548 | 0.409 |
| gloves | 208 | 0.752 | 0.495 | 0.555 | 0.261 | 0.338 |
| hand | 267 | 0.525 | 0.176 | 0.222 | 0.092 | 0.098 |
| boots | 230 | 0.734 | 0.617 | 0.696 | 0.369 | 0.262 |
| goggles | 166 | 0.747 | 0.392 | 0.450 | 0.173 | 0.393 |
| no_goggles | 49 | 1.000* | 0.000 | 0.034 | 0.008 | 0.059 |
| **mean** | 2,992 | 0.780 | 0.516 | **0.568** | 0.302 | |

Stage 1 alone scored 0.524 mean mAP50 (person 0.683, helmet 0.867, vest 0.849); stage 2 improved every class.

Operating thresholds are per class, chosen to maximise F1 on the **validation** split. \* Ultralytics reports precision 1 when a class has no detections at the chosen confidence.

### Against the blueprint targets (SHOULD)

| target | result |
|---|---|
| person mAP50 ≥ 0.80 | 0.726, **not met** |
| helmet mAP50 ≥ 0.70 | 0.901, met |
| vest mAP50 ≥ 0.70 | 0.888, met |
| head mAP50 ≥ 0.70 | 0.644, **not met** |

### Against the baselines (person class, same test split)

| model | person mAP50 | person mAP50-95 | PPE classes |
|---|---|---|---|
| v1 setup: YOLO11m, COCO weights (20.1 M params) | 0.745 | 0.424 | none |
| Stock YOLO26n, COCO weights | 0.720 | 0.387 | none |
| **vs2-y26n (this model)** | 0.726 | 0.404 | 8 PPE classes |

The trained model is 0.6 mAP50 points ahead of the stock nano model on `person` (at a smaller input size) and 1.9
points behind the 8× larger v1 model, and it detects PPE as well. Both
COCO models score 0 on every PPE class because they have none.

## Speed

`training/scripts/benchmark.py` → `training/benchmarks/latency.json`. One image per call, including pre- and
post-processing, 60 frames from the test split, 4-core Intel Xeon 2.10 GHz, 3 torch threads, no GPU, measured
2026-10-23.

| runtime | 480 px p50 / p95 | 640 px p50 / p95 |
|---|---|---|
| PyTorch | 32.0 / 60.7 ms | 52.1 / 79.6 ms |
| ONNX Runtime | 23.1 / 44.1 ms | 36.6 / 84.1 ms |

The network is the same size as stage 1's (measured 29.9 ms PyTorch at 480 px on 2026-10-22); the difference is the
build machine, which was re-provisioned in between (see the training report).

Not measured: GPU latency (no GPU was available to the build).

## Known limitations

From the error analysis (`training/reports/error_analysis/`, see the training report for the full list):

* **`hand` and `no_goggles` are not usable.** `hand` recall is 0.18 and `no_goggles` has 49 test instances and an
  mAP50 of 0.034. Gloves and goggles are therefore judged mostly as "unknown" rather than "missing". Helmet and vest,
  the two items most sites require, are the reliable ones.
* **Close-ups and partial bodies.** Most missed people are crops where only legs, hands or a face are visible; most
  confident false positives are people the Open Images labels left out or boxed differently. CCTV framing (whole
  bodies, mid distance) is under-represented in the data.
* **Domain.** Helmet, vest and no_goggles come only from Construction-PPE (daylight construction sites, mostly
  frontal). Expect lower accuracy at night, in rain, from high or top-down angles, and for other industries' PPE.
* **Hard-hat look-alikes.** A hard hat that is not worn (on a table, held) is sometimes detected as `helmet`;
  motorbike helmets were excluded from training and are unseen.
* **Small model, CPU training.** After both stages validation mAP50 is flat at about 0.57 over the last 8 epochs:
  the nano model at 480 px has converged on this data. A larger model at 640 px on a GPU
  (`training/configs/hyp_gpu_full.yaml` or `training/notebooks/train_colab.ipynb`) is the next improvement to make.

## Ethical considerations

The system watches workers. It stores no identity: track IDs reset per camera and per session, evidence frames can
have heads blurred (`privacy.blur_heads_in_snapshots`) and are deleted after `storage.retention_days`. Alerts go to
a human, never to automatic sanctions, and every alert can be marked wrong, which is logged for retraining.
