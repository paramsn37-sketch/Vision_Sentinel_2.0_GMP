# Performance

Measured by `backend/eval/perf.py` (raw numbers in [`performance.json`](performance.json)): each camera runs the full
pipeline (detect → track → PPE → zones and incidents) plus the live JPEG encode, unpaced, on its own thread, sharing
one detector as the server does. Clips are the 960×540 samples in `data/samples/`, 60 s per run.

**Machine:** the build container, 4 vCPU (Intel Xeon 2.10 GHz), 4 torch threads, no GPU. Nothing else was running.
GPU numbers are **not measured**: no GPU was available to the build.

## Throughput and per-stage latency (milliseconds, p50 / p95)

| configuration | cameras | total fps | fps per camera | detect | track | PPE | zones + incidents | JPEG | whole frame |
|---|---|---|---|---|---|---|---|---|---|
| **Default:** trained model 480 px (PPE) + COCO yolo26n 640 px (people) | 1 | 9.6 | 9.6 | 94.6 / 123.5 | 1.6 / 2.5 | 0.3 / 0.5 | 0.2 / 0.5 | 1.5 / 1.9 | 97.1 / 126.0 |
| Default | 4 | 9.7 | 2.4 | 405.3 / 457.8 | 2.4 / 3.5 | 0.2 / 0.4 | 0.3 / 0.7 | 1.5 / 2.0 | 408.2 / 460.7 |
| Trained model only (`person_model: ""`) | 1 | 21.3 | 21.3 | 40.6 / 54.2 | 1.4 / 2.1 | 0.2 / 0.3 | 0.2 / 0.5 | 1.4 / 1.8 | 42.4 / 56.6 |
| Trained model only | 4 | 22.1 | 5.5 | 172.5 / 208.0 | 2.0 / 2.9 | 0.1 / 0.2 | 0.2 / 0.5 | 1.5 / 1.9 | 175.0 / 210.7 |

With four cameras, per-frame times include waiting for the shared detector (one forward at a time), which is why
total throughput stays flat while each camera's share drops.

### Re-measured on 2026-10-23 with the stage-2 weights

The table above was measured on 2026-10-22 with stage 1's weights (labels `dual-default` and `single-model` in
`performance.json`). After the second training stage (ADR-0014) the same script ran again (labels `default` and
`trained-only`; logs in `training/logs/2026-10-23_perf_*_ft.log`):

| configuration | cameras | total fps | fps per camera | detect | whole frame |
|---|---|---|---|---|---|
| Default (both networks) | 1 | 7.8 | 7.8 | 114.9 / 140.5 | 117.5 / 143.7 |
| Default | 4 | 8.5 | 2.1 | 462.5 / 541.6 | 465.9 / 545.5 |
| Trained model only | 1 | 18.0 | 18.0 | 47.5 / 63.9 | 50.1 / 66.9 |
| Trained model only | 4 | 18.8 | 4.7 | 203.8 / 246.5 | 207.4 / 251.3 |

The networks are identical in size to the day before, so the work per frame did not change. The build machine was
re-provisioned in between and is about 15–20 % slower now: the unchanged parts of the pipeline (tracking, JPEG) are
slower too, and on the same machine stage 1's and stage 2's weights benchmark within run-to-run variation of each
other (training report, "Speed"). Read both tables as the range one 4-vCPU cloud machine gives.

## Against the blueprint targets (§2.5)

| target | result | verdict |
|---|---|---|
| ≥ 25 FPS on one 720p stream on an RTX 3050-class GPU (MUST) | not measured (no GPU) | **not verified** |
| ≥ 8 FPS on a modern 8-core CPU, nano model at 640 px (SHOULD) | 7.8–9.6 FPS on 4 vCPU with both models; 18.0–21.3 FPS with the trained model alone (two measurement days) | met with one network; with both, met on one day and 0.2 FPS short on the other, on half the cores the target names |
| Detection → incident visible in the UI < 1.0 s (MUST) | pipeline p95 126 ms (one camera), 461 ms (four cameras); the WebSocket hop was not instrumented separately | met for the pipeline; end-to-end not measured |
| Grad-CAM < 300 ms per explanation on GPU | 161 ms p50, 248 ms p95 on the CPU (stage-2 weights) ([xai_report.md](xai_report.md)) | met on CPU |
| Frontend initial JS < 250 KB gzip | 173.7 KB (Phase 8 build) | met |
| Backend image < 2.5 GB | 1.82 GB (was 6.14 GB: the lock file pulled CUDA wheels into the CPU image; `nvidia-*`, `cuda-*` and `triton` are now excluded and CI fails if the image is over budget) | met |

## Bottlenecks and what was done

1. **Detection is 97 % of the frame time.** Everything else (tracking, PPE, zones, incidents, JPEG) together takes
   under 4 ms. The one lever is the network.
2. **Two networks per frame (ADR-0013)** cost 54 ms of the 95 ms. This buys back the counting accuracy (MOT17
   unique-count error 20.0 % instead of 32.9–41.3 % with the trained model's own person class). Sites that care more
   about frame rate than counting can set `detection.person_model: ""` and get 21 FPS.
3. **ONNX Runtime** was benchmarked (`training/benchmarks/latency.json`): 27.6 ms vs 29.9 ms p50 at 480 px for the
   trained model on 2026-10-22 (8 % faster), 23.1 ms vs 32.0 ms on 2026-10-23 (28 %). Not switched: the explanation feature needs the PyTorch graph for gradients, and
   loading the model twice in two runtimes costs more memory than the gain is worth.
4. **Image size:** the backend image went from 6.14 GB to 1.82 GB by keeping CUDA wheels out of the CPU image.

Not done: half precision and TensorRT (GPU only), frame skipping (it would change counting behaviour, which is
tuned at full frame rate).
