"""Generate docs/api.md from the live OpenAPI schema plus the WebSocket message formats.

cd backend && uv run python ../scripts/gen_api_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402

WS = """
## WebSockets

Both sockets need the session cookie; without it they close with code `4401`.

### `/ws/live?camera_id=<id>&fps=<n>`

For every frame the server sends a JSON text message, then the JPEG of the same frame as a binary message. The
client may send `{"fps": n}` at any time to change the rate (capped by `server.stream_fps`). Slow clients get fewer
frames, never a backlog.

```json
{
  "type": "frame", "camera_id": "street-night", "frame_idx": 1234, "ts": 1761150000.123,
  "width": 1920, "height": 1080, "fps": 3.1, "latency_ms": 210.4,
  "counts": {"current": 12, "unique_total": 140, "per_zone": {"z_ab12cd34": {"current": 2, "unique": 31}}},
  "persons": [
    {"track_id": 17, "box": [812.0, 340.5, 901.2, 610.0], "conf": 0.81, "confirmed": true, "since_s": 4.2,
     "ppe": {"helmet": "present", "vest": "unknown"},
     "items": [{"cls": "helmet", "conf": 0.66, "box": [840.1, 341.0, 873.9, 371.2]}],
     "zones": ["z_ab12cd34"], "violations": ["intrusion"]}
  ],
  "objects": [],
  "zones": [{"id": "z_ab12cd34", "name": "Vehicle lane", "kind": "restricted", "severity": "high",
             "polygon": [[0.40, 0.20], [0.62, 0.20], [0.70, 1.0], [0.38, 1.0]]}],
  "alert_level": "red"
}
```

Only confirmed people are listed. Box coordinates are original-frame pixels; zone polygons are normalised (0–1); the JPEG may be downscaled (`server.stream_max_width`), so scale by
`width`/`height`. When the camera has no new frame the server sends `{"type": "status", "status": "...",
"error": null}` instead.

### `/ws/events`

Server to client only. A `{"type": "ping"}` is sent after 15 s of silence.

| `type` | Fields | When |
|---|---|---|
| `incident` | `kind` (`opened`, `evidence`, `closed`, `reopened`, `status`), `incident` (id, camera, track, rule, zone, severity, status, active, times, duration, peak confidence, reopen count) | incident lifecycle and workflow changes |
| `incident_xai` | `incident_id`, `meta` (method, target class, energy in box, timing) | explanation for an incident is ready |
| `zone_event` | `camera_id`, `zone_id`, `track_id`, `kind` (`entered`, `exited`) | zone membership changes |
| `upload` | `id`, `status`, `progress` (0–1) | upload processing |
| `system` | `level`, `message`, `camera_id` | a problem the operator must act on (for example a full disk) |
| `ping` | | keep-alive |
"""


def main() -> None:
    spec = create_app(start_cameras=False).openapi()
    out = [
        "# API reference",
        "",
        "Generated from the OpenAPI schema by `scripts/gen_api_docs.py`; the interactive version is served at",
        "`/api/docs` while the backend runs. All paths are under `/api/v1`. Every route except `/health`, `/metrics`",
        "and `/auth/login` needs the session cookie; state-changing requests also need the `x-csrf-token` header",
        '(value of the `vs_csrf` cookie). Errors have the shape `{"error": {"code", "message", "details"}}`.',
        "",
        "## REST",
        "",
        "| Method | Path | Summary |",
        "|---|---|---|",
    ]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            summary = op.get("summary") or op.get("operationId", "")
            params = [p["name"] for p in op.get("parameters", []) if p.get("in") == "query"]
            if params:
                summary += f" (query: {', '.join(params)})"
            out.append(f"| `{method.upper()}` | `{path.removeprefix('/api/v1')}` | {summary} |")
    out.append(WS)
    (ROOT / "docs" / "api.md").write_text("\n".join(out) + "\n")
    print(f"wrote docs/api.md ({sum(len(o) for o in spec['paths'].values())} operations)")


if __name__ == "__main__":
    main()
