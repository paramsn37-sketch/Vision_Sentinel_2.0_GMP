# Operations

How to configure, run, back up and troubleshoot a Vision Sentinel installation.

## Configuration

Settings are read in this order (later wins): `config/default.yaml` → `.env` in the repository root → environment
variables. An environment variable is `VS_<SECTION>__<KEY>`, for example `VS_TRACKING__MIN_HITS=3` or
`VS_SERVER__CORS_ORIGINS='["https://sentinel.example"]'`. The thresholds in `tracking`, `ppe`, `zones` and
`incidents` can also be changed in **Settings → Thresholds**; those overrides are stored in the database and applied
to running cameras without a restart.

### Secrets and sign-in

| Variable | Default | Meaning |
|---|---|---|
| `VS_ADMIN_PASSWORD` | unset | Password of the `admin` account on first start. If unset, a random one is generated and written to `data/runtime/ADMIN_PASSWORD.txt` (delete that file after reading it). Change it later in Settings. |
| `VS_SECRET_KEY` | unset | Key that signs session cookies. If unset, one is generated once and kept in `data/runtime/.secret_key`. Set it explicitly when running more than one container. |

### `server`

| Key | Default | Meaning |
|---|---|---|
| `cors_origins` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | Origins allowed to call the API with cookies. Set to the UI's address in production. |
| `session_hours` | `12` | Sign-in lifetime. |
| `stream_fps` | `12` | Highest frame rate sent to one browser tile. |
| `stream_max_width` | `1280` | Live JPEGs are downscaled to this width (overlays are scaled by the browser). |
| `jpeg_quality` | `70` | Quality of live JPEGs. |

### `storage`

| Key | Default | Meaning |
|---|---|---|
| `data_dir` | `data/runtime` | Database, evidence snapshots, explanations, uploads and exports. |
| `retention_days` | `30` | Snapshots and explanations older than this are deleted (checked hourly). Incident rows are kept. |
| `max_upload_mb` | `200` | Largest file accepted on the Uploads screen (nginx in the Docker image uses the same limit). |

Evidence frames stop being written when less than 200 MB of disk is free; detection continues and the UI shows one
"System problem" notification until space is available again.

### `privacy`

| Key | Default | Meaning |
|---|---|---|
| `blur_heads_in_snapshots` | `false` | Blur the top 22 % of every person box (head and face) in saved evidence frames. |

### `demo`

| Key | Default | Meaning |
|---|---|---|
| `seed` | `true` | On first start with an empty database, create three demo cameras that play the clips in `data/samples/` in a loop, with sample zones. Turn off for a real site. Looping clips make "unique today" grow with every loop: each loop is new people to the tracker. |

### `detection`

| Key | Default | Meaning |
|---|---|---|
| `device` | `auto` | `auto` (GPU if available), `cpu`, `cuda:0`, … |
| `imgsz` | `null` | Inference size; `null` uses the size recorded in `models/model.json`. |

### `tracking` (counting people)

Defaults tuned on MOT17-02/04 (`docs/eval/counting_report.md`, ADR-0009).

| Key | Default | Meaning |
|---|---|---|
| `track_high_thresh` | `0.2` | Detection score above which boxes are matched to tracks first. |
| `track_low_thresh` | `0.1` | Weaker boxes may still continue an existing track (helps in crowds). |
| `new_track_thresh` | `0.25` | Score needed to start a new track. Higher = fewer false people, later starts. |
| `match_thresh` | `0.8` | IoU matching tolerance. |
| `track_buffer_s` | `1.5` | How long a lost track survives an occlusion. |
| `min_hits` | `2` | A track counts as a person only after this many detections… |
| `min_age_s` | `0.2` | …and after this many seconds… |
| `min_hit_ratio` | `0.5` | …and if it was detected in at least this share of frames since it appeared. Blocks flicker. |
| `reid_window_s` | `0.0` | Merge a new ID into a just-lost one with similar size and clothing within this time. Off by default: it undercounted on MOT17. |

### `ppe`

| Key | Default | Meaning |
|---|---|---|
| `evidence_tau_s` | `0.6` | Time constant of the per-item evidence filter. |
| `absent_below` / `present_above` | `0.3` / `0.7` | Hysteresis band: evidence below means missing, above means worn, between keeps the last state. |
| `violation_min_s` | `2.0` | An item must be missing this long before an incident opens. |
| `min_person_height_px` | `60` | Smaller people are not judged (every item stays unknown). |

PPE checks only run for items the active model can detect. With the fallback person-only model no PPE incidents are
raised and compliance shows "—".

### `zones`

| Key | Default | Meaning |
|---|---|---|
| `enter_frames` / `exit_frames` | `3` / `5` | Consecutive frames inside/outside before a person counts as entered/left. |
| `point_mode` | `foot` | `foot` (bottom-centre of the box) or `center` (for top-down cameras). |
| `lost_grace_s` | `1.0` | A person briefly lost by the tracker keeps zone membership this long. |

### `incidents`

| Key | Default | Meaning |
|---|---|---|
| `clear_s` | `3.0` | An incident ends when its condition has been false this long. |
| `cooldown_s` | `30.0` | A recurrence within this time reopens the same incident. |
| `overcrowding_min_s` | `2.0` | Occupancy must exceed the zone limit this long. |

### `site`

| Key | Default | Meaning |
|---|---|---|
| `required_ppe` | `[]` | PPE required everywhere on the site, for example `[helmet, vest]`. Zones can require more. |

## Running

* **Docker:** `docker compose up --build`, then open http://localhost:8080. The database, evidence and uploads live
  in the `runtime` named volume and survive rebuilds; the active model is copied from `models/` at build time, so
  rebuild after promoting a new one. Read a generated admin password with
  `docker compose exec backend cat /app/data/runtime/ADMIN_PASSWORD.txt`.
* **Without Docker:** `make setup` once, then `make dev` (backend on :8000, UI on :5173).
* **Health:** `GET /api/v1/health` (status of the model and every camera) and `GET /api/v1/metrics` (Prometheus
  text: uptime, per-camera fps, latency, open incidents).
* **Logs:** structured JSON lines in `data/runtime/vision_sentinel.log` and on stdout.

## Backups

Everything durable is in `data/runtime/` (the `runtime` volume under Docker) and `models/`. To back up while running, copy the database with SQLite's
online backup (`sqlite3 data/runtime/vision_sentinel.db ".backup backup.db"`) and copy `snapshots/` and `xai/`.
Restore by stopping the backend and putting the files back.

## Upgrading the model

1. Train and evaluate a model ([training.md](training.md)); the export step writes `models/<name>.pt` and
   `models/model.json` (classes, per-class thresholds, image size, metrics).
2. Restart the backend. The Model screen shows the new name, classes and measured accuracy.
3. Remove `models/model.json` to fall back to the person-only model.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| A camera shows "error" | The source cannot be opened. Use **Settings → Cameras → Test** to see the exact error. Streams reconnect by themselves with back-off up to 30 s. |
| No PPE incidents at all | The person-only fallback model is active (Model screen says "PPE model: No"). Install a trained model. |
| Too many people counted | Raise `min_hits` or `new_track_thresh`; check the camera is not looping a file. |
| People counted late or missed | Lower `new_track_thresh`; make sure people are taller than about 60 px. |
| Intrusions fire at a zone's edge | Zones use the foot point; draw the zone on the floor, not at head height. Raise `enter_frames`. |
| "Too many sign-in attempts" | Five wrong passwords from one address within a minute; wait a minute. |
| "System problem: evidence frames are not being saved" | The disk under `data/runtime` has less than 200 MB free. Free space or lower `retention_days`. |
| Browser shows nothing after login behind a proxy | WebSockets must be proxied (`/ws/`) with `Upgrade` headers; see `frontend/nginx.conf`. |
