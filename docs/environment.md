# Build environment (probed in Phase 0, 2026-10-22)

| Item | Value |
|---|---|
| OS | Linux 6.18 (container), x86_64 |
| CPU | 4 vCPU Intel Xeon @ 2.10 GHz; measured: a 2000×2000 matmul loop takes 2.5 s on 1 thread and 9.1 s on 4 threads, so the container gets roughly **one core** of usable compute |
| RAM | 15 GB, no swap |
| Disk | ~30 GB free |
| GPU | none (`nvidia-smi` absent, `torch.cuda.is_available()` false) |
| Python | 3.12.13 via uv (system 3.13.16) |
| Node | 22.22.0, npm 10.9.4 |
| Key packages | ultralytics 8.4.183 (YOLO26 available), torch 2.14.1 |
| Playwright | 1.56.1 with preinstalled Chromium (`/opt/pw-browsers`) |
| Docker | CLI present (daemon availability checked in Phase 11) |

## Credentials (names only)
| Variable | Present |
|---|---|
| KAGGLE_USERNAME / KAGGLE_KEY | no |
| ROBOFLOW_API_KEY | no |

## Network reachability
| Destination | Reachable | Used for |
|---|---|---|
| github.com release assets | yes | Ultralytics weights, Construction-PPE, sample clips, MOT17 subset (boxmot release) |
| storage.googleapis.com, open-images-dataset.s3.amazonaws.com | yes | Open Images V7 boxes and images |
| pypi.org, registry.npmjs.org | yes | packages |
| huggingface.co, kaggle.com, roboflow.com, motchallenge.net, pexels.com, download.pytorch.org | **no** (proxy policy) | — |

## Training mode
**`cpu-budget`** (blueprint §4.4). See ADR-0004 and ADR-0007 in `docs/DECISIONS.md`.
