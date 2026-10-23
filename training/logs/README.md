# Training and evaluation logs

Console output of every training, evaluation and measurement run behind the numbers in this repository, kept for the
project report. Colour codes and progress-bar redraws are stripped; nothing else is edited. File names are
`<date>_<what>.log`. Per-epoch metrics of each training run live next to its arguments in `training/runs/<run>/`
(`results.csv`, `args.yaml`, `results.png` and the label/batch plots); weights are not committed except the promoted
model in `models/`.

| File | What produced it | Results written to |
|---|---|---|
| `2026-10-22_baselines_eval.log` | `training/scripts/evaluate.py` on the stock COCO models (v1's YOLO11m, YOLO26n), frozen test split | `docs/eval/detector_results.json` |
| `2026-10-22_vs2-y26n-cpu480_eval.log` | `evaluate.py --thresholds` on the first CPU run, test split + per-class thresholds chosen on validation | `training/reports/eval/vs2-y26n-cpu480/` |
| `2026-10-22_vs2-y26n_export.log` | `export.py`: optimizer strip, ONNX export, sha256 into `models/model.json` | `models/` |
| `2026-10-22_vs2-y26n_benchmark.log` | `benchmark.py`: PyTorch vs ONNX Runtime latency on CPU | `training/benchmarks/latency.json` |
| `2026-10-22_vs2-y26n_error_analysis.log` | `error_analysis.py`: worst false positives/negatives on test | `training/reports/error_analysis/` |
| `2026-10-22_counting_trained-only_480.{log,json}` | `backend/eval/counting_eval.py`, trained model's own person class at 480 px (ADR-0013 evidence) | this folder |
| `2026-10-22_counting_trained-only_640.{log,json}` | same at 640 px | this folder |
| `2026-10-22_counting_dual-detector.log` | `counting_eval.py` with the shipped two-model detector | `docs/eval/counting_report.md` |
| `2026-10-22_xai_eval.log` | `backend/eval/xai_eval.py`: pointing game, deletion, randomisation, latency | `docs/eval/xai_report.md` |
| `2026-10-22_perf_dual.log`, `_perf_single.log` | `backend/eval/perf.py`, both detector modes, 1 and 4 cameras | `docs/eval/performance.md` |
| `2026-10-22_soak.log` | `scripts/soak.py`, 60 minutes, three cameras | `docs/eval/soak.md` |
| `2026-10-23_vs2-y26n-cpu480-ft_train.log` | `training/scripts/train.py` second CPU stage (ADR-0014); added when the run finishes | `training/runs/vs2-y26n-cpu480-ft/` |

**Missing:** the console log of the first training run (`vs2-y26n-cpu480`, 26 epochs) was lost when the build
machine restarted mid-run. Its complete per-epoch record survives in `training/runs/vs2-y26n-cpu480/results.csv`
(every loss and validation metric per epoch), `args.yaml` (every hyperparameter) and `results.png`.
