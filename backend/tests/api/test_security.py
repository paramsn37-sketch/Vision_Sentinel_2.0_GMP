"""Security pass (Phase 11): every route needs a session, file endpoints do not traverse, headers are set."""

import re

from .test_auth import anonymous

PUBLIC = {"/api/v1/health", "/api/v1/metrics", "/api/v1/auth/login"}


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def test_every_route_requires_a_session(client) -> None:
    anon = anonymous(client)
    checked = 0
    for path, ops in client.app.openapi()["paths"].items():
        if path in PUBLIC:
            continue
        for method in ops:
            r = anon.request(method.upper(), _concrete(path))
            assert r.status_code in (401, 403), f"{method} {path} answered {r.status_code} without a session"
            checked += 1
    assert checked > 25


def test_websockets_require_a_session(client) -> None:
    anon = anonymous(client)
    for path in ("/ws/events", "/ws/live?camera_id=x"):
        try:
            with anon.websocket_connect(path) as ws:
                ws.receive_text()
            raise AssertionError(f"{path} accepted an anonymous socket")
        except AssertionError:
            raise
        except Exception:
            pass


def test_file_endpoints_do_not_traverse(client, auth) -> None:
    for path in ("/api/v1/incidents/..%2F..%2Fsettings/evidence", "/api/v1/xai/..%2F..%2Fetc%2Fpasswd/source",
                 "/api/v1/uploads/..%2F..%2Fvision_sentinel.db/file"):  # fmt: skip
        r = client.get(path, headers=auth)
        assert r.status_code in (400, 404, 422), (path, r.status_code)


def test_security_headers(client) -> None:
    h = client.get("/api/v1/health").headers
    assert h["x-frame-options"] == "DENY"
    assert h["x-content-type-options"] == "nosniff"
