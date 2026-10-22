# Training, evaluating and promoting a model

The detector finds people and PPE in one pass. Classes (in this order, the order is part of the model contract):
`person, head, helmet, vest, gloves, hand, boots, goggles, no_goggles`. `head`, `hand` and `no_goggles` are the
"bare part" classes: they are what lets the system say an item is *missing* rather than merely *not seen*.

Results of the current model: [`training/reports/training_report.md`](../training/reports/training_report.md) and
[`MODEL_CARD.md`](../MODEL_CARD.md). Every number in them comes from the scripts below.

All commands run from `backend/` (`uv sync --group train --group eval` once).

## 1. Data

```bash
uv run python ../training/scripts/download_construction_ppe.py   # Ultralytics Construction-PPE (AGPL-3.0)
uv run python ../training/scripts/download_openimages.py         # capped Open Images V7 subset (CC BY)
uv run python ../training/scripts/merge.py                       # remap to the taxonomy, clip, drop tiny boxes
uv run python ../training/scripts/split.py                       # pHash dedup, stratified 70/15/15, manifests
uv run python ../training/scripts/dataset_card.py                # data/DATASET_CARD.md and figures
```

* Mapping from every source class to the taxonomy (or to "dropped") lives in `training/configs/class_map.yaml`;
  `backend/tests/training` fails if a source class is unmapped or if a near-duplicate crosses splits.
* The test split is frozen: `data/manifests/test.txt` plus `test_manifest.sha256`. Keep it frozen so results stay
  comparable across models; add new data to train/val only.
* **Adding data:** put a YOLO-format folder under `data/raw/<source>/`, add its classes to `class_map.yaml`, add a
  branch in `merge.py:sources()`, then re-run merge, split and the dataset card. Images that operators marked "This
  alert was wrong" are saved under `data/runtime/feedback/` as candidates for labelling.
* Datasets are never committed (`data/raw`, `data/merged` are git-ignored). `VS_DATA_ROOT` moves them to a bigger
  disk.

## 2. Train

```bash
# CPU, time-boxed (what this repository's model was trained with)
uv run python ../training/scripts/train.py --hyp ../training/configs/hyp_cpu_budget.yaml --name vs2-y26n-cpu
# GPU, full plan (YOLO26s, 640 px, 150 epochs) — or run training/notebooks/train_colab.ipynb on Colab
uv run python ../training/scripts/train.py --hyp ../training/configs/hyp_gpu_full.yaml --name vs2-y26s-gpu640
```

Every run is recorded in `training/registry.json` at start and end: git commit, data manifest hash, environment,
hyperparameters, best epoch and validation metrics. Curves and plots land in `training/runs/<name>/` (weights are
git-ignored there).

## 3. Evaluate

```bash
# Baselines (once): the v1 setup and the stock nano model, person only
uv run python ../training/scripts/evaluate.py --weights yolo11m.pt --name baseline-v1-yolo11m --coco
uv run python ../training/scripts/evaluate.py --weights yolo26n.pt --name baseline-yolo26n-coco --coco
# A trained run: test-split metrics plus per-class F1-optimal thresholds chosen on val
uv run python ../training/scripts/evaluate.py --weights ../training/runs/<name>/weights/best.pt --name <name> \
    --imgsz 480 --thresholds
```

Results accumulate in `docs/eval/detector_results.json`; PR, F1 and confusion-matrix plots in
`training/reports/eval/<name>/`. Thresholds are chosen on **val**, never on test.

## 4. Promote

```bash
uv run python ../training/scripts/export.py --run <name> --name vs2-y26n --imgsz 480
uv run python ../training/scripts/benchmark.py --weights ../models/vs2-y26n.pt --name vs2-y26n
uv run python ../training/scripts/error_analysis.py --weights ../models/vs2-y26n.pt
uv run pytest -m model
```

`export.py` copies the weights to `models/`, exports ONNX, and writes `models/model.json` (classes, thresholds,
image size, test metrics, sha256 of both files, training mode). `pytest -m model` checks the class list matches the
taxonomy and that a person is found in at least 90 % of the fixture images that contain one. Restart the backend
(or rebuild the Docker image) to switch models; the Model screen shows what is active.

To roll back, restore the previous `models/` folder from git, or delete `models/model.json` to fall back to the
person-only COCO model.

## 5. Re-run the system evaluations

```bash
uv run python -m eval.counting_eval   # docs/eval/counting_report.md (MOT17 unique-count error, IDF1)
uv run python -m eval.xai_eval        # docs/eval/xai_report.md (pointing game, deletion, randomisation checks)
```
