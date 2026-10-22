# Model card: vs2-y26n

The detector shipped in `models/` (`vs2-y26n.pt`, `vs2-y26n.onnx`, metadata in `models/model.json`). Every number
below was produced by the scripts named next to it; nothing is estimated.

## Summary

| | |
|---|---|
| Architecture | YOLO26n (Ultralytics 8.4.183), 2.39 M parameters, fine-tuned from COCO weights (`yolo26n.pt`); see ADR-0012 |
| Task | Detect people and PPE in one pass: `person, head, helmet, vest, gloves, hand, boots, goggles, no_goggles` |
| Input size | 480 px (letterboxed) |
| Training | CPU only, run `vs2-y26n-cpu480`, 26 epochs (3.8 h), AdamW, lr 0.002 cosine, mosaic; see [training report](training/reports/training_report.md) |
| Data | 3,708 images: Ultralytics Construction-PPE + an Open Images V7 subset, 70/15/15 split, near-duplicates removed ([dataset card](data/DATASET_CARD.md)) |
| Licence | AGPL-3.0 (Ultralytics and Construction-PPE are AGPL-3.0; Open Images annotations CC BY 4.0, images CC BY 2.0) |
| sha256 | `.pt` `f7d1d75f…f79394d9`, `.onnx` `29edcdae…be88534f` (full hashes in `models/model.json`) |

## Intended use

Flag people on an industrial site who are missing a hard hat or high-visibility vest, or who are inside a restricted
zone, for a human safety officer to review. Each alert carries an evidence frame and a heatmap explanation so the
officer can judge it. It is a decision aid, not an automatic enforcement system.

**Not for:** identifying people (there is no face or identity model), judging whether PPE is certified or correctly
fastened, top-down or thermal cameras, or any use where a missed detection is the only safeguard.

## Test results (frozen test split, 559 images, never used for training or threshold choice)

`training/scripts/evaluate.py`, results in `docs/eval/detector_results.json`, plots in
`training/reports/eval/vs2-y26n-cpu480/`. Precision and recall at Ultralytics' F1-optimal confidence.

| class | test instances | precision | recall | mAP50 | mAP50-95 | operating threshold |
|---|---|---|---|---|---|---|
| person | 976 | 0.690 | 0.702 | **0.683** | 0.368 | 0.361 |
| head | 681 | 0.654 | 0.602 | **0.579** | 0.315 | 0.303 |
| helmet | 205 | 0.785 | 0.839 | **0.867** | 0.454 | 0.287 |
| vest | 210 | 0.807 | 0.814 | **0.849** | 0.503 | 0.317 |
| gloves | 208 | 0.764 | 0.468 | 0.514 | 0.232 | 0.253 |
| hand | 267 | 0.444 | 0.060 | 0.150 | 0.058 | 0.090 |
| boots | 230 | 0.737 | 0.591 | 0.683 | 0.375 | 0.213 |
| goggles | 166 | 0.633 | 0.319 | 0.380 | 0.138 | 0.271 |
| no_goggles | 49 | 1.000* | 0.000 | 0.016 | 0.004 | 0.038 |
| **mean** | 2,992 | 0.724 | 0.488 | **0.524** | 0.272 | |

Operating thresholds are per class, chosen to maximise F1 on the **validation** split. \* Ultralytics reports precision 1 when a class has no detections at the chosen confidence.

### Against the blueprint targets (SHOULD)

| target | result |
|---|---|
| person mAP50 ≥ 0.80 | 0.683, **not met** |
| helmet mAP50 ≥ 0.70 | 0.867, met |
| vest mAP50 ≥ 0.70 | 0.849, met |
| head mAP50 ≥ 0.70 | 0.579, **not met** |

### Against the baselines (person class, same test split)

| model | person mAP50 | person mAP50-95 | PPE classes |
|---|---|---|---|
| v1 setup: YOLO11m, COCO weights (20.1 M params) | 0.745 | 0.424 | none |
| Stock YOLO26n, COCO weights | 0.720 | 0.387 | none |
| **vs2-y26n (this model)** | 0.683 | 0.368 | 8 PPE classes |

The trained model gives up 3.7 mAP50 points on `person` against the stock nano model (within the 5-point budget
the build set itself) and 6.2 points against the 8× larger v1 model, in exchange for detecting PPE at all. Both
COCO models score 0 on every PPE class because they have none.

## Speed

`training/scripts/benchmark.py` → `training/benchmarks/latency.json`. One image per call, including pre- and
post-processing, 60 frames from the test split, 4-core Intel Xeon 2.10 GHz, 3 torch threads, no GPU.

| runtime | 480 px p50 / p95 | 640 px p50 / p95 |
|---|---|---|
| PyTorch | 29.9 / 60.0 ms | 44.1 / 70.6 ms |
| ONNX Runtime | 27.6 / 59.0 ms | 35.6 / 52.4 ms |

Not measured: GPU latency (no GPU was available to the build).

## Known limitations

From the error analysis (`training/reports/error_analysis/`, see the training report for the full list):

* **`hand` and `no_goggles` are not usable.** `hand` recall is 0.06 and `no_goggles` has 49 test instances and an
  mAP50 of 0.016. Gloves and goggles are therefore judged mostly as "unknown" rather than "missing". Helmet and vest,
  the two items most sites require, are the reliable ones.
* **Close-ups and partial bodies.** Most missed people are crops where only legs, hands or a face are visible; most
  confident false positives are people the Open Images labels left out or boxed differently. CCTV framing (whole
  bodies, mid distance) is under-represented in the data.
* **Domain.** Helmet, vest and no_goggles come only from Construction-PPE (daylight construction sites, mostly
  frontal). Expect lower accuracy at night, in rain, from high or top-down angles, and for other industries' PPE.
* **Hard-hat look-alikes.** A hard hat that is not worn (on a table, held) is sometimes detected as `helmet`;
  motorbike helmets were excluded from training and are unseen.
* **Training was cut short.** The planned 8-hour CPU run stopped after 26 epochs when the build machine restarted;
  validation mAP50 was still rising slowly (0.512 at epoch 18, 0.539 at epoch 26). A full GPU run
  (`training/configs/hyp_gpu_full.yaml` or `training/notebooks/train_colab.ipynb`) is the first improvement to make.

## Ethical considerations

The system watches workers. It stores no identity: track IDs reset per camera and per session, evidence frames can
have heads blurred (`privacy.blur_heads_in_snapshots`) and are deleted after `storage.retention_days`. Alerts go to
a human, never to automatic sanctions, and every alert can be marked wrong, which is logged for retraining.
